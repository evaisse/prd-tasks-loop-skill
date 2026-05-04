#!/usr/bin/env python3
"""prd-tasks-loop
Copyright (c) 2026
Inspired by the original Ralph loop from snarktank/ralph:
https://github.com/snarktank/ralph

This implementation is a simplified Python runner focused on canonical PRDs,
visible state logs, positional PRD arguments, retry backoff, and automatic
macOS caffeinate support.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
PROMPT_TEMPLATE_PATH = SKILL_ROOT / "references" / "PROMPT_TEMPLATE.md"
PROMPT_AGENT_NOTES_PATH = SKILL_ROOT / "references" / "PROMPT_AGENT_NOTES.md"
PROMPT_ARGV_BRIDGE_PATH = SKILL_ROOT / "scripts" / "prompt_argv_bridge.py"
DEFAULT_PRD_DIR = Path.cwd() / "docs" / "prd"

DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT_RAW = "2h"
DEFAULT_AGENT_COMMAND = "codex exec --skip-git-repo-check --yolo -"
DEFAULT_BACKOFF_BASE_SECONDS = 1.0
DEFAULT_BACKOFF_MAX_SECONDS = 30.0
CONVENTIONAL_COMMIT_RE = re.compile(r"^[a-z]+(?:\([a-z0-9-]+\))?!?: .+")

FILENAME_RE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}-[a-z0-9][a-z0-9-]*$")
PRD_TITLE_RE = re.compile(r"^#\s+PRD:\s*(.+?)\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
STORY_RE = re.compile(r"^###\s+(US-\d+):\s*(.+?)\s*$", re.MULTILINE)

REQUIRED_SECTIONS = (
    "Introduction/Overview",
    "Goals",
    "User Stories",
    "Functional Requirements",
    "Non-Goals",
    "Success Metrics",
    "Open Questions",
)


@dataclass
class Story:
    story_id: str
    title: str
    description: str
    acceptance: list[str]
    tdd_test: str
    tdd_implementation: str
    dependencies: list[str]
    parallel_group: str


@dataclass
class PrdData:
    path: Path
    prd_id: str
    title: str
    execution: dict
    stories: list[Story]
    errors: list[str]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fail(message: str) -> NoReturn:
    raise SystemExit(f"Error: {message}")


def status_line(message: str) -> None:
    print(f"{iso_now()} {message}")


def debug(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[debug] {message}", file=sys.stderr)


def parse_duration_to_seconds(raw: str) -> int:
    match = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", raw.strip())
    if not match or not any(match.groups()):
        raise ValueError(raw)
    days, hours, minutes, seconds = (int(value or 0) for value in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def discover_prds() -> list[Path]:
    if not DEFAULT_PRD_DIR.is_dir():
        return []
    return sorted(
        path
        for path in DEFAULT_PRD_DIR.glob("*.md")
        if FILENAME_RE.fullmatch(path.stem)
    )


def resolve_prd_list(values: list[str]) -> list[Path]:
    if not values:
        return discover_prds()
    resolved: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        path = Path(value).expanduser().resolve()
        if path in seen:
            continue
        resolved.append(path)
        seen.add(path)
    return resolved


def parse_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip("\n")
    return sections


def parse_execution_settings(section_text: str) -> dict:
    execution = {
        "agent_command": "",
        "test_command": "",
        "quality_gates": [],
    }
    if not section_text:
        return execution

    agent_match = re.search(r"^Agent Command:\s*(.+?)\s*$", section_text, re.MULTILINE)
    test_match = re.search(r"^Test Command:\s*(.+?)\s*$", section_text, re.MULTILINE)
    if agent_match:
        execution["agent_command"] = agent_match.group(1).strip()
    if test_match:
        execution["test_command"] = test_match.group(1).strip()

    capture = False
    gates: list[str] = []
    for line in section_text.splitlines():
        if line.strip() == "Quality Gates:":
            capture = True
            continue
        if capture:
            bullet = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if bullet:
                gates.append(bullet.group(1).strip())
            elif line.strip():
                capture = False
    execution["quality_gates"] = gates
    return execution


def parse_story(body: str, story_id: str, story_title: str, errors: list[str]) -> Story:
    desc_match = re.search(r"(?ms)^\*\*Description:\*\*\s*(.+?)(?:\n\s*\n|\n\*\*|\Z)", body)
    description = desc_match.group(1).strip() if desc_match else ""
    if not description:
        errors.append(f"{story_id} is missing `**Description:**`.")

    acceptance_match = re.search(r"(?ms)^\*\*Acceptance Criteria:\*\*\s*(.+?)(?:\n\s*\n\*\*|\Z)", body)
    acceptance_block = acceptance_match.group(1).strip() if acceptance_match else ""
    acceptance = [line.strip() for line in acceptance_block.splitlines() if re.match(r"^\s*-\s+\[[ xX]\]\s+", line)]
    if not acceptance:
        errors.append(f"{story_id} must define at least one acceptance criterion checkbox.")

    tdd_match = re.search(r"(?ms)^\*\*TDD Plan:\*\*\s*(.+?)(?:\n\s*\n\*\*|\Z)", body)
    tdd_block = tdd_match.group(1).strip() if tdd_match else ""
    test_match = re.search(r"^\s*-\s*Test:\s*(.+?)\s*$", tdd_block, re.MULTILINE)
    impl_match = re.search(r"^\s*-\s*Implementation:\s*(.+?)\s*$", tdd_block, re.MULTILINE)
    if not test_match:
        errors.append(f"{story_id} is missing `- Test:` in `**TDD Plan:**`.")
    if not impl_match:
        errors.append(f"{story_id} is missing `- Implementation:` in `**TDD Plan:**`.")

    deps_match = re.search(r"^\*\*Dependencies:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    deps_raw = deps_match.group(1).strip() if deps_match else ""
    if not deps_raw:
        errors.append(f"{story_id} is missing `**Dependencies:**`.")
    dependencies = [] if deps_raw in {"", "-"} else [item.strip() for item in deps_raw.split(",") if item.strip()]

    parallel_match = re.search(r"^\*\*Parallel Group:\*\*\s*(.+?)\s*$", body, re.MULTILINE)
    parallel_group = parallel_match.group(1).strip() if parallel_match else ""
    if not parallel_group:
        errors.append(f"{story_id} is missing `**Parallel Group:**`.")

    return Story(
        story_id=story_id,
        title=story_title,
        description=description,
        acceptance=acceptance,
        tdd_test=test_match.group(1).strip() if test_match else "",
        tdd_implementation=impl_match.group(1).strip() if impl_match else "",
        dependencies=dependencies,
        parallel_group=parallel_group,
    )


def parse_prd(path: Path) -> PrdData:
    text = path.read_text()
    errors: list[str] = []

    if not FILENAME_RE.fullmatch(path.stem):
        errors.append(f"Invalid PRD filename `{path.name}`. Expected `YYYY-MM-DD-HHMMSS-<slug>.md`.")

    title_match = PRD_TITLE_RE.search(text)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        errors.append("Missing required heading `# PRD: <title>`.")

    sections = parse_sections(text)
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            errors.append(f"Missing required section `## {section}`.")

    stories: list[Story] = []
    story_ids: set[str] = set()
    stories_text = sections.get("User Stories", "")
    story_matches = list(STORY_RE.finditer(stories_text))
    if not story_matches:
        errors.append("Missing at least one user story under `## User Stories`.")

    for index, match in enumerate(story_matches):
        story_id = match.group(1).strip()
        story_title = match.group(2).strip()
        start = match.end()
        end = story_matches[index + 1].start() if index + 1 < len(story_matches) else len(stories_text)
        body = stories_text[start:end].strip()
        if story_id in story_ids:
            errors.append(f"Duplicate story id `{story_id}`.")
        story_ids.add(story_id)
        stories.append(parse_story(body, story_id, story_title, errors))

    execution = parse_execution_settings(sections.get("Execution Settings", ""))
    return PrdData(
        path=path.resolve(),
        prd_id=path.stem,
        title=title,
        execution=execution,
        stories=stories,
        errors=errors,
    )


def state_path_for(prd_path: Path) -> Path:
    return prd_path.with_suffix(".json.log")


def progress_path_for(prd_path: Path) -> Path:
    return prd_path.with_suffix(".progress.log")


def append_progress(progress_path: Path, message: str) -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{iso_now()} {message}\n")


def load_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text())


def write_state(state_path: Path, state: dict) -> None:
    state["updated_at"] = iso_now()
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def ensure_state(prd: PrdData, retries: int, timeout_raw: str, agent_command: str) -> tuple[Path, Path]:
    state_path = state_path_for(prd.path)
    progress_path = progress_path_for(prd.path)
    if not state_path.exists():
        now = iso_now()
        state = {
            "formatVersion": 1,
            "prd_path": str(prd.path),
            "prd_id": prd.prd_id,
            "title": prd.title,
            "status": "open",
            "active_story_id": None,
            "active_story_title": None,
            "retry_count": 0,
            "max_retries": retries,
            "timeout": timeout_raw,
            "selected_agent": agent_command,
            "created_at": now,
            "updated_at": now,
            "completed_story_ids": completed_story_ids_from_prd(prd),
            "failed_story_id": None,
            "last_error": None,
            "attempts": [],
        }
        write_state(state_path, state)
        progress_path.touch()
        append_progress(progress_path, f"initialized runtime state for {prd.path.name}")
    else:
        state = load_state(state_path)
        synced_state = sync_state_with_prd(prd, state)
        if synced_state != state:
            write_state(state_path, synced_state)
            append_progress(progress_path, f"synchronized runtime state from {prd.path.name}")
    return state_path, progress_path


def recent_progress_block(progress_path: Path) -> str:
    if not progress_path.exists():
        return "- No progress log yet."
    lines = progress_path.read_text().splitlines()
    tail = lines[-12:]
    if not tail:
        return "- No progress log yet."
    return "\n".join(f"- {line}" for line in tail)


def agent_notes_block(preset: str) -> str:
    text = PROMPT_AGENT_NOTES_PATH.read_text()
    heading_map = {
        "codex": "Codex",
        "amp": "Amp",
        "claude-code": "Claude Code",
        "gemini": "Gemini",
        "opencode": "OpenCode",
        "custom": "Custom",
    }
    heading = heading_map.get(preset, "Custom")
    match = re.search(rf"(?ms)^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text)
    return match.group(1).strip() if match else "Use exit status to signal success or failure."


def render_prompt(
    prd: PrdData,
    story: Story,
    state_path: Path,
    progress_path: Path,
    agent_command: str,
    preset: str,
) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text()
    replacements = {
        "{{PRD_PATH}}": str(prd.path),
        "{{STATE_PATH}}": str(state_path),
        "{{PROGRESS_PATH}}": str(progress_path),
        "{{PRD_ID}}": prd.prd_id,
        "{{STORY_ID}}": story.story_id,
        "{{STORY_TITLE}}": story.title,
        "{{DESCRIPTION}}": story.description,
        "{{ACCEPTANCE}}": "\n".join(story.acceptance),
        "{{TDD_TEST}}": story.tdd_test,
        "{{TDD_IMPLEMENTATION}}": story.tdd_implementation,
        "{{AGENT_COMMAND}}": agent_command,
        "{{TEST_COMMAND}}": prd.execution["test_command"] or "(none)",
        "{{QUALITY_GATES}}": "\n".join(f"- {gate}" for gate in prd.execution["quality_gates"]) or "- (none)",
        "{{RECENT_PROGRESS}}": recent_progress_block(progress_path),
        "{{AGENT_NOTES}}": agent_notes_block(preset),
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def choose_agent_command(args: argparse.Namespace) -> tuple[str, str]:
    value = args.agent.strip()
    bridge = shlex.quote(str(PROMPT_ARGV_BRIDGE_PATH))
    python_exec = shlex.quote(sys.executable)
    preset_map = {
        "codex": ("codex", "codex exec --skip-git-repo-check --yolo -"),
        "amp": ("amp", "amp -p -"),
        "claude-code": ("claude-code", "claude -p"),
        "gemini": (
            "gemini",
            f"{python_exec} {bridge} replace-last gemini -p __PROMPT__",
        ),
        "opencode": (
            "opencode",
            f"{python_exec} {bridge} append opencode run",
        ),
    }
    return preset_map.get(value, ("custom", value))


def maybe_wrap_with_caffeinate(args: argparse.Namespace) -> None:
    if os.environ.get("PRD_TASKS_LOOP_CAFFEINATE_WRAPPED") == "1":
        return
    os_name = os.environ.get("PRD_TASKS_LOOP_OS", os.uname().sysname)
    if os_name != "Darwin":
        return
    if shutil.which("caffeinate") is None:
        return
    debug(args.verbose, "relaunching under caffeinate")
    env = os.environ.copy()
    env["PRD_TASKS_LOOP_CAFFEINATE_WRAPPED"] = "1"
    os.execvpe("caffeinate", ["caffeinate", "-dimsu", sys.executable, str(SCRIPT_PATH), *sys.argv[1:]], env)


def run_agent_command(command: str, prompt: str, timeout_seconds: int) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return completed.returncode, completed.stdout + completed.stderr
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return 124, f"{stdout}{stderr}\n[runner] timeout exceeded\n"


def git_repo_root(cwd: Path) -> Path | None:
    if shutil.which("git") is None:
        return None
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0:
        return None
    return Path(probe.stdout.strip())


def git_head_commit(cwd: Path) -> str | None:
    repo_root = git_repo_root(cwd)
    if repo_root is None:
        return None
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    return head.stdout.strip() if head.returncode == 0 else None


def git_commit_subject(cwd: Path, revision: str = "HEAD") -> str | None:
    repo_root = git_repo_root(cwd)
    if repo_root is None:
        return None
    subject = subprocess.run(
        ["git", "log", "-1", "--pretty=%s", revision],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    return subject.stdout.strip() if subject.returncode == 0 else None


def git_worktree_clean(cwd: Path, ignored_paths: list[Path] | None = None) -> bool | None:
    repo_root = git_repo_root(cwd)
    if repo_root is None:
        return None
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if status.returncode != 0:
        return None
    ignored = {str(path.resolve()) for path in (ignored_paths or [])}
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        relative = line[3:].strip()
        candidate = (repo_root / relative).resolve()
        if str(candidate) in ignored:
            continue
        return False
    return True


def git_current_branch(cwd: Path) -> str | None:
    repo_root = git_repo_root(cwd)
    if repo_root is None:
        return None
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if branch.returncode != 0:
        return None
    value = branch.stdout.strip()
    return value or None


def git_checkout_branch(cwd: Path, branch_name: str) -> None:
    repo_root = git_repo_root(cwd)
    if repo_root is None:
        fail("--branch requires a Git repository.")
    checkout = subprocess.run(
        ["git", "checkout", branch_name],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if checkout.returncode != 0:
        stderr = checkout.stderr.strip() or checkout.stdout.strip() or "git checkout failed"
        fail(f"Unable to checkout branch `{branch_name}`: {stderr}")


def cleanup_runtime_files(prd: PrdData) -> None:
    for path in (state_path_for(prd.path), progress_path_for(prd.path)):
        if path.exists():
            path.unlink()


def prompt_run_confirmation(args: argparse.Namespace, prd_paths: list[Path]) -> None:
    if os.environ.get("PRD_TASKS_LOOP_AUTO_CONFIRM") == "1":
        return

    repo_root = git_repo_root(Path.cwd())
    print("About to start PRD loop:")
    if repo_root is None:
        if args.branch:
            fail("--branch requires a Git repository.")
        print("- Workspace is not inside a Git repository.")
        print("- The loop will run without branch management or commit verification.")
    else:
        current_branch = git_current_branch(repo_root) or "(detached HEAD)"
        target_branch = args.branch or current_branch
        print(f"- Git repository: {repo_root}")
        print(f"- Current branch: {current_branch}")
        print(f"- Target branch: {target_branch}")
    print(f"- Agent: {args.agent}")
    print(f"- Retries: {args.retries}")
    print(f"- Timeout: {args.timeout}")
    print(f"- PRDs to execute: {len(prd_paths)}")
    for index, prd_path in enumerate(prd_paths, start=1):
        print(f"  {index}. {prd_path}")

    prompt = "Continue outside a Git repository? [y/N]: " if repo_root is None else "Continue and start the loop? [y/N]: "
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        fail("Confirmation required to start the loop.")
    if answer not in {"y", "yes"}:
        fail("Loop aborted by user.")

    if repo_root is not None and args.branch:
        current_branch = git_current_branch(repo_root)
        if current_branch != args.branch:
            git_checkout_branch(repo_root, args.branch)


def select_next_story(prd: PrdData, state: dict) -> Story | None:
    completed = set(state.get("completed_story_ids", []))
    if len(completed) == len(prd.stories):
        return None
    for story in prd.stories:
        if story.story_id in completed:
            continue
        if all(dep in completed for dep in story.dependencies):
            return story
    raise RuntimeError("Blocked by unresolved dependencies")


def record_attempt(state: dict, story_id: str, attempt: int, exit_code: int, result: str, output: str) -> None:
    state.setdefault("attempts", []).append(
        {
            "story_id": story_id,
            "attempt": attempt,
            "exit_code": exit_code,
            "result": result,
            "finished_at": iso_now(),
            "output_excerpt": output[-4000:],
        }
    )


def compute_backoff_seconds(attempt_index: int) -> float:
    scale = float(os.environ.get("PRD_TASKS_LOOP_BACKOFF_SCALE", "1"))
    raw = min(DEFAULT_BACKOFF_BASE_SECONDS * (2 ** max(attempt_index - 1, 0)), DEFAULT_BACKOFF_MAX_SECONDS)
    return raw * scale


def extract_story_block(text: str, story_id: str) -> str:
    matches = list(STORY_RE.finditer(text))
    for index, match in enumerate(matches):
        current_id = match.group(1).strip()
        if current_id != story_id:
            continue
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end]
    return ""


def story_checkbox_counts(text: str, story_id: str) -> tuple[int, int]:
    block = extract_story_block(text, story_id)
    if not block:
        return 0, 0
    total = 0
    checked = 0
    for line in block.splitlines():
        match = re.match(r"^\s*-\s+\[([ xX])\]\s+", line)
        if not match:
            continue
        total += 1
        if match.group(1).lower() == "x":
            checked += 1
    return total, checked


def completed_story_ids_from_prd(prd: PrdData) -> list[str]:
    text = prd.path.read_text()
    completed: list[str] = []
    for story in prd.stories:
        total, checked = story_checkbox_counts(text, story.story_id)
        if total > 0 and checked == total:
            completed.append(story.story_id)
    return completed


def sync_state_with_prd(prd: PrdData, state: dict) -> dict:
    synced = dict(state)
    completed = list(
        dict.fromkeys(
            [
                *synced.get("completed_story_ids", []),
                *completed_story_ids_from_prd(prd),
            ]
        )
    )
    synced["completed_story_ids"] = completed
    if synced.get("active_story_id") in completed:
        synced["active_story_id"] = None
        synced["active_story_title"] = None
        synced["retry_count"] = 0
        synced["failed_story_id"] = None
        synced["last_error"] = None
        if synced.get("status") == "running":
            synced["status"] = "open"
    return synced


def verify_story_progress(prd_path: Path, before_text: str, story_id: str) -> str | None:
    after_text = prd_path.read_text()
    if after_text == before_text:
        return "PRD file was not updated."
    before_total, before_checked = story_checkbox_counts(before_text, story_id)
    after_total, after_checked = story_checkbox_counts(after_text, story_id)
    if before_total == 0 or after_total == 0:
        return "Current story does not expose markdown checkbox acceptance criteria."
    if after_checked <= before_checked:
        return "Current story checkboxes were not advanced."
    return None


def verify_story_commit_subject(repo_root: Path, prd: PrdData, story: Story, revision: str) -> str | None:
    subject = git_commit_subject(repo_root, revision)
    if not subject:
        return "The story commit message is missing."
    if not CONVENTIONAL_COMMIT_RE.match(subject):
        return "The story commit message must use the Conventional Commits subject format."
    if story.story_id not in subject:
        return f"The story commit message must include `{story.story_id}`."
    if prd.prd_id not in subject:
        return f"The story commit message must include `{prd.prd_id}`."
    return None


def start_status_message(story_id: str, attempt: int, retries: int) -> str:
    if attempt == 1:
        return f"{story_id} running"
    return f"{story_id} retry {attempt}/{retries}"


def success_status_message(story_id: str, attempt: int, retries: int) -> str:
    if attempt == 1:
        return f"{story_id} passed"
    return f"{story_id} passed ({attempt}/{retries})"


def failure_status_message(story_id: str, attempt: int, retries: int, exit_code: int) -> str:
    if attempt == 1:
        return f"{story_id} failed (exit {exit_code})"
    return f"{story_id} failed ({attempt}/{retries}, exit {exit_code})"


def run_one_prd(
    args: argparse.Namespace,
    prd: PrdData,
    preset: str,
    agent_command: str,
    timeout_seconds: int,
    index: int,
    total: int,
) -> bool:
    status_line(f"{index}/{total} {prd.path.name}")
    if prd.errors:
        status_line(f"PRD validation failed: {prd.path}")
        for error in prd.errors:
            print(f"  - {error}")
        return False

    if prd.execution["agent_command"] and args.agent == DEFAULT_AGENT_COMMAND:
        agent_command = prd.execution["agent_command"]
    elif prd.execution["agent_command"] and args.agent == "codex":
        agent_command = prd.execution["agent_command"]
    prd.execution["agent_command"] = agent_command

    state_path, progress_path = ensure_state(prd, args.retries, args.timeout, agent_command)
    append_progress(progress_path, f"validated {prd.path.name}")

    while True:
        state = sync_state_with_prd(prd, load_state(state_path))
        write_state(state_path, state)
        try:
            story = select_next_story(prd, state)
        except RuntimeError as exc:
            state["status"] = "failed"
            state["last_error"] = str(exc)
            write_state(state_path, state)
            append_progress(progress_path, "failed because remaining stories are blocked by dependencies")
            status_line(f"Blocked by dependencies: {prd.path}")
            return False

        if story is None:
            state["status"] = "completed"
            state["active_story_id"] = None
            state["active_story_title"] = None
            state["retry_count"] = 0
            write_state(state_path, state)
            append_progress(progress_path, f"completed all stories for {prd.path.name}")
            status_line(f"Completed: {prd.path}")
            cleanup_runtime_files(prd)
            return True

        for attempt in range(1, args.retries + 1):
            before_prd_text = prd.path.read_text()
            repo_root = prd.path.parent.parent.parent
            before_head = git_head_commit(repo_root)
            state = load_state(state_path)
            state["status"] = "running"
            state["active_story_id"] = story.story_id
            state["active_story_title"] = story.title
            state["retry_count"] = attempt - 1
            state["failed_story_id"] = None
            state["last_error"] = None
            write_state(state_path, state)
            before_clean = git_worktree_clean(
                prd.path.parent.parent.parent,
                ignored_paths=[state_path, progress_path],
            )
            append_progress(progress_path, f"starting {story.story_id} attempt {attempt}/{args.retries} with command: {agent_command}")
            status_line(start_status_message(story.story_id, attempt, args.retries))

            prompt = render_prompt(prd, story, state_path, progress_path, agent_command, preset)
            exit_code, output = run_agent_command(agent_command, prompt, timeout_seconds)
            if args.verbose and output:
                print(output, end="" if output.endswith("\n") else "\n")

            if exit_code == 0:
                verification_error = verify_story_progress(prd.path, before_prd_text, story.story_id)
                if verification_error is not None:
                    exit_code = 65
                    output = f"{output}\n[runner] verification failed: {verification_error}\n"
            if exit_code == 0 and before_head is not None and before_clean is True:
                after_head = git_head_commit(repo_root)
                if after_head == before_head:
                    exit_code = 66
                    output = f"{output}\n[runner] verification failed: no new git commit was created for this story.\n"
                else:
                    commit_error = verify_story_commit_subject(repo_root, prd, story, after_head)
                    if commit_error is not None:
                        exit_code = 67
                        output = f"{output}\n[runner] verification failed: {commit_error}\n"

            state = load_state(state_path)
            if exit_code == 0:
                record_attempt(state, story.story_id, attempt, exit_code, "success", output)
                completed = state.setdefault("completed_story_ids", [])
                if story.story_id not in completed:
                    completed.append(story.story_id)
                state["status"] = "open"
                state["active_story_id"] = None
                state["active_story_title"] = None
                state["retry_count"] = 0
                state["failed_story_id"] = None
                state["last_error"] = None
                write_state(state_path, state)
                append_progress(progress_path, f"completed {story.story_id} on attempt {attempt}/{args.retries}")
                status_line(success_status_message(story.story_id, attempt, args.retries))
                break

            record_attempt(state, story.story_id, attempt, exit_code, "failure", output)
            state["status"] = "open"
            state["retry_count"] = attempt
            state["failed_story_id"] = story.story_id
            state["last_error"] = f"agent exit {exit_code}"
            write_state(state_path, state)
            append_progress(progress_path, f"failed {story.story_id} on attempt {attempt}/{args.retries} with exit {exit_code}")
            status_line(
                failure_status_message(
                    story.story_id,
                    attempt,
                    args.retries,
                    exit_code,
                )
            )

            if attempt < args.retries:
                backoff = compute_backoff_seconds(attempt)
                append_progress(progress_path, f"backing off {backoff:g}s before retrying {story.story_id}")
                status_line(f"{story.story_id} backing off {backoff:g}s before retry")
                status_line(f"{story.story_id} retrying")
                time.sleep(backoff)
                continue

            state["status"] = "failed"
            state["last_error"] = "retries exhausted"
            write_state(state_path, state)
            append_progress(progress_path, f"retries exhausted for {story.story_id}; stopping PRD")
            status_line(f"{story.story_id} failed permanently")
            status_line(f"Failed after retries: {prd.path} ({story.story_id})")
            return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prd-tasks-loop.py",
        description="Execute one or more PRDs sequentially with a single agent command.",
        epilog=(
            "Examples:\n"
            "  prd-tasks-loop.py --agent=codex docs/prd/2026-04-30-104512-jwt-authentication.md\n"
            "  prd-tasks-loop.py --agent=amp docs/prd/2026-04-30-104512-auth.md docs/prd/2026-04-30-111200-rate-limit.md\n"
            "  prd-tasks-loop.py --agent='./myagent --stdin' --retries=5 --timeout=45m prd1.md prd2.md prd3.md"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("prds", nargs="*", help="PRD paths processed in order")
    parser.add_argument("--branch", default="", help="Git branch to checkout before starting the loop")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT_RAW)
    parser.add_argument(
        "--agent",
        default="codex",
        help=(
            "Agent preset or full command. Built-in presets: codex, amp, claude-code, gemini, opencode. "
            "Custom commands must read the rendered prompt from stdin."
        ),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    maybe_wrap_with_caffeinate(args)
    prd_paths = resolve_prd_list(args.prds)
    if not prd_paths:
        fail("No PRD files found.")
    prompt_run_confirmation(args, prd_paths)
    if args.retries < 1:
        fail("--retries must be >= 1")
    try:
        timeout_seconds = parse_duration_to_seconds(args.timeout)
    except ValueError:
        fail(f"Invalid timeout: {args.timeout}")

    preset, agent_command = choose_agent_command(args)
    total = len(prd_paths)
    for index, prd_path in enumerate(prd_paths, start=1):
        prd = parse_prd(prd_path)
        if not run_one_prd(args, prd, preset, agent_command, timeout_seconds, index, total):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
