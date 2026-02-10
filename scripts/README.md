# Scripts（流水线阶段）

本目录的脚本是 OpenLedger 的“后端处理流水线”。它们遵循 **File as State**：

- 输入：用户导出的 PDF/CSV/XLSX（通常在 `runs/<run_id>/inputs/`）
- 输出：每个阶段生成的派生文件（通常在 `runs/<run_id>/output/`，或手动模式下的 `output/`）

## 约定（面向贡献者）

- 统一参数：尽量提供 `--out-dir`，所有产物只写入该目录。
- 统一日志：尽量使用 `scripts/_common.py` 的 `log(stage, msg)` 打印形如 `[stage] ...` 的日志，便于 UI/CI/用户定位问题。
- 纯函数思维：脚本尽量避免修改输入文件；必要的“缓存/中间态”也写入 `--out-dir` 下。

## Stage 对应脚本

- `extract_pdf` -> `extract_pdf_transactions.py`
- `extract_exports` -> `extract_payment_exports.py`
- `match_credit_card` -> `match_credit_card_details.py`
- `match_bank` -> `match_bank_statement_details.py`
- `build_unified` -> `build_unified_output.py`
- `classify` -> `classify_unified_openrouter.mjs`
- `finalize` -> `finalize_classification.py`

## extract_pdf：PDF 解析模式（mode）

`extract_pdf_transactions.py` 支持可插拔解析器，并提供 `auto` 自动识别：

- 默认：`--mode auto`（对每个 PDF 读取第一页文本并自动选择解析器）
- 指定解析器：`--mode <mode_id>`（例如 `--mode cmb`）
- 查看支持列表：`--list-modes`
- 严格失败：任意 PDF 无法识别或解析异常，脚本会返回非 0（exit_code=2）以触发工作流阶段失败

### 如何新增一个银行解析器（贡献者）

1) 新增模块：`openledger/parsers/pdf/<mode_id>.py`
2) 导出常量：`MODE_ID`、`MODE_NAME`
3) 实现函数：
- `detect_kind_from_text(first_page_text) -> kind | None`
- `extract_rows(pdf_path, kind) -> list[dict]`（输出 schema 与现有 CSV 保持一致）
4) 在 `openledger/parsers/pdf/__init__.py` 注册到 `iter_pdf_parsers()`
5) 本地验证：`uv run python scripts/extract_pdf_transactions.py --list-modes`

## 手动跑通（示例）

默认写到根目录的 `output/`：

```bash
uv run python scripts/extract_pdf_transactions.py *.pdf
uv run python scripts/extract_payment_exports.py
uv run python scripts/match_credit_card_details.py
uv run python scripts/match_bank_statement_details.py
uv run python scripts/build_unified_output.py
node scripts/classify_unified_openrouter.mjs
uv run python scripts/finalize_classification.py
```

跑指定 run 目录（与 Workflow UI 一致）：

```bash
RUN=runs/<run_id>
uv run python scripts/extract_pdf_transactions.py --out-dir "$RUN/output" "$RUN/inputs"/*.pdf
uv run python scripts/extract_payment_exports.py --out-dir "$RUN/output" --wechat "$RUN/inputs/wechat.xlsx" --alipay "$RUN/inputs/alipay.csv"
uv run python scripts/match_credit_card_details.py --out-dir "$RUN/output" --credit-card "$RUN/output/<cc>.transactions.csv" --wechat "$RUN/output/wechat.normalized.csv" --alipay "$RUN/output/alipay.normalized.csv"
uv run python scripts/match_bank_statement_details.py --out-dir "$RUN/output" --wechat "$RUN/output/wechat.normalized.csv" --alipay "$RUN/output/alipay.normalized.csv" "$RUN/output/"*.transactions.csv
uv run python scripts/build_unified_output.py --out-dir "$RUN/output" --wechat "$RUN/output/wechat.normalized.csv" --alipay "$RUN/output/alipay.normalized.csv"
node scripts/classify_unified_openrouter.mjs --input "$RUN/output/unified.transactions.csv" --out-dir "$RUN/output/classify" --config "$RUN/config/classifier.json"
uv run python scripts/finalize_classification.py --config "$RUN/config/classifier.json" --unified-with-id "$RUN/output/classify/unified.with_id.csv" --review "$RUN/output/classify/review.csv" --out-dir "$RUN/output"
```
