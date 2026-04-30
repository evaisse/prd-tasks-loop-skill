#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CONTRACTS = {
    "codex": {
        "command": ["npx", "-y", "codex", "exec", "--help"],
        "contains": [
            "codex exec [OPTIONS] [PROMPT]",
            "If not provided as an argument (or if `-` is used)",
            "instructions are read from stdin",
            "--model <MODEL>",
        ],
    },
    "gemini": {
        "command": ["npx", "-y", "@google/gemini-cli", "--help"],
        "contains": [
            "-p, --prompt",
            "Run in non-interactive (headless) mode with the given prompt.",
            "Appended to input on stdin",
        ],
    },
    "opencode": {
        "command": ["npx", "-y", "opencode", "run", "--help"],
        "contains": [
            "opencode run [message..]",
            "message to send",
            "--format",
        ],
    },
}


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for name, contract in CONTRACTS.items():
        result = subprocess.run(
            contract["command"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        ensure(
            result.returncode == 0,
            f"{name} help command failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        output = result.stdout + result.stderr
        for needle in contract["contains"]:
            ensure(
                needle in output,
                f"{name} help output is missing expected text: {needle!r}\noutput:\n{output}",
            )
        print(f"cli contract {name}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
