import json
from openai import AsyncOpenAI
from .config import settings

class LLMError(RuntimeError):
    pass

def make_client(agent: str) -> AsyncOpenAI:
    api_key = settings.key_for(agent)
    if not api_key or "PASTE_YOUR" in api_key:
        raise LLMError("NVIDIA API key missing. Add NVIDIA_API_KEY to the .env file.")
    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.base_url,
        timeout=settings.agent_timeout_seconds,
        max_retries=2
    )

async def ask(agent: str, model: str, system_prompt: str, user_content,
              max_tokens=None) -> str:
    client = make_client(agent)
    try:
        request_options = {}
        # The Planner only needs concise structured output. Nemotron 3.5 Lightning
        # can spend its entire max_tokens budget on hidden reasoning and return
        # an empty content field with finish_reason="length".
        if ((agent == "planner" and "nemotron-3.5-lightning" in model)
                or (agent == "computer" and "nemotron-3.5-super-vl" in model)):
            request_options["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False}
            }

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=settings.temperature,
            max_tokens=max_tokens or settings.max_tokens,
            **request_options
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            finish = getattr(response.choices[0], "finish_reason", None)
            raise LLMError(
                f"{agent} returned an empty response (model={model}, finish_reason={finish})."
            )
        return content.strip()
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"{agent} model request failed ({model}): {exc}") from exc
    finally:
        await client.close()

def parse_json(text: str) -> dict:
    """Parse a JSON object even when surrounded by prose or Markdown fences."""
    if not isinstance(text, str) or not text.strip():
        raise LLMError("The model returned an empty response instead of JSON.")
    cleaned = text.strip().lstrip("\\ufeff")
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char == "{":
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue

    excerpt = cleaned[:900].replace("\\n", " ")
    raise LLMError(
        "The model did not return valid JSON. Response begins: "
        + repr(excerpt)
        + ". Check model output formatting or try another model in .env."
    )

async def ask_json(agent: str, model: str, system_prompt: str, user_content,
                   max_tokens=None) -> dict:
    try:
        first = await ask(agent, model, system_prompt, user_content, max_tokens)
    except LLMError as first_call_error:
        # Vision models can occasionally consume the full output budget. Retry
        # once with a larger budget before surfacing an empty-response error.
        if agent == "computer" and "finish_reason=length" in str(first_call_error):
            first = await ask(agent, model, system_prompt, user_content, 6144)
        else:
            raise
    try:
        return parse_json(first)
    except LLMError as first_error:
        repair_prompt = (
            "Your previous answer was not valid JSON. Return ONLY one valid JSON object. "
            "Do not add Markdown fences, explanations, or text before or after the object. "
            "Preserve the requested schema. Use empty strings, arrays, false, or null "
            "for unknown values.\\n\\nPrevious response:\\n" + first[:5000]
        )
        second = await ask(
            agent, model,
            system_prompt + "\\n\\nSTRICT OUTPUT RULE: respond with one valid JSON object only.",
            repair_prompt, max_tokens
        )
        try:
            return parse_json(second)
        except LLMError as second_error:
            raise LLMError(
                f"{agent} failed to produce JSON after one retry. "
                f"First error: {first_error}. Second error: {second_error}"
            ) from second_error
