from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str  # ERROR | WARN
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Finding:
    file_path: str
    line_no: int
    severity: str
    rule_id: str
    message: str
    excerpt: str

    def render(self) -> str:
        return (
            f"{self.file_path}:{self.line_no} [{self.severity}] {self.rule_id} - "
            f"{self.message}\n    {self.excerpt.strip()}"
        )


ERROR_RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="openai_like_key",
        severity="ERROR",
        pattern=re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        message="疑似 OpenAI/OpenRouter 类密钥",
    ),
    Rule(
        rule_id="aws_access_key",
        severity="ERROR",
        pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        message="疑似 AWS Access Key",
    ),
    Rule(
        rule_id="private_key_block",
        severity="ERROR",
        pattern=re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        message="疑似私钥内容",
    ),
    Rule(
        rule_id="bearer_token",
        severity="ERROR",
        pattern=re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}\b"),
        message="疑似 Bearer Token",
    ),
    Rule(
        rule_id="api_key_assignment",
        severity="ERROR",
        pattern=re.compile(
            r"(?i)\b(?:openai|openrouter|deepseek|alibaba|moonshot|minimax)[_-]?api[_-]?key\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{16,}['\"]?"
        ),
        message="疑似真实 API Key 赋值",
    ),
    Rule(
        rule_id="cn_phone_number",
        severity="ERROR",
        pattern=re.compile(r"(?i)(?:phone|mobile|手机号|电话|tel)[^\n]{0,24}(?<!\d)1[3-9]\d{9}(?!\d)"),
        message="疑似手机号",
    ),
    Rule(
        rule_id="cn_id_number",
        severity="ERROR",
        pattern=re.compile(
            r"(?i)(?:身份证(?:号)?|identity(?:_?number)?|id[_ -]?card|id[_ -]?number)"
            r"[^\n]{0,24}(?<!\d)\d{17}[0-9Xx](?!\d)"
        ),
        message="疑似身份证号",
    ),
    Rule(
        rule_id="bank_card_number",
        severity="ERROR",
        pattern=re.compile(
            r"(?i)(?:card(?:_?number)?|account(?:_?number)?|bank\s*account|银行卡|卡号|账号)"
            r"[^\n]{0,32}(?<!\d)\d{12,19}(?!\d)"
        ),
        message="疑似银行卡号/账户号",
    ),
    Rule(
        rule_id="email",
        severity="ERROR",
        pattern=re.compile(
            r"\b(?P<local>[A-Za-z0-9._%+-]+)@(?P<domain>[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
        ),
        message="疑似邮箱地址",
    ),
)

WARN_RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="card_last4_literal",
        severity="WARN",
        pattern=re.compile(
            r"(?i)\b(?:account_last4|card_last4)\b[^\n]{0,80}['\"]\d{4}['\"]"
        ),  # privacy-guard: allow
        message="出现卡尾号字面值，请确认已脱敏",
    ),
    Rule(
        rule_id="pay_method_last4_literal",
        severity="WARN",
        pattern=re.compile(r"(?:信用卡|储蓄卡|Debit|CreditCard)\(\d{4}\)"),  # privacy-guard: allow
        message="支付方式中出现卡尾号，请确认已脱敏",
    ),
    Rule(
        rule_id="region_literal",
        severity="WARN",
        pattern=re.compile(
            r"(?i)\boriginal_region\b[^\n]{0,60}['\"][A-Z]{2,3}['\"]"
        ),  # privacy-guard: allow
        message="出现地区码字面值，请确认是否为匿名占位",
    ),
    Rule(
        rule_id="geo_keyword",
        severity="WARN",
        pattern=re.compile(
            r"北京|上海|杭州|厦门|深圳|广州|南京|苏州|成都|武汉|重庆|西安|天津|宁波|福州|青岛|省直单位|住房公积金"  # privacy-guard: allow
        ),  # privacy-guard: allow
        message="出现地理/机构关键词，请确认已匿名化",
    ),
)


PLACEHOLDER_HINTS = (
    "your_key",
    "example",
    "sample",
    "dummy",
    "placeholder",
    "changeme",
    "mock",
)
ALLOWLIST_EMAIL_DOMAINS = {"example.com", "example.org", "test.com", "local"}
INLINE_ALLOW_TOKEN = "privacy-guard: allow"
ALL_MODE_SKIP_FILES = {
    "uv.lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
}


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _load_user_ignores(root: Path) -> tuple[re.Pattern[str], ...]:
    ignore_file = root / ".privacy-guard-ignore"
    if not ignore_file.exists():
        return ()
    patterns: list[re.Pattern[str]] = []
    for raw in ignore_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(re.compile(line))
    return tuple(patterns)


def _is_placeholder(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in PLACEHOLDER_HINTS)


def _iter_staged_added_lines() -> Iterator[tuple[str, int, str]]:
    diff = _run_git(["diff", "--cached", "--unified=0", "--no-color", "--diff-filter=ACMRTUXB"])
    current_file = ""
    current_line = 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            current_line = int(match.group(1)) if match else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if current_file:
                yield current_file, current_line, raw[1:]
            current_line += 1
            continue
        if raw.startswith(" "):
            current_line += 1


def _iter_all_tracked_lines() -> Iterator[tuple[str, int, str]]:
    tracked = _run_git(["ls-files"]).splitlines()
    for file_path in tracked:
        if file_path in ALL_MODE_SKIP_FILES:
            continue
        path = Path(file_path)
        if not path.exists() or path.is_dir():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for idx, line in enumerate(content.splitlines(), start=1):
            yield file_path, idx, line


def _should_ignore_line(file_path: str, line: str, ignores: Iterable[re.Pattern[str]]) -> bool:
    if INLINE_ALLOW_TOKEN in line:
        return True
    text = f"{file_path}:{line}"
    return any(p.search(text) for p in ignores)


def _should_ignore_match(rule: Rule, line: str, match: re.Match[str]) -> bool:
    if _is_placeholder(line):
        return True
    if rule.rule_id == "email":
        domain = match.group("domain").lower()
        local = match.group("local").lower()
        if domain in ALLOWLIST_EMAIL_DOMAINS:
            return True
        if local.startswith(("sample_", "test_", "dummy_", "mock_")):
            return True
    return False


def _scan_lines(
    lines: Iterable[tuple[str, int, str]],
    ignores: Iterable[re.Pattern[str]],
    errors_only: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    rules = ERROR_RULES if errors_only else ERROR_RULES + WARN_RULES
    for file_path, line_no, line in lines:
        if _should_ignore_line(file_path, line, ignores):
            continue
        for rule in rules:
            match = rule.pattern.search(line)
            if not match:
                continue
            if _should_ignore_match(rule, line, match):
                continue
            findings.append(
                Finding(
                    file_path=file_path,
                    line_no=line_no,
                    severity=rule.severity,
                    rule_id=rule.rule_id,
                    message=rule.message,
                    excerpt=line,
                )
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect potential privacy/sensitive data before commit.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="Scan staged added lines only (for pre-commit).")
    mode.add_argument("--all", action="store_true", help="Scan all tracked files (for CI).")
    parser.add_argument("--fail-on-warn", action="store_true", help="Treat WARN as blocking.")
    parser.add_argument("--errors-only", action="store_true", help="Only evaluate ERROR rules.")
    args = parser.parse_args()

    root = Path(_run_git(["rev-parse", "--show-toplevel"]).strip())
    ignores = _load_user_ignores(root)

    scan_staged = args.staged or not args.all
    lines = _iter_staged_added_lines() if scan_staged else _iter_all_tracked_lines()
    findings = _scan_lines(lines, ignores, errors_only=args.errors_only)

    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]

    if not findings:
        target = "staged changes" if scan_staged else "tracked files"
        print(f"[privacy-guard] OK: no findings in {target}.")
        return 0

    print("[privacy-guard] Findings:")
    for finding in findings:
        print(f" - {finding.render()}")

    if errors:
        print(f"[privacy-guard] BLOCKED: {len(errors)} error finding(s).")
        return 1
    if args.fail_on_warn and warns:
        print(f"[privacy-guard] BLOCKED: {len(warns)} warning finding(s), strict mode enabled.")
        return 1

    print(
        f"[privacy-guard] WARN ONLY: {len(warns)} warning finding(s). "
        "Commit allowed. Use --fail-on-warn for strict mode."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
