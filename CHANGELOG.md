# Changelog

All notable changes to this skill are documented in this file.

The format is based on Keep a Changelog and this repository uses Git tags for released versions.

## [v0.1.0] - 2026-05-07

### Added

- Canonical PRD format and Python loop runner for story-by-story execution.
- Visible runtime state and progress logs beside each PRD.
- Built-in agent presets for Codex, Gemini, OpenCode, Amp, and Claude Code notes.
- GitHub Pages demo site with animated terminal playback.
- CLI contract checks and real-agent E2E workflow coverage.
- Story commit validation requiring Conventional Commits plus `US-xxx` and PRD references.

### Changed

- Gemini and OpenCode presets now use their current non-interactive prompt contracts instead of the old stdin-only assumption.
- Codex CI execution is pinned to an explicit OpenAI provider/model path.
- First-attempt loop output is more compact and only shows retry counters after an actual retry.
- Loop state now resumes from already completed stories detected in the PRD itself.

### Documentation

- Clarified that `--timeout` applies per agent run attempt for one user story, not for a whole PRD or the whole loop.
- Documented versioning expectations and changelog maintenance for future releases.
