import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
from astra.accessibility_extractor import index_controls
from astra.action_executor import center, resolve
from astra.som_annotator import annotate, pixels
from astra.vlm_grounding import select


class MarkTests(unittest.TestCase):
    def test_filter_and_scale(self):
        rows = [('Save', 'Button', (4, 2, 19, 11)), ('label', 'Text', (1, 1, 2, 2)),
                ('hidden', 'Edit', (-1, 1, 8, 8)), ('empty', 'Edit', (0, 0, 0, 2))]
        els = index_controls(rows, (20, 15))
        self.assertEqual(list(els), [1])
        self.assertEqual(center(els[1]), (11, 6))
        self.assertEqual(pixels(center(els[1]), (40, 30), (20, 15)), (22, 12))
        image = Image.new('RGB', (40, 30))
        marked = annotate(image, els, (20, 15))
        self.assertEqual(image.getbbox(), None)
        self.assertIsNotNone(marked.getbbox())


class SelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_strict_selection(self):
        els = {1: dict(name='Save', role='Button')}
        for raw in ['{"element_id":true,"action":"click"}', '{"element_id":2,"action":"click"}',
                    '{"element_id":1,"action":"type"}', '{"element_id":1,"action":"click","x":9}']:
            with patch('astra.vlm_grounding.ask', AsyncMock(return_value=raw)), self.assertRaises(ValueError):
                await select(Image.new('RGB',(80,80)), els, 'Save','click')

    async def test_revalidation_and_empty_tree(self):
        gui = Mock()
        gui.size.return_value = (100,100)
        gui.screenshot.return_value = Image.new('RGB',(100,100))
        snapshot = (44, {1:dict(name='Save',role='Button',bbox=[10,20,61,85])})
        with patch.dict(sys.modules, pyautogui=gui), patch('astra.action_executor.extract') as extract, \
             patch('astra.action_executor.select', AsyncMock(return_value=1)), \
             patch('astra.action_executor.locate', AsyncMock(return_value=((40,90),dict(width=200,height=200)))) as fallback:
            extract.return_value = snapshot
            self.assertEqual(await resolve('Save'), (35,52))
            extract.side_effect = [snapshot, (45, snapshot[1])]
            with self.assertRaises(RuntimeError):
                await resolve('Save')
            fallback.assert_not_called()
            extract.side_effect = None
            extract.return_value = (44,{})
            self.assertEqual(await resolve('Save'), (20,45))
            fallback.assert_awaited_once()

    async def test_dispatch_uses_exact_point_and_approved_payload(self):
        from astra.action_executor import execute
        gui, computer = Mock(), Mock()
        with patch.dict(sys.modules, pyautogui=gui, **{'astra.computer':computer}), \
             patch('astra.action_executor.resolve', AsyncMock(return_value=(17,31))) as resolve_target:
            for action in ['click', 'double_click', 'right_click', 'type_text', 'scroll']:
                item = {'action':action, 'target':'Field', 'x':999, 'y':888}
                if action == 'type_text':
                    item['text'] = 'approved text'
                if action == 'scroll':
                    item['amount'] = -3
                await execute(item)
                resolve_target.assert_awaited_with('Field', 'type' if action == 'type_text' else action, item.get('text'))
                gui.moveTo.assert_called_with(17,31,duration=0.18)
                computer.execute_action.assert_called_with(dict(item,x=17,y=31))
            gui.click.assert_called_once_with(17,31)
