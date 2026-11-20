"""Execute explicit 'open ChatGPT, <request>' tasks in a visible browser."""
import re
import webbrowser
from urllib.parse import urlencode


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


def run_chatgpt(prompt):
    """Hand off to the OS browser; do not attach to or close its session."""
    url = 'https://chatgpt.com/?' + urlencode({'q': prompt})
    opened = webbrowser.open_new_tab(url)
    return {
        'action': 'chatgpt_prompt',
        'browser_open_requested': bool(opened),
        'verification': ('Prompt passed in the ChatGPT URL. Submission and response are not '
                         'confirmed; press Send if the prompt is still in the composer.' if opened else
                         'Browser launch not confirmed. Check your default browser setting.'),
    }
