import asyncio
import unittest
from astra.input_activity import activity, activity_sink, requests_input


class ActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_worker_trace(self):
        events = []
        token = activity_sink.set(events.append)
        try:
            await asyncio.to_thread(activity, 'target_measured', mouse_xy=(10, 25))
        finally:
            activity_sink.reset(token)
        self.assertEqual(events, [dict(event='target_measured', mouse_xy=(10, 25))])

    def test_browser_action_vs_navigation(self):
        for task in ['Double-click Settings', 'Scroll down', 'Press Tab', 'Type a title']:
            self.assertTrue(requests_input(task))
        self.assertFalse(requests_input('Open https://example.org/click'))
