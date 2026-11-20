"""One fresh snapshot per approved target; coordinates returned in mouse units."""
from .recovery import TargetNotReady
import os
import re
import sys
from PIL import ImageDraw
from .accessibility_extractor import extract
from .som_annotator import annotate, pixels
from .vlm_grounding import select
from .grounding import locate
from .input_activity import activity


def center(element):
    l, t, r, b = element['bbox']
    return int((l+r)//2), int((t+b)//2)


def logical_size(gui):
    if sys.platform == 'darwin':
        from Quartz import CGDisplayBounds, CGMainDisplayID
        bounds = CGDisplayBounds(CGMainDisplayID()).size
        return int(bounds.width), int(bounds.height)
    return tuple(gui.size())


async def resolve(target, action='click', text=None):
    import pyautogui as gui
    size = logical_size(gui)
    image = gui.screenshot().convert('RGB')
    if sys.platform == 'win32' and size != image.size:
        raise RuntimeError('Windows primary display DPI mismatch; refusing misaligned input.')
    system_ui = bool(re.search(r'taskbar|system tray|notification area|start button', target, re.I))
    window, elements = extract(size, system_ui)
    if not elements:
        (x,y), frame = await locate(target)
        point = x*size[0]//frame['width'], y*size[1]//frame['height']
        activity('target_measured', source='vision', screenshot_px=[x,y], mouse_xy=point,
                 screenshot_size=frame, desktop_size=size)
        return point
    marked = annotate(image, elements, size)
    debug = os.getenv('DEBUG_SOM','').lower() in {'true','1','yes'}
    if debug:
        marked.save('debug_som.png')
    key = await select(marked, elements, target, action, text)
    element = elements[key]
    point = center(element)
    x,y = pixels(point, image.size, size)
    current_window, current_elements = extract(size, system_ui)
    current = gui.screenshot().convert('RGB')
    patch = (max(0,x-12), max(0,y-12), min(image.width,x+13), min(image.height,y+13))
    if (window != current_window or element not in current_elements.values() or current.size != image.size
            or logical_size(gui) != size or current.crop(patch).tobytes() != image.crop(patch).tobytes()):
        raise TargetNotReady('Selected control changed during inference. No input performed.')
    if debug:
        ImageDraw.Draw(marked).ellipse((x-4,y-4,x+4,y+4), fill='red', outline='white')
        marked.save('debug_target.png')
    activity('target_measured', source='accessibility', element_id=key, role=element['role'],
             bbox=element['bbox'], screenshot_px=[x,y], mouse_xy=point,
             screenshot_size=image.size, desktop_size=size)
    return point


async def execute(item):
    import pyautogui as gui
    from .computer import execute_action
    action = item['action']
    target = item.get('target') or item.get('reason')
    if not target:
        raise ValueError('An element-targeted action requires a named target.')
    if action == 'type_text' and len(str(item.get('text', ''))) > 2000:
        raise ValueError('Text input exceeds the per-action limit.')
    selection = {'move':'click','type_text':'type'}.get(action, action)
    x,y = await resolve(target, selection, item.get('text'))
    gui.moveTo(x,y,duration=0.18)
    if action == 'type_text':
        gui.click(x,y)
    return execute_action(dict(item, x=x, y=y))
