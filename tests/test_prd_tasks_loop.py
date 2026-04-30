#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "prd-tasks-loop" / "scripts" / "prd-tasks-loop.py"


def write_prd(workspace: Path, name: str, title: str, story_two_dep: str = "US-001") -> Path:
    path = workspace / "docs" / "prd" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            f"""\
            # PRD: {title}

            ## Introduction/Overview
            Implement {title.lower()}.

            ## Goals
            - Deliver the behavior.

            ## Execution Settings
            Test Command: ./scripts/test.sh
            Quality Gates:
            - ./scripts/lint.sh

            ## User Stories
            ### US-001: First step
            **Description:** Build the first step.

            **Acceptance Criteria:**
            - [ ] The first step is complete.

            **TDD Plan:**
            - Test: Add a failing test for the first step.
            - Implementation: Implement the first step.

            **Dependencies:** -
            **Parallel Group:** core

            ### US-002: Second step
            **Description:** Build the second step.

            **Acceptance Criteria:**
            - [ ] The second step is complete.

            **TDD Plan:**
            - Test: Add a failing test for the second step.
            - Implementation: Implement the second step.

            **Dependencies:** {story_two_dep}
            **Parallel Group:** core

            ## Functional Requirements
            - The system must support the requested feature.

            ## Non-Goals
            - No unrelated work.

            ## Success Metrics
            - The change can be validated.

            ## Open Questions
            - None.
            """
        )
    )
    return path


def write_bad_prd(workspace: Path, name: str) -> Path:
    path = workspace / "docs" / "prd" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# PRD: Broken\n\n## Introduction/Overview\nBroken.\n")
    return path


def write_agent(workspace: Path, name: str, body: str) -> Path:
    path = workspace / "bin" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def write_story_completion_agent(workspace: Path, name: str, *, sleep_seconds: int = 0, exit_code: int = 0, update_prd: bool = True) -> Path:
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import re
        import sys
        import time
        from pathlib import Path

        prompt = sys.stdin.read()
        if {sleep_seconds}:
            time.sleep({sleep_seconds})

        if {str(update_prd)}:
            prd_match = re.search(r"^- PRD: (.+)$", prompt, re.MULTILINE)
            story_match = re.search(r"^Target story: (US-\\d+):", prompt, re.MULTILINE)
            if not prd_match or not story_match:
                sys.exit(91)
            prd_path = Path(prd_match.group(1).strip())
            story_id = story_match.group(1).strip()
            text = prd_path.read_text()
            pattern = re.compile(rf"(?ms)(^###\\s+{{re.escape(story_id)}}:.*?)(?=^###\\s+US-|\\Z)")
            match = pattern.search(text)
            if not match:
                sys.exit(92)
            block = match.group(1)
            updated_block = re.sub(r"^(\\s*- \\[) (\\]\\s+)", r"\\1x\\2", block, flags=re.MULTILINE)
            text = text[:match.start()] + updated_block + text[match.end():]
            prd_path.write_text(text)

        sys.exit({exit_code})
        """
    )
    return write_agent(workspace, name, body)


def write_story_completion_commit_agent(workspace: Path, name: str) -> Path:
    body = textwrap.dedent(
        """\
        #!/usr/bin/env python3
        import re
        import subprocess
        import sys
        from pathlib import Path

        prompt = sys.stdin.read()
        prd_match = re.search(r"^- PRD: (.+)$", prompt, re.MULTILINE)
        story_match = re.search(r"^Target story: (US-\\d+):", prompt, re.MULTILINE)
        if not prd_match or not story_match:
            sys.exit(91)
        prd_path = Path(prd_match.group(1).strip())
        story_id = story_match.group(1).strip()
        text = prd_path.read_text()
        pattern = re.compile(rf"(?ms)(^###\\s+{re.escape(story_id)}:.*?)(?=^###\\s+US-|\\Z)")
        match = pattern.search(text)
        if not match:
            sys.exit(92)
        block = match.group(1)
        updated_block = re.sub(r"^(\\s*- \\[) (\\]\\s+)", r"\\1x\\2", block, flags=re.MULTILINE)
        text = text[:match.start()] + updated_block + text[match.end():]
        prd_path.write_text(text)
        subprocess.run(["git", "add", str(prd_path)], check=True, cwd=prd_path.parent.parent.parent)
        subprocess.run(["git", "commit", "-m", f"feat: complete {story_id.lower()}"], check=True, cwd=prd_path.parent.parent.parent)
        sys.exit(0)
        """
    )
    return write_agent(workspace, name, body)


class PrdTasksLoopTests(unittest.TestCase):
    def make_workspace(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="prd-tasks-loop-test."))

    def run_script(
        self,
        workspace: Path,
        *args: str,
        allow_failure: bool = False,
        extra_env: dict | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{workspace / 'bin'}:{env.get('PATH', '')}"
        env["PRD_TASKS_LOOP_BACKOFF_SCALE"] = "0"
        env["PRD_TASKS_LOOP_AUTO_CONFIRM"] = "1"
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), *args],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            input=input_text,
        )
        if not allow_failure and result.returncode != 0:
            self.fail(result.stdout + result.stderr)
        return result

    def init_git_repo(self, workspace: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-qm", "chore: initial"], cwd=workspace, check=True)

    def test_no_prd_files_found(self) -> None:
        workspace = self.make_workspace()
        result = self.run_script(workspace, allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error: No PRD files found.", result.stderr)

    def test_invalid_prd_fails_before_execution(self) -> None:
        workspace = self.make_workspace()
        write_bad_prd(workspace, "wrong-name.md")
        result = self.run_script(workspace, allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error: No PRD files found.", result.stderr)

    def test_explicit_invalid_prd_still_fails_validation(self) -> None:
        workspace = self.make_workspace()
        prd = write_bad_prd(workspace, "wrong-name.md")
        result = self.run_script(workspace, str(prd), allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid PRD filename `wrong-name.md`", result.stdout)
        self.assertIn("Missing required section `## Goals`.", result.stdout)

    def test_auto_discovery_skips_non_canonical_prd_names(self) -> None:
        workspace = self.make_workspace()
        valid = write_prd(workspace, "2026-04-30-104512-valid.md", "Valid")
        write_bad_prd(workspace, "prd-agent-attention-plan-mode.md")
        write_story_completion_agent(workspace, "success-agent")
        result = self.run_script(workspace, "--agent=success-agent")
        self.assertIn("1/1 2026-04-30-104512-valid.md", result.stdout)
        self.assertNotIn("prd-agent-attention-plan-mode.md", result.stdout)
        self.assertFalse(valid.with_suffix(".json.log").exists())

    def test_run_creates_state_logs_and_parses_dependencies(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-happy-path.md", "Happy Path")
        write_story_completion_agent(workspace, "success-agent")
        result = self.run_script(workspace, "--agent=success-agent", str(prd))
        state_file = prd.with_suffix(".json.log")
        progress_file = prd.with_suffix(".progress.log")
        self.assertFalse(state_file.exists())
        self.assertFalse(progress_file.exists())
        self.assertIn("US-001 passed (1/3)", result.stdout)
        self.assertIn("US-002 passed (1/3)", result.stdout)
        prd_text = prd.read_text()
        self.assertIn("- [x] The first step is complete.", prd_text)
        self.assertIn("- [x] The second step is complete.", prd_text)

    def test_custom_agent_overrides_preset(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-custom-override.md", "Custom Override")
        write_agent(workspace, "custom-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 7\n")
        self.run_script(workspace, "--agent=custom-agent", "--retries", "1", str(prd), allow_failure=True)
        state = json.loads(prd.with_suffix(".json.log").read_text())
        self.assertEqual(state["selected_agent"], "custom-agent")

    def test_timeout_retry_exhaustion_and_backoff(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-timeout-case.md", "Timeout Case")
        write_story_completion_agent(workspace, "sleep-agent", sleep_seconds=2)
        result = self.run_script(
            workspace,
            "--agent=sleep-agent",
            "--timeout",
            "1s",
            "--retries",
            "2",
            str(prd),
            allow_failure=True,
        )
        self.assertIn("US-001 failed (1/2, exit 124)", result.stdout)
        self.assertIn("US-001 backing off 0s before retry", result.stdout)
        self.assertIn("US-001 retrying", result.stdout)
        self.assertIn("US-001 failed permanently", result.stdout)
        state = json.loads(prd.with_suffix(".json.log").read_text())
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["failed_story_id"], "US-001")
        self.assertEqual(len(state["attempts"]), 2)

    def test_caffeinate_wrap_on_mac(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-caffeinate.md", "Caffeinate")
        write_story_completion_agent(workspace, "success-agent")
        write_agent(workspace, "caffeinate", "#!/usr/bin/env bash\nprintf 'CAFFEINATE\\n' >&2\nshift 1\nexec \"$@\"\n")
        result = self.run_script(
            workspace,
            "--agent=success-agent",
            str(prd),
            extra_env={"PRD_TASKS_LOOP_OS": "Darwin"},
        )
        self.assertIn("CAFFEINATE", result.stderr)

    def test_multiple_prds_stop_on_first_failure_with_positional_args(self) -> None:
        workspace = self.make_workspace()
        first = write_prd(workspace, "2026-04-30-104512-first-fails.md", "First Fails")
        second = write_prd(workspace, "2026-04-30-104513-second-skipped.md", "Second Skipped")
        write_agent(workspace, "fail-agent", "#!/usr/bin/env bash\ncat >/dev/null\nexit 7\n")
        result = self.run_script(
            workspace,
            "--agent=fail-agent",
            "--retries",
            "1",
            str(first),
            str(second),
            allow_failure=True,
        )
        self.assertIn("1/2 2026-04-30-104512-first-fails.md", result.stdout)
        self.assertIn("Failed after retries", result.stdout)
        self.assertTrue(first.with_suffix(".json.log").exists())
        self.assertFalse(second.with_suffix(".json.log").exists())

    def test_exit_zero_without_prd_update_is_rejected(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-no-prd-update.md", "No PRD Update")
        write_story_completion_agent(workspace, "noop-agent", update_prd=False)
        result = self.run_script(workspace, "--agent=noop-agent", "--retries", "1", str(prd), allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("US-001 failed (1/1, exit 65)", result.stdout)
        self.assertIn("Failed after retries", result.stdout)

    def test_help_mentions_agent_and_multiple_prds(self) -> None:
        workspace = self.make_workspace()
        result = self.run_script(workspace, "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--agent", result.stdout)
        self.assertIn("--branch", result.stdout)
        self.assertIn("Built-in presets: codex, amp, claude-code, gemini, opencode", result.stdout)
        self.assertIn("prd1.md prd2.md prd3.md", result.stdout)

    def test_confirmation_prompt_outside_git_repo(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-confirm.md", "Confirm")
        write_story_completion_agent(workspace, "success-agent")
        result = self.run_script(
            workspace,
            "--agent=success-agent",
            str(prd),
            extra_env={"PRD_TASKS_LOOP_AUTO_CONFIRM": "0"},
            input_text="yes\n",
        )
        self.assertIn("About to start PRD loop:", result.stdout)
        self.assertIn("Workspace is not inside a Git repository.", result.stdout)
        self.assertIn(str(prd), result.stdout)

    def test_confirmation_prompt_in_git_repo_mentions_branch(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-branch.md", "Branch")
        write_story_completion_commit_agent(workspace, "commit-agent")
        self.init_git_repo(workspace)
        result = self.run_script(
            workspace,
            "--agent=commit-agent",
            str(prd),
            extra_env={"PRD_TASKS_LOOP_AUTO_CONFIRM": "0"},
            input_text="yes\n",
        )
        self.assertIn("Current branch:", result.stdout)
        self.assertIn("Target branch:", result.stdout)

    def test_branch_override_checks_out_requested_branch(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-branch-override.md", "Branch Override")
        write_story_completion_commit_agent(workspace, "commit-agent")
        self.init_git_repo(workspace)
        current = subprocess.run(["git", "branch", "--show-current"], cwd=workspace, text=True, capture_output=True, check=True).stdout.strip()
        other = "feature/prd-loop-test"
        subprocess.run(["git", "checkout", "-b", other], cwd=workspace, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", current], cwd=workspace, check=True, capture_output=True, text=True)
        result = self.run_script(
            workspace,
            "--agent=commit-agent",
            f"--branch={other}",
            str(prd),
            extra_env={"PRD_TASKS_LOOP_AUTO_CONFIRM": "0"},
            input_text="yes\n",
        )
        self.assertIn(f"Target branch: {other}", result.stdout)
        branch_after = subprocess.run(["git", "branch", "--show-current"], cwd=workspace, text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(branch_after, other)

    def test_git_repo_requires_commit_when_worktree_starts_clean(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-git-commit.md", "Git Commit")
        write_story_completion_agent(workspace, "success-agent")
        self.init_git_repo(workspace)
        result = self.run_script(workspace, "--agent=success-agent", "--retries", "1", str(prd), allow_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("US-001 failed (1/1, exit 66)", result.stdout)

    def test_git_repo_accepts_story_commit(self) -> None:
        workspace = self.make_workspace()
        prd = write_prd(workspace, "2026-04-30-104512-git-commit-ok.md", "Git Commit OK")
        write_story_completion_commit_agent(workspace, "commit-agent")
        self.init_git_repo(workspace)
        result = self.run_script(workspace, "--agent=commit-agent", str(prd))
        self.assertIn("US-001 passed (1/3)", result.stdout)


if __name__ == "__main__":
    unittest.main()
