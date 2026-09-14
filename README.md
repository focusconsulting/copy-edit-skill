# copy-editor

A Claude Code plugin that copy-edits the prose in a change before it is
committed: comments, docstrings, markdown, template comments. It never
touches code. The rule it applies is one sentence: say only what the
artifact itself cannot. [`skills/copy-edit/standard.md`](skills/copy-edit/standard.md)
spells that out as a taxonomy of what to keep, delete, and compress.

## How it works

Three parts, three jobs.

- **The `copy-editor` agent reviews.** A read-only subagent reads the
  standard, then the diff, and returns findings in a fixed format: file,
  lines, verdict, category, the current text, the replacement.
- **The session judges.** Claude reads the numbered findings and skips
  any that would delete load-bearing content: a why, a constraint, an
  invariant, a gotcha, a regression record, a removal condition.
- **`copyedit.py` applies.** A stdlib-only script applies the remaining
  findings by exact match, reports what it applied, missed, and
  skipped, and appends one line to a log.

The split matters. The agent decides what to cut, the session decides
what to keep, and the script only moves text.

## Install

In the repository that should use it, add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "copy-editor": {
      "source": { "source": "github", "repo": "OWNER/REPO" }
    }
  },
  "enabledPlugins": {
    "copy-editor@copy-editor": true
  }
}
```

Everyone who opens that repository in Claude Code gets the plugin.
Requirements on their machine: `git`, and `python3` 3.11 or later
(3.10 works for everything except sweep mode).

To try it from a local checkout instead:

```sh
claude --plugin-dir /path/to/this/repo
```

## Use

Before committing, in any repository with the plugin enabled:

```text
/copy-editor:copy-edit
```

It reviews the staged diff, or the working-tree diff if nothing is
staged. To sweep whole files instead, name paths:

```text
/copy-editor:copy-edit src/ docs/
```

Sweep mode partitions the tracked files under those paths into groups
of ten and reviews each group with its own agent. Files without prose
markers and migration directories are left out.

### Configuration

Optional. A `.claude/copy-edit.toml` at the repository root lists paths
a sweep leaves alone unless an argument names one of them, such as
files another person maintains by hand:

```toml
skip = [
  "infrastructure/",
  "design/",
]
```

[`skills/copy-edit/copy-edit.example.toml`](skills/copy-edit/copy-edit.example.toml)
shows the format. Diff mode ignores the list: a staged change is always
in scope.

Add `.claude/copy-edit-findings.txt` and `.claude/copy-edit.log` to the
repository's `.gitignore`. The first is scratch; the second is a
per-run record you may want to keep locally.

## Tests

```sh
uvx pytest skills/copy-edit
```

Black-box tests that run the script in throwaway git repositories.

## Origin

Extracted from a Focus Consulting engagement's repository in September
2026, where the skill ran from July onward. The standard's examples are
anonymized from that codebase.
