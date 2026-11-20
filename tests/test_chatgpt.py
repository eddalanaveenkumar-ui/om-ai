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
             patch('astra.chatgpt._submit_windows', return_value='click') as submit:
            result = run_chatgpt('Build MeanAI')
        launch.assert_called_once_with('https://chatgpt.com/')
        submit.assert_called_once_with('Build MeanAI')
        self.assertTrue(result['send_clicked'])

    def test_origin(self):
        from astra.chatgpt import _origin_ok
        self.assertTrue(_origin_ok('chatgpt.com/'))
        self.assertFalse(_origin_ok('https://chatgpt.com.example.org/'))


class SendTargetTests(unittest.TestCase):
    def test_icon_inside_unnamed_button(self):
        from unittest.mock import Mock
        from astra.chatgpt import _send_hit
        doc, button, icon = Mock(), Mock(), Mock()
        icon.element_info.control_type = 'Image'
        icon.parent.return_value = button
        button.element_info.control_type = 'Button'
        button.parent.return_value = doc
        button.window_text.return_value = ''
        self.assertTrue(_send_hit(icon, doc))
        button.window_text.return_value = 'Think'
        self.assertFalse(_send_hit(icon, doc))
        button.window_text.return_value = 'Send message (Enter)'
        self.assertTrue(_send_hit(icon, doc))
        button.is_enabled.return_value = False
        self.assertFalse(_send_hit(icon, doc))

class ComposerTests(unittest.TestCase):
    def test_existing_draft(self):
        from astra.chatgpt import _needs_paste
        self.assertTrue(_needs_paste('', 'MeanAI'))
        self.assertFalse(_needs_paste('MeanAI\r\nHTML', 'MeanAI\nHTML'))
        with self.assertRaises(RuntimeError):
            _needs_paste('Unrelated draft', 'MeanAI')

    def test_unnamed_editor_in_verified_document(self):
        from unittest.mock import Mock
        from astra.chatgpt import _editor_hit
        text, editor, document = Mock(), Mock(), Mock()
        text.element_info.control_type = 'Text'
        text.parent.return_value = editor
        editor.element_info.control_type = 'Edit'
        editor.parent.return_value = document
        self.assertIs(_editor_hit(text, document), editor)
        editor.parent.return_value = None
        self.assertIsNone(_editor_hit(text, document))
