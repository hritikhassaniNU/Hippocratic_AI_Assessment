"""The one place that talks to OpenAI.

Everything else goes through call_model, so the model choice, the retries and
the JSON handling only have to be right once.
"""

import json
import os
import re
import time

import openai

MODEL = "gpt-3.5-turbo"  # fixed by the assignment


def call_model(prompt: str, system=None, max_tokens=1200, temperature=0.7,
               retries=2) -> str:
    """Send one prompt and return the reply.

    Same shape as the skeleton's version, with a system message added. That
    turned out to be where nearly all of the story quality comes from.
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")

    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})

    delay = 1.0
    for attempt in range(retries + 1):
        try:
            resp = openai.ChatCompletion.create(
                model=MODEL,
                messages=messages,
                stream=False,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message["content"].strip()  # type: ignore
        except Exception:
            if attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2
    return ""


def call_json(prompt: str, system=None, max_tokens=600, temperature=0.0):
    """Ask for JSON and parse it leniently. Returns None if it cannot be read."""
    return parse_json(call_model(prompt, system, max_tokens, temperature))


def parse_json(raw: str):
    """Pull the first JSON object out of a reply.

    gpt-3.5-turbo wraps JSON in code fences, adds commentary either side of
    it, and now and then leaves a trailing comma. json.loads on the raw reply
    fails often enough that this is worth being forgiving about.
    """
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    blob = raw[start : end + 1]
    for candidate in (blob, re.sub(r",\s*([}\]])", r"\1", blob)):
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None
