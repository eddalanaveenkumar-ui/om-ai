import asyncio
import unittest
from unittest.mock import AsyncMock, Mock
from astra.preparation import prepare


class PreparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_skill_skips_preparatory_calls(self):
        remote = AsyncMock(side_effect=AssertionError('unexpected remote call'))
        routing, plan, prompt, proposed = await prepare('Create a form using ChatGPT', remote, remote, remote, remote, Mock())
        self.assertTrue(routing['needs_verification'])
        self.assertEqual(proposed['actions'], plan['steps'])
        self.assertEqual(prompt, 'Create a form')

    async def test_plan_and_inspect_overlap(self):
        planning, inspecting = asyncio.Event(), asyncio.Event()
        async def plan(*args):
            planning.set()
            await inspecting.wait()
            return {'goal':'test'}
        async def inspect(*args):
            inspecting.set()
            await planning.wait()
            return {'screen':'test'}
        propose = AsyncMock(return_value={'actions':[]})
        await asyncio.wait_for(prepare('test', AsyncMock(return_value={}), plan, inspect, propose, Mock()), 2)
        propose.assert_awaited_once_with('test', {'goal':'test'}, {'screen':'test'})
