"""Trusted recipes: one default-browser launch capability, then ordinary UI actions."""
import re
import sys


def launch_default_browser():
    """No destination, user-supplied executable, shell, or arguments on Windows."""
    if sys.platform == 'win32':
        import ctypes
        import subprocess
        from pathlib import Path
        from ctypes import wintypes
        query = ctypes.windll.shlwapi.AssocQueryStringW
        query.argtypes = [wintypes.DWORD, ctypes.c_int, wintypes.LPCWSTR, wintypes.LPCWSTR,
                          wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        path = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(path))
        # ASSOCF_IS_PROTOCOL / ASSOCSTR_EXECUTABLE: executable registered for HTTPS.
        hr = query(0x1000, 2, 'https', 'open', path, ctypes.byref(length))
        browser = Path(path.value)
        if hr or not browser.is_absolute() or not browser.is_file():
            raise RuntimeError('Cannot resolve the default HTTPS browser. Check Windows Default apps.')
        subprocess.Popen([str(browser)], shell=False)
    else:
        import webbrowser
        if not webbrowser.open_new_tab('about:blank'):
            raise RuntimeError('The default browser did not accept the launch request.')
    return {'status': 'default_browser_launch_requested'}


def search_web(query):
    return [{'action': 'type_text', 'target': 'browser address/search bar', 'text': query},
            {'action': 'press_key', 'key': 'enter'}, {'action': 'wait', 'seconds': 2}]


def chatgpt_goal(task):
    # Only claim direct creation requests. Leave explicit step-by-step instructions alone.
    match = re.fullmatch(r'\s*(?:please\s+)?((?:create|make|build|generate|write|design)\s+.+?)'
                         r'\s+(?:with|using|via|in)\s+chat\s?gpt[.!?\s]*', task, re.I | re.S)
    return match[1].strip() if match else None


def chatgpt_skill(prompt):
    return [{'action': 'launch_default_browser'}, *search_web('ChatGPT'),
            {'action': 'click', 'target': 'official ChatGPT search result for chatgpt.com (not an ad)'},
            {'action': 'wait', 'seconds': 2},
            {'action': 'confirm_chatgpt'},
            {'action': 'type_text', 'target': 'empty ChatGPT message composer', 'text': prompt},
            {'action': 'click', 'target': 'enabled Send message arrow in the ChatGPT composer'},
            {'action': 'wait', 'seconds': 3}]
