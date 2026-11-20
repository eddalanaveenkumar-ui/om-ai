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
    def test_submit_once_in_default_browser(self):
        from unittest.mock import patch
        from astra.chatgpt import run_chatgpt
        with patch('astra.chatgpt.webbrowser.open_new_tab', return_value=True) as launch, \
             patch('astra.chatgpt._submit_windows') as submit:
            result = run_chatgpt('Build MeanAI')
        launch.assert_called_once_with('https://chatgpt.com/')
        submit.assert_called_once_with('Build MeanAI')
        self.assertTrue(result['send_clicked'])

    def test_origin(self):
        from astra.chatgpt import _origin_ok
        self.assertTrue(_origin_ok('chatgpt.com/'))
        self.assertFalse(_origin_ok('https://chatgpt.com.example.org/'))
