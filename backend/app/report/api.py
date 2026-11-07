"""Report generation HTTP endpoint -- Step 6 of the workflow.

POST /report/generate receives the mission config and every step's
captured output from the frontend, assembles a DARPA-style PDF, and
returns it as application/pdf. Every result in the PDF carries its
Section 21 epistemic tag.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.report.generator import ReportInput, generate_report_pdf

router = APIRouter(prefix="/report", tags=["report"])


class ReportRequest(BaseModel):
    mission_config: dict[str, Any] = Field(default_factory=dict)
    step_outputs: dict[int, dict[str, Any]] = Field(default_factory=dict)
    mission_state: dict[str, Any] | None = None


@router.post("/generate")
async def generate(request: ReportRequest) -> Response:
    """Generate a DARPA-style PDF report from the request payload."""
    try:
        pdf_bytes = generate_report_pdf(
            ReportInput(
                mission_config=request.mission_config,
                step_outputs=request.step_outputs,
                mission_state=request.mission_state,
                generated_at=datetime.now(UTC).isoformat(),
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"report generation failed: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="aerogrid-report.pdf"',
        },
    )
