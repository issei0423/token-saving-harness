# token-saving-harness

[日本語](README.md) · **English**

A small harness for spending fewer tokens in Claude Code: a set of rule documents, five subagent definitions, and a usage watcher.

The idea: let the capable model do only the **thinking**, and hand research, testing and implementation to subagents that run on smaller models with fewer tools.

> The documents and the agent prompts are written in Japanese. Claude follows them regardless of the language you talk to it in, but you will want to read Japanese (or translate) to customize them.

## What it saved (measured on the author's machine)

| Change | Before | After | Diff |
| :-- | --: | --: | --: |
| Split the always-loaded rules into a small core plus read-on-demand documents | 6,442 | 4,153 | **−36%** |
| Ran a read-only research task on a haiku `researcher` instead of an agent on the main model | 61,200 | 29,000 | **−53%** |

Units are tokens. The second row returned nearly the same answer (32 of 33 items).

One thing got worse: right after installing, in a session where the new agent types were not loaded yet, a general-purpose agent told to "act as the researcher" used 76,134 tokens — 2.6× the real `researcher`.

One machine, October–November 2026, measured on the author's private version that this repository was derived from. Method and caveats: [token/measure.md](token/measure.md) (Japanese).

## Three principles

1. **Keep what is always loaded small.** Anything imported into `CLAUDE.md` with `@` is loaded in full, every session.
2. **Read details only when needed.** The core keeps a one-line summary and a "→ 読む (read)" pointer.
3. **Give a subagent only what its task needs.** Not the conversation history.

## What is inside

| Path | What |
| :-- | :-- |
| `core/graph.md` | The core rules for the main session (about 3,700 characters; a test fails above 5,000) |
| `core/graph/` | Documents read on demand (flow, roles, budget, permissions, away mode, state file) |
| `core/agents/` | Five agents: `thinker`, `executor` (sonnet), `researcher` (haiku), `tester` (haiku), `verifier` (sonnet) |
| `core/budget.sh` | Reads the 5-hour and 7-day usage and answers `GO` / `STOP` before a new agent is launched |
| `statusline/statusline-tee.sh` | Saves the usage numbers that Claude Code passes to the status line |
| `token/` | Loading rules, model routing, briefing rules, measurements |

## Install

Requires Claude Code (signed in with a subscription plan), bash (Git Bash on Windows) and Python 3.

```bash
git clone https://github.com/issei0423/token-saving-harness ~/.claude/token-harness
cd ~/.claude/token-harness
bash install.sh           # dry run: prints what it would do
bash install.sh --apply   # copies the agent definitions into ~/.claude/agents
```

`install.sh` only copies the five agent files (an existing file with the same name is backed up to `~/.claude/agents-backup/` first). It never edits your settings. Paste these two yourself — the script prints both with the paths for your machine:

1. Add the block in [core/claude-md-snippet.md](core/claude-md-snippet.md) to `~/.claude/CLAUDE.md`.
2. Add a `statusLine` entry to `~/.claude/settings.json`:

   ```json
   "statusLine": { "type": "command", "command": "bash \"<absolute path>/statusline/statusline-tee.sh\"" }
   ```

Then start a **new** Claude Code session (agent types are loaded at session start).

Check your usage any time:

```bash
bash ~/.claude/token-harness/core/budget.sh 85 50
```

The last line is `GO`, `STOP`, or `UNKNOWN` (exit code 0 / 1 / 2). The output text is Japanese.

## Uninstall

Remove the block from `CLAUDE.md`, restore `statusLine`, delete the five files in `~/.claude/agents/`, and delete `~/.claude/token-harness/`.

## Verified / not verified

- Verified: the tests (`bash tests/run.sh`) pass on Ubuntu, macOS and Windows in GitHub Actions. The private version this was derived from is in use on the author's machine (Windows, Claude Code 2.1).
- Not verified: long-term use of this public version on a fresh setup; real use together with Claude Code on macOS or Linux.
- The usage numbers (`rate_limits`) appear only when Claude Code is signed in with a subscription plan. With an API key, `budget.sh` answers `UNKNOWN`.

## License

[MIT](LICENSE)
