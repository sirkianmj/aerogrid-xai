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

    def _c(text: str, style: ParagraphStyle) -> Paragraph:
        # Wrap every cell in Paragraph. ReportLab's raw-string cells skip
        # the PLATYPUS flow machinery: they do not wrap, they do not
        # respect codepoint mappings cleanly for extraction tools, and
        # some viewers render them as garbage. Paragraph is the correct
        # primitive for table cells.
        return Paragraph(text, style)

    header = [
        _c("Section", styles["body"]),
        _c("Step", styles["body"]),
        _c("Status", styles["body"]),
    ]
    rows: list[list[Any]] = [header]
    sections = [
        ("Mission configuration", "-", "always present"),
        ("Step 1 - Design", "1", "from config"),
        ("Step 2 - Mission", "2", "from state" if inp.mission_state else "not executed"),
        ("Step 3 - Discovery", "3", "executed" if 3 in inp.step_outputs else "not executed"),
        ("Step 4 - Selection", "4", "executed" if 4 in inp.step_outputs else "not executed"),
        ("Step 5 - Simulation", "5", "executed" if 5 in inp.step_outputs else "not executed"),
        ("Section 21 epistemic summary", "-", "always present"),
        ("Reproducibility appendix", "-", "always present"),
    ]
    for sec, step, status in sections:
        rows.append([_c(sec, styles["body"]), _c(step, styles["mono"]), _c(status, styles["mono"])])
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
    if trans.get("relay_note"):
        summary["relay_note"] = trans["relay_note"]
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
    step5_samples = data.get("samples") or []
    step5_runaway_uavs: set[int] = set()
    for s in step5_samples:
        if not isinstance(s, dict):
            continue
        for u in s.get("uavs") or []:
            if isinstance(u, dict) and u.get("thermal_runaway"):
                step5_runaway_uavs.add(int(u.get("uav_id", -1)))
    summary = {
        "preset": data.get("preset", "?"),
        "duration_s": data.get("duration_s", "?"),
        "n_samples": data.get("n_samples", "?"),
        "warnings": len(data.get("warnings") or []),
        "thermal_runaway_uavs": len(step5_runaway_uavs),
    }
    els.append(_kv_table(summary, styles))
    els.append(Spacer(1, 6))
    samples = data.get("samples") or []
    if isinstance(samples, list) and len(samples) >= 2:
        try:
            for chart in _charts_grid(samples):
                els.append(chart)
                els.append(Spacer(1, 6))
        except Exception:
            els.append(
                Paragraph("(charts could not be rendered from the sample data)", styles["missing"])
            )
    else:
        els.append(
            Paragraph(
                "Fewer than two samples were captured; chart series cannot be "
                "rendered. Run Step 5 with a longer preset to populate the charts.",
                styles["missing"],
            )
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
    story.extend(_final_summary_section(inp, styles))
    story.extend(_epistemic_summary_section(styles))
    story.extend(_reproducibility_section(inp, styles))
    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Additional chart helpers and final-summary section.
# Appended by PR #180. Kept separate from the original generator so the
# original code path stays untouched when a caller only wants the baseline.
# ---------------------------------------------------------------------------


def _downsample(xs: list[float], ys: list[float], n: int = 20) -> tuple[list[float], list[float]]:
    """Reduce a series to at most n points for chart readability.

    ReportLab's HorizontalLineChart renders category labels one per point;
    a 100-sample simulation would produce unreadable axis text. Downsample
    is uniform in index space (not value space) — good enough for a
    thumbnail-style figure where the user's own ECharts view in the app
    carries the full-resolution data.
    """
    if len(xs) <= n:
        return xs, ys
    step = len(xs) / float(n)
    out_x: list[float] = []
    out_y: list[float] = []
    for i in range(n):
        idx = min(int(i * step), len(xs) - 1)
        out_x.append(xs[idx])
        out_y.append(ys[idx])
    return out_x, out_y


def _line_chart(
    xs: list[float],
    ys: list[float],
    *,
    title: str,
    y_label: str,
    x_label: str = "elapsed (s)",
    color: str = "#007aff",
    width_in: float = 6.5,
    height_in: float = 2.6,
) -> Drawing | None:
    """Build a single line chart Drawing, or None if the series is degenerate."""
    if len(xs) < 2 or len(ys) < 2:
        return None
    xs_d, ys_d = _downsample(xs, ys)
    d = Drawing(width_in * inch, height_in * inch)
    chart = HorizontalLineChart()
    chart.x = 50
    chart.y = 40
    chart.height = int(height_in * inch) - 60
    chart.width = int(width_in * inch) - 70
    chart.data = [ys_d]
    chart.categoryAxis.categoryNames = [f"{x:.0f}" for x in xs_d]
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.valueMin = 0
    y_max = max(ys_d) if ys_d else 1.0
    chart.valueAxis.valueMax = max(y_max * 1.1, 1.0)
    chart.valueAxis.labels.fontSize = 6
    chart.lines[0].strokeColor = colors.HexColor(color)
    chart.lines[0].strokeWidth = 1.5
    d.add(chart)
    d.add(
        String(
            width_in * inch / 2,
            22,
            f"{title}  ·  y: {y_label}",
            fontSize=9,
            textAnchor="middle",
        )
    )
    d.add(
        String(
            width_in * inch / 2,
            8,
            x_label,
            fontSize=7,
            textAnchor="middle",
            fillColor=colors.HexColor("#86868b"),
        )
    )
    return d


def _extract_series(
    samples: list[Any], field_path: tuple[str, ...]
) -> tuple[list[float], list[float]]:
    """Extract (xs, ys) from a list of sample dicts. Missing values become 0."""
    xs: list[float] = []
    ys: list[float] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        try:
            xs.append(float(s.get("elapsed_s", 0.0)))
        except (TypeError, ValueError):
            continue
        v: Any = s
        for key in field_path:
            if isinstance(v, dict):
                v = v.get(key)
            else:
                v = None
                break
        try:
            ys.append(float(v) if v is not None else 0.0)
        except (TypeError, ValueError):
            ys.append(0.0)
    return xs, ys


def _charts_grid(samples: list[Any]) -> list[Any]:
    """Render 4 charts in a 2x2 grid for the Step 5 section."""
    if len(samples) < 2:
        return []

    received_xs, received_ys = _extract_series(samples, ("received_power_w",))
    energy_xs, energy_ys = _extract_series(samples, ("cumulative_energy_j",))
    tau_xs, tau_ys = _extract_series(samples, ("atmospheric_transmittance",))
    elev_xs, elev_ys = _extract_series(samples, ("satellite_elevation_deg",))

    charts = [
        _line_chart(
            received_xs,
            received_ys,
            title="Received power (W)",
            y_label="received (W)",
            color="#34c759",
        ),
        _line_chart(
            energy_xs,
            energy_ys,
            title="Cumulative energy (J)",
            y_label="energy (J)",
            color="#ff9500",
        ),
        _line_chart(
            tau_xs,
            tau_ys,
            title="Atmospheric transmittance",
            y_label="tau",
            color="#5856d6",
        ),
        _line_chart(
            elev_xs,
            elev_ys,
            title="Satellite elevation (deg)",
            y_label="elev (deg)",
            color="#af52de",
        ),
    ]
    return [c for c in charts if c is not None]


def _peak_and_totals(samples: list[Any]) -> dict[str, float]:
    """Extract the numbers the summary paragraph needs, tolerant to shape."""
    peak_delivered = 0.0
    peak_received = 0.0
    total_energy = 0.0
    tau_min = float("inf")
    tau_max = float("-inf")
    elev_min = float("inf")
    elev_max = float("-inf")
    count = 0
    for s in samples:
        if not isinstance(s, dict):
            continue
        try:
            peak_delivered = max(peak_delivered, float(s.get("delivered_power_w", 0.0)))
            peak_received = max(peak_received, float(s.get("received_power_w", 0.0)))
            total_energy = max(total_energy, float(s.get("cumulative_energy_j", 0.0)))
            tau = float(s.get("atmospheric_transmittance", 0.0))
            elev = float(s.get("satellite_elevation_deg", 0.0))
            tau_min = min(tau_min, tau)
            tau_max = max(tau_max, tau)
            elev_min = min(elev_min, elev)
            elev_max = max(elev_max, elev)
            count += 1
        except (TypeError, ValueError):
            continue
    if count == 0:
        return {
            "peak_delivered": 0.0,
            "peak_received": 0.0,
            "total_energy": 0.0,
            "tau_min": 0.0,
            "tau_max": 0.0,
            "elev_min": 0.0,
            "elev_max": 0.0,
        }
    return {
        "peak_delivered": peak_delivered,
        "peak_received": peak_received,
        "total_energy": total_energy,
        "tau_min": 0.0 if tau_min == float("inf") else tau_min,
        "tau_max": 0.0 if tau_max == float("-inf") else tau_max,
        "elev_min": 0.0 if elev_min == float("inf") else elev_min,
        "elev_max": 0.0 if elev_max == float("-inf") else elev_max,
    }


def _final_summary_section(inp: ReportInput, styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Human-readable summary of the run's own output. Not a claim about
    physical reality — see the Section 21 note embedded in the paragraph."""
    els: list[Any] = [PageBreak()]
    els.extend(
        _section_header("Final Results Summary", "simulation_result", 5 in inp.step_outputs, styles)
    )

    if 5 not in inp.step_outputs:
        els.append(
            Paragraph(
                "Step 5 (Simulation) was not executed in this session. No "
                "summary can be derived from the run's own output. To "
                "produce a summary, run Step 5 first, then generate the "
                "report again.",
                styles["missing"],
            )
        )
        return els

    data = inp.step_outputs[5].get("data")
    if not isinstance(data, dict):
        els.append(
            Paragraph(
                "Step 5 output has an unexpected shape; summary cannot be derived.",
                styles["missing"],
            )
        )
        return els

    samples = data.get("samples") or []
    if not isinstance(samples, list) or len(samples) < 2:
        els.append(
            Paragraph(
                "Step 5 produced fewer than two samples; summary cannot be derived.",
                styles["missing"],
            )
        )
        return els

    peak = _peak_and_totals(samples)
    preset = str(data.get("preset", "unknown"))
    duration_s = data.get("duration_s", 0)
    n_samples = data.get("n_samples", len(samples))
    n_uavs = len(inp.step_outputs[5].get("data", {}).get("samples", [{}])[0].get("uavs", [])) or "?"

    # --- Key numbers table ---
    rows = [["Metric", "Value", "Unit"]]
    rows.append(["Samples", f"{n_samples}", "count"])
    rows.append(["Duration", f"{float(duration_s):.0f}", "s"])
    rows.append(["Preset", preset, "—"])
    rows.append(["Peak received (sum over UAVs)", f"{peak['peak_received']:.3f}", "W"])
    rows.append(["Peak delivered (sum over UAVs)", f"{peak['peak_delivered']:.3f}", "W"])
    rows.append(["Total delivered energy", f"{peak['total_energy'] / 1000:.3f}", "kJ"])
    rows.append(
        [
            "Atmospheric transmittance range",
            f"{peak['tau_min']:.4f} \u2014 {peak['tau_max']:.4f}",
            "—",
        ]
    )
    rows.append(
        [
            "Satellite elevation range",
            f"{peak['elev_min']:.1f} \u2014 {peak['elev_max']:.1f}",
            "deg",
        ]
    )
    t = Table(rows, colWidths=[3.0 * inch, 1.8 * inch, 1.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e5e5ea")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    els.append(t)
    els.append(Spacer(1, 12))

    # --- Interpretation paragraph, derived ONLY from the numbers above ---
    atm_desc = "clear-sky"
    if peak["tau_min"] < 0.3:
        atm_desc = "heavily degraded"
    elif peak["tau_min"] < 0.6:
        atm_desc = "moderately degraded"
    elif peak["tau_min"] < 0.85:
        atm_desc = "slightly degraded"

    delivered_str = (
        f"{peak['peak_delivered']:.2f} W"
        if peak["peak_delivered"] < 1e3
        else f"{peak['peak_delivered'] / 1e3:.2f} kW"
    )
    energy_str = (
        f"{peak['total_energy']:.0f} J"
        if peak["total_energy"] < 1e4
        else f"{peak['total_energy'] / 1e3:.2f} kJ"
    )

    interpretation = (
        f"During this run, the simulated mission delivered a peak of "
        f"<b>{delivered_str}</b> to <b>{n_uavs}</b> UAV(s) across "
        f"<b>{float(duration_s):.0f} s</b> of simulated time, integrating "
        f"<b>{energy_str}</b>. Atmospheric transmittance ranged from "
        f"<b>{peak['tau_min']:.3f}</b> to <b>{peak['tau_max']:.3f}</b>, "
        f"characterising the pass as <b>{atm_desc}</b> under the configured "
        f"environment. Satellite elevation ranged from "
        f"<b>{peak['elev_min']:.1f}\u00b0</b> to <b>{peak['elev_max']:.1f}\u00b0</b>, "
        f"which sets the geometric path length through the atmosphere at "
        f"each sample."
    )
    els.append(Paragraph(interpretation, styles["body"]))
    els.append(Spacer(1, 4))

    # Thermal runaway disclosure. Distinguishes "0 W because nothing was
    # received" from "0 W because the receiver exceeded its thermal limit."
    # Without this, an overpowered ground-mode mission looks like a bug.
    runaway_ids: set[int] = set()
    for s in samples:
        if not isinstance(s, dict):
            continue
        for u in s.get("uavs") or []:
            if isinstance(u, dict) and u.get("thermal_runaway"):
                runaway_ids.add(int(u.get("uav_id", -1)))
    if runaway_ids:
        els.append(
            Paragraph(
                f"<b>Thermal runaway detected:</b> {len(runaway_ids)} UAV(s) "
                f"received non-zero incident power but exceeded the "
                f"receiver's thermal runaway threshold. Delivered power is "
                f"0 W as a physical consequence of heat generation exceeding "
                f"all cooling mechanisms, not by design. To stay below the "
                f"runaway boundary, reduce transmitter power or increase the "
                f"receiver aperture.",
                styles["body"],
            )
        )
        els.append(Spacer(1, 4))

    els.append(Spacer(1, 6))

    note = (
        "<i>This paragraph is derived strictly from the numbers in the "
        "table above and the run's own sample data. It is a "
        "<b>simulation_result</b> per Section 21, not a claim about "
        "physical reality. It makes no recommendation about how to "
        "improve the mission \u2014 such a claim would require a validated "
        "physical model for each alternative configuration, which this "
        "report does not carry.</i>"
    )
    els.append(Paragraph(note, styles["missing"]))
    els.append(Spacer(1, 12))

    # --- Composed multi-chart page ---
    els.append(Paragraph("Chart series across the simulation window", styles["h2"]))
    els.append(Spacer(1, 4))
    for chart in _charts_grid(samples):
        els.append(chart)
        els.append(Spacer(1, 6))

    return els
