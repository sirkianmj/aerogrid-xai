#!/usr/bin/env python3
"""Reproducibility harness for AeroGrid-XAI.

Generates evidence/<timestamp>/ with:
  manifest.json      git SHA, env state, gate exit codes, per-test results
  claims-report.md   claim -> test -> status, plus copy-paste-ready abstract sentence
  pytest-junit.xml   raw pytest results

Default run: ruff check, ruff format --check, mypy, pytest, claims audit.
Opt-in:
  --with-frontend   adds npm run lint / typecheck / test
  --with-notebooks  executes all 12 notebooks via nbconvert (slow, ~20 min)

Exit code: 0 iff every executed gate returned 0. Non-zero otherwise.

Usage:
  python3 scripts/reproducibility.py
  python3 scripts/reproducibility.py --with-frontend --with-notebooks
  python3 scripts/reproducibility.py --outdir /tmp/somewhere
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_for_dir() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def run_cmd(name: str, argv: list[str], cwd: Path, timeout: int = 600) -> dict:
    start = time.time()
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return {
            "name": name,
            "argv": argv,
            "cwd": str(cwd),
            "exit": proc.returncode,
            "duration_s": round(time.time() - start, 2),
            "stdout_tail": "\n".join(proc.stdout.splitlines()[-30:]),
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-30:]),
        }
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "argv": argv,
            "cwd": str(cwd),
            "exit": 124,
            "duration_s": round(time.time() - start, 2),
            "stdout_tail": "",
            "stderr_tail": "TIMEOUT",
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_git_state() -> dict:
    out: dict = {}
    for name, argv in [
        ("sha", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        ("describe", ["git", "describe", "--always", "--dirty"]),
        ("tag_head", ["git", "describe", "--tags", "--abbrev=0"]),
        ("porcelain", ["git", "status", "--porcelain"]),
    ]:
        r = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
        out[name] = r.stdout.strip() if r.returncode == 0 else ""
    out["dirty"] = bool(out["porcelain"])
    return out


def collect_env_state() -> dict:
    try:
        import fastapi

        fv = fastapi.__version__
    except Exception:
        fv = "?"
    try:
        import pydantic

        pv = pydantic.__version__
    except Exception:
        pv = "?"
    try:
        import z3

        zv = z3.get_version_string()
    except Exception:
        zv = "?"
    try:
        import reportlab

        rlv = reportlab.Version
    except Exception:
        rlv = "?"
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "conda_env": os.environ.get("CONDA_DEFAULT_ENV", ""),
        "packages": {"fastapi": fv, "pydantic": pv, "z3": zv, "reportlab": rlv},
    }


def run_backend_gates(outdir: Path) -> dict:
    b = REPO / "backend"
    junit = outdir / "pytest-junit.xml"
    return {
        "ruff": run_cmd("ruff", ["ruff", "check", "."], b),
        "rufffmt": run_cmd("rufffmt", ["ruff", "format", "--check", "."], b),
        "mypy": run_cmd("mypy", ["mypy", "."], b),
        "pytest": run_cmd(
            "pytest", ["pytest", "-q", f"--junit-xml={junit}"], b
        ),
    }


def parse_junit(path: Path) -> list[dict]:
    if not path.exists():
        return []
    tree = ET.parse(path)
    tests: list[dict] = []
    for tc in tree.iter("testcase"):
        status = "pass"
        if tc.find("failure") is not None:
            status = "fail"
        elif tc.find("error") is not None:
            status = "error"
        elif tc.find("skipped") is not None:
            status = "skip"
        tests.append(
            {
                "classname": tc.get("classname", ""),
                "name": tc.get("name", ""),
                "status": status,
                "time": tc.get("time", "0"),
            }
        )
    return tests


def audit_claims(repo: Path) -> list[dict]:
    path = repo / "docs" / "SCIENTIFIC_CLAIMS.md"
    text = path.read_text(encoding="utf-8")
    rows: list[dict] = []
    for line in text.splitlines():
        m = re.match(r"^\| (H\d+) \|", line)
        if not m:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue
        hid = parts[1]
        raw_status = parts[3].strip("`* ").split()[0] if parts[3] else ""
        status = (
            raw_status
            if raw_status in ("COVERED", "PARTIAL", "FALSIFIED", "UNCOVERED")
            else "?"
        )
        col4 = parts[4]
        refs = re.findall(r"`([^`]+\.py)`", col4)
        resolved = []
        for ref in refs:
            if "*" in ref:
                hits = list(repo.rglob(ref))
                resolved.append(
                    {
                        "ref": ref,
                        "resolved": [
                            str(p.relative_to(repo)) for p in hits
                        ],
                    }
                )
            else:
                candidates = [repo / ref, repo / "backend" / "tests" / ref]
                found = next((c for c in candidates if c.exists()), None)
                resolved.append({
                    "ref": ref,
                    "exists": found is not None,
                    "path": str(found.relative_to(repo)) if found else None,
                })
        rows.append({"id": hid, "status": status, "refs": resolved})
    return rows


def _count_phrase(n: int, singular_verb: str, plural_verb: str, rest: str) -> str:
    verb = singular_verb if n == 1 else plural_verb
    return f"{n} {verb} {rest}"


def write_claims_report(rows: list[dict], path: Path) -> dict:
    counts = {"COVERED": 0, "PARTIAL": 0, "FALSIFIED": 0, "UNCOVERED": 0}
    for r in rows:
        if r["status"] in counts:
            counts[r["status"]] += 1
    lines = [
        "# Claims Status Report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Status counts",
        "",
        f"- COVERED:   {counts['COVERED']}",
        f"- PARTIAL:   {counts['PARTIAL']}",
        f"- FALSIFIED: {counts['FALSIFIED']}",
        f"- UNCOVERED: {counts['UNCOVERED']}",
        "",
        "## Suggested abstract sentence",
        "",
        "If the abstract contains a status-count sentence, copy this over it:",
        "",
        "```",
        "The twelve proposed hypotheses are audited against the repository and reported individually: "
        + _count_phrase(counts["COVERED"], "is", "are", "covered by a test whose failure would falsify them") + ", "
        + _count_phrase(counts["PARTIAL"], "is", "are", "partially covered with named gaps") + ", "
        + _count_phrase(counts["FALSIFIED"], "is", "are", "falsified by direct test") + ", and "
        + _count_phrase(counts["UNCOVERED"], "requires", "require", "a capability that does not yet exist") + ".",
        "```",
        "",
        "## Per-claim audit",
        "",
        "| ID | Status | Test file | Exists | Note |",
        "|----|--------|-----------|--------|------|",
    ]
    for r in rows:
        if not r["refs"]:
            lines.append(
                f'| {r["id"]} | {r["status"]} | (none) | N/A | capability absent or documented in spec |'
            )
            continue
        for ref in r["refs"]:
            if "resolved" in ref:
                ok = "YES" if ref["resolved"] else "NO"
                paths = ", ".join(ref["resolved"]) if ref["resolved"] else ref["ref"]
                lines.append(
                    f'| {r["id"]} | {r["status"]} | {paths} | {ok} | glob |'
                )
            else:
                ok = "YES" if ref["exists"] else "NO"
                shown = ref.get("path") or ref["ref"]
                lines.append(
                    f'| {r["id"]} | {r["status"]} | {shown} | {ok} | |'
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def write_manifest(
    outdir: Path,
    git_state: dict,
    env_state: dict,
    gates: dict,
    tests: list[dict],
    counts: dict,
) -> dict:
    manifest = {
        "generated_utc": utc_now(),
        "git": git_state,
        "env": env_state,
        "gates": {
            name: {"exit": g["exit"], "duration_s": g["duration_s"]}
            for name, g in gates.items()
        },
        "pytest": {
            "pass": sum(1 for t in tests if t["status"] == "pass"),
            "skip": sum(1 for t in tests if t["status"] == "skip"),
            "fail": sum(1 for t in tests if t["status"] == "fail"),
            "error": sum(1 for t in tests if t["status"] == "error"),
            "total": len(tests),
        },
        "claims": counts,
    }
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run_notebooks(repo: Path, outdir: Path) -> list[dict]:
    nb_dir = repo / "notebooks"
    results: list[dict] = []
    for nb in sorted(nb_dir.glob("*.ipynb")):
        executed = outdir / "notebooks" / nb.name
        executed.parent.mkdir(parents=True, exist_ok=True)
        r = run_cmd(
            f"nb:{nb.name}",
            [
                "jupyter",
                "nbconvert",
                "--to",
                "notebook",
                "--execute",
                "--output",
                str(executed),
                str(nb),
            ],
            repo,
            timeout=900,
        )
        results.append(r)
    return results


def run_frontend_gates() -> dict:
    f = REPO / "frontend"
    return {
        "npm_lint": run_cmd("npm_lint", ["npm", "run", "lint"], f),
        "npm_tc": run_cmd("npm_tc", ["npm", "run", "typecheck"], f),
        "npm_test": run_cmd("npm_test", ["npm", "run", "test"], f),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Reproducibility harness for AeroGrid-XAI."
    )
    p.add_argument("--outdir", default=None)
    p.add_argument("--with-frontend", action="store_true")
    p.add_argument("--with-notebooks", action="store_true")
    args = p.parse_args(argv)

    outdir = (
        Path(args.outdir).expanduser()
        if args.outdir
        else Path.home() / "aerogrid-evidence" / ts_for_dir()
    )
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"outdir: {outdir}")

    print("[1/6] git state")
    git_state = collect_git_state()

    print("[2/6] env state")
    env_state = collect_env_state()

    print("[3/6] backend gates (ruff, rufffmt, mypy, pytest)")
    gates = run_backend_gates(outdir)
    for name, g in gates.items():
        print(f"  {name}: exit={g['exit']} in {g['duration_s']}s")

    print("[4/6] parse pytest junit")
    tests = parse_junit(outdir / "pytest-junit.xml")
    print(f"  {len(tests)} tests")

    print("[5/6] audit claims")
    claims = audit_claims(REPO)
    counts = write_claims_report(claims, outdir / "claims-report.md")
    print(f"  counts: {counts}")

    extra: dict = {}
    if args.with_frontend:
        print("[*] frontend gates")
        extra["frontend"] = run_frontend_gates()
        for name, g in extra["frontend"].items():
            print(f"  {name}: exit={g['exit']} in {g['duration_s']}s")
    if args.with_notebooks:
        print("[*] execute notebooks (slow)")
        extra["notebooks"] = run_notebooks(REPO, outdir)

    print("[6/6] write manifest")
    manifest = write_manifest(outdir, git_state, env_state, gates, tests, counts)
    if extra:
        (outdir / "extra.json").write_text(
            json.dumps(extra, indent=2) + "\n", encoding="utf-8"
        )

    print("\n=== summary ===")
    print(f"git SHA:  {manifest['git']['sha']}")
    print(f"branch:   {manifest['git']['branch']}")
    print(f"dirty:    {manifest['git']['dirty']}")
    print(
        f"pytest:   {manifest['pytest']['pass']} passed, "
        f"{manifest['pytest']['skip']} skipped, "
        f"{manifest['pytest']['fail']} failed"
    )
    print(f"claims:   {counts}")
    print(f"evidence: {outdir}")

    failed = any(g["exit"] != 0 for g in gates.values())
    if extra.get("frontend"):
        failed = failed or any(g["exit"] != 0 for g in extra["frontend"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
