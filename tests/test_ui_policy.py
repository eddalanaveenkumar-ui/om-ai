import unittest
from astra.ui_policy import validate_ui_action


class UIPolicyTests(unittest.TestCase):
    def test_no_direct_launch(self):
        for action in [dict(action='open_url'), dict(action='hotkey', keys=['win','r']),
                       dict(action='type_text', target='address bar', text='chatgpt.com'),
                       dict(action='type_text', target='terminal', text='start chrome')]:
            with self.assertRaises(ValueError):
                validate_ui_action(action)

    def test_ui_search(self):
        validate_ui_action(dict(action='type_text', target='Start search', text='Chrome'))
        validate_ui_action(dict(action='type_text', target='browser address bar', text='ChatGPT'))

    def test_chrome_profile_checkpoint(self):
        from astra.ui_policy import opens_chrome
        self.assertTrue(opens_chrome(dict(action='click', target='Google Chrome taskbar icon')))
        self.assertFalse(opens_chrome(dict(action='click', target='Chrome address bar')))
        self.assertFalse(opens_chrome(dict(action='move', target='Google Chrome taskbar icon')))

    def test_missing_search_payload(self):
        with self.assertRaises(ValueError):
            validate_ui_action(dict(action='type_text', target='address bar', reason="Type NVIDIA"))
