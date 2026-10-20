# copy-edit-skill

A Claude Code plugin that copy-edits the prose in a change before you
commit it: comments, docstrings, markdown, template comments. It never
touches code. The rule it applies is one sentence: say only what the
artifact itself cannot.
[`standard.md`](skills/copy-edit/standard.md) spells that out as a
taxonomy of what to keep, delete, and compress.

## Install

Needs Claude Code 2.1.275 or later, `git`, and `python3` 3.11 or later.

```sh
claude plugin install copy-editor --marketplace focusconsulting/copy-edit-skill
```

Or from a clone:

```sh
git clone https://github.com/focusconsulting/copy-edit-skill.git
claude plugin marketplace add ./copy-edit-skill
claude plugin install copy-editor@copy-edit-skill
```

To turn it on for everyone who opens a repository, add this to that
repository's `.claude/settings.json` instead:

```json
{
  "extraKnownMarketplaces": {
    "copy-edit-skill": {
      "source": { "source": "github", "repo": "focusconsulting/copy-edit-skill" }
    }
  },
  "enabledPlugins": { "copy-editor@copy-edit-skill": true }
}
```

## Use

Before committing, in a Claude Code session:

```text
/copy-editor:copy-edit
```

It reviews the staged diff, or the working-tree diff if nothing is
staged. A read-only agent reads the standard and the diff and returns
findings with exact replacement text; the session skips any finding
that would delete a why, a constraint, an invariant, a gotcha, or a
regression record; a script applies the rest by exact match and
appends one line to `.copy-edit/runs.log`.

To sweep whole files instead, name paths:

```text
/copy-editor:copy-edit src/ docs/
```

A sweep reviews the tracked files under those paths in groups of ten,
one agent per group. Files without prose markers and migration
directories are left out.

### Configuration

Optional. A `.claude/copy-edit.toml` at the repository root lists paths
a sweep leaves alone unless an argument names one of them, such as
files another person maintains by hand:

```toml
skip = ["infrastructure/", "design/"]
```

Diff mode ignores the list: a staged change is always in scope.

Scratch files, the findings and the run log, live in `.copy-edit/` at
the repository root. The script writes a `.gitignore` there, so there
is nothing to add to yours.

## Tests

```sh
uvx pytest skills/copy-edit
```

## Origin

Extracted from a Focus Consulting engagement's repository, where it has
been in use since July 2026. The standard's examples are anonymized
from that codebase. MIT license.
