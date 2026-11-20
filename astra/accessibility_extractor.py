"""Primary-display controls. Bounds stay in OS mouse units, never bitmap units."""
import math
import sys

ROLES = {'Button', 'Edit', 'CheckBox', 'RadioButton', 'ComboBox', 'MenuItem', 'TabItem', 'Hyperlink'}
AX_ROLES = {'AXButton': 'Button', 'AXTextField': 'Edit', 'AXTextArea': 'Edit',
            'AXCheckBox': 'CheckBox', 'AXRadioButton': 'RadioButton', 'AXComboBox': 'ComboBox',
            'AXMenuItem': 'MenuItem', 'AXTab': 'TabItem', 'AXLink': 'Hyperlink'}


def index_controls(rows, size):
    result = {}
    for name, role, bounds in rows:
        if role not in ROLES or not all(map(math.isfinite, bounds)):
            continue
        l, t, r, b = bounds
        # Don't shift the true center of a partially off-screen control by clipping it.
        if 0 <= l < r <= size[0] and 0 <= t < b <= size[1]:
            result[len(result) + 1] = dict(name=str(name or ''), role=role, bbox=list(bounds))
    return result


def _windows(size, system_ui):
    import ctypes
    import uiautomation as ui
    from comtypes import COMError
    with ui.UIAutomationInitializerInThread():
        root = ui.GetForegroundControl()
        if root is None:
            raise RuntimeError('No foreground window available for accessibility capture.')
        handle = root.NativeWindowHandle
        stack = [root]
        if system_ui:
            tray = ctypes.windll.user32.FindWindowW('Shell_TrayWnd', None)
            if tray and tray != handle:
                stack.append(ui.ControlFromHandle(tray))
        rows = []
        while stack:
            node = stack.pop()
            try:
                role = node.ControlTypeName.removesuffix('Control')
                if role in ROLES and not node.IsOffscreen and node.IsEnabled:
                    rect = node.BoundingRectangle
                    rows.append((node.Name, role, (rect.left, rect.top, rect.right, rect.bottom)))
                stack.extend(reversed(node.GetChildren()))
            except COMError:  # An individual transient menu or virtualized item disappeared.
                continue
        if ctypes.windll.user32.GetForegroundWindow() != handle:
            raise RuntimeError('Foreground window changed during accessibility capture.')
        return handle, index_controls(rows, size)


def _mac(size):
    import ApplicationServices as ax
    from AppKit import NSWorkspace
    if not ax.AXIsProcessTrusted():
        raise PermissionError('Grant Astra Accessibility access in macOS Privacy & Security.')

    def attr(node, key):
        error, value = ax.AXUIElementCopyAttributeValue(node, key, None)
        return value if not error else None

    pid = NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()
    app = ax.AXUIElementCreateApplication(pid)
    win = attr(app, 'AXFocusedWindow')
    rows, stack = [], [win] if win is not None else []
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen or attr(node, 'AXHidden'):
            continue
        seen.add(node)
        role = AX_ROLES.get(attr(node, 'AXRole'))
        if role and attr(node, 'AXEnabled') != False:
            point, extent = attr(node, 'AXPosition'), attr(node, 'AXSize')
            if point is not None and extent is not None:
                okp, p = ax.AXValueGetValue(point, ax.kAXValueCGPointType, None)
                oks, s = ax.AXValueGetValue(extent, ax.kAXValueCGSizeType, None)
                if okp and oks:
                    name = attr(node, 'AXTitle') or attr(node, 'AXDescription') or ''
                    x, y = p
                    width, height = s
                    rows.append((name, role, (x, y, x+width, y+height)))
        children = attr(node, 'AXVisibleChildren')
        stack.extend(reversed(children if children is not None else attr(node, 'AXChildren') or []))
    return (pid, win), index_controls(rows, size)


def extract(size, system_ui=False):
    if sys.platform == 'win32':
        return _windows(size, system_ui)
    if sys.platform == 'darwin':
        return _mac(size)
    return None, {}
