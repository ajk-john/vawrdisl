#!/usr/bin/env python3
"""Fetch and verify GitHub Actions build artifacts for ToolShear into local builds/."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDS_DIR = ROOT / "builds"
DEFAULT_GH_CANDIDATES = [
    shutil.which("gh"),
    r"C:\Users\13160\bin\gh.exe",
    r"C:\Program Files\GitHub CLI\gh.exe",
]


def find_gh() -> str:
    for cand in DEFAULT_GH_CANDIDATES:
        if cand and Path(cand).is_file():
            return cand
    raise SystemExit("error: gh CLI not found in PATH or standard Windows locations")


def get_origin_slug() -> str:
    url = subprocess.check_output(
        ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
    if not m:
        raise SystemExit(f"error: cannot parse GitHub owner/repo from origin URL: {url!r}")
    return m.group(1)


def run_gh(gh: str, args: list[str], capture: bool = True) -> str:
    res = subprocess.run(
        [gh, *args],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=True,
    )
    return res.stdout if capture else ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch ToolShear CI artifacts into builds/")
    parser.add_argument("--limit", type=int, default=5, help="number of recent runs to inspect (default: 5)")
    parser.add_argument("--run-id", type=int, help="specific GitHub Actions run ID to download")
    parser.add_argument("--force", action="store_true", help="re-download even if directory already exists")
    parser.add_argument("--no-debug", action="store_true", help="skip downloading toolshear-debug artifact")
    args = parser.parse_args(argv)

    gh = find_gh()
    slug = get_origin_slug()

    if args.run_id:
        raw = run_gh(gh, ["api", f"repos/{slug}/actions/runs/{args.run_id}"])
        runs = [json.loads(raw)]
    else:
        raw = run_gh(
            gh,
            [
                "run",
                "list",
                "--repo",
                slug,
                "--workflow",
                "build.yml",
                "--limit",
                str(args.limit),
                "--json",
                "databaseId,number,headBranch,headSha,status,conclusion,createdAt,event,url",
            ],
        )
        runs = json.loads(raw)

    if not runs:
        print("No workflow runs found.")
        return 0

    BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded_dirs: list[Path] = []

    for run in runs:
        run_id = run.get("databaseId") or run.get("id")
        number = run.get("number") or run.get("run_number")
        branch = (run.get("headBranch") or run.get("head_branch") or "unknown").replace("/", "_")
        sha7 = (run.get("headSha") or run.get("head_sha") or "0000000")[:7]
        status = run.get("status")
        conclusion = run.get("conclusion") or "pending"

        if status != "completed":
            print(f"Skipping run #{number} (id={run_id}): status={status}")
            continue

        dest = BUILDS_DIR / f"{number:03d}-{branch}-{sha7}-{conclusion}"
        if dest.exists() and not args.force:
            print(f"Already fetched: {dest.relative_to(ROOT).as_posix()}")
            continue

        dest.mkdir(parents=True, exist_ok=True)
        for art in (["toolshear-release"] + ([] if args.no_debug else ["toolshear-debug"])):
            art_dir = dest / art
            if art_dir.exists() and args.force:
                shutil.rmtree(art_dir)
            print(f"Downloading {art} from run #{number} (id={run_id})...")
            res = subprocess.run(
                [gh, "run", "download", str(run_id), "--repo", slug, "-n", art, "-D", str(art_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            if res.returncode != 0:
                print(f"warning: failed to download {art}: {res.stderr.strip()}", file=sys.stderr)

        apks = sorted(dest.glob("toolshear-release/*.apk"))
        if apks and conclusion == "success":
            print(f"Verifying {len(apks)} release APK(s) with diy/toolshear_diy.py check --apk ...")
            subprocess.run(
                [sys.executable, str(ROOT / "diy" / "toolshear_diy.py"), "check", "--apk", *(str(p) for p in apks)],
                cwd=ROOT,
                check=True,
            )
            checksums = [f"{sha256_file(p)}  {p.name}" for p in apks]
            with open(dest / "SHA256SUMS.local.txt", "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(checksums) + "\n")
            for line in checksums:
                print(f"  {line}")

        downloaded_dirs.append(dest)

    # Rebuild builds/INDEX.md
    index_lines = ["# ToolShear Local Builds Index", ""]
    for d in sorted(BUILDS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        apks = sorted(d.glob("toolshear-release/*.apk"))
        index_lines.append(f"## {d.name}")
        for apk in apks:
            index_lines.append(f"- `{apk.name}` — sha256 `{sha256_file(apk)}`")
        if not apks:
            index_lines.append("- (no release APKs)")
        index_lines.append("")
    with open(BUILDS_DIR / "INDEX.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(index_lines))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
