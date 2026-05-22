# CLAUDE.md - Claude Code Compatibility Instructions

@AGENTS.md

## Claude Code Notes

- `AGENTS.md` is the canonical instruction file for this repository.
- Keep shared rules in `AGENTS.md` so Codex and Claude Code follow the same source of truth.
- Add only Claude Code-specific behavior here.
- Use `/memory` and `/context` in Claude Code to verify which instruction files loaded.
- If Claude Code needs scoped test instructions, read `tests/AGENTS.md` before editing files under `tests/`.
