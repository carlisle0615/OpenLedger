#!/usr/bin/env python3
"""
App.tsx 重构验证脚本

用途：
- 生成 `App.tsx.bak` vs `App.tsx` 的 unified diff（便于逐行查看）
- 做“迁移完整性”启发式检查：旧文件里的 API 路由 / UI 文案 / 样式标记是否仍能在新代码中找到
- 做“行覆盖率”粗检：旧文件的非噪音行是否能在新代码（web/src/**）中找到对应行

注意：
这是静态检查，无法替代真正的交互回归测试；但能快速定位“疑似丢功能/丢样式”的点。
"""

from __future__ import annotations

import argparse
import difflib
import re
from dataclasses import dataclass
from pathlib import Path


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def normalize_line(line: str) -> str:
    return line.strip()


def is_noise_line(line: str) -> bool:
    s = normalize_line(line)
    if not s:
        return True
    if s.startswith("//"):
        return True
    if s.startswith("import "):
        return True
    if s.startswith("export ") and "from" in s:
        return True
    return False


def extract_non_noise_lines(text: str) -> list[str]:
    lines = text.splitlines()
    return [normalize_line(l) for l in lines if not is_noise_line(l)]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.endswith(".bak"):
            continue
        if p.suffix not in {".ts", ".tsx", ".css"}:
            continue
        files.append(p)
    return sorted(files)


def build_corpus(files: list[Path]) -> str:
    parts: list[str] = []
    for p in files:
        try:
            parts.append(read_text(p))
        except UnicodeDecodeError:
            continue
    return "\n\n".join(parts)


def extract_api_paths(text: str) -> list[str]:
    # 粗提取：/api/... 直到引号/空白结束
    raw = re.findall(r"/api/[^\"'\s]+", text)
    # 去掉一些显然的拼接残留
    cleaned = [r.rstrip(")`;,") for r in raw]
    return sorted(set(cleaned))


def extract_hash_fragments(text: str) -> list[str]:
    raw = re.findall(r"#([a-zA-Z0-9_-]{2,})", text)
    return sorted(set(f"#{x}" for x in raw))


def extract_string_literals(text: str) -> list[str]:
    # 近似提取（不解析 TS AST）：足够用于“文案/样式标记”粗检
    out: list[str] = []
    for m in re.finditer(r'"(?:\\.|[^"\\])*"', text):
        out.append(m.group(0)[1:-1])
    for m in re.finditer(r"'(?:\\.|[^'\\])*'", text):
        out.append(m.group(0)[1:-1])
    for m in re.finditer(r"`(?:\\.|[^`\\])*`", text, flags=re.DOTALL):
        s = m.group(0)[1:-1]
        # 跳过超长 multi-line 模板（误报多）
        if "\n" in s and len(s) > 200:
            continue
        out.append(s)
    return out


def extract_ui_strings(text: str) -> list[str]:
    candidates = []
    for s in extract_string_literals(text):
        ss = s.strip()
        if not ss:
            continue
        if len(ss) > 100:
            continue
        if CHINESE_RE.search(ss) or ss in {"Manual Review"}:
            candidates.append(ss)
    # 去重，过滤掉过于“结构化”的噪音
    uniq = sorted(set(candidates))
    uniq = [s for s in uniq if not re.fullmatch(r"[{}()[\];,<>/\\s]+", s)]
    return uniq


def extract_class_markers(text: str) -> list[str]:
    # 提取 className="..." 与 cn("...") 里的字符串，聚合为“样式标记”
    markers: list[str] = []
    for m in re.finditer(r'className="([^"]+)"', text):
        markers.append(m.group(1))
    for m in re.finditer(r'cn\(\s*"([^"]+)"', text):
        markers.append(m.group(1))
    # 只保留包含布局/高亮的关键 token 的长串（更能代表样式是否迁移）
    keep_tokens = {"fixed", "inset-0", "z-50", "bg-muted/30", "bg-amber-50/40", "bg-accent"}
    picked = []
    for s in markers:
        toks = set(s.split())
        if toks & keep_tokens:
            picked.append(s.strip())
    return sorted(set(picked))


@dataclass(frozen=True)
class FeatureCheck:
    name: str
    markers: list[str]


FEATURES: list[FeatureCheck] = [
    FeatureCheck(
        name="Manual Review 全屏弹窗",
        markers=["#review", "fixed inset-0 z-50", "document.body.style.overflow"],
    ),
    FeatureCheck(
        name="批量多选 + 批量应用",
        markers=["reviewSelectedTxnIds", "全选/取消全选", "批量应用"],
    ),
    FeatureCheck(
        name="连续标注 + 快捷键",
        markers=["连续标注", "快捷键", "ArrowDown", "Enter"],
    ),
    FeatureCheck(
        name="不记账低饱和提示",
        markers=["bg-muted/30", "不记账"],
    ),
    FeatureCheck(
        name="快速规则（试运行）",
        markers=["快速规则（试运行）", "regex_category_rules", "ignore_rules", "Use merchant"],
    ),
    FeatureCheck(
        name="配置保存（本次任务/默认）",
        markers=["保存到本次任务", "保存为默认"],
    ),
    FeatureCheck(
        name="文件预览（CSV/Text）",
        markers=["/preview?path=", "csvPreview", "该文件类型暂不支持预览"],
    ),
    FeatureCheck(
        name="工作流启动/取消",
        markers=["/start", "/cancel", "startWorkflow", "cancelRun"],
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify App.tsx refactor completeness.")
    parser.add_argument("--old", type=Path, default=None, help="Old file path (default: web/src/App.tsx.bak)")
    parser.add_argument("--new-app", type=Path, default=None, help="New App.tsx path (default: web/src/App.tsx)")
    parser.add_argument("--new-root", type=Path, default=None, help="New source root to scan (default: web/src)")
    parser.add_argument("--out-dir", type=Path, default=None, help="Output dir (default: output/refactor_verify)")
    parser.add_argument("--max-list", type=int, default=80, help="Max items to list per section.")
    args = parser.parse_args()

    web_dir = Path(__file__).resolve().parent
    repo_root = web_dir.parent
    src_root = web_dir / "src"

    old_path = args.old or (src_root / "App.tsx.bak")
    new_app_path = args.new_app or (src_root / "App.tsx")
    new_root = args.new_root or src_root
    out_dir = args.out_dir or (repo_root / "output" / "refactor_verify")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not old_path.exists():
        raise SystemExit(f"Old file not found: {old_path}")
    if not new_root.exists():
        raise SystemExit(f"New root not found: {new_root}")

    old_text = read_text(old_path)
    new_app_text = read_text(new_app_path) if new_app_path.exists() else ""

    new_files = iter_source_files(new_root)
    new_corpus = build_corpus(new_files)

    # ---------- unified diff ----------
    diff_path = out_dir / "app_unified.diff"
    old_lines = old_text.splitlines(keepends=False)
    new_lines = new_app_text.splitlines(keepends=False)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=str(old_path),
        tofile=str(new_app_path),
        lineterm="",
    )
    diff_path.write_text("\n".join(diff) + "\n", encoding="utf-8")

    # ---------- line coverage ----------
    old_non_noise = set(extract_non_noise_lines(old_text))
    new_non_noise: set[str] = set()
    for p in new_files:
        try:
            new_non_noise.update(extract_non_noise_lines(read_text(p)))
        except UnicodeDecodeError:
            continue

    missing_lines = old_non_noise - new_non_noise
    structural = {
        "{",
        "}",
        "(",
        ")",
        ";",
        "},",
        "],",
        "};",
        ");",
        "),",
        "</>",
        "</div>",
    }
    missing_lines = {l for l in missing_lines if l not in structural and len(l) > 8}

    # ---------- markers ----------
    api_paths = extract_api_paths(old_text)
    missing_api = [p for p in api_paths if p not in new_corpus]

    hashes = extract_hash_fragments(old_text)
    missing_hash = [h for h in hashes if h not in new_corpus]

    ui_strings = extract_ui_strings(old_text)
    missing_ui = [s for s in ui_strings if s not in new_corpus]

    class_markers = extract_class_markers(old_text)
    missing_styles = [s for s in class_markers if s not in new_corpus]

    feature_results = []
    for feat in FEATURES:
        missing = [m for m in feat.markers if m not in new_corpus]
        feature_results.append((feat, missing))

    # ---------- report ----------
    report_path = out_dir / "report.md"
    coverage = 0.0 if not old_non_noise else (1.0 - (len(missing_lines) / len(old_non_noise)))
    lines_old = len(old_text.splitlines())
    lines_new_app = len(new_app_text.splitlines())

    def md_list(items: list[str], maxn: int) -> str:
        if not items:
            return "- (none)\n"
        shown = items[:maxn]
        s = "".join(f"- `{x}`\n" for x in shown)
        if len(items) > maxn:
            s += f"- ... (+{len(items) - maxn} more)\n"
        return s

    report = []
    report.append("# App.tsx Refactor Verify Report\n")
    report.append(f"- old: `{old_path}`\n")
    report.append(f"- new app: `{new_app_path}`\n")
    report.append(f"- scanned: `{new_root}` ({len(new_files)} files)\n")
    report.append(f"- diff: `{diff_path}`\n")
    report.append("\n## Stats\n")
    report.append(f"- old lines: {lines_old}\n")
    report.append(f"- new App.tsx lines: {lines_new_app}\n")
    report.append(f"- non-noise line coverage (heuristic): {coverage:.1%}\n")
    report.append(f"- missing non-noise lines: {len(missing_lines)}\n")

    report.append("\n## Feature Checks (heuristic)\n")
    for feat, missing in feature_results:
        ok = "✅" if not missing else "⚠️"
        report.append(f"- {ok} {feat.name}\n")
        if missing:
            report.append("  - missing markers:\n")
            for m in missing:
                report.append(f"    - `{m}`\n")

    report.append("\n## Missing API Paths (old → new scan)\n")
    report.append(md_list(missing_api, args.max_list))

    report.append("\n## Missing Hash Fragments\n")
    report.append(md_list(missing_hash, args.max_list))

    report.append("\n## Missing UI Strings (Chinese / Manual Review)\n")
    report.append(md_list(missing_ui, args.max_list))

    report.append("\n## Missing Style Markers (className snippets)\n")
    report.append(md_list(missing_styles, args.max_list))

    report.append("\n## Missing Non-noise Lines (sample)\n")
    sample_lines = sorted(missing_lines)[: args.max_list]
    report.append(md_list(sample_lines, args.max_list))

    report_path.write_text("".join(report), encoding="utf-8")

    # ---------- stdout summary ----------
    print("=" * 72)
    print("App.tsx Refactor Verify")
    print("=" * 72)
    print(f"old:      {old_path}")
    print(f"new app:  {new_app_path}")
    print(f"scanned:  {new_root} ({len(new_files)} files)")
    print(f"diff:     {diff_path}")
    print(f"report:   {report_path}")
    print(f"coverage: {coverage:.1%}  missing_lines={len(missing_lines)}")
    if missing_api:
        print(f"missing_api: {len(missing_api)} (see report)")
    if missing_ui:
        print(f"missing_ui:  {len(missing_ui)} (see report)")
    if missing_styles:
        print(f"missing_style_markers: {len(missing_styles)} (see report)")
    print("=" * 72)


if __name__ == "__main__":
    main()
