#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "agent-presets" / "fixture"
SCRIPT_PATH = ROOT / "prd-tasks-loop" / "scripts" / "prd-tasks-loop.py"
BIN_DIR = ROOT / "tests" / "agent-presets" / "bin"
PRD_REL = Path("docs/prd/2026-04-30-120000-agent-preset-smoke.md")

EXPECTED = {
    "codex": {
        "args": ["exec", "--skip-git-repo-check", "--yolo", "-"],
        "prompt_source": "stdin",
    },
    "gemini": {
        "args_prefix": ["-p"],
        "prompt_source": "argv",
    },
    "opencode": {
        "args_prefix": ["run"],
        "prompt_source": "argv",
    },
}


def run(
    command: list[str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def install_stub(wrapper_name: str, workspace_bin: Path) -> None:
    wrapper = workspace_bin / wrapper_name
    wrapper.write_text(
        f'#!/usr/bin/env sh\nPRD_AGENT_STUB_NAME="{wrapper_name}" "{sys.executable}" "{BIN_DIR / "agent_stub.py"}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EXPECTED:
        print(
            f"usage: {Path(sys.argv[0]).name} <{'|'.join(EXPECTED)}>", file=sys.stderr
        )
        return 2

    agent = sys.argv[1]
    expected = EXPECTED[agent]

    with tempfile.TemporaryDirectory(prefix=f"preset-{agent}-") as tmp:
        workspace = Path(tmp) / "repo"
        shutil.copytree(FIXTURE_ROOT, workspace)
        workspace_bin = workspace / ".bin"
        workspace_bin.mkdir()
        install_stub(agent, workspace_bin)

        base_env = dict(os_env for os_env in [])
        env = dict(**subprocess.os.environ)
        env["PATH"] = f"{workspace_bin}:{env.get('PATH', '')}"
        env["PRD_TASKS_LOOP_AUTO_CONFIRM"] = "1"
        env["PRD_TASKS_LOOP_OS"] = "Linux"

        run(["git", "init"], workspace, env)
        run(["git", "config", "user.name", "CI"], workspace, env)
        run(["git", "config", "user.email", "ci@example.test"], workspace, env)
        run(["git", "add", "."], workspace, env)
        initial_commit = run(["git", "commit", "-m", "Initial fixture"], workspace, env)
        ensure(
            initial_commit.returncode == 0,
            initial_commit.stdout + initial_commit.stderr,
        )

        result = run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                f"--agent={agent}",
                "--retries=1",
                "--timeout=30s",
                str(PRD_REL),
            ],
            workspace,
            env,
        )
        ensure(result.returncode == 0, result.stdout + result.stderr)

        artifact_dir = workspace / ".agent-artifacts"
        args_file = artifact_dir / f"{agent}.args.txt"
        stdin_file = artifact_dir / f"{agent}.stdin.txt"
        prompt_file = artifact_dir / f"{agent}.prompt.txt"
        json_file = artifact_dir / f"{agent}.json"
        result_file = workspace / "project" / "result.txt"
        prd_file = workspace / PRD_REL

        ensure(args_file.exists(), f"missing args file for {agent}")
        ensure(stdin_file.exists(), f"missing stdin file for {agent}")
        ensure(prompt_file.exists(), f"missing resolved prompt file for {agent}")
        ensure(json_file.exists(), f"missing json marker for {agent}")

        marker = json.loads(json_file.read_text(encoding="utf-8"))
        actual_args = marker["args"]
        if "args" in expected:
            ensure(
                actual_args == expected["args"],
                f"unexpected args for {agent}: {actual_args} != {expected['args']}",
            )
        else:
            prefix = expected["args_prefix"]
            ensure(
                actual_args[: len(prefix)] == prefix,
                f"unexpected args prefix for {agent}: {actual_args}",
            )

        prompt_payload = prompt_file.read_text(encoding="utf-8")
        ensure(
            "Target story: US-001: Validate preset agent invocation" in prompt_payload,
            "resolved prompt missing target story",
        )
        ensure(
            "Acceptance criteria:" in prompt_payload,
            "resolved prompt missing acceptance criteria",
        )

        ensure(
            marker["prompt_source"] == expected["prompt_source"],
            f"unexpected prompt source for {agent}: {marker['prompt_source']}",
        )
        ensure(
            marker["resolved_prompt_non_empty"] is True,
            "resolved prompt should be non-empty",
        )
        if expected["prompt_source"] == "stdin":
            ensure(marker["stdin_non_empty"] is True, "stdin should be non-empty")
        else:
            ensure(marker["stdin_non_empty"] is False, "stdin should be empty")

        result_text = result_file.read_text(encoding="utf-8")
        ensure(f"agent={agent}" in result_text, "result file missing agent marker")
        ensure(
            "prompt_contains_story=True" in result_text,
            "result file missing prompt marker",
        )

        prd_text = prd_file.read_text(encoding="utf-8")
        ensure(
            "- [x] The preset stub records the expected CLI arguments" in prd_text,
            "PRD checkbox 1 not checked",
        )
        ensure(
            "- [x] The preset stub records a non-empty rendered prompt payload" in prd_text,
            "PRD checkbox 2 not checked",
        )
        ensure(
            "- [x] The fixture target file records the invoked agent metadata"
            in prd_text,
            "PRD checkbox 3 not checked",
        )

        commit_count = run(["git", "rev-list", "--count", "HEAD"], workspace, env)
        ensure(commit_count.returncode == 0, commit_count.stdout + commit_count.stderr)
        ensure(
            commit_count.stdout.strip() == "2",
            f"expected 2 commits, got {commit_count.stdout.strip()}",
        )

        for suffix in ("json.log", "progress.log"):
            ensure(
                not (
                    workspace
                    / "docs"
                    / "prd"
                    / f"2026-04-30-120000-agent-preset-smoke.{suffix}"
                ).exists(),
                f"runtime log should be cleaned: {suffix}",
            )

        print(f"preset {agent}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
