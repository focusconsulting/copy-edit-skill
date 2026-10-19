"""Deterministic half of the copy-edit skill: partition a sweep, list the
copy-editor's findings, apply them, and log each run. The agent decides what
to cut; the session decides what to keep; this script only moves text.

Findings arrive in the copy-editor agent's report format. Several reports
may be concatenated; indexes are reassigned in file order.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11; only `partition` needs it
    tomllib = None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


ROOT = Path(git("rev-parse", "--show-toplevel"))
DEFAULT_FINDINGS = ".claude/copy-edit-findings.txt"
DEFAULT_LOG = ".claude/copy-edit.log"
DEFAULT_CONFIG = ".claude/copy-edit.toml"


@dataclass
class Finding:
    index: int
    file: str
    start: int | None
    end: int | None
    verdict: str
    category: str
    reason: str
    current: str
    replacement: str

    @property
    def where(self) -> str:
        span = "" if self.start is None else f":{self.start}" + ("" if self.end in (None, self.start) else f"-{self.end}")
        return f"{self.file}{span}"


FIELD = re.compile(r"^(file|lines|verdict|category|reason):\s*(.*)$")


def parse(text: str) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    warnings: list[str] = []
    lines = text.splitlines()
    i = 0

    def block(at: int) -> tuple[str, int]:
        # at points to the line after "current:"/"replacement:".
        if at >= len(lines) or lines[at].strip() != "<<<":
            raise ValueError("expected <<<")
        at += 1
        body: list[str] = []
        while at < len(lines) and lines[at].strip() != ">>>":
            body.append(lines[at])
            at += 1
        if at >= len(lines):
            raise ValueError("unterminated <<< block")
        return "\n".join(body), at + 1

    while i < len(lines):
        head = re.match(r"^FINDING\s+(\d+)", lines[i])
        if not head:
            i += 1
            continue
        label = head.group(1)
        fields: dict[str, str] = {}
        i += 1
        try:
            while i < len(lines) and not lines[i].startswith("current:"):
                if re.match(r"^(FINDING\s+\d+|SUMMARY:)", lines[i]):
                    raise ValueError("no current: block")
                m = FIELD.match(lines[i])
                if m:
                    fields[m.group(1)] = m.group(2).strip()
                i += 1
            if i >= len(lines):
                raise ValueError("no current: block")
            current, i = block(i + 1)
            if i >= len(lines) or not lines[i].startswith("replacement:"):
                raise ValueError("no replacement: block")
            replacement, i = block(i + 1)
        except ValueError as err:
            warnings.append(f"FINDING {label} skipped: {err}")
            continue
        if "file" not in fields or not current.strip():
            warnings.append(f"FINDING {label} skipped: missing file or empty current")
            continue
        start = end = None
        if m := re.match(r"^(\d+)(?:\s*-\s*(\d+))?", fields.get("lines", "")):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
        findings.append(
            Finding(
                index=len(findings) + 1,
                file=fields["file"],
                start=start,
                end=end,
                verdict=fields.get("verdict", "?"),
                category=fields.get("category", "?"),
                reason=fields.get("reason", ""),
                current=current,
                replacement=replacement,
            )
        )
    return findings, warnings


def spans(text: str, needle: str) -> list[tuple[int, int]]:
    # Trailing whitespace at any line end of the match is consumed, never required,
    # so a partial-line match still stops before the next word.
    *body, last = [re.escape(line.rstrip()) for line in needle.split("\n")]
    pattern = "".join(part + r"[ \t]*\n" for part in body) + last + r"(?:[ \t]*(?=\n|\Z))?"
    return [(m.start(), m.end()) for m in re.finditer(pattern, text)]


def choose(text: str, found: list[tuple[int, int]], hint: int | None) -> tuple[int, int] | None:
    if len(found) == 1:
        return found[0]
    if hint is None:
        return None
    return min(found, key=lambda s: abs(text.count("\n", 0, s[0]) + 1 - hint))


def apply_one(f: Finding) -> str:
    path = ROOT / f.file
    if not path.is_file():
        return "missing-file"
    text = path.read_text()
    found = spans(text, f.current)
    if not found:
        return "missed"
    span = choose(text, found, f.start)
    if span is None:
        return "ambiguous"
    start, end = span
    whole = (start == 0 or text[start - 1] == "\n") and (end == len(text) or text[end] == "\n")
    if f.replacement == "" and whole:
        end = min(end + 1, len(text))
        text = text[:start] + text[end:]
        if start == 0:  # a deleted module docstring would leave its blank lines on top
            text = text.lstrip("\n")
    else:
        text = text[:start] + f.replacement + text[end:]
    path.write_text(text)
    return "applied"


def cmd_list(args: argparse.Namespace) -> int:
    findings, warnings = parse(Path(args.findings).read_text())
    for f in findings:
        exists = "" if (ROOT / f.file).is_file() else "  [file not found]"
        print(f"{f.index:>3}  {f.verdict:<8} {f.category:<22} {f.where}{exists}")
        if f.reason:
            print(f"     {f.reason}")
    for w in warnings:
        print(f"warning: {w}")
    print(f"{len(findings)} findings" + (f", {len(warnings)} malformed" if warnings else ""))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    findings, warnings = parse(Path(args.findings).read_text())
    skip = {int(s) for s in args.skip.split(",") if s.strip()} if args.skip else set()
    unknown = skip - {f.index for f in findings}
    if unknown:
        print(f"error: --skip names findings that do not exist: {sorted(unknown)}")
        return 2
    # Apply bottom-up within each file so earlier line hints stay valid.
    order = sorted(
        (f for f in findings if f.index not in skip),
        key=lambda f: (f.file, -(f.start or 0)),
    )
    status: dict[int, str] = {f.index: "skipped" for f in findings if f.index in skip}
    for f in order:
        status[f.index] = apply_one(f)
    for f in findings:
        print(f"{f.index:>3}  {status[f.index]:<12} {f.verdict:<8} {f.where}")
    for w in warnings:
        print(f"warning: {w}")
    counts = {k: sum(1 for v in status.values() if v == k) for k in ("applied", "missed", "ambiguous", "missing-file", "skipped")}
    verdicts = {k: sum(1 for f in findings if f.verdict == k) for k in ("delete", "compress")}
    summary = (
        f"findings={len(findings)}\tdelete={verdicts['delete']}\tcompress={verdicts['compress']}\t"
        f"applied={counts['applied']}\tmissed={counts['missed'] + counts['ambiguous'] + counts['missing-file']}\t"
        f"skipped={counts['skipped']}"
    )
    print(summary.replace("\t", "  "))
    if not args.no_log:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        log = ROOT / args.log
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as fh:
            fh.write(f"{stamp}\t{branch}\t{args.mode}\t{summary}\n")
    return 0


MARKERS: dict[str, tuple[str, ...]] = {
    ".py": ("#", '"""', "'''"),
    ".ts": ("//", "/*", "*"),
    ".js": ("//", "/*", "*"),
    ".mjs": ("//", "/*", "*"),
    ".html": ("{#", "<!--", "{% comment %}"),
    ".css": ("/*", "*"),
    ".scss": ("/*", "*"),
    ".tf": ("#", "//", "/*"),
    ".hcl": ("#", "//", "/*"),
    ".yml": ("#",),
    ".yaml": ("#",),
    ".toml": ("#",),
    ".sh": ("#",),
    ".md": (),
}
BASENAME_MARKERS: dict[str, tuple[str, ...]] = {"justfile": ("#",), "Dockerfile": ("#",)}


def load_skips(config: str) -> list[str] | None:
    path = ROOT / config
    if not path.is_file():
        return None
    if tomllib is None:
        sys.exit(f"error: reading {config} needs Python 3.11 or newer")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as err:
        sys.exit(f"error: {config}: {err}")
    skips = data.get("skip", [])
    if not isinstance(skips, list) or not all(isinstance(e, str) and e.strip("/") for e in skips):
        sys.exit(f"error: {config}: skip must be a list of non-empty paths")
    return [e.removeprefix("./") for e in skips]


def covers(entry: str, path: str) -> bool:
    if entry.endswith("/"):
        return path.startswith(entry) or path == entry[:-1]
    return path == entry or path.startswith(entry + "/")


def markers_for(path: str) -> tuple[str, ...] | None:
    name = Path(path).name
    if name in BASENAME_MARKERS:
        return BASENAME_MARKERS[name]
    return MARKERS.get(Path(path).suffix)


def has_prose(path: str) -> bool:
    marks = markers_for(path)
    if marks is None:
        return False
    if not marks:
        return True
    try:
        text = (ROOT / path).read_text()
    except (UnicodeDecodeError, OSError):
        return False
    for line in text.splitlines():
        stripped = line.lstrip()
        for m in marks:
            if (stripped.startswith("*") if m == "*" else m in line):
                return True
    return False


def cmd_partition(args: argparse.Namespace) -> int:
    rel = [Path(p).resolve().relative_to(ROOT).as_posix() for p in args.paths]
    skips = load_skips(args.config)
    # A skipped file is in scope only under an argument that itself sits
    # inside the skip entry; a broad parent path never admits it.
    inside = [r for r in rel if any(covers(e, r) for e in (skips or []))]
    files = git("ls-files", "--", *rel).split("\n") if rel else []
    files = [f for f in files if f]
    kept: list[str] = []
    no_prose = 0
    guarded: dict[str, int] = {}
    for f in files:
        if "/migrations/" in f:
            continue
        entry = next((e for e in (skips or []) if covers(e, f)), None)
        if entry and not any(covers(r, f) for r in inside):
            guarded[entry] = guarded.get(entry, 0) + 1
            continue
        if not has_prose(f):
            no_prose += 1
            continue
        kept.append(f)
    kept.sort()
    parts = [kept[i : i + args.max_files] for i in range(0, len(kept), args.max_files)]
    for n, members in enumerate(parts, 1):
        print(f"PARTITION {n} ({len(members)} file{'s' if len(members) != 1 else ''})")
        for f in members:
            print(f"  {f}")
    if no_prose:
        print(f"skipped {no_prose} files without prose markers")
    for entry, count in guarded.items():
        print(f"skipped {count} files under {entry} (listed in {args.config}; name the path to include it)")
    if skips is None:
        print(f"note: no skip list at {args.config}")
    print(f"{len(parts)} partition{'s' if len(parts) != 1 else ''}, {len(kept)} file{'s' if len(kept) != 1 else ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="copyedit.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_part = sub.add_parser("partition", help="group the files a sweep should review")
    p_part.add_argument("paths", nargs="+")
    p_part.add_argument("--max-files", type=int, default=10)
    p_part.add_argument("--config", default=DEFAULT_CONFIG, help="TOML file with a `skip` list")
    p_part.set_defaults(fn=cmd_partition)

    p_list = sub.add_parser("list", help="number and summarize the findings")
    p_list.add_argument("findings", nargs="?", default=DEFAULT_FINDINGS)
    p_list.set_defaults(fn=cmd_list)

    p_apply = sub.add_parser("apply", help="apply findings by exact match and log the run")
    p_apply.add_argument("findings", nargs="?", default=DEFAULT_FINDINGS)
    p_apply.add_argument("--skip", default="", help="comma-separated indexes to leave alone")
    p_apply.add_argument("--mode", choices=("diff", "sweep"), default="diff")
    p_apply.add_argument("--log", default=DEFAULT_LOG)
    p_apply.add_argument("--no-log", action="store_true")
    p_apply.set_defaults(fn=cmd_apply)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
