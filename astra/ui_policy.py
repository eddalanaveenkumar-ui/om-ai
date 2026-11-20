"""Reject launcher shortcuts and direct-navigation payloads before dispatch."""
import re


def validate_ui_action(item):
    action = item.get('action')
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
