/**
 * Typed client for POST /report/generate.
 *
 * The backend returns application/pdf; this client returns a Blob.
 * The caller is responsible for triggering the download (see
 * downloadPdf below) — keeping the fetch separate from the DOM
 * click makes the client testable in jsdom.
 */

import type { StepOutput } from "../MissionControl/missionContext"

export type ReportRequest = {
  mission_config: Record<string, unknown>
  step_outputs: Record<number, StepOutput>
  mission_state: Record<string, unknown> | null
}

export class ReportApiError extends Error {
  readonly status_code?: number
  constructor(message: string, status_code?: number) {
    super(message)
    this.name = "ReportApiError"
    this.status_code = status_code
  }
}

export async function generateReport(
  req: ReportRequest,
  signal?: AbortSignal,
): Promise<Blob> {
  const r = await fetch("/api/report/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    let detail = `report generation returned HTTP ${r.status}`
    try {
      const body = (await r.json()) as { detail?: unknown }
      if (body && body.detail) detail = String(body.detail)
    } catch {
      /* response is not JSON (unlikely for this endpoint) */
    }
    throw new ReportApiError(detail, r.status)
  }
  return await r.blob()
}

/** Trigger a browser download of a Blob with the given filename. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
