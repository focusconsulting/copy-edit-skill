---
name: copy-edit
description: >
  Copy-edit the prose in pending changes — comments, docstrings, and
  markdown — against the editorial standard shipped with this plugin,
  before committing. Use when about to commit, or when asked to tighten,
  trim, or copy-edit comments, docstrings, or docs. Reviews text only,
  never code logic. With path arguments, reviews whole files instead of
  the diff.
argument-hint: "[paths…]"
allowed-tools:
  - Bash(git diff:*)
  - Bash(git status:*)
  - Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/copyedit.py" *)
  - Agent(copy-editor:copy-editor)
  - Read
  - Write
  - Edit
---

# Copy-edit pending prose

Review and fix TEXT only: comments, docstrings, markdown, template
comments (`{# #}`, `<!-- -->`). Never logic, naming, or structure. The
standard is `${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/standard.md`. The
`copy-editor:copy-editor` agent reviews, `copyedit.py` applies, and you
judge in between. Run every `copyedit.py` command from the repository
root, exactly as written below.

## 1. Scope

- No arguments: run `git diff --cached -U5`; if empty, `git diff HEAD
  -U5`. If that is also empty, report "nothing pending" and stop.
- Path arguments: sweep mode. Run `python3
  "${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/copyedit.py" partition
  <paths>`. It lists the tracked files under those paths that carry
  prose, in partitions of ten, and reports what it left out: files
  without prose markers, migrations, and the paths listed under `skip`
  in the repository's `.claude/copy-edit.toml` unless an argument names
  one (`copy-edit.example.toml` beside this file shows the format). No
  partitions → report "nothing to review" and stop.

Scope guard (diff mode): judge added or modified lines by the file's
language. A line is prose when it carries the marker for its
extension:

| Files | Markers |
|---|---|
| `.py` | `#`, `"""`, `'''` |
| `.ts`, `.js`, `.mjs` | `//`, `/*`, a line starting with `*` |
| `.html` | `{#`, `<!--`, `{% comment %}` |
| `.css`, `.scss` | `/*`, a line starting with `*` |
| `.tf`, `.hcl` | `#`, `//`, `/*` |
| `.yml`, `.yaml`, `.toml`, `.sh`, `justfile`, `Dockerfile` | `#` |
| `.md` | any change |

`#` is not a marker in CSS or HTML, where it is a color or an anchor.
If no line qualifies, report "no text changes to edit" and stop
without spawning the agent.

## 2. Review

Every prompt to the `copy-editor:copy-editor` agent opens with "Read
${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/standard.md first."

- Diff mode: one agent. Add the diff verbatim inside `<diff>` tags,
  plus "judge only added or modified lines; read surrounding files for
  context, but do not report on untouched text".
- Sweep mode: one agent per partition, all spawned in the same turn.
  Add the partition's file list, plus "review all prose in these
  files".

Write the reports, concatenated, to `.copy-edit/findings.txt` in the
repository. If every report ends `SUMMARY: clean.`, report that and
stop.

## 3. Judge

Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/copyedit.py"
list`. It numbers the findings and flags malformed ones. You are the
judgment layer: skip a finding that deletes load-bearing content (a
why, constraint, invariant, gotcha, regression record, or removal
condition) and say in one line why.

## 4. Apply

Run `python3 "${CLAUDE_PLUGIN_ROOT}/skills/copy-edit/copyedit.py"
apply --mode diff` (or `--mode sweep`), with `--skip 2,5` for the
indexes you are keeping. It applies each remaining finding by exact
match, reports applied, missed, and skipped, and appends one line to
`.copy-edit/runs.log` in the repository. For a missed finding,
re-read the file and apply the intent by hand with Edit. Read `git
diff` once. Do not re-run the agent on its own output.

## 5. Report

One line: N findings, applied A, skipped S (with reasons), missed M.
If a commit was in progress, continue it.
