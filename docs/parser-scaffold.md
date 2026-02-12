# PDF Parser Scaffold

用于快速搭建新银行 PDF 解析器的最小流程模板（脚手架 + 测试样例 + golden fixture）。

## 1) 生成脚手架

```bash
uv run python -m tools.scaffold_pdf_parser \
  --mode-id boc \
  --mode-name "中国银行（信用卡/流水）" \
  --kinds boc_credit_card,boc_statement
```

生成内容：

- `openledger/parsers/pdf/<mode_id>.py`：parser 模板（含 `MODE_ID/MODE_NAME/SUPPORTED_KINDS` 等）
- `tests/test_pdf_<mode_id>_golden.py`：golden 测试样例（默认 `@unittest.skip`）
- `tests/fixtures/pdf_parsers/<mode_id>/`：fixture 占位目录
  - `pdf_text/<kind>.txt`
  - `expected/<kind>.csv`
  - `README.md`

## 2) 注册 parser（手动）

在 `openledger/parsers/pdf/__init__.py` 中：

- 导入新 parser 的 `MODE_ID/MODE_NAME/SUPPORTED_KINDS/FILENAME_HINTS/DETECT_SAMPLES`
- 扩展 `PdfParserModeId` / `PdfParserModeIdOrAuto` / `PdfParserKind` / `PdfRow`
- 注册到 `_PARSERS`
- 在 `get_pdf_parser()` 和 `parse_pdf_mode_id()` 里加分支

## 3) 补齐解析逻辑与 fixture

1. 实现 `detect_kind_from_text()` / `extract_rows()`
2. 准备 `pdf_text/<kind>.txt`（以 `---PAGE---` 分页）
3. 生成并校验 `expected/<kind>.csv`
4. 去掉 `tests/test_pdf_<mode_id>_golden.py` 的 `@unittest.skip`

## 4) 运行测试

```bash
uv run python -m unittest tests/test_pdf_<mode_id>_golden.py
uv run python -m unittest discover -s tests
```

## 5) UI 可消费的能力接口

为“数据源支持矩阵”和“解析器健康状态”提供的 API：

- `GET /api/sources/support`
- `GET /api/parsers/pdf/health`
- `GET /api/capabilities`（聚合输出）

