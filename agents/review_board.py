"""
agents/review_board.py

Track C - Multi-Agent Review Board.

Three specialist agents (Finance, Delivery, Equity) each investigate the
'Not Started' portfolio from their own lens and produce a structured JSON
finding. A Coordinator agent then receives all three structured messages,
resolves at least one real disagreement/trade-off between them, and builds
a concrete, costed shortlist of projects to fund -- citing which agent
raised which concern.

Task: "We have an extra PKR 2 billion (2000 M). Which currently
Not Started projects should be funded first, and why?"
"""

from __future__ import annotations

import json
import sys
import os
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import session_scope, init_db
from db.models import QueryRun, ToolCall
from core.llm_client import run_agent_loop
from core.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS


DEFAULT_TASK = (
    "We have an extra PKR 2 billion (2000 M) to allocate. Which currently "
    "'Not Started' projects should be funded first, and why?"
)

# Kept minimal deliberately -- specialists only get the 4 core tools, not
# audit/history tools, to keep each request small (Groq free-tier TPM is
# the binding constraint, not agent capability).
SPECIALIST_TOOLS = TOOL_SCHEMAS
SPECIALIST_FUNCS = TOOL_FUNCTIONS


def _finding_schema_instructions() -> str:
    return """After investigating, respond with ONLY a JSON object as your final \
TEXT MESSAGE (do not call any tool to produce this JSON -- write it directly as \
plain text), in this exact shape:
...
{
  "agent": "<your agent name>",
  "findings": [
    {"finding": "short label", "evidence": "the real number/fact you found via tools", "severity": "high|medium|low"}
  ],
  "recommendation": "one paragraph: from your perspective, what kind of Not Started projects should be prioritized for funding, and why"
}"""


FINANCE_SYSTEM_PROMPT = f"""You are the FINANCE AGENT on a project review board. \
dataset_id is always 'default'. Your job: analyze the 'Not Started' portfolio \
from a financial-efficiency lens -- budget concentration by district/category, \
cost outliers, and value-for-money. Use tools to get REAL numbers; never guess.
Investigate efficiently: prefer aggregate(operation=count/sum, group_by=...) \
over fetching many raw rows. You have at most 5 tool calls -- use them wisely.
{_finding_schema_instructions()}"""

DELIVERY_SYSTEM_PROMPT = f"""You are the DELIVERY AGENT on a project review board. \
dataset_id is always 'default'. Your job: analyze the 'Not Started' portfolio \
from a delivery-risk lens -- which categories/districts have historically low \
completion rates (poor track record = higher risk for new funding), and where \
accountability is weak (missing XEN Name/Contact on active or Not Started work). \
Use tools to get REAL numbers; never guess.
Investigate efficiently: prefer aggregate(operation=count/sum, group_by=...) \
over fetching many raw rows. You have at most 5 tool calls -- use them wisely.
{_finding_schema_instructions()}"""

EQUITY_SYSTEM_PROMPT = f"""You are the EQUITY AGENT on a project review board. \
dataset_id is always 'default'. Your job: analyze the 'Not Started' portfolio \
from a fairness lens -- which districts have a large share of their own \
portfolio still Not Started (underserved relative to their own project count), \
and which categories are neglected in specific districts. Use tools to get \
REAL numbers; never guess.
Investigate efficiently: prefer aggregate(operation=count/sum, group_by=...) \
over fetching many raw rows. You have at most 5 tool calls -- use them wisely.
{_finding_schema_instructions()}"""

COORDINATOR_SYSTEM_PROMPT = """You are the COORDINATOR of a project review board. \
dataset_id is always 'default'. The dataset's relevant columns are: Global ID, \
District, Category, Description, Cost (M), Status. You do NOT need to call \
describe_schema -- you already know the schema; go straight to filter_rows/aggregate.

Three specialist agents have already investigated and reported their structured \
findings below. Your job:

1. Read all three specialists' findings carefully.
2. Identify at least ONE real disagreement or trade-off between them (e.g. \
   Finance may favor low-cost districts already well-served, while Equity \
   favors underserved districts even if costlier per project -- find the \
   genuine tension in what THESE agents actually said, don't invent one).
3. Use filter_rows to query REAL candidate 'Not Started' projects. BE EFFICIENT: \
   plan your query combinations before calling tools, and make as FEW calls as \
   possible. Budget your calls: if you intend to include projects from multiple \
   Categories (e.g. both PHE/Road AND Education/Health), you need a SEPARATE \
   filter_rows call per Category -- plan for this before you start calling tools, \
   so you don't run out of budget after only fetching one Category. NEVER repeat \
   an identical or near-identical tool call you have already made in this \
   conversation -- check what you already retrieved first.
4. CRITICAL RULE -- NEVER FABRICATE: Every row in your final shortlist MUST be \
   a real row returned by one of your tool calls in this conversation, with its \
   real Global ID, District, Category, and Cost (M). If you run out of tool-call \
   budget before covering every category/district you wanted to, DO NOT invent \
   placeholder or example rows (e.g. "Road-Sample-1"). Instead, build your \
   shortlist ONLY from rows you actually retrieved, and explicitly state which \
   categories/districts you were unable to fully cover due to budget limits.
5. Explicitly resolve the disagreement you identified -- explain which \
   consideration wins for which projects, and why.
6. Every recommendation must cite which agent (Finance/Delivery/Equity) \
   raised the concern behind it.
7. Produce a final ranked shortlist as a markdown table using ONLY real \
   retrieved rows: Global ID, District, Category, Cost (M), and a one-line \
   rationale citing the relevant agent(s).
8. End with the total cost of your shortlist and confirm it is within budget \
   (2000 M unless stated otherwise in the task).
9. Your final message must be ONLY the finished report -- never write out your \
   reasoning process, planning notes, or draft thinking as prose (e.g. "We'll \
   resolve by...", "Let's compile..."). If you are still deciding what to \
   include, call another tool instead of writing that decision process into \
   your answer.
10. NEVER fabricate a row. Every project in your final shortlist MUST be one you \
    actually retrieved via a filter_rows call in this conversation, with its real \
    Global ID, District, Category, and Cost (M) exactly as returned. Before adding \
    ANY row to your shortlist, check: did the SPECIFIC filter_rows call that \
    returned this row include a filter matching this row's actual Category? If you \
    only ran ONE filter_rows call without a Category filter, you can ONLY use rows \
    from THAT call's actual returned rows -- you cannot add a different Category \
    (e.g. Education, Irrigation) unless you separately called filter_rows with that \
    Category as an explicit filter and it actually returned matching rows. A single \
    filter_rows call sorted by cost will mostly return PHE/Road/Building projects -- \
    if your shortlist includes other categories (Education, Health, Irrigation, \
    etc.), you MUST have made a SEPARATE filter_rows call for each of those \
    categories specifically, and you must be able to point to which call returned \
    each row.
11. Do not call describe_schema more than once -- you already know the schema \
    from the opening paragraph above. Do not repeat any other identical tool \
    call either.
12. All costs in this dataset (Cost (M)) are already in millions of PKR -- the same \
    currency and unit as any budget figure given in the task. NEVER convert to \
    USD or any other currency; do not invent an exchange rate. If the task says \
    "PKR 500 million," treat that as 500 in Cost (M) units directly.

SPECIALIST FINDINGS:
{specialist_findings_json}
"""




def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _run_specialist(
    name: str,
    system_prompt: str,
    task: str,
    dataset_id: str,
    on_step: Optional[Any] = None,
    cancel_event: Optional[Any] = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Runs one specialist's agent loop. Returns (structured_finding, steps)."""
    result = run_agent_loop(
        system_prompt=system_prompt,
        user_message=f"Task context: {task}",
        tool_schemas=SPECIALIST_TOOLS,
        tool_functions=SPECIALIST_FUNCS,
        fixed_tool_args={"dataset_id": dataset_id},
        on_step=lambda s: on_step({**s, "agent_role": name}) if on_step else None,
        max_steps=5,
        cancel_event=cancel_event,
    )

    finding = _extract_json_object(result["final_answer"])
    if not finding:
        # Fall back to a minimal structured wrapper so the Coordinator
        # still has something usable, rather than crashing the whole board.
        finding = {
            "agent": name,
            "findings": [],
            "recommendation": result["final_answer"] or "(no structured output produced)",
        }

    steps = [{**s, "agent_role": name} for s in result["steps"]]
    return finding, steps


def _run_coordinator(
    task: str,
    specialist_findings: list[dict[str, Any]],
    dataset_id: str,
    on_step: Optional[Any] = None,
    cancel_event: Optional[Any] = None,
) -> tuple[str, list[dict[str, Any]]]:
    prompt = COORDINATOR_SYSTEM_PROMPT.format(
        specialist_findings_json=json.dumps(specialist_findings, indent=2)
    )

    # Coordinator already knows the schema from the prompt -- remove
    # describe_schema from its toolset entirely so it can't call it
    # (more reliable than a prompt instruction alone).
    coordinator_tools = [t for t in SPECIALIST_TOOLS if t["name"] != "describe_schema"]
    coordinator_funcs = {k: v for k, v in SPECIALIST_FUNCS.items() if k != "describe_schema"}

    result = run_agent_loop(
        system_prompt=prompt,
        user_message=f"Task: {task}\nBuild the final ranked shortlist now.",
        tool_schemas=coordinator_tools,
        tool_functions=coordinator_funcs,
        fixed_tool_args={"dataset_id": dataset_id},
        on_step=lambda s: on_step({**s, "agent_role": "Coordinator"}) if on_step else None,
        max_steps=10,
        cancel_event=cancel_event,
    )
    steps = [{**s, "agent_role": "Coordinator"} for s in result["steps"]]
    return result["final_answer"], steps


def _persist_run(
    dataset_id: str,
    task: str,
    specialist_findings: list[dict[str, Any]],
    final_answer: str,
    all_steps: list[dict[str, Any]],
) -> str:
    with session_scope() as db:
        run = QueryRun(
            track="C",
            dataset_id=dataset_id,
            question=task,
            plan=specialist_findings,
            final_answer=final_answer,
            status="completed",
        )
        db.add(run)
        db.flush()

        for i, step in enumerate(all_steps, start=1):
            db.add(ToolCall(
                query_run_id=run.id,
                step_number=i,
                agent_role=step.get("agent_role"),
                tool_name=step["tool_name"],
                arguments=step["arguments"],
                result=step["result"],
            ))

        query_id = run.id
    return query_id


def run_review_board(
    task: str = DEFAULT_TASK,
    dataset_id: str = "default",
    on_specialist_done: Optional[Any] = None,
    on_step: Optional[Any] = None,
    cancel_event: Optional[Any] = None,
) -> dict[str, Any]:
    all_steps: list[dict[str, Any]] = []
    specialist_findings: list[dict[str, Any]] = []

    for name, prompt in [
        ("Finance Agent", FINANCE_SYSTEM_PROMPT),
        ("Delivery Agent", DELIVERY_SYSTEM_PROMPT),
        ("Equity Agent", EQUITY_SYSTEM_PROMPT),
    ]:
        if cancel_event is not None and cancel_event.is_set():
            break
        finding, steps = _run_specialist(name, prompt, task, dataset_id, on_step=on_step, cancel_event=cancel_event)
        specialist_findings.append(finding)
        all_steps.extend(steps)
        if on_specialist_done:
            on_specialist_done(name, finding)

    if cancel_event is not None and cancel_event.is_set():
        query_id = _persist_run(dataset_id, task, specialist_findings, "Cancelled by user.", all_steps)
        return {
            "query_id": query_id,
            "specialist_findings": specialist_findings,
            "final_answer": "Cancelled by user.",
            "steps": all_steps,
            "stopped_reason": "cancelled",
        }

    final_answer, coord_steps = _run_coordinator(
        task, specialist_findings, dataset_id, on_step=on_step, cancel_event=cancel_event
    )
    all_steps.extend(coord_steps)

    query_id = _persist_run(dataset_id, task, specialist_findings, final_answer, all_steps)

    return {
        "query_id": query_id,
        "specialist_findings": specialist_findings,
        "final_answer": final_answer,
        "steps": all_steps,
        "stopped_reason": "completed",
    }


def _print_step(step: dict[str, Any]) -> None:
    role = step.get("agent_role", "?")
    print(f"  [{role} | step {step['step_number']}] {step['tool_name']}({step['arguments']})")
    result_preview = str(step["result"])
    if len(result_preview) > 200:
        result_preview = result_preview[:200] + "..."
    print(f"    -> {result_preview}")


def _print_specialist_done(name: str, finding: dict[str, Any]) -> None:
    print(f"\n=== {name} — structured finding ===")
    print(json.dumps(finding, indent=2))
    print()


def _cli() -> None:
    init_db()
    print("=== Track C: Multi-Agent Review Board ===\n")
    task = input(f"Task (press Enter for default): ").strip()
    if not task:
        task = DEFAULT_TASK

    print(f"\nTask: {task}\n")
    result = run_review_board(task, on_specialist_done=_print_specialist_done, on_step=_print_step)

    print("\n=== COORDINATOR'S FINAL RECOMMENDATION ===")
    print(result["final_answer"])
    print(f"\n(query_id: {result['query_id']}, total_steps: {len(result['steps'])})")


if __name__ == "__main__":
    _cli()