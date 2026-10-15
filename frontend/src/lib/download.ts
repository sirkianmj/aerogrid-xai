/**
 * Artifact export helpers.
 *
 * A single function builds the JSON envelope every exportable artifact
 * shares, and a second function triggers a client-side download. No
 * round trip through the backend: the frontend already holds the exact
 * payload the user saw, so a download is a serialization and a click.
 *
 * Envelope shape:
 *
 *   {
 *     artifact_kind:    "cleard-loop" | "xai-trace" | ...
 *     artifact_version: 1
 *     exported_at:      ISO-8601 UTC timestamp
 *     epistemic_tag:    one of the seven Section 21 categories
 *     ...extras:        caller-supplied (e.g. mission_config)
 *     payload:          the raw API response
 *   }
 *
 * The mission_config extras field is what makes a CLEAR-D export
 * reproducible: without it, a JSON dump of a run cannot be re-run.
 */

export function downloadJson(filename: string, data: unknown): void {
  const json = JSON.stringify(data, null, 2)
  const blob = new Blob([json], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function exportArtifact(
  artifactKind: string,
  epistemicTag: string,
  payload: unknown,
  extras?: Record<string, unknown>,
): void {
  const now = new Date()
  const fileSafeTimestamp = now
    .toISOString()
    .replace(/[:.]/g, "-")
    .slice(0, 19)
  const filename = `aerogrid-${artifactKind}-${fileSafeTimestamp}.json`
  const body: Record<string, unknown> = {
    artifact_kind: artifactKind,
    artifact_version: 1,
    exported_at: now.toISOString(),
    epistemic_tag: epistemicTag,
    ...(extras ?? {}),
    payload,
  }
  downloadJson(filename, body)
}
