"""Temporary Windows desktop HUD. Never replace system cursors or intercept input."""
import sys


class ControlIndicator:
    def __init__(self, root):
        self.root = root
        self.hwnd = self.timer = self.position = None
        self.atom = None

    def start(self):
        if self.hwnd or sys.platform != 'win32':
            return
        import win32api as api
        import win32con as c
        import win32gui as gui

        if self.atom is None:
            wc = gui.WNDCLASS()
            wc.hInstance = api.GetModuleHandle(None)
            wc.lpszClassName = 'AstraControlIndicator'
            wc.lpfnWndProc = self._message
            self.atom = gui.RegisterClass(wc)
        w, h = api.GetSystemMetrics(0), api.GetSystemMetrics(1)
        styles = (c.WS_EX_LAYERED | c.WS_EX_TRANSPARENT | c.WS_EX_TOOLWINDOW |
                  c.WS_EX_NOACTIVATE | c.WS_EX_TOPMOST)
        self.hwnd = gui.CreateWindowEx(styles, 'AstraControlIndicator', '', c.WS_POPUP, 0, 0, w, h,
                                       0, 0, api.GetModuleHandle(None), None)
        gui.SetLayeredWindowAttributes(self.hwnd, 0, 255, c.LWA_COLORKEY)
        # Windows 10 2004+: keep the HUD out of screenshot-based grounding.
        # Older versions interpret this flag as a black capture mask, so skip it.
        if sys.getwindowsversion().build >= 19041:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(ctypes.c_void_p(self.hwnd), 0x11)
        gui.ShowWindow(self.hwnd, c.SW_SHOWNOACTIVATE)
        self._track()

    def _track(self):
        import win32gui as gui
        point = gui.GetCursorPos()
        if point != self.position:
            old, self.position = self.position, point
            for pos in (old, point):
                if pos:
                    x, y = pos
                    gui.InvalidateRect(self.hwnd, (x-18, y-18, x+19, y+19), False)
        self.timer = self.root.after(33, self._track)

    def _message(self, hwnd, msg, wp, lp):
        import win32api as api
        import win32con as c
        import win32gui as gui
        if msg == c.WM_NCHITTEST:
            return c.HTTRANSPARENT
        if msg != c.WM_PAINT:
            return gui.DefWindowProc(hwnd, msg, wp, lp)
        dc, paint = gui.BeginPaint(hwnd)
        try:
            rect = gui.GetClientRect(hwnd)
            gui.FillRect(dc, rect, gui.GetStockObject(c.BLACK_BRUSH))  # keyed transparent
            for inset, rgb in enumerate(((132,234,255), (54,192,255), (21,144,255),
                                         (16,103,226), (17,72,161), (18,48,93))):
                brush = gui.CreateSolidBrush(api.RGB(*rgb))
                try:
                    gui.FrameRect(dc, (inset, inset, rect[2]-inset, rect[3]-inset), brush)
                finally:
                    gui.DeleteObject(brush)
            if self.position:
                x, y = self.position
                # Offset spark leaves the native cursor and its hotspot untouched.
                for radius, color in ((7, (73,51,114)), (5, (195,175,255)), (3, (139,225,209))):
                    pen = gui.CreatePen(c.PS_SOLID, 2, api.RGB(*color))
                    old = gui.SelectObject(dc, pen)
                    try:
                        cx, cy = x+10, y-8
                        gui.MoveToEx(dc, cx, cy-radius)
                        for dx, dy in ((1,-1),(radius,0),(1,1),(0,radius),(-1,1),(-radius,0),(-1,-1),(0,-radius)):
                            gui.LineTo(dc, cx+dx, cy+dy)
                    finally:
                        gui.SelectObject(dc, old)
                        gui.DeleteObject(pen)
        finally:
            gui.EndPaint(hwnd, paint)
        return 0

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.hwnd:
            import win32gui as gui
            gui.DestroyWindow(self.hwnd)
            self.hwnd = self.position = None
