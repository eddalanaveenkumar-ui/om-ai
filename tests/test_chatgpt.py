import unittest

from astra.chatgpt import extract_prompt


class PromptRoutingTests(unittest.TestCase):
    def test_original_request(self):
        prompt = extract_prompt('open chatgpt, creaate a landing page for a saas llm named meanai,')
        for requirement in ('meanai', 'HTML', 'header', 'hero', 'features', 'call to action'):
            self.assertIn(requirement, prompt)

    def test_navigation_is_not_a_prompt(self):
        for task in ('Open ChatGPT', 'Open ChatGPT.', 'Open ChatGPT in Chrome',
                     'Open chatgpt.com.example.org', 'Open YouTube and play music'):
            self.assertIsNone(extract_prompt(task), task)

    def test_other_prompt(self):
        self.assertEqual(extract_prompt('Visit https://chatgpt.com/ and write a poem'), 'write a poem')


class BrowserHandoffTests(unittest.TestCase):
    def test_default_browser_gets_exact_prompt(self):
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlsplit
        from astra.chatgpt import run_chatgpt

        prompt = 'Build MeanAI & show C++ examples\nதமிழ் #1'
        with patch('astra.chatgpt.webbrowser.open_new_tab', return_value=True) as launch:
            result = run_chatgpt(prompt)
        launch.assert_called_once()
        url = urlsplit(launch.call_args.args[0])
        self.assertEqual((url.scheme, url.netloc), ('https', 'chatgpt.com'))
        self.assertEqual(parse_qs(url.query), {'q': [prompt]})
        self.assertTrue(result['browser_open_requested'])
