"""
core/llm_client.py

Thin wrapper around the Groq API. This is the ONLY file that should know
about "Groq" specifically -- agents call the functions below, never the
Groq SDK directly. Swapping providers later means editing only this file.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

from groq import Groq
from dotenv import load_dotenv
from groq import BadRequestError, RateLimitError, APIStatusError
import re
import time

load_dotenv()

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "8"))

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )
        _client = Groq(api_key=api_key)
    return _client


def _to_groq_tool_format(tool_schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tool_schemas
    ]


def _extract_wait_seconds(error_message: str) -> float:
    # Handles both "try again in 2.5s" and "try again in 13m55.488s"
    match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", error_message)
    if not match:
        return 3.0
    minutes = float(match.group(1)) if match.group(1) else 0.0
    seconds = float(match.group(2))
    return minutes * 60 + seconds

def _looks_unfinished(text: str) -> bool:
    """Heuristic check for scratchpad/reasoning leaking into what should be
    a finished final answer -- e.g. an unexecuted tool-call JSON fragment
    pasted into prose, or explicit planning language."""
    text_lower = text.lower()
    suspicious_markers = [
        '"dataset_id"',           # a raw tool-call JSON fragment in the text
        "we'll resolve",
        "let's compile",
        "we have enough rows",
        "need shortlist",
        "we'll include",
    ]
    if any(marker in text_lower for marker in suspicious_markers):
        return True
    # A final report that never opens a markdown table but is fairly long
    # is suspicious for tasks that explicitly require a table.
    return False

def _trim_oldest_tool_results(messages: list[dict[str, Any]], keep_full_last_n: int = 2) -> list[dict[str, Any]]:
    """When a request is too large, shrink older tool-role message contents
    to a short placeholder, keeping only the most recent `keep_full_last_n`
    tool results intact. System/user/assistant messages are untouched."""
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    to_shrink = tool_indices[:-keep_full_last_n] if keep_full_last_n else tool_indices

    trimmed = []
    for i, m in enumerate(messages):
        if i in to_shrink:
            m = {**m, "content": '{"note": "older tool result omitted to save space"}'}
        trimmed.append(m)
    return trimmed

def call_llm(
    messages: list[dict[str, Any]],
    tool_schemas: Optional[list[dict[str, Any]]] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    _retry_count: int = 0,
) -> Any:
    client = _get_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if tool_schemas:
        kwargs["tools"] = _to_groq_tool_format(tool_schemas)
        kwargs["tool_choice"] = "auto"

    if "gpt-oss" in model:
        kwargs["reasoning_effort"] = "low"

    try:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message
    except RateLimitError as e:
        error_str = str(e)
        if "tokens per day" in error_str.lower() or "TPD" in error_str:
            wait = _extract_wait_seconds(error_str)
            raise RuntimeError(
                f"Groq's daily free-tier token limit has been reached. "
                f"Try again in about {wait/60:.0f} minutes, or once your daily "
                f"quota resets (typically UTC midnight), or use a different "
                f"GROQ_API_KEY."
            ) from e

        if _retry_count >= 3:
            raise
        wait = _extract_wait_seconds(error_str) + 0.5
        if wait > 20:
            # A long per-minute wait usually also signals we're close to the
            # daily cap too -- don't spin silently for a long time.
            raise RuntimeError(
                f"Groq rate limit requires a {wait:.0f}s wait, which is longer "
                f"than this script will spin-retry for. Wait and rerun."
            ) from e
        print(f"  [rate limited, waiting {wait:.1f}s before retry...]")
        time.sleep(wait)
        return call_llm(messages, tool_schemas, model, temperature, _retry_count + 1)
    except (APIStatusError, BadRequestError) as e:
        error_str = str(e)

        # gpt-oss sometimes wraps a plain-JSON final answer as a fake tool
        # call named "json" when tools are enabled alongside a "respond
        # with ONLY JSON" instruction. The real content is recoverable from
        # failed_generation -- extract it and treat it as the final answer
        # instead of losing the whole turn.
        if "attempted to call tool 'json'" in error_str:
            match = re.search(r'"arguments":\s*(\{.*\})\s*\}\s*$', error_str, re.DOTALL)
            if not match:
                # fall back: try to pull failed_generation's arguments via json parsing
                fg_match = re.search(r"'failed_generation':\s*'(.+)'\}", error_str, re.DOTALL)
                extracted_text = fg_match.group(1) if fg_match else None
            else:
                extracted_text = match.group(1)

            if extracted_text:
                class _FakeMessage:
                    def __init__(self, content):
                        self.content = content
                        self.tool_calls = None
                        self.reasoning = None
                return _FakeMessage(extracted_text)
            raise

        too_large = (
            (isinstance(e, APIStatusError) and getattr(e, "status_code", None) == 413)
            or "context_length_exceeded" in error_str
            or "reduce the length" in error_str.lower()
        )
        if too_large and _retry_count < 3:
            print("  [context too large, trimming older tool results and retrying...]")
            trimmed = _trim_oldest_tool_results(messages)
            return call_llm(trimmed, tool_schemas, model, temperature, _retry_count + 1)
        if "output_parse_failed" in error_str:
            retry_messages = messages + [{
                "role": "system",
                "content": "Your previous response could not be parsed. Respond "
                            "with ONLY a direct, final answer in plain text -- "
                            "no internal reasoning, no meta-commentary about "
                            "what you are about to say."
            }]
            kwargs["messages"] = retry_messages
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message
        raise

def run_agent_loop(
    system_prompt: str,
    user_message: str,
    tool_schemas: list[dict[str, Any]],
    tool_functions: dict[str, Callable[..., Any]],
    fixed_tool_args: Optional[dict[str, Any]] = None,
    on_step: Optional[Callable[[dict[str, Any]], None]] = None,
    model: str = DEFAULT_MODEL,
    max_steps: int = MAX_AGENT_STEPS,
    cancel_event: Optional[Any] = None,  # threading.Event, checked between steps
) -> dict[str, Any]:
    fixed_tool_args = fixed_tool_args or {}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    steps: list[dict[str, Any]] = []
    step_number = 0
    stopped_reason = "completed"

    while step_number < max_steps:
        if cancel_event is not None and cancel_event.is_set():
            return {
                "final_answer": "Cancelled by user before completion.",
                "steps": steps,
                "stopped_reason": "cancelled",
            }
        message = call_llm(messages, tool_schemas=tool_schemas, model=model)
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            # Model produced a final answer with no further tool use.
            final_answer = message.content or getattr(message, "reasoning", None) or ""

            if not final_answer.strip():
                messages.append({
                    "role": "user",
                    "content": "Your last response was empty. Please provide "
                                "your final answer now, as plain text.",
                })
                retry_message = call_llm(messages, tool_schemas=None, model=model)
                final_answer = retry_message.content or getattr(retry_message, "reasoning", None) or ""

            elif _looks_unfinished(final_answer):
                # The model narrated its reasoning/plan (sometimes including
                # an unexecuted tool-call-looking JSON fragment) instead of
                # producing the actual finished deliverable. Force one clean
                # finalization pass using only what's already been retrieved.
                messages.append({
                    "role": "assistant",
                    "content": final_answer,
                })
                messages.append({
                    "role": "user",
                    "content": "That was your internal planning, not a finished "
                                "answer. Do not call any more tools. Using ONLY "
                                "the tool results already in this conversation, "
                                "write the complete, polished final report now -- "
                                "no stream-of-consciousness reasoning, no "
                                "unexecuted tool-call fragments, no placeholders. "
                                "If you were going to reference a row you have not "
                                "actually retrieved yet, omit it instead.",
                })
                retry_message = call_llm(messages, tool_schemas=None, model=model)
                final_answer = retry_message.content or getattr(retry_message, "reasoning", None) or final_answer

            return {
                "final_answer": final_answer,
                "steps": steps,
                "stopped_reason": stopped_reason,
            }

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

                # Build a lookup of which parameters each tool actually accepts,
        # so fixed_tool_args (e.g. dataset_id) is only injected into tools
        # that declare it -- avoids crashing tools like lookup_query that
        # don't take a dataset_id.
        schema_params_by_tool = {
            t["name"]: set(t.get("input_schema", {}).get("properties", {}).keys())
            for t in tool_schemas
        }

        for tc in tool_calls:
            step_number += 1
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            accepted_params = schema_params_by_tool.get(tool_name, set())
            applicable_fixed_args = {
                k: v for k, v in fixed_tool_args.items() if k in accepted_params
            }
            # applicable_fixed_args wins over model-guessed args (e.g. dataset_id)
            call_args = {**arguments, **applicable_fixed_args}
            if "limit" in call_args and isinstance(call_args["limit"], int):
                call_args["limit"] = min(call_args["limit"], 10)
            
            func = tool_functions.get(tool_name)
            if func is None:
                result: Any = {"error": f"Unknown tool '{tool_name}'"}
            else:
                try:
                    result = func(**call_args)
                except Exception as e:
                    result = {"error": str(e)}

            step_record = {
                "step_number": step_number,
                "tool_name": tool_name,
                "arguments": call_args,
                "result": result,
            }
            steps.append(step_record)
            if on_step:
                on_step(step_record)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

            if step_number >= max_steps:
                stopped_reason = "max_steps_reached"
                break

            if cancel_event is not None and cancel_event.is_set():
                return {
                    "final_answer": "Cancelled by user before completion.",
                    "steps": steps,
                    "stopped_reason": "cancelled",
                }
            
    messages.append({
        "role": "user",
        "content": "You have reached the maximum number of tool calls. "
                    "Summarize your findings and give your best final answer now, "
                    "noting any limitation caused by stopping early.",
    })
    final_message = call_llm(messages, tool_schemas=None, model=model)

    return {
        "final_answer": final_message.content or getattr(final_message, "reasoning", None) or "",
        "steps": steps,
        "stopped_reason": "max_steps_reached",
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

    result = run_agent_loop(
        system_prompt=(
            "You are a data analyst answering questions about a government "
            "infrastructure projects dataset (dataset_id will always be 'default', "
            "pass that literally for every tool call). Always use the provided "
            "tools to get real numbers -- never guess or make up a number. If data "
            "is missing, say so explicitly. Cite the filters/counts you used."
        ),
        user_message="How many water (PHE) projects in Kech are completed?",
        tool_schemas=TOOL_SCHEMAS,
        tool_functions=TOOL_FUNCTIONS,
        fixed_tool_args={"dataset_id": "default"},
        on_step=lambda s: print(f"[step {s['step_number']}] {s['tool_name']}({s['arguments']}) -> {str(s['result'])[:200]}"),
    )

    print("\n=== FINAL ANSWER ===")
    print(result["final_answer"])
    print(f"\nStopped reason: {result['stopped_reason']}")
    print(f"Total steps: {len(result['steps'])}")