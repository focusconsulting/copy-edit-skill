"""Black-box tests for copyedit.py, each in a throwaway git repo.

Run with `uvx pytest skills/copy-edit` from the plugin root.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("copyedit.py")

MOD = '''"""Module docstring that restates the module name.

It also explains, at length, what the functions below visibly do.
"""

# ---- helpers ----


def f(x: int) -> int:
    """Return x plus one."""
    return x + 1  # add one


def g(x: int) -> int:
    return x + 1  # add one
'''
DOCSTRING = MOD.split("\n\n#")[0]


def sh(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, check=check
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


def commit(repo: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "fixture")


def finding(
    n: int,
    file: str,
    current: str,
    replacement: str = "",
    lines: str | None = None,
    category: str = "restatement",
) -> str:
    verdict = "delete" if replacement == "" else "compress"
    head = [f"FINDING {n}", f"file: {file}"]
    if lines is not None:
        head.append(f"lines: {lines}")
    head += [f"verdict: {verdict}", f"category: {category}", "reason: r"]
    return "\n".join(head) + f"\ncurrent:\n<<<\n{current}\n>>>\nreplacement:\n<<<\n{replacement}\n>>>\n"


def findings(repo: Path, text: str) -> str:
    (repo / "findings.txt").write_text(text)
    return "findings.txt"


def apply(repo: Path, text: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return sh(repo, "apply", findings(repo, text), "--no-log", *args, check=check)


def test_list_numbers_concatenated_reports_and_flags_malformed(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = (
        finding(1, "app/mod.py", '    """Return x plus one."""')
        + "SUMMARY: 1 findings\n"
        + finding(1, "app/none.py", "# ---- helpers ----", category="banner")
        + "FINDING 9\nfile: app/mod.py\nverdict: delete\nSUMMARY: x\n"
    )
    out = sh(repo, "list", findings(repo, text)).stdout
    assert "  1  delete   restatement" in out
    assert "  2  delete   banner" in out and "[file not found]" in out
    assert "warning: FINDING 9 skipped: no current: block" in out
    assert out.rstrip().endswith("2 findings, 1 malformed")


def test_compress_replaces_in_place(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    out = apply(repo, finding(1, "app/mod.py", DOCSTRING, '"""Helpers."""', lines="1-4")).stdout
    assert "  1  applied      compress app/mod.py:1-4" in out
    text = (repo / "app/mod.py").read_text()
    assert text.startswith('"""Helpers."""\n\n# ---- helpers ----')
    assert "at length" not in text


def test_delete_removes_the_whole_line(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    apply(repo, finding(1, "app/mod.py", '    """Return x plus one."""'))
    assert "def f(x: int) -> int:\n    return x + 1  # add one\n" in (repo / "app/mod.py").read_text()


def test_delete_at_file_start_drops_the_blank_lines_below_it(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    apply(repo, finding(1, "app/mod.py", DOCSTRING, lines="1-4"))
    assert (repo / "app/mod.py").read_text().startswith("# ---- helpers ----\n\n\ndef f")


def test_partial_line_edit_keeps_the_rest_and_uses_the_line_hint(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = "    return x + 1  # add one"
    out = apply(repo, finding(1, "app/mod.py", text, "    return x + 1", lines="15")).stdout
    assert "applied" in out
    lines = (repo / "app/mod.py").read_text().splitlines()
    assert lines[10] == "    return x + 1  # add one"
    assert lines[14] == "    return x + 1"


def test_ambiguous_match_without_hint_leaves_the_file(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    out = apply(repo, finding(1, "app/mod.py", "    return x + 1  # add one", "    return x + 1")).stdout
    assert "  1  ambiguous" in out and "missed=1" in out
    assert (repo / "app/mod.py").read_text() == MOD


def test_missed_and_missing_file_leave_everything_alone(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = finding(1, "app/mod.py", "    # nothing like this") + finding(2, "app/none.py", "# x")
    out = apply(repo, text).stdout
    assert "  1  missed" in out and "  2  missing-file" in out and "missed=2" in out
    assert (repo / "app/mod.py").read_text() == MOD


def test_trailing_whitespace_in_the_file_is_tolerated(repo: Path) -> None:
    commit(repo, {"app/ws.py": "x = 1  # note   \ny = 2\n"})
    apply(repo, finding(1, "app/ws.py", "x = 1  # note", "x = 1"))
    assert (repo / "app/ws.py").read_text() == "x = 1\ny = 2\n"


def test_skip_keeps_a_finding_and_unknown_skip_is_an_error(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = finding(1, "app/mod.py", '    """Return x plus one."""')
    out = apply(repo, text, "--skip", "1").stdout
    assert "  1  skipped" in out and "applied=0" in out and "skipped=1" in out
    assert (repo / "app/mod.py").read_text() == MOD
    err = apply(repo, text, "--skip", "42", check=False)
    assert err.returncode == 2 and "do not exist: [42]" in err.stdout


def test_several_findings_in_one_file_all_apply(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = finding(1, "app/mod.py", DOCSTRING, '"""Helpers."""', lines="1-4") + finding(
        2, "app/mod.py", "# ---- helpers ----", lines="6", category="banner"
    )
    out = apply(repo, text).stdout
    assert "applied=2" in out
    result = (repo / "app/mod.py").read_text()
    assert result.startswith('"""Helpers."""\n') and "----" not in result


def test_default_paths_live_in_a_self_ignoring_folder(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    work = repo / ".copy-edit"
    work.mkdir()
    (work / "findings.txt").write_text(finding(1, "app/mod.py", '    """Return x plus one."""'))
    assert "applied=1" in sh(repo, "apply").stdout
    assert (work / ".gitignore").read_text().endswith("*\n")
    assert (work / "runs.log").read_text().count("\n") == 1
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert status.strip() == "M app/mod.py"


def test_apply_logs_one_line_per_run_unless_told_not_to(repo: Path) -> None:
    commit(repo, {"app/mod.py": MOD})
    text = finding(1, "app/mod.py", '    """Return x plus one."""')
    path = findings(repo, text)
    sh(repo, "apply", path, "--mode", "sweep", "--log", "run.log")
    (line,) = (repo / "run.log").read_text().splitlines()
    assert "\tmain\tsweep\tfindings=1\tdelete=1\tcompress=0\tapplied=1\tmissed=0\tskipped=0" in line
    sh(repo, "apply", path, "--no-log", "--log", "quiet.log")
    assert not (repo / "quiet.log").exists()


def test_partition_applies_the_marker_table(repo: Path) -> None:
    commit(
        repo,
        {
            "a/plain.py": "x = 1\n",
            "a/noted.py": "x = 1  # why\n",
            "a/hex.css": "a { color: #fff; }\n",
            "a/noted.css": "/* why */\na {}\n",
            "a/app.ts": "// why\n",
            "a/anchor.html": '<a href="#top">t</a>\n',
            "a/noted.html": "{# why #}\n",
            "a/migrations/0001.py": "# Generated\n",
            "a/blob.bin": "\x00\x01",
            "README.md": "hello\n",
            "justfile": "# why\n",
            "Dockerfile": "# why\n",
        },
    )
    out = sh(repo, "partition", ".").stdout
    included = [line.strip() for line in out.splitlines() if line.startswith("  ")]
    assert included == [
        "Dockerfile",
        "README.md",
        "a/app.ts",
        "a/noted.css",
        "a/noted.html",
        "a/noted.py",
        "justfile",
    ]
    assert "skipped 4 files without prose markers" in out
    assert "note: no skip list at .claude/copy-edit.toml" in out


def test_partition_chunks_by_max_files(repo: Path) -> None:
    commit(repo, {"a.md": "a", "b.md": "b", "c.md": "c"})
    out = sh(repo, "partition", ".", "--max-files", "2").stdout
    assert "PARTITION 1 (2 files)" in out and "PARTITION 2 (1 file)" in out
    assert out.rstrip().endswith("2 partitions, 3 files")
    assert sh(repo, "partition", "a.md").stdout.rstrip().endswith("1 partition, 1 file")


def test_partition_skip_list_yields_only_to_a_named_path(repo: Path) -> None:
    commit(
        repo,
        {
            ".claude/copy-edit.toml": 'skip = ["infra/", "design/", "app/owned.py"]\n',
            "infra/a.tf": "# why\n",
            "infra/sub/b.tf": "# why\n",
            "design/d.md": "d",
            "app/x.py": "# why\n",
            "app/owned.py": "# why\n",
        },
    )

    def files(*args: str) -> list[str]:
        out = sh(repo, "partition", *args).stdout
        return [line.strip() for line in out.splitlines() if line.startswith("  ")]

    broad = sh(repo, "partition", ".").stdout
    assert files(".") == ["app/x.py"]
    assert "skipped 2 files under infra/" in broad
    assert "skipped 1 files under design/" in broad
    assert "skipped 1 files under app/owned.py" in broad
    assert files("infra") == ["infra/a.tf", "infra/sub/b.tf"]
    assert files("infra/sub") == ["infra/sub/b.tf"]
    assert files(".", "infra/sub") == ["app/x.py", "infra/sub/b.tf"]
    assert files("app/owned.py") == ["app/owned.py"]
    assert files("design") == ["design/d.md"]


def test_partition_config_errors_and_config_flag(repo: Path) -> None:
    commit(repo, {"a.md": "a", "other.toml": 'skip = ["a.md"]\n'})
    assert sh(repo, "partition", ".", "--config", "other.toml").stdout.rstrip().endswith(
        "0 partitions, 0 files"
    )
    (repo / ".claude").mkdir()
    (repo / ".claude/copy-edit.toml").write_text('skip = "a.md"\n')
    bad = sh(repo, "partition", ".", check=False)
    assert bad.returncode == 1 and "skip must be a list of non-empty paths" in bad.stderr
    (repo / ".claude/copy-edit.toml").write_text("skip = [\n")
    broken = sh(repo, "partition", ".", check=False)
    assert broken.returncode == 1 and "error: .claude/copy-edit.toml:" in broken.stderr
