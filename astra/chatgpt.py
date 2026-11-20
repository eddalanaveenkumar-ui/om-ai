"""Execute explicit 'open ChatGPT, <request>' tasks in a visible browser."""
import re
import webbrowser
import time
from urllib.parse import urlsplit


def extract_prompt(task):
    match = re.match(
        r'^\s*(?:please\s+)?(?:open|launch|visit|go to)\s+(?:https?://)?'
        r'(?:chatgpt(?:\.com)?|chat\.openai\.com)/?(?:\s+|[,;:]\s*|[.!]\s+)'
        r'(?:(?:and\s+then|and|then)\s+)?(.+?)\s*$', task, re.I | re.S)
    if not match:
        return None
    prompt = match[1].strip(' ,;:.!?')
    if (not prompt or not re.search(r'\w', prompt)
            or re.fullmatch(r'in (?:my |the )?(?:default browser|browser|chrome|brave|edge)', prompt, re.I)):
        return None
    if re.search(r'\blanding[ -]page\b', prompt, re.I):
        prompt += ('\nReturn one complete, self-contained HTML document with CSS and JavaScript. '
                   'Include a branded header, hero section, features and a clear call to action.')
    return prompt


def _origin_ok(value):
    parsed = urlsplit(value if '://' in value else 'https://' + value)
    return parsed.scheme == 'https' and parsed.netloc.lower() == 'chatgpt.com'


def _submit_windows(prompt):
    # Each asyncio worker needs its own COM apartment, including on later runs
    # when pywinauto is already imported. Balance our initialization on exit.
    import ctypes
    ole = ctypes.windll.ole32
    if ole.CoInitializeEx(None, 0) < 0:
        raise RuntimeError("Windows accessibility initialization failed.")
    try:
        return _drive_composer(prompt)
    finally:
        ole.CoUninitialize()


def _send_hit(hit, doc):
    """Validate the visually located arrow, including an icon child of an unnamed button."""
    button = None
    while hit and hit != doc:
        if button is None and hit.element_info.control_type == 'Button':
            button = hit
        hit = hit.parent()
    if not hit or button is None or not button.is_enabled() or not button.is_visible():
        return False
    name = button.window_text().strip()
    return (not name or bool(re.search(r'\bsend\b', name, re.I))
            or button.element_info.automation_id in {'send-button', 'composer-submit-button'})


def _drive_composer(prompt):
    import ctypes
    import pyautogui
    import pyperclip
    from pywinauto import Desktop

    desktop = Desktop(backend='uia')
    foreground = ctypes.windll.user32.GetForegroundWindow

    def active_document():
        handle = foreground()
        if not handle:
            return None, None
        window = desktop.window(handle=handle).wrapper_object()
        # Check the browser's address field, not text inside the web page.
        for field in window.descendants(control_type='Edit'):
            if not re.search(r'address|search or enter', field.window_text(), re.I):
                continue
            parent = field.parent()
            while parent and parent != window and parent.element_info.control_type != 'Document':
                parent = parent.parent()
            if parent == window and _origin_ok(field.get_value()):
                docs = [d for d in window.descendants(control_type='Document') if d.is_visible()]
                if docs and foreground() == handle:
                    return handle, docs[0]
        return None, None

    def find(kind, matches, expected=None):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            handle, doc = active_document()
            if expected and handle != expected:
                raise RuntimeError('Browser focus or address changed; stopped without sending.')
            if doc:
                for control in doc.descendants(control_type=kind):
                    if matches(control) and control.is_visible() and control.is_enabled():
                        return handle, control
            time.sleep(.4)
        raise RuntimeError('ChatGPT control not found. Check login, browser accessibility and the active tab.')

    def target_point(target):
        import asyncio
        from .grounding import locate
        (px, py), frame = asyncio.run(locate(target))
        width, height = pyautogui.size()
        x = px * width // frame['width']
        y = py * height // frame['height']
        return x, y

    def click(handle, control, target):
        x, y = target_point(target)
        hit = desktop.from_point(x, y)
        while hit and hit != control:
            hit = hit.parent()
        if not hit or foreground() != handle:
            raise RuntimeError('Control moved or is covered; no click performed.')
        pyautogui.click(x, y)

    handle, editor = find('Edit', lambda c: c.element_info.automation_id == 'prompt-textarea'
                          or re.search(r'ask (anything|chatgpt)|message chatgpt', c.window_text(), re.I))
    click(handle, editor, "The editable ChatGPT message composer, inside its text area")
    if foreground() != handle or not editor.has_keyboard_focus():
        raise RuntimeError('Composer focus could not be confirmed; no text pasted.')
    pyperclip.copy(prompt)
    pyautogui.hotkey('ctrl', 'v')
    # Locate visually first. Some browser builds expose the arrow with an empty
    # accessible name, so waiting for a named UIA Send button never reaches locate().
    x, y = target_point("The enabled Send message arrow in the ChatGPT composer containing the pasted prompt")
    active, doc = active_document()
    if active != handle or doc is None or foreground() != handle:
        raise RuntimeError('Active ChatGPT tab changed after paste; stopped without sending.')
    if _send_hit(desktop.from_point(x, y), doc) and foreground() == handle:
        pyautogui.click(x, y)
        return 'click'
    # Do not click an unrelated control. Enter is safe only in the same focused editor.
    if editor.has_keyboard_focus() and foreground() == handle:
        pyautogui.press('enter')
        return 'enter'
    raise RuntimeError('Send hit-test and composer focus checks failed; prompt left unsent.')


def run_chatgpt(prompt):
    result = {'action': 'chatgpt_prompt', 'browser_open_requested': False, 'send_clicked': False}
    if not webbrowser.open_new_tab('https://chatgpt.com/'):
        result['problem'] = 'Browser launch not confirmed. Check your default browser setting.'
        return result
    result['browser_open_requested'] = True
    try:
        method = _submit_windows(prompt)
        result['submission_action'] = method
        result['send_clicked'] = method == 'click'
        result['verification'] = 'Submission attempted; a completed response is not yet confirmed.'
    except Exception as exc:
        result['problem'] = str(exc)
    return result
