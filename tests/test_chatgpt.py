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
