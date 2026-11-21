import json
import base64
import struct
from .config import settings
from .llm import ask_json
from .prompts import (ORCHESTRATOR_PROMPT, PLANNER_PROMPT, EXECUTOR_PROMPT,
                      VERIFIER_PROMPT, COMPUTER_PROMPT, COMPACT_SCREEN_PROMPT)
from .computer import screenshot_data_url, screen_size

async def orchestrate(user_task):
    return await ask_json("orchestrator", settings.orchestrator_model,
                          ORCHESTRATOR_PROMPT, user_task)

async def plan(user_task, routing):
    payload = json.dumps({"user_task": user_task, "routing": routing}, ensure_ascii=False)
    return await ask_json("planner", settings.planner_model, PLANNER_PROMPT, payload)

async def inspect_screen(user_task, screenshot_url=None):
    screenshot_url = screenshot_url or screenshot_data_url()
    compact = screenshot_url.startswith('data:image/jpeg;')
    dimensions = ''
    if not compact:
        width, height = struct.unpack('>II', base64.b64decode(screenshot_url.split(',', 1)[1][:32])[16:24])
        dimensions = f'Screenshot bitmap dimensions: {width} x {height}.'
    content = [
        {"type": "text", "text": (
            f"User request: {user_task}\n{dimensions}\n"
            "Inspect this screenshot. Return grounded observations in the required JSON schema."
        )},
        {"type": "image_url", "image_url": {"url": screenshot_url}}
    ]
    return await ask_json("computer", settings.computer_model,
                          COMPACT_SCREEN_PROMPT if compact else COMPUTER_PROMPT,
                          content, max_tokens=768 if compact else 4096)

async def make_actions(user_task, plan_data, screen_observation=None):
    payload = {
        "user_task": user_task,
        "approved_plan": plan_data,
        "screen_observation": screen_observation,
        "screen_size": screen_size()
    }
    return await ask_json("executor", settings.executor_model, EXECUTOR_PROMPT,
                          json.dumps(payload, ensure_ascii=False))

async def verify(user_task, plan_data, execution_log, final_observation=None):
    payload = {
        "original_goal": user_task,
        "plan": plan_data,
        "execution_log": execution_log,
        "final_screen_observation": final_observation
    }
    return await ask_json("verifier", settings.verifier_model, VERIFIER_PROMPT,
                          json.dumps(payload, ensure_ascii=False))
