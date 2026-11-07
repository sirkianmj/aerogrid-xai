"""DARPA-style PDF mission report generator.

Assembles a multi-page report from the mission config, the per-step
outputs captured on the frontend (step_outputs in the mission context),
and the live mission state. Every section carries its Section 21
epistemic tag. Sections whose step was not executed in the session
render as "Not executed in this session" rather than being silently
omitted.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass(frozen=True)
class ReportInput:
    mission_config: dict[str, Any]
    step_outputs: dict[int, dict[str, Any]]
    mission_state: dict[str, Any] | None
    generated_at: str


_SECTION_21_ORDER = [
    ("physical_measurement", "Physical measurement"),
    ("validated_physical_model", "Validated physical model"),
    ("estimated_model", "Estimated model"),
    ("simulation_result", "Simulation result"),
    ("ai_prediction", "AI prediction"),
    ("formal_verification_result", "Formal verification result"),
    ("hypothetical_scenario", "Hypothetical scenario"),
]

_TAG_SHORT = {
    "physical_measurement": "MEASUREMENT",
    "validated_physical_model": "VALIDATED MODEL",
    "estimated_model": "ESTIMATED MODEL",
    "simulation_result": "SIMULATION",
    "ai_prediction": "AI PREDICTION",
    "formal_verification_result": "FORMAL VERIFICATION",
    "hypothetical_scenario": "HYPOTHETICAL",
}

_TAG_COLOR = {
    "physical_measurement": "#34c759",
    "validated_physical_model": "#30d158",
    "estimated_model": "#ff9500",
    "simulation_result": "#007aff",
    "ai_prediction": "#5856d6",
    "formal_verification_result": "#af52de",
    "hypothetical_scenario": "#86868b",
}


def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=22,
            leading=28,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#6e6e73"),
            alignment=TA_CENTER,
            spaceAfter=24,
        ),
        "h1": ParagraphStyle(
            "ReportH1",
            parent=base["Heading1"],
            fontSize=16,
            leading=20,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1d1d1f"),
        ),
        "h2": ParagraphStyle(
            "ReportH2",
            parent=base["Heading2"],
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=4,
            textColor=colors.HexColor("#1d1d1f"),
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1d1d1f"),
        ),
        "mono": ParagraphStyle(
            "ReportMono",
            parent=base["Code"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#6e6e73"),
        ),
        "missing": ParagraphStyle(
            "ReportMissing",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#86868b"),
            fontName="Helvetica-Oblique",
        ),
        "chip": ParagraphStyle(
            "ReportChip",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def _tag_chip(tag: str, styles: dict[str, ParagraphStyle]) -> Table:
    label = _TAG_SHORT.get(tag, tag.upper())
    bg = _TAG_COLOR.get(tag, "#86868b")
    cell = Paragraph(f"<b>{label}</b>", styles["chip"])
    t = Table([[cell]], colWidths=[1.6 * inch], rowHeights=[0.22 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _section_header(
    title: str, tag: str, executed: bool, styles: dict[str, ParagraphStyle]
) -> list[Any]:
    chip = _tag_chip(tag, styles)
    status = "Executed" if executed else "Not executed in this session"
    header = Table(
        [
            [
                Paragraph(f"<b>{title}</b>", styles["h1"]),
                chip,
                Paragraph(status, styles["mono"]),
            ]
        ],
        colWidths=[3.5 * inch, 1.8 * inch, 2.0 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ]
        )
    )
    return [header, Spacer(1, 6)]


def _kv_table(data: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[Any]] = []
    for k, v in data.items():
        val_str = str(v) if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>"
        rows.append([Paragraph(f"<b>{k}</b>", styles["body"]), Paragraph(val_str, styles["mono"])])
    if not rows:
        return Table([[""]], colWidths=[6 * inch])
    t = Table(rows, colWidths=[2.2 * inch, 4.5 * inch])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e5e5ea")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _cover_page(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    els: list[Any] = [Spacer(1, 1.2 * inch)]
    els.append(Paragraph("AeroGrid-XAI", styles["title"]))
    els.append(Paragraph("CLEAR-D Mission Report", styles["subtitle"]))
    els.append(Spacer(1, 0.5 * inch))
    meta = [
        ("Generated at (UTC)", inp.generated_at),
        ("Seed", str(inp.mission_config.get("seed", "unknown"))),
        ("Satellite", str(inp.mission_config.get("satellite_key", "unknown"))),
        ("UAVs", str(inp.mission_config.get("n_uavs", "unknown"))),
        ("Transmitter (W)", str(inp.mission_config.get("transmitter_power_w", "unknown"))),
        ("Wavelength (nm)", str(inp.mission_config.get("wavelength_nm", "unknown"))),
    ]
    meta_t = Table(
        [
            [Paragraph(f"<b>{k}</b>", styles["body"]), Paragraph(str(v), styles["mono"])]
            for k, v in meta
        ],
        colWidths=[2.5 * inch, 3.5 * inch],
    )
    meta_t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    els.append(meta_t)
    els.append(Spacer(1, 1.0 * inch))
    note = (
        "Every result in this report is tagged with its Section 21 "
        "epistemic category. A simulation result is the output of the "
        "Digital Twin running validated or estimated physics models -- "
        "not a physical measurement and not a formal verification "
        "verdict."
    )
    els.append(Paragraph(note, styles["missing"]))
    els.append(PageBreak())
    return els


def _toc_page(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    els: list[Any] = [Paragraph("Table of contents", styles["h1"])]
    rows = [["Section", "Step", "Status"]]
    sections = [
        ("Mission configuration", "\u2014", "always present"),
        ("Step 1 \u2014 Design", "1", "from config"),
        ("Step 2 \u2014 Mission", "2", "from state" if inp.mission_state else "not executed"),
        ("Step 3 \u2014 Discovery", "3", "executed" if 3 in inp.step_outputs else "not executed"),
        ("Step 4 \u2014 Selection", "4", "executed" if 4 in inp.step_outputs else "not executed"),
        ("Step 5 \u2014 Simulation", "5", "executed" if 5 in inp.step_outputs else "not executed"),
        ("Section 21 epistemic summary", "\u2014", "always present"),
        ("Reproducibility appendix", "\u2014", "always present"),
    ]
    for s, step, status in sections:
        rows.append([s, step, status])
    t = Table(rows, colWidths=[3.5 * inch, 0.8 * inch, 2.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e5ea")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    els.append(t)
    els.append(PageBreak())
    return els


def _config_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    els = _section_header("Mission configuration", "estimated_model", True, styles)
    els.append(
        Paragraph(
            "The mission's configured parameters. Every value here feeds one "
            "or more backend computations.",
            styles["body"],
        )
    )
    els.append(Spacer(1, 6))
    els.append(_kv_table(inp.mission_config, styles))
    els.append(Spacer(1, 12))
    return els


def _step1_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    els = _section_header("Step 1 \u2014 Design", "estimated_model", True, styles)
    cfg = inp.mission_config
    hw_list = cfg.get("uav_hardware_list") or []
    if not hw_list:
        els.append(
            Paragraph(
                "No UAV hardware adopted. The mission uses default receiver parameters.",
                styles["missing"],
            )
        )
    else:
        els.append(
            Paragraph(
                f"{len(hw_list)} UAV hardware configuration(s) adopted into the mission.",
                styles["body"],
            )
        )
        els.append(Spacer(1, 4))
        for i, hw in enumerate(hw_list):
            if isinstance(hw, dict):
                els.append(Paragraph(f"<b>UAV-{i}</b>", styles["h2"]))
                els.append(_kv_table(hw, styles))
                els.append(Spacer(1, 4))
    sat_el = cfg.get("satellite_elements")
    if isinstance(sat_el, dict):
        els.append(Paragraph("<b>Custom orbital elements</b>", styles["h2"]))
        els.append(_kv_table(sat_el, styles))
    els.append(Spacer(1, 12))
    return els


def _step2_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    executed = inp.mission_state is not None
    els = _section_header("Step 2 \u2014 Mission", "simulation_result", executed, styles)
    if not executed or not inp.mission_state:
        els.append(
            Paragraph(
                "Step 2 output was not captured. Re-run Step 2 to include this section.",
                styles["missing"],
            )
        )
        els.append(Spacer(1, 12))
        return els
    state = inp.mission_state
    sat = state.get("satellite") or {}
    trans = state.get("transmission") or {}
    atm = state.get("atmosphere") or {}
    summary: dict[str, Any] = {
        "t_utc": state.get("t_utc", "unknown"),
        "satellite_key": sat.get("key", "unknown"),
        "satellite_alt_km": sat.get("alt_km", "unknown"),
        "transmission_modality": trans.get("modality", "unknown"),
        "atmospheric_transmittance": atm.get("transmittance", "unknown"),
        "uav_count": len(state.get("uavs") or []),
    }
    els.append(_kv_table(summary, styles))
    els.append(Spacer(1, 12))
    return els


def _step3_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    executed = 3 in inp.step_outputs
    els = _section_header("Step 3 \u2014 Discovery", "simulation_result", executed, styles)
    if not executed:
        els.append(Paragraph("Step 3 was not executed in this session.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    data = inp.step_outputs[3].get("data")
    if not isinstance(data, dict):
        els.append(Paragraph("Step 3 output has an unexpected shape.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    summary = {
        "population_size": data.get("population_size", "?"),
        "n_generations": data.get("n_generations", "?"),
        "n_discovered": len(data.get("discovered") or []),
        "conflict_prone_features": len(data.get("conflict_prone_table") or {}),
    }
    els.append(_kv_table(summary, styles))
    els.append(Spacer(1, 12))
    return els


def _step4_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    executed = 4 in inp.step_outputs
    els = _section_header(
        "Step 4 \u2014 Selection (Trade Space)", "simulation_result", executed, styles
    )
    if not executed:
        els.append(Paragraph("Step 4 was not executed in this session.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    data = inp.step_outputs[4].get("data")
    if not isinstance(data, dict):
        els.append(Paragraph("Step 4 output has an unexpected shape.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    summary = {
        "n_pareto": data.get("n_pareto", "?"),
        "n_final_population": data.get("n_final_population", "?"),
    }
    els.append(_kv_table(summary, styles))
    els.append(Spacer(1, 12))
    return els


def _step5_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    executed = 5 in inp.step_outputs
    els = _section_header("Step 5 \u2014 Simulation", "simulation_result", executed, styles)
    if not executed:
        els.append(Paragraph("Step 5 was not executed in this session.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    data = inp.step_outputs[5].get("data")
    if not isinstance(data, dict):
        els.append(Paragraph("Step 5 output has an unexpected shape.", styles["missing"]))
        els.append(Spacer(1, 12))
        return els
    summary = {
        "preset": data.get("preset", "?"),
        "duration_s": data.get("duration_s", "?"),
        "n_samples": data.get("n_samples", "?"),
        "warnings": len(data.get("warnings") or []),
    }
    els.append(_kv_table(summary, styles))
    els.append(Spacer(1, 6))
    samples = data.get("samples") or []
    if isinstance(samples, list) and samples:
        try:
            drawing = _power_chart(samples)
            if drawing is not None:
                els.append(drawing)
        except Exception:
            els.append(
                Paragraph("(chart could not be rendered from the sample data)", styles["missing"])
            )
    els.append(Spacer(1, 12))
    return els


def _power_chart(samples: list[Any]) -> Drawing | None:
    if len(samples) < 2:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        try:
            xs.append(float(s.get("elapsed_s", 0.0)))
            ys.append(float(s.get("delivered_power_w", 0.0)))
        except (TypeError, ValueError):
            continue
    if not ys:
        return None
    d = Drawing(6.5 * inch, 2.8 * inch)
    chart = HorizontalLineChart()
    chart.x = 50
    chart.y = 40
    chart.height = 140
    chart.width = 380
    chart.data = [ys]
    chart.categoryAxis.categoryNames = [f"{x:.0f}" for x in xs]
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.title = "elapsed (s)"
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(max(ys) * 1.1, 1.0)
    chart.valueAxis.title = "delivered power (W)"
    chart.valueAxis.labels.fontSize = 6
    chart.lines[0].strokeColor = colors.HexColor("#007aff")
    chart.lines[0].strokeWidth = 1.5
    d.add(chart)
    d.add(String(210, 10, "Delivered power over time", fontSize=9, textAnchor="middle"))
    return d


def _epistemic_summary_section(styles: dict[str, ParagraphStyle]) -> list[Any]:
    els = _section_header("Section 21 epistemic summary", "simulation_result", True, styles)
    els.append(
        Paragraph(
            "The AeroGrid-XAI platform enforces a strict seven-category "
            "epistemic hierarchy. Every output in this report belongs to "
            "exactly one category, ordered from strongest to weakest.",
            styles["body"],
        )
    )
    els.append(Spacer(1, 6))
    rows = [["#", "Category", "Meaning"]]
    meanings = {
        "physical_measurement": "An actual reported hardware test result.",
        "validated_physical_model": "A model whose parameters have been fit against measurements.",
        "estimated_model": "A model built from first principles, not yet validated.",
        "simulation_result": "Output of the Digital Twin running physics models.",
        "ai_prediction": "A Tier 2 surrogate output with a calibrated uncertainty interval.",
        "formal_verification_result": "SAT/UNSAT against the PWL-approximated encoding.",
        "hypothetical_scenario": "A user-defined what-if with no real-world claim.",
    }
    for i, (key, label) in enumerate(_SECTION_21_ORDER, start=1):
        rows.append([str(i), label, meanings[key]])
    t = Table(rows, colWidths=[0.4 * inch, 2.2 * inch, 4.1 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e5ea")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    els.append(t)
    els.append(Spacer(1, 12))
    return els


def _reproducibility_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    els = _section_header("Reproducibility appendix", "estimated_model", True, styles)
    seed = inp.mission_config.get("seed", "unknown")
    cfg_str = ", ".join(
        f"{k}={v}"
        for k, v in sorted(inp.mission_config.items())
        if not isinstance(v, (dict, list)) and v is not None
    )
    cmd = (
        f"curl -X GET 'http://127.0.0.1:8000/mission/state?seed={seed}' --output mission_state.json"
    )
    els.append(
        Paragraph(
            "To reproduce the mission computation behind this report, the "
            "following request reconstructs the Step 2 state. Steps 3-5 "
            "depend on the same seed values being configured in their "
            "respective panels.",
            styles["body"],
        )
    )
    els.append(Spacer(1, 4))
    els.append(Paragraph(f"<b>Config:</b> {cfg_str}", styles["mono"]))
    els.append(Spacer(1, 4))
    els.append(Paragraph(f"<b>Command:</b><br/>{cmd}", styles["mono"]))
    return els


def generate_report_pdf(inp: ReportInput) -> bytes:
    """Generate the DARPA-style PDF report and return the raw bytes."""
    styles = _make_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="AeroGrid-XAI Mission Report",
        author="AeroGrid-XAI",
        subject="CLEAR-D Mission Report",
        creator="AeroGrid-XAI",
    )
    story: list[Any] = []
    story.extend(_cover_page(inp, styles))
    story.extend(_toc_page(inp, styles))
    story.extend(_config_section(inp, styles))
    story.extend(_step1_section(inp, styles))
    story.extend(_step2_section(inp, styles))
    story.extend(_step3_section(inp, styles))
    story.extend(_step4_section(inp, styles))
    story.extend(_step5_section(inp, styles))
    story.extend(_epistemic_summary_section(styles))
    story.extend(_reproducibility_section(inp, styles))
    doc.build(story)
    return buf.getvalue()
