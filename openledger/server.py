from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .capabilities import (
    get_capabilities_payload,
    get_pdf_parser_health,
    list_source_support_matrix,
)
from .config import global_classifier_write_path, resolve_global_classifier_config
from .files import safe_filename
from .logger import get_logger
from .parsers.pdf import list_pdf_modes
from .profiles import (
    add_bill_from_run,
    check_profile_integrity,
    create_profile,
    list_profiles,
    load_profile,
    remove_bills,
    reimport_bill,
    update_profile,
)
from .settings import load_settings
from .state import resolve_under_root
from .workflow import (
    WorkflowRunner,
    create_run,
    get_state,
    list_artifacts,
    list_runs,
    make_paths,
    save_state,
)

_PDF_RENDER_LOCK = threading.Lock()

def _read_request_body(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return b""
    return handler.rfile.read(length)


def _send_json(handler: BaseHTTPRequestHandler, status: int, obj: Any) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    _set_cors(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _set_cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _preview_cache_path(run_dir: Path, rel_path: str, mtime: float, page: int, dpi: int) -> Path:
    key = f"{rel_path}|{mtime:.3f}|{page}|{dpi}".encode("utf-8")
    digest = hashlib.sha1(key).hexdigest()[:16]
    cache_dir = run_dir / "preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"pdf_{digest}_p{page}_d{dpi}.png"


def _preview_xlsx(file_path: Path, limit: int, offset: int) -> dict[str, Any]:
    from openpyxl import load_workbook

    wb = load_workbook(file_path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if header is None:
            return {
                "columns": [],
                "rows": [],
                "offset": offset,
                "limit": limit,
                "has_more": False,
                "next_offset": None,
                "prev_offset": max(offset - limit, 0) if offset > 0 else None,
            }
        columns: list[str] = []
        for i, h in enumerate(header):
            if h is None or str(h).strip() == "":
                columns.append(f"col_{i + 1}")
            else:
                columns.append(str(h))

        rows: list[dict[str, Any]] = []
        has_more = False
        seen = 0
        for row in rows_iter:
            if seen < offset:
                seen += 1
                continue
            if len(rows) >= limit:
                has_more = True
                break
            out: dict[str, Any] = {}
            for i, col in enumerate(columns):
                val = row[i] if i < len(row) else None
                out[col] = "" if val is None else str(val)
            rows.append(out)
            seen += 1
        return {
            "columns": columns,
            "rows": rows,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + limit if has_more else None,
            "prev_offset": max(offset - limit, 0) if offset > 0 else None,
        }
    finally:
        wb.close()


def _count_csv_rows(path: Path, status_key: str = "match_status") -> tuple[int, dict[str, int]]:
    import csv

    if not path.exists() or not path.is_file():
        return 0, {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return 0, {}
        count = 0
        reasons: dict[str, int] = {}
        has_status = status_key in reader.fieldnames
        for row in reader:
            count += 1
            if not has_status:
                continue
            status = str(row.get(status_key, "") or "").strip()
            if not status:
                status = "unknown"
            reasons[status] = reasons.get(status, 0) + 1
    return count, reasons


def _parse_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    raw = _read_request_body(handler)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid json body")


_DISPOSITION_RE = re.compile(
    r'form-data;\s*name="(?P<name>[^"]+)";\s*filename="(?P<filename>[^"]*)"'
)


def _parse_multipart(body: bytes, boundary: bytes) -> list[dict[str, Any]]:
    # 极简 multipart 解析器（满足本地上传场景即可）。
    out: list[dict[str, Any]] = []
    delim = b"--" + boundary
    for part in body.split(delim):
        part = part.strip()
        if not part or part == b"--":
            continue
        if part.startswith(b"\r\n"):
            part = part[2:]
        header_blob, _, content = part.partition(b"\r\n\r\n")
        if not _:
            continue
        headers = {}
        for line in header_blob.split(b"\r\n"):
            if b":" not in line:
                continue
            k, v = line.split(b":", 1)
            headers[k.decode("utf-8", "ignore").strip().lower()] = v.decode(
                "utf-8", "ignore"
            ).strip()
        disp = headers.get("content-disposition", "")
        m = _DISPOSITION_RE.search(disp)
        if not m:
            continue
        name = m.group("name")
        filename = m.group("filename")
        # 去掉末尾 CRLF
        if content.endswith(b"\r\n"):
            content = content[:-2]
        out.append(
            {"name": name, "filename": filename, "content": content, "headers": headers}
        )
    return out


class WorkflowHTTPServer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runner = WorkflowRunner(root)
        self.logger = get_logger()
        self.settings = load_settings()


def _file_item(run_dir: Path, file_path: Path) -> dict[str, Any]:
    try:
        rel = str(file_path.resolve().relative_to(run_dir.resolve()))
    except Exception:
        rel = str(file_path)
    item: dict[str, Any] = {
        "path": rel,
        "name": file_path.name,
        "exists": file_path.exists(),
    }
    if file_path.exists() and file_path.is_file():
        item["size"] = file_path.stat().st_size
    return item


def _stage_io(root: Path, run_id: str, stage_id: str) -> dict[str, Any]:
    paths = make_paths(root, run_id)
    run_dir = paths.run_dir
    inputs_dir = paths.inputs_dir
    out_dir = paths.out_dir
    cfg_dir = paths.config_dir

    def glob_items(base: Path, pattern: str) -> list[dict[str, Any]]:
        return [
            _file_item(run_dir, p) for p in sorted(base.glob(pattern)) if p.is_file()
        ]

    def one_item(p: Path) -> list[dict[str, Any]]:
        return [_file_item(run_dir, p)]

    if stage_id == "extract_pdf":
        return {
            "stage_id": stage_id,
            "inputs": glob_items(inputs_dir, "*.pdf"),
            "outputs": glob_items(out_dir, "*.transactions.csv"),
        }

    if stage_id == "extract_exports":
        return {
            "stage_id": stage_id,
            "inputs": glob_items(inputs_dir, "*.xlsx")
            + glob_items(inputs_dir, "*.csv"),
            "outputs": one_item(out_dir / "wechat.normalized.csv")
            + one_item(out_dir / "alipay.normalized.csv"),
        }

    if stage_id == "match_credit_card":
        cc_candidates = glob_items(out_dir, "*信用卡*.transactions.csv") or glob_items(
            out_dir, "*.transactions.csv"
        )
        cc_csv = cc_candidates[:1]
        return {
            "stage_id": stage_id,
            "inputs": cc_csv
            + one_item(out_dir / "wechat.normalized.csv")
            + one_item(out_dir / "alipay.normalized.csv"),
            "outputs": one_item(out_dir / "credit_card.enriched.csv")
            + one_item(out_dir / "credit_card.unmatched.csv")
            + one_item(out_dir / "credit_card.match.xlsx")
            + one_item(out_dir / "credit_card.match_debug.csv"),
        }

    if stage_id == "match_bank":
        bank_candidates = glob_items(
            out_dir, "*交易流水*.transactions.csv"
        ) or glob_items(out_dir, "*.transactions.csv")
        return {
            "stage_id": stage_id,
            "inputs": bank_candidates
            + one_item(out_dir / "wechat.normalized.csv")
            + one_item(out_dir / "alipay.normalized.csv"),
            "outputs": one_item(out_dir / "bank.enriched.csv")
            + one_item(out_dir / "bank.unmatched.csv")
            + one_item(out_dir / "bank.match.xlsx")
            + one_item(out_dir / "bank.match_debug.csv"),
        }

    if stage_id == "build_unified":
        return {
            "stage_id": stage_id,
            "inputs": one_item(out_dir / "credit_card.enriched.csv")
            + one_item(out_dir / "credit_card.unmatched.csv")
            + one_item(out_dir / "bank.enriched.csv")
            + one_item(out_dir / "bank.unmatched.csv")
            + one_item(out_dir / "wechat.normalized.csv")
            + one_item(out_dir / "alipay.normalized.csv"),
            "outputs": one_item(out_dir / "unified.transactions.csv")
            + one_item(out_dir / "unified.transactions.xlsx")
            + one_item(out_dir / "unified.transactions.all.csv")
            + one_item(out_dir / "unified.transactions.all.xlsx"),
        }

    if stage_id == "classify":
        return {
            "stage_id": stage_id,
            "inputs": one_item(out_dir / "unified.transactions.csv")
            + one_item(cfg_dir / "classifier.json"),
            "outputs": glob_items(out_dir / "classify", "**/*")
            if (out_dir / "classify").exists()
            else [],
        }

    if stage_id == "finalize":
        return {
            "stage_id": stage_id,
            "inputs": one_item(out_dir / "classify" / "unified.with_id.csv")
            + one_item(out_dir / "classify" / "review.csv")
            + one_item(cfg_dir / "classifier.json"),
            "outputs": one_item(out_dir / "unified.transactions.categorized.csv")
            + one_item(out_dir / "unified.transactions.categorized.xlsx")
            + one_item(out_dir / "category.summary.csv")
            + one_item(out_dir / "pending_review.csv"),
        }

    return {"stage_id": stage_id, "inputs": [], "outputs": []}


def make_handler(server: WorkflowHTTPServer):
    root = server.root

    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            _set_cors(self)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            try:
                self._handle_get()
            except Exception as exc:
                _send_json(self, 500, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            try:
                self._handle_post()
            except Exception as exc:
                _send_json(self, 500, {"error": str(exc)})

        def do_PUT(self) -> None:  # noqa: N802
            try:
                self._handle_put()
            except Exception as exc:
                _send_json(self, 500, {"error": str(exc)})

        def _handle_get(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                _send_json(self, 200, {"ok": True})
                return

            if path == "/api/parsers/pdf":
                _send_json(self, 200, {"modes": list_pdf_modes()})
                return

            if path == "/api/parsers/pdf/health":
                _send_json(self, 200, get_pdf_parser_health())
                return

            if path == "/api/sources/support":
                _send_json(self, 200, {"sources": list_source_support_matrix()})
                return

            if path == "/api/capabilities":
                _send_json(self, 200, get_capabilities_payload())
                return

            if path == "/api/config/classifier":
                cfg = resolve_global_classifier_config(root)
                if not cfg.exists():
                    _send_json(self, 404, {"error": "config not found"})
                    return
                _send_json(self, 200, json.loads(cfg.read_text(encoding="utf-8")))
                return

            if path == "/api/runs":
                runs = list_runs(root)
                meta = []
                for run_id in runs:
                    try:
                        paths = make_paths(root, run_id)
                        st = get_state(paths)
                        meta.append(
                            {
                                "id": run_id,
                                "name": str(st.get("name") or "").strip(),
                                "status": str(st.get("status") or "").strip(),
                                "created_at": str(st.get("created_at") or "").strip(),
                            }
                        )
                    except Exception:
                        meta.append({"id": run_id, "name": "", "status": "", "created_at": ""})
                _send_json(self, 200, {"runs": runs, "runs_meta": meta})
                return

            if path == "/api/profiles":
                _send_json(self, 200, {"profiles": list_profiles(root)})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                _send_json(self, 200, get_state(paths))
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)", path)
            if m:
                profile_id = m.group("profile_id")
                try:
                    profile = load_profile(root, profile_id)
                except FileNotFoundError:
                    _send_json(self, 404, {"error": "profile not found"})
                    return
                _send_json(self, 200, profile)
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)/check", path)
            if m:
                profile_id = m.group("profile_id")
                try:
                    result = check_profile_integrity(root, profile_id)
                except FileNotFoundError:
                    _send_json(self, 404, {"error": "profile not found"})
                    return
                _send_json(self, 200, result)
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/artifacts", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                _send_json(self, 200, {"artifacts": list_artifacts(paths)})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/artifact", path)
            if m:
                run_id = m.group("run_id")
                rel = (qs.get("path") or [""])[0]
                if not rel:
                    _send_json(self, 400, {"error": "missing path"})
                    return
                paths = make_paths(root, run_id)
                file_path = resolve_under_root(paths.run_dir, rel)
                if not file_path.exists() or not file_path.is_file():
                    _send_json(self, 404, {"error": "not found"})
                    return
                mime, _ = mimetypes.guess_type(file_path.name)
                mime = mime or "application/octet-stream"
                data = file_path.read_bytes()
                self.send_response(200)
                _set_cors(self)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{file_path.name}"'
                )
                self.end_headers()
                self.wfile.write(data)
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/preview", path)
            if m:
                import csv

                run_id = m.group("run_id")
                rel = (qs.get("path") or [""])[0]
                limit = int((qs.get("limit") or ["50"])[0])
                offset = int((qs.get("offset") or ["0"])[0])
                if not rel:
                    _send_json(self, 400, {"error": "missing path"})
                    return
                paths = make_paths(root, run_id)
                file_path = resolve_under_root(paths.run_dir, rel)
                if not file_path.exists() or not file_path.is_file():
                    _send_json(self, 404, {"error": "not found"})
                    return
                suffix = file_path.suffix.lower()
                if suffix == ".csv":
                    rows: list[dict[str, Any]] = []
                    columns: list[str] = []
                    has_more = False
                    with file_path.open("r", encoding="utf-8", newline="") as f:
                        reader = csv.DictReader(f)
                        columns = list(reader.fieldnames or [])
                        seen = 0
                        for r in reader:
                            if seen < offset:
                                seen += 1
                                continue
                            if len(rows) >= limit:
                                has_more = True
                                break
                            rows.append(r)
                    _send_json(
                        self,
                        200,
                        {
                            "columns": columns,
                            "rows": rows,
                            "offset": offset,
                            "limit": limit,
                            "has_more": has_more,
                            "next_offset": offset + limit if has_more else None,
                            "prev_offset": max(offset - limit, 0) if offset > 0 else None,
                        },
                    )
                    return
                if suffix in {".xlsx", ".xls"}:
                    if suffix == ".xls":
                        _send_json(self, 400, {"error": "preview supports xlsx only"})
                        return
                    data = _preview_xlsx(file_path, limit=limit, offset=offset)
                    _send_json(self, 200, data)
                    return
                _send_json(self, 400, {"error": "preview supports csv/xlsx only"})
                return

            m = re.fullmatch(
                r"/api/runs/(?P<run_id>[^/]+)/logs/(?P<stage_id>[^/]+)", path
            )
            if m:
                run_id = m.group("run_id")
                stage_id = m.group("stage_id")
                paths = make_paths(root, run_id)
                log_path = paths.run_dir / "logs" / f"{stage_id}.log"
                if not log_path.exists():
                    _send_json(self, 404, {"error": "log not found"})
                    return
                text = log_path.read_text(encoding="utf-8", errors="replace")
                _send_json(self, 200, {"text": text})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/config/classifier", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                cfg = paths.config_dir / "classifier.json"
                if not cfg.exists():
                    _send_json(self, 404, {"error": "config not found"})
                    return
                _send_json(self, 200, json.loads(cfg.read_text(encoding="utf-8")))
                return

            m = re.fullmatch(
                r"/api/runs/(?P<run_id>[^/]+)/stages/(?P<stage_id>[^/]+)/io", path
            )
            if m:
                run_id = m.group("run_id")
                stage_id = m.group("stage_id")
                _send_json(
                    self, 200, _stage_io(root=root, run_id=run_id, stage_id=stage_id)
                )
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/stats/match", path)
            if m:
                run_id = m.group("run_id")
                stage_id = (qs.get("stage") or [""])[0]
                if stage_id not in {"match_credit_card", "match_bank"}:
                    _send_json(self, 400, {"error": "stage must be match_credit_card or match_bank"})
                    return
                paths = make_paths(root, run_id)
                if stage_id == "match_credit_card":
                    matched_path = paths.out_dir / "credit_card.enriched.csv"
                    unmatched_path = paths.out_dir / "credit_card.unmatched.csv"
                else:
                    matched_path = paths.out_dir / "bank.enriched.csv"
                    unmatched_path = paths.out_dir / "bank.unmatched.csv"
                matched_count, _ = _count_csv_rows(matched_path)
                unmatched_count, unmatched_reasons = _count_csv_rows(unmatched_path)
                total = matched_count + unmatched_count
                match_rate = round(matched_count / total, 4) if total else 0.0
                reasons_sorted = sorted(unmatched_reasons.items(), key=lambda x: (-x[1], x[0]))
                _send_json(
                    self,
                    200,
                    {
                        "stage_id": stage_id,
                        "matched": matched_count,
                        "unmatched": unmatched_count,
                        "total": total,
                        "match_rate": match_rate,
                        "unmatched_reasons": [{"reason": k, "count": v} for k, v in reasons_sorted],
                    },
                )
                return

            m = re.fullmatch(
                r"/api/runs/(?P<run_id>[^/]+)/preview/pdf/meta", path
            )
            if m:
                from pypdf import PdfReader

                run_id = m.group("run_id")
                rel = (qs.get("path") or [""])[0]
                if not rel:
                    _send_json(self, 400, {"error": "missing path"})
                    return
                paths = make_paths(root, run_id)
                file_path = resolve_under_root(paths.run_dir, rel)
                if not file_path.exists() or not file_path.is_file():
                    _send_json(self, 404, {"error": "not found"})
                    return
                if file_path.suffix.lower() != ".pdf":
                    _send_json(self, 400, {"error": "preview supports pdf only"})
                    return
                reader = PdfReader(str(file_path))
                page_count = len(reader.pages)
                _send_json(self, 200, {"page_count": page_count})
                return

            m = re.fullmatch(
                r"/api/runs/(?P<run_id>[^/]+)/preview/pdf/page", path
            )
            if m:
                import pdfplumber

                run_id = m.group("run_id")
                rel = (qs.get("path") or [""])[0]
                page = int((qs.get("page") or ["1"])[0])
                dpi = int((qs.get("dpi") or ["120"])[0])
                if not rel:
                    _send_json(self, 400, {"error": "missing path"})
                    return
                if dpi < 72:
                    dpi = 72
                if dpi > 200:
                    dpi = 200
                paths = make_paths(root, run_id)
                file_path = resolve_under_root(paths.run_dir, rel)
                if not file_path.exists() or not file_path.is_file():
                    _send_json(self, 404, {"error": "not found"})
                    return
                if file_path.suffix.lower() != ".pdf":
                    _send_json(self, 400, {"error": "preview supports pdf only"})
                    return
                if page < 1:
                    _send_json(self, 400, {"error": "page must be >= 1"})
                    return
                try:
                    mtime = file_path.stat().st_mtime
                    cache_path = _preview_cache_path(paths.run_dir, rel, mtime, page, dpi)
                    with _PDF_RENDER_LOCK:
                        if cache_path.exists():
                            data = cache_path.read_bytes()
                        else:
                            with pdfplumber.open(file_path) as pdf:
                                if page > len(pdf.pages):
                                    _send_json(self, 400, {"error": "page out of range"})
                                    return
                                img = pdf.pages[page - 1].to_image(resolution=dpi).original
                                buf = io.BytesIO()
                                img.save(buf, format="PNG")
                                data = buf.getvalue()
                            cache_path.write_bytes(data)
                except Exception as exc:
                    _send_json(self, 500, {"error": f"pdf render failed: {exc}"})
                    return
                self.send_response(200)
                _set_cors(self)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            self.send_response(200)
            _set_cors(self)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                (
                    "<html><body>"
                    "<h3>OpenLedger server is running.</h3>"
                    "<p>Frontend is not served by this backend. Run <code>pnpm install</code> and <code>pnpm dev</code> under <code>web/</code>.</p>"
                    "</body></html>"
                ).encode("utf-8")
            )

        def _handle_post(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/runs":
                paths = create_run(root)
                # 允许从 JSON body 读取可选 name。
                name = ""
                try:
                    raw = _read_request_body(self)
                    if raw:
                        payload = json.loads(raw.decode("utf-8"))
                        if isinstance(payload, dict):
                            name = str(payload.get("name") or "").strip()
                except Exception:
                    name = ""
                if name:
                    state = get_state(paths)
                    state["name"] = name[:80]
                    save_state(paths, state)
                server.logger.bind(run_id=paths.run_dir.name, stage_id="-").info(
                    "已创建 Run"
                )
                _send_json(self, 200, get_state(paths))
                return

            if path == "/api/profiles":
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "payload must be json object"})
                    return
                name = str(payload.get("name") or "").strip()
                if not name:
                    _send_json(self, 400, {"error": "missing name"})
                    return
                profile = create_profile(root, name)
                _send_json(self, 200, profile)
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)/bills", path)
            if m:
                profile_id = m.group("profile_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "payload must be json object"})
                    return
                run_id = str(payload.get("run_id") or "").strip()
                if not run_id:
                    _send_json(self, 400, {"error": "missing run_id"})
                    return
                try:
                    profile = add_bill_from_run(root, profile_id, run_id)
                except FileNotFoundError:
                    _send_json(self, 404, {"error": "profile or run not found"})
                    return
                except Exception as exc:
                    _send_json(self, 400, {"error": str(exc)})
                    return
                _send_json(self, 200, profile)
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)/bills/remove", path)
            if m:
                profile_id = m.group("profile_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "payload must be json object"})
                    return
                period_key = str(payload.get("period_key") or "").strip()
                run_id = str(payload.get("run_id") or "").strip()
                if not period_key and not run_id:
                    _send_json(self, 400, {"error": "missing period_key or run_id"})
                    return
                try:
                    profile = remove_bills(root, profile_id, period_key=period_key or None, run_id=run_id or None)
                except FileNotFoundError:
                    _send_json(self, 404, {"error": "profile not found"})
                    return
                except Exception as exc:
                    _send_json(self, 400, {"error": str(exc)})
                    return
                _send_json(self, 200, profile)
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)/bills/reimport", path)
            if m:
                profile_id = m.group("profile_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "payload must be json object"})
                    return
                period_key = str(payload.get("period_key") or "").strip()
                run_id = str(payload.get("run_id") or "").strip()
                if not period_key or not run_id:
                    _send_json(self, 400, {"error": "missing period_key or run_id"})
                    return
                try:
                    profile = reimport_bill(root, profile_id, period_key=period_key, run_id=run_id)
                except FileNotFoundError as exc:
                    _send_json(self, 404, {"error": str(exc)})
                    return
                except Exception as exc:
                    _send_json(self, 400, {"error": str(exc)})
                    return
                _send_json(self, 200, profile)
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/upload", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                if not paths.run_dir.exists():
                    _send_json(self, 404, {"error": "run not found"})
                    return

                max_bytes = int(server.settings.max_upload_bytes)
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                if content_length <= 0:
                    _send_json(self, 400, {"error": "missing Content-Length"})
                    return
                if content_length > max_bytes:
                    _send_json(
                        self,
                        413,
                        {
                            "error": "payload too large",
                            "max_upload_bytes": max_bytes,
                            "content_length": content_length,
                        },
                    )
                    return

                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    _send_json(self, 400, {"error": "expected multipart/form-data"})
                    return
                m2 = re.search(r"boundary=(?P<b>[^;]+)", ctype)
                if not m2:
                    _send_json(self, 400, {"error": "missing boundary"})
                    return
                boundary = m2.group("b").strip().strip('"').encode("utf-8")
                body = _read_request_body(self)
                parts = _parse_multipart(body, boundary)

                saved = []
                paths.inputs_dir.mkdir(parents=True, exist_ok=True)

                def pick_unique_name(name: str) -> str:
                    p = paths.inputs_dir / name
                    if not p.exists():
                        return name
                    stem = Path(name).stem
                    suffix = Path(name).suffix
                    for i in range(1, 1000):
                        cand = f"{stem}_{i}{suffix}"
                        if not (paths.inputs_dir / cand).exists():
                            return cand
                    return f"{stem}_{os.getpid()}{suffix}"

                for part in parts:
                    raw_name = part.get("filename") or ""
                    if not raw_name:
                        continue
                    filename = safe_filename(raw_name, default="upload.bin")
                    filename = pick_unique_name(filename)
                    out = paths.inputs_dir / filename
                    out.write_bytes(part["content"])
                    saved.append(
                        {
                            "name": filename,
                            "path": f"inputs/{filename}",
                            "size": out.stat().st_size,
                        }
                    )

                state = get_state(paths)
                state["inputs"] = saved
                save_state(paths, state)
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"已上传文件数: {len(saved)}"
                )
                _send_json(self, 200, {"saved": saved})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/start", path)
            if m:
                run_id = m.group("run_id")
                payload = _parse_json(self)
                stages = payload.get("stages")
                if stages is not None and not isinstance(stages, list):
                    _send_json(self, 400, {"error": "stages must be list"})
                    return
                options = (
                    payload.get("options")
                    if isinstance(payload.get("options"), dict)
                    else {}
                )
                server.runner.start(run_id, stages=stages, options=options)
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"已请求启动 Run（stages={stages or 'all'}）"
                )
                _send_json(self, 200, {"ok": True, "run_id": run_id})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/cancel", path)
            if m:
                run_id = m.group("run_id")
                server.runner.request_cancel(run_id)
                server.logger.bind(run_id=run_id, stage_id="-").warning(
                    "已通过 API 请求取消"
                )
                _send_json(self, 200, {"ok": True})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/reset", path)
            if m:
                run_id = m.group("run_id")
                if server.runner.is_running(run_id):
                    _send_json(self, 409, {"error": "run is running"})
                    return
                payload = _parse_json(self)
                scope = str(payload.get("scope") or "classify").strip()
                paths = make_paths(root, run_id)
                state = get_state(paths)

                if scope == "classify":
                    shutil.rmtree(paths.out_dir / "classify", ignore_errors=True)
                    for p in [
                        paths.out_dir / "unified.transactions.categorized.csv",
                        paths.out_dir / "unified.transactions.categorized.xlsx",
                        paths.out_dir / "category.summary.csv",
                        paths.out_dir / "category.summary.xlsx",
                        paths.out_dir / "pending_review.csv",
                    ]:
                        try:
                            p.unlink()
                        except FileNotFoundError:
                            pass

                    for st in state.get("stages", []):
                        if st.get("id") in {"classify", "finalize"}:
                            st.update(
                                {
                                    "status": "pending",
                                    "started_at": "",
                                    "ended_at": "",
                                    "error": "",
                                }
                            )
                else:
                    _send_json(self, 400, {"error": f"unknown scope: {scope}"})
                    return

                state["status"] = "idle"
                state["current_stage"] = None
                state["cancel_requested"] = False
                save_state(paths, state)
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"重置完成（scope={scope}）"
                )
                _send_json(self, 200, {"ok": True, "scope": scope})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/review/updates", path)
            if m:
                import csv

                run_id = m.group("run_id")
                payload = _parse_json(self)
                updates = payload.get("updates")
                if not isinstance(updates, list):
                    _send_json(self, 400, {"error": "updates must be list"})
                    return

                paths = make_paths(root, run_id)
                review_path = paths.out_dir / "classify" / "review.csv"
                if not review_path.exists():
                    _send_json(self, 404, {"error": "review.csv not found"})
                    return

                update_map: dict[str, dict[str, Any]] = {}
                for u in updates:
                    if not isinstance(u, dict):
                        continue
                    txn_id = str(u.get("txn_id", "")).strip()
                    if not txn_id:
                        continue
                    update_map[txn_id] = u

                tmp_path = review_path.with_suffix(".csv.tmp")
                with review_path.open("r", encoding="utf-8", newline="") as f_in:
                    reader = csv.DictReader(f_in)
                    fieldnames = list(reader.fieldnames or [])
                    if "txn_id" not in fieldnames:
                        _send_json(self, 400, {"error": "review.csv missing txn_id"})
                        return
                    rows = list(reader)

                editable = {
                    "final_category_id",
                    "final_note",
                    "final_ignored",
                    "final_ignore_reason",
                }
                editable = {k for k in editable if k in set(fieldnames)}
                for r in rows:
                    txn_id = str(r.get("txn_id", "")).strip()
                    if txn_id in update_map:
                        u = update_map[txn_id]
                        for k in editable:
                            if k in u and u[k] is not None:
                                r[k] = str(u[k])

                with tmp_path.open("w", encoding="utf-8", newline="") as f_out:
                    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                tmp_path.replace(review_path)

                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"已更新 review.csv 行数={len(update_map)}"
                )
                _send_json(self, 200, {"ok": True, "updated": len(update_map)})
                return

            _send_json(self, 404, {"error": "not found"})

        def _handle_put(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/config/classifier":
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "config must be json object"})
                    return
                cfg = global_classifier_write_path(root)
                cfg.parent.mkdir(parents=True, exist_ok=True)
                cfg.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                server.logger.bind(run_id="-", stage_id="-").info(
                    "已更新全局分类器配置"
                )
                _send_json(self, 200, {"ok": True})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/config/classifier", path)
            if m:
                run_id = m.group("run_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "config must be json object"})
                    return
                paths = make_paths(root, run_id)
                cfg = paths.config_dir / "classifier.json"
                cfg.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    "已更新本次 Run 的分类器配置"
                )
                _send_json(self, 200, {"ok": True})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/options", path)
            if m:
                run_id = m.group("run_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "options must be json object"})
                    return
                paths = make_paths(root, run_id)
                state = get_state(paths)
                state.setdefault("options", {}).update(payload)
                save_state(paths, state)
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"已更新 options: {payload}"
                )
                _send_json(self, 200, {"ok": True})
                return

            m = re.fullmatch(r"/api/profiles/(?P<profile_id>[^/]+)", path)
            if m:
                profile_id = m.group("profile_id")
                payload = _parse_json(self)
                if not isinstance(payload, dict):
                    _send_json(self, 400, {"error": "payload must be json object"})
                    return
                try:
                    profile = update_profile(root, profile_id, payload)
                except FileNotFoundError:
                    _send_json(self, 404, {"error": "profile not found"})
                    return
                _send_json(self, 200, profile)
                return

            _send_json(self, 404, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            # 本地使用时尽量保持安静，避免 http.server 默认日志刷屏。
            return

    return Handler


def serve(
    root: Path, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True
) -> None:
    server = WorkflowHTTPServer(root)
    handler = make_handler(server)
    httpd = ThreadingHTTPServer((host, port), handler)

    url = f"http://{host}:{port}"
    server.logger.bind(run_id="-", stage_id="-").info(f"UI 服务地址 -> {url}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    httpd.serve_forever()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    s = load_settings()
    serve(root=root, host=s.host, port=s.port, open_browser=s.open_browser)


if __name__ == "__main__":
    main()
