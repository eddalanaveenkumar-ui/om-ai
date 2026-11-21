"""Reject launcher shortcuts and direct-navigation payloads before dispatch."""
import re


PRESS_KEYS = frozenset('enter tab esc escape backspace delete up down left right home end pageup pagedown space'.split())


def single_key(value):
    if isinstance(value, str):
        key = value.strip().lower()
        if key in PRESS_KEYS:
            return key
    return None


def planned_key(item):
    """Accept a literal single key only; never infer a keystroke from prose."""
    if item.get('key') not in (None, ''):
        return single_key(item['key'])
    keys = item.get('keys')
    if keys is not None:
        if not isinstance(keys, list) or len(keys) != 1 or not single_key(keys[0]):
            return None
        key = single_key(keys[0])
        other = single_key(item.get('target'))
        return key if other in (None, key) else None
    return single_key(item.get('target'))


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


def folder_key_pair(task, click, following):
    """Resolve only a direct select-folder then Delete instruction, never a default key."""
    if (not isinstance(following, dict) or click.get('action') != 'click'
            or following.get('action') != 'press_key' or not re.search(r'\bfolder\b', task, re.I)):
        return False
    if not re.search(r'\b(?:press|pree|hit)\s+(?:the\s+)?delete(?:\s+key)?[.!\s]*$', task, re.I):
        return False
    if re.search(r"\b(?:not|never|don.t|without|instead)\b", task, re.I):
        return False
    key = planned_key(following)
    return key == 'delete' or (key is None and not any(following.get(k) for k in ('key','keys')))
