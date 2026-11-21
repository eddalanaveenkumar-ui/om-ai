import base64, io, time, ctypes, platform
from PIL import Image
from .ui_policy import PRESS_KEYS

# Set Windows DPI awareness BEFORE importing PyAutoGUI. Without this, Windows
# display scaling (125%, 150%, etc.) can make screenshot pixels and mouse
# coordinates use different coordinate spaces.
DPI_AWARENESS = "not-windows"
if platform.system() == "Windows":
    try:
        hr = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        DPI_AWARENESS = "per-monitor" if hr == 0 else "already-set-or-unavailable"
    except (AttributeError, OSError):
        DPI_AWARENESS = "system-aware-fallback" if ctypes.windll.user32.SetProcessDPIAware() else "failed"

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


ALLOWED = {"click", "double_click", "right_click", "move", "scroll",
           "type_text", "hotkey", "press_key", "wait", "screenshot"}

def screen_size():
    w, h = pyautogui.size()
    return {"width": int(w), "height": int(h)}

def screenshot_bytes():
    image = pyautogui.screenshot()
    buf = io.BytesIO()
    image.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()

def screenshot_dimensions():
    """Return exact screenshot bitmap dimensions in pixels."""
    image = pyautogui.screenshot()
    return {"width": int(image.width), "height": int(image.height)}

def coordinate_calibration():
    """Compare screenshot pixels with PyAutoGUI mouse-coordinate dimensions."""
    image_size = screenshot_dimensions()
    mouse_size = screen_size()
    return {
        "screenshot_pixels": image_size,
        "mouse_coordinate_space": mouse_size,
        "scale_x": round(mouse_size["width"] / max(1, image_size["width"]), 6),
        "scale_y": round(mouse_size["height"] / max(1, image_size["height"]), 6),
        "dpi_awareness": DPI_AWARENESS,
        "aligned": image_size == mouse_size,
    }

def screenshot_data_url():
    return "data:image/png;base64," + base64.b64encode(screenshot_bytes()).decode("ascii")

def execute_action(item, coordinate_size=None):
    action = item.get("action")
    if action not in ALLOWED:
        raise ValueError(f"Unsupported action: {action}")
    if action == "screenshot":
        return {"status": "captured", "screen": screen_size()}
    if action == "wait":
        seconds = float(item.get("seconds", 1))
        if not 0 <= seconds <= 10:
            raise ValueError("wait must be between 0 and 10 seconds")
        time.sleep(seconds)
        return {"status": "waited", "seconds": seconds}
    size = screen_size()
    if action in {"click", "double_click", "right_click", "move"}:
        x, y = int(item["x"]), int(item["y"])
        # Vision coordinates refer to the screenshot bitmap. Windows DPI scaling
        # can make that bitmap differ from PyAutoGUI's logical screen coordinates.
        if coordinate_size:
            cw = max(1, int(coordinate_size.get("width", size["width"])))
            ch = max(1, int(coordinate_size.get("height", size["height"])))
            x = round(x * size["width"] / cw)
            y = round(y * size["height"] / ch)
        if not (0 <= x < size["width"] and 0 <= y < size["height"]):
            raise ValueError(f"Coordinates outside screen: {x},{y}; screen={size}")
        if action == "click": pyautogui.click(x, y)
        elif action == "double_click": pyautogui.doubleClick(x, y)
        elif action == "right_click": pyautogui.rightClick(x, y)
        else: pyautogui.moveTo(x, y, duration=0.2)
        return {"status": "performed", "action": action, "x": x, "y": y}

    if action == "scroll":
        amount = int(item.get("amount", 0))
        if not -20 <= amount <= 20:
            raise ValueError("scroll amount must be between -20 and 20")
        pyautogui.scroll(amount)
        return {"status": "performed", "action": action, "amount": amount}

    if action == "type_text":
        value = str(item.get("text", ""))
        if len(value) > 2000:
            raise ValueError("Text input is limited to 2000 characters per action")
        pyautogui.write(value, interval=0.01)
        return {"status": "typed", "character_count": len(value)}

    if action == "hotkey":
        keys = item.get("keys", [])
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4:
            raise ValueError("hotkey keys must be a list of 1-4 key names")
        pyautogui.hotkey(*[str(k).lower() for k in keys])
        return {"status": "hotkey_performed", "keys": keys}

    if action == "press_key":
        key = str(item.get("key", "")).lower()
        if key not in PRESS_KEYS:
            raise ValueError(f"Key not allowed: {key}")
        pyautogui.press(key)
        return {"status": "key_pressed", "key": key}


def selected_explorer_item(x, y):
    """Fail closed before Delete: foreground Explorer and exactly one selected item at hit point."""
    if platform.system() != 'Windows':
        return False
    import win32gui
    from pywinauto import Desktop
    hwnd = win32gui.GetForegroundWindow()
    if win32gui.GetClassName(hwnd) not in {'CabinetWClass', 'ExploreWClass', 'Progman', 'WorkerW'}:
        return False
    if win32gui.GetAncestor(win32gui.WindowFromPoint((x, y)), 2) != hwnd:
        return False
    ctrl = Desktop(backend='uia').from_point(x, y)
    while ctrl and ctrl.element_info.control_type not in {'ListItem', 'DataItem', 'TreeItem'}:
        ctrl = ctrl.parent()
    if ctrl is None:
        return False
    selection = ctrl.iface_selection_item
    if not selection.CurrentIsSelected:
        return False
    from comtypes.gen.UIAutomationClient import IUIAutomationSelectionPattern
    pattern = selection.CurrentSelectionContainer.GetCurrentPattern(10001).QueryInterface(IUIAutomationSelectionPattern)
    return pattern.GetCurrentSelection().Length == 1 and win32gui.GetForegroundWindow() == hwnd
