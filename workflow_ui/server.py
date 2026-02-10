from __future__ import annotations

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

from .config import global_classifier_write_path, resolve_global_classifier_config
from .logger import get_logger
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
    # Very small multipart parser (sufficient for local uploads).
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
        # Strip final CRLF
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
            + one_item(out_dir / "credit_card.match.xlsx"),
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
            + one_item(out_dir / "bank.match.xlsx"),
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

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                _send_json(self, 200, get_state(paths))
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
                if file_path.suffix.lower() != ".csv":
                    _send_json(self, 400, {"error": "preview supports csv only"})
                    return

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

            # Static frontend (optional): serve web/dist if present.
            dist = root / "web" / "dist"
            if dist.exists():
                self._serve_static(dist, path)
                return

            self.send_response(200)
            _set_cors(self)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                (
                    "<html><body>"
                    "<h3>OpenLedger server is running.</h3>"
                    "<p>Frontend not built yet. If you use the React UI, run <code>pnpm install</code> and <code>pnpm dev</code> under <code>web/</code>.</p>"
                    "</body></html>"
                ).encode("utf-8")
            )

        def _serve_static(self, dist: Path, url_path: str) -> None:
            rel = url_path.lstrip("/")
            if not rel:
                rel = "index.html"
            target = (dist / rel).resolve()
            try:
                target.relative_to(dist.resolve())
            except Exception:
                self.send_response(404)
                self.end_headers()
                return
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                # SPA fallback
                target = dist / "index.html"
            data = target.read_bytes()
            mime, _ = mimetypes.guess_type(target.name)
            mime = mime or "application/octet-stream"
            self.send_response(200)
            _set_cors(self)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            # Avoid stale UI after rebuilds (local app).
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _handle_post(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/runs":
                paths = create_run(root)
                # Optional name from JSON body.
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
                    "Run created"
                )
                _send_json(self, 200, get_state(paths))
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/upload", path)
            if m:
                run_id = m.group("run_id")
                paths = make_paths(root, run_id)
                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    _send_json(self, 400, {"error": "expected multipart/form-data"})
                    return
                m2 = re.search(r"boundary=(?P<b>[^;]+)", ctype)
                if not m2:
                    _send_json(self, 400, {"error": "missing boundary"})
                    return
                boundary = m2.group("b").encode("utf-8")
                body = _read_request_body(self)
                parts = _parse_multipart(body, boundary)

                saved = []
                for part in parts:
                    filename = part.get("filename") or ""
                    if not filename:
                        continue
                    # Basic filename sanitize
                    filename = filename.replace("/", "_").replace("\\", "_")
                    out = paths.inputs_dir / filename
                    out.write_bytes(part["content"])
                    saved.append(
                        {"name": filename, "path": str(out), "size": out.stat().st_size}
                    )

                state = get_state(paths)
                state["inputs"] = saved
                save_state(paths, state)
                server.logger.bind(run_id=run_id, stage_id="-").info(
                    f"Uploaded files: {len(saved)}"
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
                    f"Run start requested (stages={stages or 'all'})"
                )
                _send_json(self, 200, {"ok": True, "run_id": run_id})
                return

            m = re.fullmatch(r"/api/runs/(?P<run_id>[^/]+)/cancel", path)
            if m:
                run_id = m.group("run_id")
                server.runner.request_cancel(run_id)
                server.logger.bind(run_id=run_id, stage_id="-").warning(
                    "Cancel requested via API"
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
                    f"Reset done (scope={scope})"
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
                    f"Review updated rows={len(update_map)}"
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
                    "Global classifier config updated"
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
                    "Classifier config updated"
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
                    f"Options updated: {payload}"
                )
                _send_json(self, 200, {"ok": True})
                return

            _send_json(self, 404, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            # Quieter server logs for local usage.
            return

    return Handler


def serve(
    root: Path, host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True
) -> None:
    server = WorkflowHTTPServer(root)
    handler = make_handler(server)
    httpd = ThreadingHTTPServer((host, port), handler)

    url = f"http://{host}:{port}"
    server.logger.bind(run_id="-", stage_id="-").info(f"UI server -> {url}")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    httpd.serve_forever()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    host = os.environ.get("AUTO_ACCOUNTING_HOST", "127.0.0.1")
    port = int(os.environ.get("AUTO_ACCOUNTING_PORT", "8000"))
    serve(root=root, host=host, port=port, open_browser=True)


if __name__ == "__main__":
    main()
