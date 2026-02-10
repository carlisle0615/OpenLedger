from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import resolve_global_classifier_config
from .logger import get_logger
from .state import (
    DEFAULT_STAGES,
    init_run_state,
    load_json,
    new_run_id,
    safe_rel_path,
    utc_now_iso,
    write_json,
)


@dataclass(frozen=True)
class Paths:
    root: Path
    runs_dir: Path
    run_dir: Path
    inputs_dir: Path
    out_dir: Path
    config_dir: Path


def make_paths(root: Path, run_id: str) -> Paths:
    runs_dir = root / "runs"
    run_dir = runs_dir / run_id
    return Paths(
        root=root,
        runs_dir=runs_dir,
        run_dir=run_dir,
        inputs_dir=run_dir / "inputs",
        out_dir=run_dir / "output",
        config_dir=run_dir / "config",
    )


def state_path(paths: Paths) -> Path:
    return paths.run_dir / "state.json"


def get_state(paths: Paths) -> dict[str, Any]:
    p = state_path(paths)
    if not p.exists():
        return init_run_state(paths.run_dir.name)
    state = load_json(p)
    if not isinstance(state.get("name"), str):
        state["name"] = ""
    opts = state.get("options")
    if not isinstance(opts, dict):
        opts = {}
    opts.setdefault("pdf_mode", "auto")
    opts.setdefault("classify_mode", "llm")
    opts.setdefault("allow_unreviewed", False)
    opts.setdefault("period_year", None)
    opts.setdefault("period_month", None)
    state["options"] = opts
    return state


def save_state(paths: Paths, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now_iso()
    write_json(state_path(paths), state)


def create_run(root: Path) -> Paths:
    run_id = new_run_id()
    paths = make_paths(root, run_id)
    paths.inputs_dir.mkdir(parents=True, exist_ok=True)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    (paths.run_dir / "logs").mkdir(parents=True, exist_ok=True)
    paths.config_dir.mkdir(parents=True, exist_ok=True)

    # 复制基础分类器配置到本次 run，便于在 UI 中做“按 run 调参”。
    base_cfg = resolve_global_classifier_config(root)
    if base_cfg.exists():
        shutil.copyfile(base_cfg, paths.config_dir / "classifier.json")

    save_state(paths, init_run_state(run_id))
    return paths


def list_runs(root: Path) -> list[str]:
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return []
    return sorted([p.name for p in runs_dir.iterdir() if p.is_dir()])


def _set_stage(state: dict[str, Any], stage_id: str, **updates: Any) -> None:
    for s in state.get("stages", []):
        if s.get("id") == stage_id:
            s.update(updates)
            return
    raise KeyError(f"未知 stage_id: {stage_id}")


def _detect_inputs(paths: Paths) -> dict[str, Any]:
    files = [p for p in paths.inputs_dir.iterdir() if p.is_file()]
    pdfs = [p for p in files if p.suffix.lower() == ".pdf"]
    xlsx = [p for p in files if p.suffix.lower() in {".xlsx", ".xls"}]
    csvs = [p for p in files if p.suffix.lower() == ".csv"]

    def pick_name(candidates: list[Path], keywords: list[str]) -> Path | None:
        for kw in keywords:
            for p in candidates:
                if kw in p.name:
                    return p
        return candidates[0] if candidates else None

    wechat = pick_name(xlsx, ["微信", "wechat", "WeChat"])
    alipay = pick_name(csvs, ["支付宝", "alipay", "Alipay"])

    return {
        "pdfs": pdfs,
        "wechat_xlsx": wechat,
        "alipay_csv": alipay,
    }


def _find_extracted_csvs(out_dir: Path) -> dict[str, list[Path]]:
    tx_csvs = sorted(out_dir.glob("*.transactions.csv"))
    if not tx_csvs:
        return {"credit_card": [], "bank": []}

    def header_cols(p: Path) -> set[str]:
        with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            row = next(reader, [])
        return {str(x).strip() for x in row if str(x).strip()}

    cc_required = {"section", "trans_date", "post_date", "description", "amount_rmb", "card_last4"}
    bank_required = {"account_last4", "trans_date", "currency", "amount", "balance", "summary", "counterparty"}

    cc_by_schema: list[Path] = []
    bank_by_schema: list[Path] = []
    unknown: list[Path] = []
    for p in tx_csvs:
        cols = header_cols(p)
        if cc_required.issubset(cols):
            cc_by_schema.append(p)
        elif bank_required.issubset(cols):
            bank_by_schema.append(p)
        else:
            unknown.append(p)

    # 如果能用表头 schema 判别出任意文件类型，则优先信任该结果；
    # 对剩余无法识别的文件再用文件名关键字作为次级提示。
    if cc_by_schema or bank_by_schema:
        cc = list(cc_by_schema)
        bank = list(bank_by_schema)
        for p in unknown:
            if "信用卡" in p.name:
                cc.append(p)
            elif "交易流水" in p.name:
                bank.append(p)
        return {"credit_card": sorted(set(cc)), "bank": sorted(set(bank))}

    # 兜底：schema 全部不匹配（应当很少发生），仅使用文件名关键字。
    cc = [p for p in tx_csvs if "信用卡" in p.name]
    bank = [p for p in tx_csvs if "交易流水" in p.name]
    return {"credit_card": cc, "bank": bank}


def _write_csv_header(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)


def _write_empty_credit_card_outputs(out_dir: Path) -> None:
    base_cols = [
        "source",
        "section",
        "trans_date",
        "post_date",
        "description",
        "amount_rmb",
        "card_last4",
        "original_amount",
        "original_region",
    ]
    matched_extra_cols = [
        "match_status",
        "match_sources",
        "detail_channel",
        "detail_trans_time",
        "detail_trans_date",
        "detail_direction",
        "detail_counterparty",
        "detail_item",
        "detail_pay_method",
        "detail_trade_no",
        "detail_merchant_no",
        "detail_status",
        "detail_category_or_type",
        "detail_remark",
        "match_date_diff_days",
        "match_direction_penalty",
        "match_text_similarity",
    ]
    unmatched_extra_cols = ["match_status", "match_channels_tried"]

    _write_csv_header(out_dir / "credit_card.enriched.csv", base_cols + matched_extra_cols)
    _write_csv_header(out_dir / "credit_card.unmatched.csv", base_cols + unmatched_extra_cols)


def _write_empty_bank_outputs(out_dir: Path) -> None:
    base_cols = [
        "source",
        "account_last4",
        "trans_date",
        "currency",
        "amount",
        "balance",
        "summary",
        "counterparty",
    ]
    extra_cols = [
        "match_status",
        "match_sources",
        "detail_channel",
        "detail_trans_time",
        "detail_trans_date",
        "detail_direction",
        "detail_counterparty",
        "detail_item",
        "detail_pay_method",
        "detail_trade_no",
        "detail_merchant_no",
        "detail_status",
        "detail_category_or_type",
        "detail_remark",
        "match_date_diff_days",
        "match_direction_penalty",
        "match_text_similarity",
    ]

    _write_csv_header(out_dir / "bank.enriched.csv", base_cols + extra_cols)
    _write_csv_header(out_dir / "bank.unmatched.csv", base_cols + ["match_status"])


def _write_empty_export_outputs(out_dir: Path) -> None:
    wechat_cols = [
        "channel",
        "trans_time",
        "trans_date",
        "trans_type",
        "counterparty",
        "item",
        "direction",
        "amount",
        "pay_method",
        "status",
        "trade_no",
        "merchant_no",
        "remark",
    ]
    alipay_cols = [
        "channel",
        "trans_time",
        "trans_date",
        "category",
        "counterparty",
        "counterparty_account",
        "item",
        "direction",
        "amount",
        "pay_method",
        "status",
        "trade_no",
        "merchant_no",
        "remark",
    ]
    _write_csv_header(out_dir / "wechat.normalized.csv", wechat_cols)
    _write_csv_header(out_dir / "alipay.normalized.csv", alipay_cols)


def _run_cmd(
    cmd: list[str],
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
    **kwargs,
) -> int:
    logger = kwargs.get("logger")
    if logger:
        logger.info(f"执行命令: {' '.join(cmd)}")
    else:
        print(f"执行命令: {' '.join(cmd)}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        cmd_line = "$ " + " ".join(cmd)
        f.write(cmd_line + "\n\n")
        f.flush()
        if logger is not None:
            logger.info(cmd_line)

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            f.write(line)
            f.flush()
            if logger is not None:
                logger.debug(line.rstrip("\n"))
        return proc.wait()


class WorkflowRunner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._logger = get_logger()

    def is_running(self, run_id: str) -> bool:
        with self._lock:
            t = self._threads.get(run_id)
            return bool(t and t.is_alive())

    def request_cancel(self, run_id: str) -> None:
        paths = make_paths(self.root, run_id)
        state = get_state(paths)
        state["cancel_requested"] = True
        save_state(paths, state)
        self._logger.bind(run_id=run_id, stage_id="-").warning("已请求取消")

    def start(
        self,
        run_id: str,
        stages: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        if stages is None:
            stages = [s.id for s in DEFAULT_STAGES]
        options = options or {}

        with self._lock:
            t = self._threads.get(run_id)
            if t and t.is_alive():
                return
            thread = threading.Thread(
                target=self._run, args=(run_id, stages, options), daemon=True
            )
            self._threads[run_id] = thread
            thread.start()
            self._logger.bind(run_id=run_id, stage_id="-").info(
                f"工作流已启动（stages={stages}）"
            )

    def _run(self, run_id: str, stages: list[str], options: dict[str, Any]) -> None:
        paths = make_paths(self.root, run_id)
        stage_name = {s.id: s.name for s in DEFAULT_STAGES}
        run_logger = self._logger.bind(run_id=run_id, stage_id="-")
        state = get_state(paths)
        state["status"] = "running"
        state["cancel_requested"] = False
        state["current_stage"] = None
        # 合并 options（UI 传入的 options 允许覆盖 state.json 中已有值）。
        state_opts = state.get("options", {})
        if not isinstance(state_opts, dict):
            state_opts = {}
        # 允许显式传入 null 用于清空筛选条件等。
        state_opts.update(options)
        state["options"] = state_opts
        save_state(paths, state)

        for stage_id in stages:
            state = get_state(paths)
            if state.get("cancel_requested"):
                state["status"] = "canceled"
                save_state(paths, state)
                run_logger.warning("工作流已取消")
                return

            _set_stage(
                state,
                stage_id,
                status="running",
                started_at=utc_now_iso(),
                ended_at="",
                error="",
            )
            state["current_stage"] = stage_id
            save_state(paths, state)

            st_logger = self._logger.bind(run_id=run_id, stage_id=stage_id)
            st_logger.info(f"阶段开始: {stage_name.get(stage_id, stage_id)}")
            try:
                exit_code = self._run_stage(paths, stage_id, state.get("options", {}))
            except Exception as exc:
                exit_code = 1
                _set_stage(
                    state,
                    stage_id,
                    status="failed",
                    ended_at=utc_now_iso(),
                    error=str(exc),
                )
                state["status"] = "failed"
                state["current_stage"] = stage_id
                save_state(paths, state)
                st_logger.error(f"阶段失败: {exc}")
                return

            if exit_code != 0:
                state = get_state(paths)
                if stage_id == "finalize":
                    pending_path = paths.out_dir / "pending_review.csv"
                    needs_review = pending_path.exists()
                    if needs_review:
                        rel_pending = safe_rel_path(paths.run_dir, pending_path)
                        _set_stage(
                            state,
                            stage_id,
                            status="needs_review",
                            ended_at=utc_now_iso(),
                            error=f"需要人工审核: {rel_pending}",
                        )
                        state["status"] = "needs_review"
                        state["current_stage"] = stage_id
                        save_state(paths, state)
                        st_logger.warning(f"需要人工审核: {rel_pending}")
                        return

                _set_stage(
                    state,
                    stage_id,
                    status="failed",
                    ended_at=utc_now_iso(),
                    error=f"exit_code={exit_code}",
                )
                state["status"] = "failed"
                state["current_stage"] = stage_id
                save_state(paths, state)
                st_logger.error(f"阶段失败: exit_code={exit_code}")
                return

            state = get_state(paths)
            _set_stage(
                state, stage_id, status="succeeded", ended_at=utc_now_iso(), error=""
            )
            save_state(paths, state)
            st_logger.info("阶段成功")

        state = get_state(paths)
        state["status"] = "succeeded"
        state["current_stage"] = None
        save_state(paths, state)
        run_logger.info("工作流成功")

    def _run_stage(self, paths: Paths, stage_id: str, options: dict[str, Any]) -> int:
        log_path = paths.run_dir / "logs" / f"{stage_id}.log"
        env = os.environ.copy()

        inputs = _detect_inputs(paths)
        extracted = _find_extracted_csvs(paths.out_dir)

        py = sys.executable
        root = paths.root
        st_logger = self._logger.bind(run_id=paths.run_dir.name, stage_id=stage_id)

        if stage_id == "extract_pdf":
            pdfs: list[Path] = inputs["pdfs"]
            if not pdfs:
                raise RuntimeError("未上传 PDF 文件。")
            pdf_mode = (str(options.get("pdf_mode") or "auto").strip() or "auto").lower()
            cmd = [
                py,
                "-u",
                "-m",
                "stages.extract_pdf",
                "--out-dir",
                str(paths.out_dir),
                "--mode",
                pdf_mode,
            ]
            cmd.extend([str(p) for p in pdfs])
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        if stage_id == "extract_exports":
            wechat: Path | None = inputs["wechat_xlsx"]
            alipay: Path | None = inputs["alipay_csv"]
            if not wechat and not alipay:
                _write_empty_export_outputs(paths.out_dir)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("w", encoding="utf-8") as f:
                    f.write("[extract_exports] 缺少微信 xlsx 和支付宝 csv，已跳过。\n")
                st_logger.warning("缺少微信 xlsx 和支付宝 csv，已跳过 extract_exports。")
                return 0
            cmd = [
                py,
                "-u",
                "-m",
                "stages.extract_exports",
                "--out-dir",
                str(paths.out_dir),
            ]
            if wechat:
                cmd.extend(["--wechat", str(wechat)])
            if alipay:
                cmd.extend(["--alipay", str(alipay)])
            st_logger.info(f"日志文件: {log_path}")
            exit_code = _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)
            # 确保下游阶段始终能读取到标准化 CSV（即使导出文件缺失/解析失败）。
            if not (paths.out_dir / "wechat.normalized.csv").exists() or not (paths.out_dir / "alipay.normalized.csv").exists():
                _write_empty_export_outputs(paths.out_dir)
            return exit_code

        if stage_id == "match_credit_card":
            cc_csvs: list[Path] = extracted["credit_card"]
            if not cc_csvs:
                _write_empty_credit_card_outputs(paths.out_dir)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("w", encoding="utf-8") as f:
                    f.write("[match_credit_card] 未找到信用卡账单 CSV，已跳过。\n")
                st_logger.warning("未找到信用卡账单 CSV，已跳过 match_credit_card。")
                return 0
            cc_csv = cc_csvs[0]
            cmd = [
                py,
                "-u",
                "-m",
                "stages.match_credit_card",
                "--credit-card",
                str(cc_csv),
                "--wechat",
                str(paths.out_dir / "wechat.normalized.csv"),
                "--alipay",
                str(paths.out_dir / "alipay.normalized.csv"),
                "--out-dir",
                str(paths.out_dir),
            ]
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        if stage_id == "match_bank":
            bank_csvs: list[Path] = extracted["bank"]
            if not bank_csvs:
                _write_empty_bank_outputs(paths.out_dir)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("w", encoding="utf-8") as f:
                    f.write("[match_bank] 未找到借记卡流水 CSV，已跳过。\n")
                st_logger.warning("未找到借记卡流水 CSV，已跳过 match_bank。")
                return 0
            cmd = [
                py,
                "-u",
                "-m",
                "stages.match_bank",
                "--wechat",
                str(paths.out_dir / "wechat.normalized.csv"),
                "--alipay",
                str(paths.out_dir / "alipay.normalized.csv"),
                "--out-dir",
                str(paths.out_dir),
            ]
            cmd.extend([str(p) for p in bank_csvs])
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        if stage_id == "build_unified":
            cmd = [
                py,
                "-u",
                "-m",
                "stages.build_unified",
                "--out-dir",
                str(paths.out_dir),
                "--cc-enriched",
                str(paths.out_dir / "credit_card.enriched.csv"),
                "--cc-unmatched",
                str(paths.out_dir / "credit_card.unmatched.csv"),
                "--bank-enriched",
                str(paths.out_dir / "bank.enriched.csv"),
                "--bank-unmatched",
                str(paths.out_dir / "bank.unmatched.csv"),
                "--wechat",
                str(paths.out_dir / "wechat.normalized.csv"),
                "--alipay",
                str(paths.out_dir / "alipay.normalized.csv"),
            ]
            period_year = options.get("period_year")
            period_month = options.get("period_month")
            if period_year and period_month:
                cmd.extend(["--period-year", str(period_year), "--period-month", str(period_month)])
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        if stage_id == "classify":
            cfg = paths.config_dir / "classifier.json"
            if not cfg.exists():
                raise RuntimeError(
                    "缺少分类器配置：runs/<run_id>/config/classifier.json"
                )
            classify_out = paths.out_dir / "classify"
            classify_out.mkdir(parents=True, exist_ok=True)
            cmd = [
                "node",
                str(root / "stages" / "classify_openrouter.mjs"),
                "--input",
                str(paths.out_dir / "unified.transactions.csv"),
                "--out-dir",
                str(classify_out),
                "--config",
                str(cfg),
            ]
            if options.get("classify_mode") == "dry_run":
                cmd.append("--dry-run")
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        if stage_id == "finalize":
            cfg = paths.config_dir / "classifier.json"
            cmd = [
                py,
                "-u",
                "-m",
                "stages.finalize",
                "--config",
                str(cfg),
                "--unified-with-id",
                str(paths.out_dir / "classify" / "unified.with_id.csv"),
                "--review",
                str(paths.out_dir / "classify" / "review.csv"),
                "--out-dir",
                str(paths.out_dir),
            ]
            if options.get("allow_unreviewed"):
                cmd.append("--allow-unreviewed")
            st_logger.info(f"日志文件: {log_path}")
            return _run_cmd(cmd, cwd=root, log_path=log_path, env=env, logger=st_logger)

        raise KeyError(f"未知 stage_id: {stage_id}")


def list_artifacts(paths: Paths) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if not paths.out_dir.exists():
        return artifacts
    for p in sorted(paths.out_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = safe_rel_path(paths.run_dir, p)
        artifacts.append(
            {
                "path": rel,
                "name": p.name,
                "size": p.stat().st_size,
            }
        )
    return artifacts
