import base64, io, time, webbrowser, ctypes, platform, os, subprocess, shutil
from pathlib import Path
from PIL import Image

# Set Windows DPI awareness BEFORE importing PyAutoGUI. Without this, Windows
# display scaling (125%, 150%, etc.) can make screenshot pixels and mouse
# coordinates use different coordinate spaces.
DPI_AWARENESS = "not-windows"
if platform.system() == "Windows":
    try:
        # Per-monitor DPI awareness v2 (Windows 10 1703+)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        DPI_AWARENESS = "per-monitor-v2"
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            DPI_AWARENESS = "per-monitor"
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                DPI_AWARENESS = "system-aware-fallback"
            except Exception:
                DPI_AWARENESS = "failed"

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


def _desktop_shortcut_paths(app_name: str):
    """Yield matching .lnk shortcuts from user and public Windows desktops."""
    from pathlib import Path
    roots = [
        Path.home() / "Desktop",
        Path(os.environ.get("OneDrive", str(Path.home() / "OneDrive"))) / "Desktop",
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop",
    ]
    seen = set()
    for root in roots:
        try:
            if not root.exists():
                continue
            for shortcut in root.glob("*.lnk"):
                if app_name.casefold() in shortcut.stem.casefold() and str(shortcut).casefold() not in seen:
                    seen.add(str(shortcut).casefold())
                    yield shortcut
        except OSError:
            continue

def resolve_windows_shortcut(shortcut_path):
    """Resolve a Windows .lnk target using the built-in Windows Script Host COM object."""
    escaped = str(shortcut_path).replace("'", "''")
    command = (
        "$w=New-Object -ComObject WScript.Shell; "
        f"$s=$w.CreateShortcut('{escaped}'); "
        "[Console]::Write($s.TargetPath)"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, timeout=10, check=False
    )
    target = (completed.stdout or "").strip()
    if completed.returncode != 0 or not target:
        raise RuntimeError((completed.stderr or "Could not resolve desktop shortcut target.").strip())
    return target

def launch_desktop_app(app_name: str, url: str | None = None, start: bool = True):
    """Launch an app from its real desktop shortcut target; never guess screen coordinates."""
    if platform.system() != "Windows":
        raise RuntimeError("Desktop shortcut launching is currently supported on Windows only.")
    target = None
    shortcut_used = None
    errors = []
    for shortcut in _desktop_shortcut_paths(app_name):
        try:
            candidate = resolve_windows_shortcut(shortcut)
            if os.path.isfile(candidate):
                target, shortcut_used = candidate, str(shortcut)
                break
            errors.append(f"Shortcut target does not exist: {candidate}")
        except Exception as exc:
            errors.append(str(exc))

    # Fallback to common installation locations. This still avoids coordinate
    # clicks and never types into whichever window happens to be active.
    if target is None and app_name.casefold() in {"brave", "chrome", "google chrome"}:
        if app_name.casefold() == "brave":
            candidates = [
                Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            ]
            command_names = ["brave"]
        else:
            candidates = [
                Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Google/Chrome/Application/chrome.exe",
            ]
            command_names = ["chrome", "google-chrome"]
        target = next((str(path) for path in candidates if path.is_file()), None)
        if target is None:
            target = next((shutil.which(name) for name in command_names if shutil.which(name)), None)

    if not target:
        detail = "; ".join(errors[-2:])
        raise FileNotFoundError(f"Could not locate the {app_name} desktop shortcut or installed executable. {detail}")

    if url and not str(url).startswith(("https://", "http://")):
        raise ValueError("Only HTTP and HTTPS URLs are allowed.")
    process = None
    if start:
        args = [target] + ([str(url)] if url else [])
        process = subprocess.Popen(args, close_fds=True)
    return {
        "status": "process_started" if start else "executable_resolved",
        "application": app_name,
        "executable": target,
        "desktop_shortcut": shortcut_used,
        "url_argument": url,
        "pid": process.pid if process else None,
        "method": "Windows shortcut target / executable resolution; no screen coordinates used"
    }


ALLOWED = {"click", "double_click", "right_click", "move", "scroll",
           "type_text", "hotkey", "press_key", "open_url", "wait", "screenshot"}

def screen_size():
    w, h = pyautogui.size()
    return {"width": int(w), "height": int(h)}

def screenshot_bytes():
    image = pyautogui.screenshot()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
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
    if action == "open_url":
        url = str(item.get("url", "")).strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("Only http:// and https:// URLs are allowed")
        webbrowser.open(url)
        return {"status": "browser_open_requested", "url": url}

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
        allowed_keys = {"enter","tab","esc","escape","backspace","delete","up","down",
                        "left","right","home","end","pageup","pagedown","space"}
        if key not in allowed_keys:
            raise ValueError(f"Key not allowed: {key}")
        pyautogui.press(key)
        return {"status": "key_pressed", "key": key}
