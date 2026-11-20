import unittest
from astra.recovery import RecoveryBudget, repair_queue


class RecoveryTests(unittest.TestCase):
    def test_resume_at_failed_step(self):
        tail = [{'action': 'press_key', 'key': 'enter'}]
        repair = [{'action': 'wait', 'seconds': 2}, {'action': 'click', 'target': 'search'}]
        self.assertEqual(repair_queue({'actions': repair}, tail, {'wait', 'click'}), repair + tail)
        self.assertEqual(len(tail), 1)

    def test_no_unbounded_or_privileged_recovery(self):
        budget = RecoveryBudget(2)
        self.assertEqual([budget.claim() for _ in range(4)], [True, True, False, False])
        for actions in ([], [{'action': 'launch_default_browser'}], [{'action':'wait'}]*9):
            self.assertIsNone(repair_queue({'actions':actions}, [], {'wait'}))
