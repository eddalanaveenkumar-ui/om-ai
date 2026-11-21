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

    def test_normalize_planner_key(self):
        from astra.ui_policy import planned_key
        for item in [{'target':'Enter'}, {'keys':['Enter']}, {'key':' ENTER '}]:
            self.assertEqual(planned_key(item), 'enter')
        for item in [{}, {'reason':'Press Enter to submit'}, {'keys':['ctrl','s']},
                     {'key':'unknown','target':'Enter'}, {'keys':['Enter'],'target':'Tab'}]:
            self.assertIsNone(planned_key(item))

    def test_folder_selection_delete_is_explicit(self):
        from astra.ui_policy import folder_key_pair
        click = {'action':'click','target':'Reports folder'}
        key = {'action':'press_key'}
        task = 'Select the Reports folder and pree delete key'
        self.assertTrue(folder_key_pair(task, click, key))
        self.assertFalse(folder_key_pair(task, click, dict(key,key='enter')))
        self.assertFalse(folder_key_pair('Select the folder; do not press Delete', click, key))
        self.assertFalse(folder_key_pair('Select the folder', click, key))
