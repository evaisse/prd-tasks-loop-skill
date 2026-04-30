#!/usr/bin/env python3
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "e2e-real" / "fixture"
SCRIPT_PATH = ROOT / "prd-tasks-loop" / "scripts" / "prd-tasks-loop.py"
PRD_REL = Path("docs/prd/2026-04-30-120500-real-agent-e2e.md")
EXPECTED_RESULT = "STATUS=done\n"

AGENTS = {
    "codex": {
        "command": [
            "npx",
            "-y",
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--yolo",
            "-c",
            'model_provider="openai"',
            "-c",
            'model="gpt-5.4"',
            "-",
        ],
        "env": {
            "OPENAI_API_KEY": "OPENAI_API_KEY",
        },
    },
    "gemini": {
        "command": ["npx", "-y", "@google/gemini-cli", "-p"],
        "env": {
            "OPENAI_API_KEY": "OPENROUTER_API_KEY",
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENAI_MODEL": "OPENROUTER_MODEL",
        },
    },
    "opencode": {
        "command": ["npx", "-y", "opencode", "run"],
        "env": {
            "OPENAI_API_KEY": "OPENROUTER_API_KEY",
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENAI_MODEL": "OPENROUTER_MODEL",
        },
    },
}


def run(
    command: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)


def ensure_command(result: subprocess.CompletedProcess[str], context: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{context}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def ensure(condition: bool, context: str) -> None:
    if not condition:
        raise AssertionError(context)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in AGENTS:
        print(f"usage: {Path(sys.argv[0]).name} <{'|'.join(AGENTS)}>", file=sys.stderr)
        return 2

    agent = sys.argv[1]
    config = AGENTS[agent]

    required_env = {value for value in config["env"].values() if value.isupper()}
    missing_env = [
        name for name in sorted(required_env) if not subprocess.os.environ.get(name, "")
    ]
    if missing_env:
        raise AssertionError(f"missing required env: {', '.join(missing_env)}")

    openrouter_model = subprocess.os.environ.get(
        "OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
    )

    with tempfile.TemporaryDirectory(prefix=f"real-e2e-{agent}-") as tmp:
        workspace = Path(tmp) / "repo"
        shutil.copytree(FIXTURE_ROOT, workspace)

        env = dict(subprocess.os.environ)
        env["PRD_TASKS_LOOP_AUTO_CONFIRM"] = "1"
        env["PRD_TASKS_LOOP_OS"] = "Linux"
        env["OPENROUTER_MODEL"] = openrouter_model

        for target, source in config["env"].items():
            env[target] = subprocess.os.environ.get(source, source)

        ensure_command(run(["git", "init"], workspace, env), "git init failed")
        ensure_command(
            run(["git", "config", "user.name", "CI"], workspace, env),
            "git config user.name failed",
        )
        ensure_command(
            run(["git", "config", "user.email", "ci@example.test"], workspace, env),
            "git config user.email failed",
        )
        ensure_command(run(["git", "add", "."], workspace, env), "git add failed")
        ensure_command(
            run(["git", "commit", "-m", "Initial fixture"], workspace, env),
            "initial commit failed",
        )

        if agent in {"gemini", "opencode"}:
            prompt_bridge = ROOT / "prd-tasks-loop" / "scripts" / "prompt_argv_bridge.py"
            if agent == "gemini":
                agent_parts = [
                    sys.executable,
                    str(prompt_bridge),
                    "replace-last",
                    *config["command"],
                    "__PROMPT__",
                ]
                agent_command = " ".join(
                    shlex.quote(part) for part in agent_parts
                )
            else:
                agent_parts = [
                    sys.executable,
                    str(prompt_bridge),
                    "append",
                    *config["command"],
                ]
                agent_command = " ".join(
                    shlex.quote(part) for part in agent_parts
                )
        else:
            agent_command = " ".join(shlex.quote(part) for part in config["command"])
        result = run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                f"--agent={agent_command}",
                "--retries=1",
                "--timeout=8m",
                str(PRD_REL),
            ],
            workspace,
            env,
        )
        ensure_command(result, f"loop run failed for {agent}")

        result_file = workspace / "project" / "result.txt"
        prd_file = workspace / PRD_REL
        ensure(
            result_file.exists()
            and result_file.read_text(encoding="utf-8") == EXPECTED_RESULT,
            "unexpected result.txt content",
        )

        prd_text = prd_file.read_text(encoding="utf-8")
        for line in (
            "- [x] The file `project/result.txt` exists and contains exactly `STATUS=done`",
            "- [x] The current story acceptance criteria are checked in the PRD",
            "- [x] A Git commit is created for the story",
        ):
            if line not in prd_text:
                raise AssertionError(f"missing checked acceptance line: {line}")

        commit_count = run(["git", "rev-list", "--count", "HEAD"], workspace, env)
        ensure_command(commit_count, "commit count failed")
        if commit_count.stdout.strip() != "2":
            raise AssertionError(
                f"expected 2 commits, got {commit_count.stdout.strip()}"
            )

        for suffix in ("json.log", "progress.log"):
            runtime_log = (
                workspace
                / "docs"
                / "prd"
                / f"2026-04-30-120500-real-agent-e2e.{suffix}"
            )
            if runtime_log.exists():
                raise AssertionError(f"runtime log should be cleaned: {runtime_log}")

        print(f"real e2e {agent}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
