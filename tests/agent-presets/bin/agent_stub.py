#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"missing expected text: {old}")
    return text.replace(old, new, 1)


def main() -> int:
    argv0 = Path(sys.argv[0]).name
    prompt = sys.stdin.read()
    if not prompt.strip():
        return fail("stdin payload is empty")

    cwd = Path.cwd()
    artifact_dir = cwd / ".agent-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    args_path = artifact_dir / f"{argv0}.args.txt"
    stdin_path = artifact_dir / f"{argv0}.stdin.txt"
    marker_path = artifact_dir / f"{argv0}.json"

    args_path.write_text(" ".join(sys.argv[1:]) + "\n", encoding="utf-8")
    stdin_path.write_text(prompt, encoding="utf-8")

    prd_rel = Path("docs/prd/2026-04-30-120000-agent-preset-smoke.md")
    target_rel = Path("project/result.txt")
    prd_path = cwd / prd_rel
    target_path = cwd / target_rel

    prd_text = prd_path.read_text(encoding="utf-8")
    prd_text = replace_once(
        prd_text,
        "- [ ] The preset stub records the expected CLI arguments",
        "- [x] The preset stub records the expected CLI arguments",
    )
    prd_text = replace_once(
        prd_text,
        "- [ ] The preset stub records a non-empty stdin payload",
        "- [x] The preset stub records a non-empty stdin payload",
    )
    prd_text = replace_once(
        prd_text,
        "- [ ] The fixture target file records the invoked agent metadata",
        "- [x] The fixture target file records the invoked agent metadata",
    )
    prd_path.write_text(prd_text, encoding="utf-8")

    target_path.write_text(
        f"agent={argv0}\nargs={' '.join(sys.argv[1:])}\nprompt_contains_story={'US-001' in prompt}\n",
        encoding="utf-8",
    )

    marker_path.write_text(
        json.dumps(
            {
                "agent": argv0,
                "args": sys.argv[1:],
                "stdin_non_empty": bool(prompt.strip()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "add", str(prd_rel), str(target_rel), str(artifact_dir)], check=True
    )
    subprocess.run(
        ["git", "commit", "-m", f"Complete story with {argv0} stub"], check=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
