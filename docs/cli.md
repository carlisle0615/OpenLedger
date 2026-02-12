# 命令行流水线

适用于手动跑通各阶段、排查阶段产物或做离线调试。  
日常建议优先使用 Web UI（FastAPI + React）执行完整流程，CLI 主要用于开发和排障。

## 推荐顺序

```bash
uv run python -m stages.extract_pdf --mode auto *.pdf
uv run python -m stages.extract_exports
uv run python -m stages.match_credit_card
uv run python -m stages.match_bank
uv run python -m stages.build_unified
node stages/classify_llm.mjs
uv run python -m stages.finalize
```

说明：

- 上述命令默认读写 `output/`；适合本地快速实验。
- 在正式流程中，后端会把每次任务隔离到 `runs/<run_id>/` 下执行。
- 分类阶段默认优先读取 `config/classifier.local.json`，不存在则回退 `config/classifier.json`。

## PDF 解析模式

- `--list-modes`：查看支持的解析器列表
- `--mode cmb`：强制使用“招商银行（信用卡对账单/交易流水）”解析器

## 分类阶段（LLM）

- 分类规则默认在 `config/classifier.json`
- 推荐本地覆盖 `config/classifier.local.json`（避免误提交）
- `lsp` 字段说明见 `docs/lsp.md`
- 首次使用 LSP：在仓库根目录执行 `pnpm install` 安装依赖

## 用户与账期相关能力

用户归档、run 绑定、账期审阅（异常检测/环比同比）属于后端 API 侧聚合能力，
当前不提供独立 CLI 入口，统一通过 Web UI 的“用户”页操作。
