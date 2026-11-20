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


def _editor_hit(hit, document):
    editor = None
    while hit and hit != document:
        if editor is None and (hit.element_info.control_type == 'Edit'
                               or hit.element_info.automation_id == 'prompt-textarea'):
            editor = hit
        hit = hit.parent()
    return editor if hit == document else None


def _needs_paste(draft, prompt):
    normalize = lambda text: text.replace('\r\n', '\n').strip()
    if not normalize(draft):
        return True
    if normalize(draft) == normalize(prompt):
        return False
    raise RuntimeError('A different draft is already in the composer. Nothing was sent.')


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

    def target_point(target):
        import asyncio
        from .grounding import locate
        (px, py), frame = asyncio.run(locate(target))
        width, height = pyautogui.size()
        x = px * width // frame['width']
        y = py * height // frame['height']
        return x, y

    deadline = time.monotonic() + 25
    while True:
        handle, document = active_document()
        if document is not None:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Could not verify the active chatgpt.com browser document before locating the composer.')
        time.sleep(.4)
    x, y = target_point('Inside the editable text area of the ChatGPT message composer, not its toolbar')
    editor = _editor_hit(desktop.from_point(x, y), document)
    if editor is None or foreground() != handle:
        raise RuntimeError('The visually located composer did not hit an editable control in the active document.')
    pyautogui.click(x, y)
    if foreground() != handle or not editor.has_keyboard_focus():
        raise RuntimeError('Composer focus could not be confirmed; no text pasted.')
    try:
        draft = editor.iface_value.CurrentValue
    except Exception:
        try:
            draft = editor.iface_text.DocumentRange.GetText(-1)
        except Exception as exc:
            raise RuntimeError('Could not read composer contents safely; no text pasted.') from exc
    if _needs_paste(draft, prompt):
        pyperclip.copy(prompt)
        if foreground() != handle or not editor.has_keyboard_focus():
            raise RuntimeError('Composer lost focus before paste.')
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
