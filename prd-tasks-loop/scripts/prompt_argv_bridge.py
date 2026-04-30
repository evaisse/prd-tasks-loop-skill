#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(
            "usage: prompt_argv_bridge.py <append|replace-last> <command> [args...]",
            file=sys.stderr,
        )
        return 2

    mode = args[0]
    command = args[1:]
    prompt = sys.stdin.read()

    if mode == "append":
        resolved = [*command, prompt]
    elif mode == "replace-last":
        if not command or command[-1] != "__PROMPT__":
            print(
                "replace-last mode requires the last argument to be __PROMPT__",
                file=sys.stderr,
            )
            return 2
        resolved = [*command[:-1], prompt]
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2

    return subprocess.run(resolved).returncode


if __name__ == "__main__":
    raise SystemExit(main())
