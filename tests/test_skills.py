import unittest
from astra.skills import chatgpt_goal, chatgpt_skill
from astra.ui_policy import validate_ui_action


class SkillTests(unittest.TestCase):
    def test_user_example(self):
        prompt = chatgpt_goal('create html login page with chatgpt')
        actions = chatgpt_skill(prompt)
        self.assertEqual(prompt, 'create html login page')
        self.assertEqual(actions[0], {'action': 'launch_default_browser'})
        self.assertEqual([a['text'] for a in actions if a['action']=='type_text'], ['ChatGPT', prompt])
        for action in actions[1:]:
            validate_ui_action(action)

    def test_existing_steps_not_intercepted(self):
        self.assertIsNone(chatgpt_goal('open chrome, open chatgpt, give this prompt: create HTML'))
