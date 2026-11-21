"""Prepare a workflow without waiting on independent model calls in sequence."""
import asyncio
from .skills import chatgpt_goal, chatgpt_skill


async def prepare(task, route, plan, inspect, propose, report):
    prompt = chatgpt_goal(task)
    if prompt:
        actions = chatgpt_skill(prompt)
        routing = {'task_type': 'computer_task', 'needs_verification': True, 'source': 'built-in skill'}
        plan_data = {'goal': task, 'skill': 'chatgpt_creation', 'steps': actions}
        report('LOCAL PLAN', plan_data)
        return routing, plan_data, prompt, {'skill': 'chatgpt_creation', 'actions': actions}

    routing = await route(task)
    report('ORCHESTRATOR', routing)
    # Both use the same task, but planning does not consume the screenshot.
    async with asyncio.TaskGroup() as group:
        planning = group.create_task(plan(task, routing))
        observation = group.create_task(inspect(task)) if routing.get('needs_computer', True) else None
    plan_data = planning.result()
    screen = observation.result() if observation else None
    report('PLAN', plan_data)
    if screen is not None:
        report('COMPUTER AGENT OBSERVATION', screen)
    return routing, plan_data, None, await propose(task, plan_data, screen)
