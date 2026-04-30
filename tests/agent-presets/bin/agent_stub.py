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
    argv0 = os.environ.get("PRD_AGENT_STUB_NAME", Path(sys.argv[0]).name)
    stdin_payload = sys.stdin.read()
    if argv0 == "codex":
        prompt = stdin_payload
        prompt_source = "stdin"
    elif argv0 == "gemini":
        if len(sys.argv) < 3 or sys.argv[1] != "-p":
            return fail("gemini stub expected `-p <prompt>`")
        prompt = sys.argv[2]
        prompt_source = "argv"
    elif argv0 == "opencode":
        if len(sys.argv) < 3 or sys.argv[1] != "run":
            return fail("opencode stub expected `run <prompt>`")
        prompt = sys.argv[2]
        prompt_source = "argv"
    else:
        prompt = stdin_payload
        prompt_source = "stdin"

    if not prompt.strip():
        return fail("resolved prompt payload is empty")

    cwd = Path.cwd()
    artifact_dir = cwd / ".agent-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    args_path = artifact_dir / f"{argv0}.args.txt"
    stdin_path = artifact_dir / f"{argv0}.stdin.txt"
    prompt_path = artifact_dir / f"{argv0}.prompt.txt"
    marker_path = artifact_dir / f"{argv0}.json"

    args_path.write_text(" ".join(sys.argv[1:]) + "\n", encoding="utf-8")
    stdin_path.write_text(stdin_payload, encoding="utf-8")
    prompt_path.write_text(prompt, encoding="utf-8")

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
        "- [ ] The preset stub records a non-empty rendered prompt payload",
        "- [x] The preset stub records a non-empty rendered prompt payload",
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
                "prompt_source": prompt_source,
                "stdin_non_empty": bool(stdin_payload.strip()),
                "resolved_prompt_non_empty": bool(prompt.strip()),
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
        [
            "git",
            "commit",
            "-m",
            f"feat(prd): complete US-001 for 2026-04-30-120000-agent-preset-smoke via {argv0} stub",
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
