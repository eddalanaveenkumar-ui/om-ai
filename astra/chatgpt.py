"""Execute explicit 'open ChatGPT, <request>' tasks in a visible browser."""
import os
import re
from pathlib import Path
from urllib.parse import urlparse


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
    from playwright.sync_api import sync_playwright, TimeoutError

    result = {'action': 'chatgpt_prompt', 'prompt_sent': False, 'response_complete': False}
    profile = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'AstraChatGPTProfile'
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(profile), channel='chrome', headless=False)
        try:
            page = context.new_page()
            page.goto('https://chatgpt.com/', wait_until='domcontentloaded')
            editor = page.locator('#prompt-textarea:visible').first
            # Give the user time to complete any sign-in or challenge themselves.
            editor.wait_for(timeout=120000)
            if urlparse(page.url).hostname != 'chatgpt.com':
                raise ValueError('ChatGPT composer is not on chatgpt.com')
            replies = page.locator('[data-message-author-role="assistant"]')
            reply = replies.nth(replies.count())
            editor.fill(prompt)
            page.get_by_test_id('send-button').click(timeout=10000)
            result['prompt_sent'] = True
            reply.wait_for(timeout=120000)
            # A visible assistant turn alone can still be streaming. Wait for its
            # finished-turn copy control (not the copy button inside a code block).
            turn = reply.locator('xpath=ancestor::*[starts-with(@data-testid,"conversation-turn-")][1]')
            turn.get_by_test_id('copy-turn-action-button').wait_for(state='attached', timeout=180000)
            result['response'] = reply.inner_text().strip()
            result['response_complete'] = bool(result['response'])
        except TimeoutError:
            result['problem'] = ('No completed response observed; check ChatGPT before retrying.' if result['prompt_sent']
                                 else 'Could not submit the prompt. Check sign-in and composer availability.')
        finally:
            context.close()
    return result
