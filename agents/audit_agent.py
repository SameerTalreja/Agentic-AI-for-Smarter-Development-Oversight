"""
agents/audit_agent.py

Track B - The Audit Agent.

1. PLAN     - self-generates a checklist of checks (visible, stored)
2. EXECUTE  - runs those checks via tools
3. SYNTHESIZE - ranked, human-readable report
"""

from __future__ import annotations

import json
import sys
import os
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import session_scope, init_db
from db.models import QueryRun, ToolCall
from core.llm_client import call_llm, run_agent_loop
from core.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS
from core.audit_tools import AUDIT_TOOL_SCHEMAS, AUDIT_TOOL_FUNCTIONS
from core.history_tools import HISTORY_TOOL_SCHEMAS, HISTORY_TOOL_FUNCTIONS

ALL_TOOL_SCHEMAS = TOOL_SCHEMAS + AUDIT_TOOL_SCHEMAS + HISTORY_TOOL_SCHEMAS
ALL_TOOL_FUNCTIONS = {**TOOL_FUNCTIONS, **AUDIT_TOOL_FUNCTIONS, **HISTORY_TOOL_FUNCTIONS}


DEFAULT_GOAL = (
    "Find the projects most at risk of failing or being mismanaged in this "
    "infrastructure portfolio."
)

PLANNING_SYSTEM_PROMPT = """You are a project auditor planning an investigation \
of a government infrastructure projects dataset. You have NOT yet looked at \
any data. Your only job right now is to decide what checks you will run.

The dataset has columns including: District, Phase, Category, Description, \
Executing Agency, Cost (M), TSE, Contractor, NITs (was a tender issued: \
Yes/No), Progress %, Status (Completed/In Progress/NITs Issued/Not Started), \
Work Started (date), XEN Name, XEN Contact.

Given the goal below, produce a checklist of exactly 5 SPECIFIC, CONCRETE checks \
you will run -- no more, no fewer. Prioritize the most impactful checks.\
Each check should target a distinct kind of problem (don't \
propose near-duplicate checks). Think about: internal inconsistencies \
(status vs. other fields), missing accountability, cost anomalies, and \
procurement irregularities.

Respond with ONLY a JSON array, no other text, in this exact shape:
[
  {"check_name": "short_snake_case_id", "description": "one sentence explaining what this check looks for and why it matters", "tool_hint": "which tool(s) you'll likely use, e.g. filter_rows with is_null"}
]"""

EXECUTION_SYSTEM_PROMPT = """You are a project auditor executing a pre-approved \
checklist against a government infrastructure projects dataset \
(dataset_id is always 'default' -- pass it literally for every tool call).

Your checklist (already approved, do not deviate from it or invent new checks \
beyond these):
{plan_json}

For EACH check in the checklist, use the tools available to actually run it \
and find the real offending rows/count. Rules:
0. PREFER aggregate(operation="count", filters=...) over filter_rows whenever \
   you only need a COUNT -- it returns a single number instead of full rows, \
   using far fewer tokens. Only call filter_rows when you need to show 1-3 \
   concrete example rows, and always pass limit=3 in that case.
1. Never state a number unless it came from a tool result in this conversation.
2. For each check, report how many rows/projects it flagged.
3. After running all checks, produce a RANKED report: order findings by \
   severity/impact (e.g. by total cost affected or count of projects), with \
   a short section per finding including the count, a 1-2 sentence \
   explanation, and up to 3 concrete examples (Global ID + Description).
4. If a check found zero issues, say so explicitly -- don't omit it.
5. End with a one-paragraph executive summary a manager could act on.
6. aggregate's group_by only accepts ONE column at a time, not a combined/joined \
   list, and only works well on categorical columns (District, Category, Status, \
   Phase, NITs) with few distinct values. NEVER group_by a free-text column like \
   Description or Contractor -- it has thousands of distinct values and will \
   fail. For checks needing multiple columns together (e.g. detecting duplicate \
   rows by District+Phase+Category+Description), use filter_rows to fetch \
   relevant rows instead and reason about duplicates from what's returned.
7. NEVER repeat an identical or near-identical tool call you have already made \
   in this conversation. Before calling a tool, check whether you already have \
   the answer from an earlier step and reuse it instead.
8. When reporting a "top N" ranking from a group_by aggregate result, do not \
   eyeball the raw JSON -- explicitly sort the groups by value first, then list \
   them in that exact order. Double-check your written ranking matches the \
   actual highest values before finalizing your answer.
9. NEVER invent a specific Global ID, project description, or example row. Only \
   list an example project if you retrieved it via an actual filter_rows call \
   in this conversation and can point to its exact real data. If you want \
   examples for a finding but haven't fetched matching rows yet, call \
   filter_rows first. If you still can't retrieve examples (e.g. ran out of \
   tool budget), write "example rows not retrieved" instead of making one up."""

def _extract_json_array(text: str) -> Optional[list[dict[str, Any]]]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _generate_plan(goal: str) -> list[dict[str, Any]]:
    message = call_llm(
        messages=[
            {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
            {"role": "user", "content": f"Goal: {goal}"},
        ],
        tool_schemas=None,
    )
    plan = _extract_json_array(message.content or "")
    if not plan:
        message = call_llm(
            messages=[
                {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": f"Goal: {goal}"},
                {"role": "assistant", "content": message.content or ""},
                {"role": "user", "content": "That was not valid JSON. Respond with ONLY the JSON array, nothing else."},
            ],
            tool_schemas=None,
        )
        plan = _extract_json_array(message.content or "")
    return plan or []


def _persist_run(
    dataset_id: str,
    goal: str,
    plan: list[dict[str, Any]],
    result: dict[str, Any],
) -> str:
    with session_scope() as db:
        run = QueryRun(
            track="B",
            dataset_id=dataset_id,
            question=goal,
            plan=plan,
            final_answer=result["final_answer"],
            status="completed",
        )
        db.add(run)
        db.flush()

        for step in result["steps"]:
            db.add(ToolCall(
                query_run_id=run.id,
                step_number=step["step_number"],
                tool_name=step["tool_name"],
                arguments=step["arguments"],
                result=step["result"],
            ))

        query_id = run.id
    return query_id


def run_audit(
    goal: str = DEFAULT_GOAL,
    dataset_id: str = "default",
    on_plan: Optional[Any] = None,
    on_step: Optional[Any] = None,
    cancel_event: Optional[Any] = None,
) -> dict[str, Any]:
    plan = _generate_plan(goal)
    if on_plan:
        on_plan(plan)

    plan_json = json.dumps(plan, indent=2)
    execution_prompt = EXECUTION_SYSTEM_PROMPT.format(plan_json=plan_json)

    result = run_agent_loop(
        system_prompt=execution_prompt,
        user_message=f"Execute the checklist and produce the ranked risk report. Goal: {goal}",
        tool_schemas=ALL_TOOL_SCHEMAS,
        tool_functions=ALL_TOOL_FUNCTIONS,
        fixed_tool_args={"dataset_id": dataset_id},
        on_step=on_step,
        max_steps=10,
        cancel_event=cancel_event,
        # model="openai/gpt-oss-20b",
    )

    query_id = _persist_run(dataset_id, goal, plan, result)

    return {
        "query_id": query_id,
        "plan": plan,
        "final_answer": result["final_answer"],
        "steps": result["steps"],
        "stopped_reason": result["stopped_reason"],
    }


def _print_step(step: dict[str, Any]) -> None:
    print(f"  [step {step['step_number']}] {step['tool_name']}({step['arguments']})")
    result_preview = str(step["result"])
    if len(result_preview) > 200:
        result_preview = result_preview[:200] + "..."
    print(f"    -> {result_preview}")


def _print_plan(plan: list[dict[str, Any]]) -> None:
    print("=== Self-generated checklist ===")
    if not plan:
        print("  (agent failed to produce a valid checklist)")
        return
    for i, check in enumerate(plan, 1):
        print(f"  {i}. [{check.get('check_name', '?')}] {check.get('description', '')}")
        if check.get("tool_hint"):
            print(f"     -> {check['tool_hint']}")
    print()


def _cli() -> None:
    init_db()
    print("=== Track B: Audit Agent ===\n")
    goal = input(f"Goal (press Enter for default: '{DEFAULT_GOAL}'): ").strip()
    if not goal:
        goal = DEFAULT_GOAL

    print(f"\nRunning audit with goal: {goal}\n")
    result = run_audit(goal, on_plan=_print_plan, on_step=_print_step)

    print("\n=== RANKED RISK REPORT ===")
    print(result["final_answer"])
    print(f"\n(query_id: {result['query_id']}, steps: {len(result['steps'])}, "
          f"stopped: {result['stopped_reason']})")


if __name__ == "__main__":
    _cli()