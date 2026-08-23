"""
backend/pdf_export.py

Generates a clean PDF report for a single agent run (any track), given its
full trace from the DB. Used both as a product feature (download button)
and to produce transcript deliverables for the assignment submission.

Text wrapping is done manually with textwrap + cell() instead of FPDF's
multi_cell(), which has known edge cases ("not enough horizontal space")
triggered by certain character/cursor-position combinations.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from fpdf import FPDF
from core.chart_generator import render_bar_chart_png, find_chartable_steps, infer_top_n
from io import BytesIO

def _clean_text(text: str) -> str:
    """Strip light markdown and normalize any character outside FPDF's
    core-font Latin-1 range (e.g. narrow no-break spaces the LLM emits)."""
    if not text:
        return ""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)

    replacements = {
        "\u202f": " ", "\u00a0": " ",
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2010": "-", "\u2011": "-", "\u2012": "-",
        "\u2026": "...", "\u2192": "->",
        "\u2022": "-",  # bullet points
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = text.encode("latin-1", errors="replace").decode("latin-1")
    return text


def _print_wrapped(pdf: FPDF, text: str, line_height: float = 5, width_chars: int = 95) -> None:
    """Manually wrap text to a fixed character width and print line by line
    with cell(), sidestepping FPDF's multi_cell() line-break engine."""
    text = _clean_text(text)
    if not text.strip():
        pdf.cell(0, line_height, "", ln=True)
        return

    for paragraph in text.split("\n"):
        if not paragraph.strip():
            pdf.ln(line_height)
            continue
        lines = textwrap.wrap(
            paragraph, width=width_chars, break_long_words=True, break_on_hyphens=False
        ) or [""]
        for line in lines:
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, line_height, line, ln=True)


class ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 36, 51)
        self.cell(0, 10, "Agentic Infrastructure Analyst - Run Report", ln=True)
        self.set_draw_color(230, 232, 240)
        self.line(10, 20, 200, 20)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def build_run_pdf(run: dict[str, Any], include_trace: bool = True) -> bytes:
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    track_labels = {"A": "Track A - Query Agent", "B": "Track B - Audit Agent", "C": "Track C - Review Board"}

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(79, 70, 229)
    pdf.cell(0, 8, track_labels.get(run.get("track"), "Agent Run"), ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 6, _clean_text(f"Query ID: {run.get('query_id', '')}"), ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 6, _clean_text(f"Dataset: {run.get('dataset_id', '')}"), ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 6, _clean_text(f"Run at: {run.get('created_at', '')}"), ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 36, 51)
    pdf.cell(0, 8, "Question / Goal", ln=True)
    pdf.set_font("Helvetica", "", 10)
    _print_wrapped(pdf, run.get("question", ""), line_height=5.5, width_chars=95)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Final Answer", ln=True)
    pdf.set_font("Helvetica", "", 10)
    _print_wrapped(pdf, run.get("final_answer", "") or "(no answer recorded)", line_height=5.5, width_chars=95)
    pdf.ln(3)

    tool_calls = run.get("tool_calls", [])

    if include_trace:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 36, 51)
        pdf.cell(0, 8, f"Agent Trace ({len(tool_calls)} tool calls)", ln=True)
        pdf.ln(1)

        chartable_steps = find_chartable_steps(tool_calls)
        if chartable_steps:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, "Charts", ln=True)
            pdf.ln(1)
            for step in chartable_steps:
                title = f"{step['result'].get('operation')} by {step['result'].get('group_by')}"
                try:
                    png_bytes = render_bar_chart_png(title, step["result"]["groups"])
                    if pdf.get_y() > 220:
                        pdf.add_page()
                    pdf.image(BytesIO(png_bytes), w=180)
                    pdf.ln(4)
                except Exception:
                    pass
            pdf.ln(2)

        for step in tool_calls:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(79, 70, 229)
            role = f"[{step.get('agent_role')}] " if step.get("agent_role") else ""
            _print_wrapped(
                pdf,
                f"Step {step.get('step_number')} {role}- {step.get('tool_name')}",
                line_height=5, width_chars=100,
            )

            pdf.set_font("Courier", "", 7.5)
            pdf.set_text_color(90, 90, 90)
            args_str = str(step.get("arguments", {}))[:250]
            _print_wrapped(pdf, f"args: {args_str}", line_height=3.8, width_chars=105)

            result_str = str(step.get("result", {}))[:350]
            _print_wrapped(pdf, f"result: {result_str}", line_height=3.8, width_chars=105)

            pdf.ln(2)
    else:
        # Non-admin report: note that charts still convey real results
        # (grouped aggregate data), so keep those even without the raw trace.
        chartable_steps = find_chartable_steps(tool_calls)
        if chartable_steps:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(30, 36, 51)
            pdf.cell(0, 8, "Charts", ln=True)
            pdf.ln(1)
            for step in chartable_steps:
                title = f"{step['result'].get('operation')} by {step['result'].get('group_by')}"
                try:
                    png_bytes = render_bar_chart_png(title, step["result"]["groups"])
                    if pdf.get_y() > 220:
                        pdf.add_page()
                    pdf.image(BytesIO(png_bytes), w=180)
                    pdf.ln(4)
                except Exception:
                    pass

    pdf.set_text_color(30, 36, 51)

    return bytes(pdf.output())