"""
agents/query_agent.py

Track A - The Query Agent.

Wraps core.llm_client.run_agent_loop with:
  - a system prompt tuned for grounded, citation-backed answers over the
    dataset (handles the 4 example questions from the assignment brief)
  - persistence: every run becomes a QueryRun row with its ToolCall
    history, so it gets a real Query ID and shows up in /history later
  - a simple CLI for testing before the API/frontend exist
"""

from __future__ import annotations

import sys
import os
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import session_scope, init_db
from db.models import QueryRun, ToolCall , Dataset
from core.llm_client import run_agent_loop
from core.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS
from core.history_tools import HISTORY_TOOL_SCHEMAS, HISTORY_TOOL_FUNCTIONS
from core.document_tools import DOCUMENT_TOOL_SCHEMAS, DOCUMENT_TOOL_FUNCTIONS



ALL_TOOL_SCHEMAS = TOOL_SCHEMAS + HISTORY_TOOL_SCHEMAS
ALL_TOOL_FUNCTIONS = {**TOOL_FUNCTIONS, **HISTORY_TOOL_FUNCTIONS}

SYSTEM_PROMPT = """You are a data analyst agent answering questions about a \
government infrastructure projects dataset. The dataset_id for every tool \
call is always 'default' -- pass it literally, never guess a different id.

Rules you MUST follow:
1. Never state a number, count, or statistic unless it came directly from a \
   tool result in this conversation. If you have not called a tool for a \
   fact, do not state that fact.
2. If a question requires data you have not yet fetched, call describe_schema \
   first if you're unsure of column names/values, then filter_rows or \
   aggregate to get the real numbers.
3. If a column relevant to the question has significant missing data, call \
   check_data_quality and mention the gap in your answer (e.g. "18% of rows \
   have no recorded start date, so this figure covers the other 82%").
4. Always cite what filters/columns produced your answer, so the user can \
   trace how you got it.
5. If the data cannot answer the question (e.g. asking about a district \
   that doesn't exist), say so plainly instead of guessing.
6. Keep your final answer concise and directly address what was asked.
7. If the user references a previous query by its query_id (e.g. "qry_a1b2c3d4") \
   or refers to "those" / "that result" from earlier, use lookup_query to \
   retrieve what that past run actually found before answering.
8. If a tool call returns an "error" field, do not guess what the data might \
   have been. State plainly that the tool call failed and why, based on the \
   error message you received."""

def _persist_run(
    track: str,
    dataset_id: str,
    question: str,
    result: dict[str, Any],
    plan: Optional[Any] = None,
) -> str:
    """Save a completed agent run + its tool call trace to the DB. Returns the query_id."""
    with session_scope() as db:
        run = QueryRun(
            track=track,
            dataset_id=dataset_id,
            question=question,
            plan=plan,
            final_answer=result["final_answer"],
            status="completed",
        )
        db.add(run)
        db.flush()  # populate run.id (the query ID) before adding children

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

def _get_dataset_type(dataset_id: str) -> str:
    with session_scope() as db:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        return dataset.type if dataset else "tabular"

DOCUMENT_SYSTEM_PROMPT = """You are a research assistant answering questions about an \
uploaded document. The dataset_id for every tool call is always the active document's \
id -- pass it literally, never guess a different id.

Rules you MUST follow:
1. Never state a fact unless it came from a passage returned by search_document in \
   this conversation. If you have not searched for something, do not claim to know it.
2. Call search_document with a clear, specific query related to the question. You may \
   call it more than once with different phrasings if the first search doesn't surface \
   what's needed.
3. Cite which page number(s) your answer came from.
4. If the document doesn't contain relevant information, say so plainly instead of \
   guessing or using general knowledge."""


def ask(
    question: str,
    dataset_id: str = "default",
    on_step: Optional[Any] = None,
    cancel_event: Optional[Any] = None,
) -> dict[str, Any]:
    dataset_type = _get_dataset_type(dataset_id)

    if dataset_type == "document":
        system_prompt = DOCUMENT_SYSTEM_PROMPT
        tool_schemas = DOCUMENT_TOOL_SCHEMAS + HISTORY_TOOL_SCHEMAS
        tool_functions = {**DOCUMENT_TOOL_FUNCTIONS, **HISTORY_TOOL_FUNCTIONS}
    else:
        system_prompt = SYSTEM_PROMPT
        tool_schemas = ALL_TOOL_SCHEMAS
        tool_functions = ALL_TOOL_FUNCTIONS

    result = run_agent_loop(
        system_prompt=system_prompt,
        user_message=question,
        tool_schemas=tool_schemas,
        tool_functions=tool_functions,
        fixed_tool_args={"dataset_id": dataset_id},
        on_step=on_step,
        cancel_event=cancel_event,
    )

    query_id = _persist_run(
        track="A",
        dataset_id=dataset_id,
        question=question,
        result=result,
    )

    return {
        "query_id": query_id,
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



def _cli() -> None:
    init_db()
    print("=== Track A: Query Agent ===")
    print("Ask questions about the PMTS Projects dataset. Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        print()
        response = ask(question, on_step=_print_step)
        print(f"\nAgent: {response['final_answer']}")
        print(f"(query_id: {response['query_id']}, "
              f"steps: {len(response['steps'])}, "
              f"stopped: {response['stopped_reason']})\n")


if __name__ == "__main__":
    _cli()