"""Reject launcher shortcuts and direct-navigation payloads before dispatch."""
import re


def validate_ui_action(item):
    action = item.get('action')
    if action in {'type_text', 'press_key'}:
        field = 'text' if action == 'type_text' else 'key'
        if not isinstance(item.get(field), str) or not item[field]:
            raise ValueError(f'{action} requires an explicit {field}; no input performed.')
    if action == 'open_url':
        raise ValueError('Direct URL launch disabled. Use the visible browser UI.')
    if action == 'hotkey':
        keys = {str(k).lower() for k in item.get('keys', [])}
        if 'r' in keys and keys & {'win', 'winleft', 'winright'}:
            raise ValueError('The Run dialog is not a UI launch target.')
    if action == 'type_text':
        target = str(item.get('target') or item.get('reason') or '')
        text = str(item.get('text', '')).strip()
        if re.search(r'\b(run dialog|command prompt|powershell|terminal)\b', target, re.I):
            raise ValueError('Command entry is disabled.')
        if re.search(r'address|omnibox|location bar|search|launcher', target, re.I) and re.match(
                r'^(?:[a-z][\w+.-]*:|www\.|(?:[\w-]+\.)+[a-z]{2,}(?:[/?:#]|$))', text, re.I):
            raise ValueError('Search by app or site name, not a direct link or path.')


def opens_chrome(item):
    """A launcher click, not a control inside a Chrome page."""
    target = str(item.get('target', ''))
    return (item.get('action') in {'click', 'double_click'} and
            bool(re.search(r'\bchrome\b', target, re.I)) and
            (bool(re.search(r'\b(taskbar|desktop|shortcut|dock|pinned|start menu)\b', target, re.I))
             or target.lower().strip() in {'chrome', 'google chrome', 'chrome icon', 'google chrome icon'}))
