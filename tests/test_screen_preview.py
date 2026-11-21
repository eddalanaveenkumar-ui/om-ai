import base64
import io
import unittest
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image
from astra.action_executor import resolve
from astra.screen_preview import jpeg_url


class FastScreenTests(unittest.IsolatedAsyncioTestCase):
    def test_preview_does_not_resize_source(self):
        image = Image.new('RGB', (1920,1080))
        data = jpeg_url(image, 1440).split(',')[1]
        with Image.open(io.BytesIO(base64.b64decode(data))) as preview:
            self.assertEqual(preview.size, (1440,810))
        self.assertEqual(image.size, (1920,1080))

    async def test_verified_exact_name_needs_no_remote_selection(self):
        gui = Mock()
        gui.size.return_value = (100,100)
        gui.screenshot.return_value = Image.new('RGB',(100,100))
        controls = {1:dict(name='Save',role='Button',bbox=[20,20,40,40])}
        with patch.dict('sys.modules', pyautogui=gui), patch('astra.action_executor.extract', return_value=(1,controls)) as tree, \
             patch('astra.action_executor.center_hit', return_value=True), patch('astra.action_executor.select',new_callable=AsyncMock) as model:
            self.assertEqual(await resolve('Save'), (30,30))
            model.assert_not_awaited()
            tree.assert_called_once()
