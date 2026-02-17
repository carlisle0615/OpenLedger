from __future__ import annotations

import ast
import argparse
import difflib
import json
import re
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("openledger/workflow.py", "openledger/infrastructure/workflow/runtime.py"),
    (
        "openledger/profiles.py",
        "openledger/infrastructure/persistence/sqla/profile_store.py",
    ),
    ("openledger/profile_review.py", "openledger/application/services/review_engine.py"),
    ("openledger/capabilities.py", "openledger/application/services/capabilities_core.py"),
)

_WS_RE = re.compile(r"\s+")


@dataclass
class CodeLine:
    path: str
    line_no: int
    text: str
    normalized: str


@dataclass
class FileAudit:
    old_path: str
    new_path: str
    old_total_lines: int
    new_total_lines: int
    removed_total: int
    added_total: int
    removed_functional: int
    added_functional: int
    matched_functional: int
    suspicious_removed: list[CodeLine]
    suspicious_added: list[CodeLine]
    removed_symbols: list[str]
    added_symbols: list[str]


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _repo_root() -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"]).strip())


def _read_file_at_ref(ref: str, repo_rel_path: str) -> str:
    return _run_git(["show", f"{ref}:{repo_rel_path}"])


def _is_comment_only_line(text: str, suffix: str, *, include_import_lines: bool) -> bool:
    line = text.strip()
    if not line:
        return True

    if line.startswith("#"):
        return True
    if line.startswith("//"):
        return True
    if line.startswith("/*") or line.startswith("*") or line.startswith("*/"):
        return True

    if not include_import_lines and (line.startswith("import ") or line.startswith("from ")):
        return True

    if line in {"(", ")", "[", "]", "{", "}"}:
        return True

    if suffix in {".py", ".pyi"}:
        if line.startswith('"""') and line.endswith('"""') and len(line) >= 6:
            return True
        if line.startswith("'''") and line.endswith("'''") and len(line) >= 6:
            return True

    return False


def _normalize_code_line(text: str) -> str:
    return _WS_RE.sub(" ", text.strip())


def _iter_functional_removed_added(
    old_path: str,
    new_path: str,
    old_text: str,
    new_text: str,
    *,
    include_import_lines: bool,
) -> tuple[list[CodeLine], list[CodeLine], int, int]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    suffix = Path(new_path).suffix or Path(old_path).suffix
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)

    removed_all = 0
    added_all = 0
    removed_functional: list[CodeLine] = []
    added_functional: list[CodeLine] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        if tag in {"replace", "delete"}:
            removed_all += i2 - i1
            for idx in range(i1, i2):
                text = old_lines[idx]
                if _is_comment_only_line(text, suffix, include_import_lines=include_import_lines):
                    continue
                removed_functional.append(
                    CodeLine(
                        path=old_path,
                        line_no=idx + 1,
                        text=text,
                        normalized=_normalize_code_line(text),
                    )
                )

        if tag in {"replace", "insert"}:
            added_all += j2 - j1
            for idx in range(j1, j2):
                text = new_lines[idx]
                if _is_comment_only_line(text, suffix, include_import_lines=include_import_lines):
                    continue
                added_functional.append(
                    CodeLine(
                        path=new_path,
                        line_no=idx + 1,
                        text=text,
                        normalized=_normalize_code_line(text),
                    )
                )

    return removed_functional, added_functional, removed_all, added_all


def _match_same_functional_lines(
    removed: Iterable[CodeLine], added: Iterable[CodeLine]
) -> tuple[int, list[CodeLine], list[CodeLine]]:
    added_list = list(added)
    added_budget = Counter(
        line.normalized for line in added_list if line.normalized
    )

    suspicious_removed: list[CodeLine] = []
    matched = 0
    for line in removed:
        if not line.normalized:
            continue
        if added_budget[line.normalized] > 0:
            added_budget[line.normalized] -= 1
            matched += 1
        else:
            suspicious_removed.append(line)

    consumed = Counter(line.normalized for line in removed if line.normalized)
    suspicious_added: list[CodeLine] = []
    for line in added_list:
        norm = line.normalized
        if not norm:
            continue
        if consumed[norm] > 0:
            consumed[norm] -= 1
            continue
        suspicious_added.append(line)

    return matched, suspicious_removed, suspicious_added


def _collect_python_symbols(tree: ast.AST, prefix: str = "") -> set[str]:
    out: set[str] = set()
    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(f"{prefix}{node.name}")
        elif isinstance(node, ast.ClassDef):
            class_name = f"{prefix}{node.name}"
            out.add(class_name)
            out.update(_collect_python_symbols(node, prefix=f"{class_name}."))
    return out


def _python_symbol_diff(old_text: str, new_text: str, suffix: str) -> tuple[list[str], list[str]]:
    if suffix not in {".py", ".pyi"}:
        return [], []
    try:
        old_tree = ast.parse(old_text)
        new_tree = ast.parse(new_text)
    except SyntaxError:
        return [], []

    old_symbols = _collect_python_symbols(old_tree)
    new_symbols = _collect_python_symbols(new_tree)
    removed = sorted(old_symbols - new_symbols)
    added = sorted(new_symbols - old_symbols)
    return removed, added


def _audit_pair(
    base_ref: str,
    old_path: str,
    new_path: str,
    repo_root: Path,
    *,
    include_import_lines: bool,
) -> FileAudit:
    old_text = _read_file_at_ref(base_ref, old_path)
    new_abs = repo_root / new_path
    if not new_abs.exists():
        raise FileNotFoundError(f"new path not found: {new_path}")
    new_text = new_abs.read_text(encoding="utf-8")

    removed, added, removed_all, added_all = _iter_functional_removed_added(
        old_path=old_path,
        new_path=new_path,
        old_text=old_text,
        new_text=new_text,
        include_import_lines=include_import_lines,
    )
    matched, suspicious_removed, suspicious_added = _match_same_functional_lines(removed, added)
    suffix = Path(new_path).suffix or Path(old_path).suffix
    removed_symbols, added_symbols = _python_symbol_diff(old_text, new_text, suffix)
    return FileAudit(
        old_path=old_path,
        new_path=new_path,
        old_total_lines=len(old_text.splitlines()),
        new_total_lines=len(new_text.splitlines()),
        removed_total=removed_all,
        added_total=added_all,
        removed_functional=len(removed),
        added_functional=len(added),
        matched_functional=matched,
        suspicious_removed=suspicious_removed,
        suspicious_added=suspicious_added,
        removed_symbols=removed_symbols,
        added_symbols=added_symbols,
    )


def _parse_mapping(raw: str) -> tuple[str, str]:
    parts = raw.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"invalid mapping {raw!r}; expected OLD:NEW")
    old_path = parts[0].strip()
    new_path = parts[1].strip()
    if not old_path or not new_path:
        raise ValueError(f"invalid mapping {raw!r}; OLD and NEW cannot be empty")
    return old_path, new_path


def _print_audit_report(audits: list[FileAudit], show_lines: int) -> None:
    total_removed = sum(len(item.suspicious_removed) for item in audits)
    total_added = sum(len(item.suspicious_added) for item in audits)
    print("=== Functional Migration Diff Audit ===")
    print(f"files: {len(audits)}")
    print(f"suspicious_removed_total: {total_removed}")
    print(f"suspicious_added_total: {total_added}")
    print("")

    for item in audits:
        print(f"[{item.old_path} -> {item.new_path}]")
        print(
            "  old/new lines: "
            f"{item.old_total_lines}/{item.new_total_lines}; "
            f"removed/added: {item.removed_total}/{item.added_total}; "
            "functional removed/added/matched: "
            f"{item.removed_functional}/{item.added_functional}/{item.matched_functional}"
        )
        print(
            "  suspicious removed/added: "
            f"{len(item.suspicious_removed)}/{len(item.suspicious_added)}"
        )
        if item.removed_symbols or item.added_symbols:
            print(
                "  python symbols removed/added: "
                f"{len(item.removed_symbols)}/{len(item.added_symbols)}"
            )
            if item.removed_symbols:
                print(f"  removed symbols: {', '.join(item.removed_symbols[:show_lines])}")
            if item.added_symbols:
                print(f"  added symbols: {', '.join(item.added_symbols[:show_lines])}")
        if item.suspicious_removed:
            print("  removed samples:")
            for line in item.suspicious_removed[:show_lines]:
                print(f"    - {line.path}:{line.line_no}: {line.text}")
        if item.suspicious_added:
            print("  added samples:")
            for line in item.suspicious_added[:show_lines]:
                print(f"    + {line.path}:{line.line_no}: {line.text}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit migration diff to detect potential functional deletions/rewrites."
    )
    parser.add_argument(
        "--base-ref",
        default="HEAD",
        help="Git ref used as pre-migration baseline (default: HEAD).",
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        help="Old/new path mapping: OLD:NEW (repeatable).",
    )
    parser.add_argument(
        "--show-lines",
        type=int,
        default=12,
        help="Max sample lines to print for suspicious removed/added per file.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--fail-on-suspicious-removed",
        action="store_true",
        help="Return non-zero if any suspicious removed functional lines are found.",
    )
    parser.add_argument(
        "--count-import-lines",
        action="store_true",
        help="Include import lines in functional line comparison (default: ignored).",
    )
    args = parser.parse_args()

    mappings = [_parse_mapping(raw) for raw in args.map] if args.map else list(DEFAULT_MAPPINGS)
    repo_root = _repo_root()
    audits: list[FileAudit] = []

    for old_path, new_path in mappings:
        audits.append(
            _audit_pair(
                args.base_ref,
                old_path,
                new_path,
                repo_root,
                include_import_lines=args.count_import_lines,
            )
        )

    _print_audit_report(audits, show_lines=max(1, args.show_lines))

    if args.json_output:
        out_path = Path(args.json_output)
        payload = {"base_ref": args.base_ref, "files": [asdict(item) for item in audits]}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"json report written: {out_path}")

    suspicious_removed_total = sum(len(item.suspicious_removed) for item in audits)
    if args.fail_on_suspicious_removed and suspicious_removed_total > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
