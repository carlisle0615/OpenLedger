<div align="center">
  <h1>OpenLedger</h1>
  <p>本地多渠道交叉记账工具：对账单 + 导出明细交叉回填，输出统一交易表与分类结果。</p>
  <p>
    <a href="#特性">特性</a> ·
    <a href="#快速开始">快速开始</a> ·
    <a href="#工作流-ui">工作流 UI</a> ·
    <a href="#命令行流水线">命令行流水线</a> ·
    <a href="#目录结构">目录结构</a> ·
    <a href="#隐私与安全">隐私与安全</a>
  </p>
  <p>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-blue"></a>
    <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/python-3.13%2B-3776AB"></a>
    <a href="https://nodejs.org/"><img alt="Node" src="https://img.shields.io/badge/node-20%2B-339933"></a>
    <a href="https://pnpm.io/"><img alt="pnpm" src="https://img.shields.io/badge/pnpm-9%2B-F69220"></a>
  </p>
</div>

---

## 概览

OpenLedger 采用 **File as State**：你把 PDF/CSV/XLSX 导出放进输入目录，流水线按阶段生成派生产物。
它不依赖任何银行/支付平台 API，所有数据只在本地机器处理。

文档：
- 架构说明：`docs/architecture.md`
- 方案思路：`docs/strategy.zh-CN.md`

## 特性

- 本地处理为主：LLM 分类可选，开启后会联网调用你配置的 LSP
- 结构化流水线：每个阶段都有可追溯的输入、输出与日志
- PDF 解析模式：支持 `auto` 自动识别与扩展解析器
- 多源回填：信用卡/借记卡账单与微信/支付宝明细交叉匹配
- 审核友好：生成 `review.csv` 支持人工修订再汇总

## 快速开始

### 1) 环境准备

```bash
uv sync
```

### 2) 启动 Workflow UI

后端（自动打开 `http://127.0.0.1:8000`）：

```bash
uv run python main.py
```

前端：

```bash
cd web
pnpm install
pnpm dev
```

打开 `http://127.0.0.1:5173`，上传 PDF + 微信/支付宝导出，执行全流程。

### 3) PDF 与导出文件准备

当前适配：
- 微信：`微信支付账单流水文件*.xlsx`
- 支付宝：`支付宝交易明细*.csv`
- 招行信用卡对账单：`*信用卡账单*.pdf`
- 招行交易流水：`招商银行交易流水*.pdf`

## 工作流 UI

UI 支持：
- 上传文件、查看 stage 产物与日志
- 设置 `pdf_mode` / 账期 / 分类模式
- 编辑 `classifier.json`
- 审核 `review.csv` 并生成最终结果

可选：`pnpm build` 后由后端直接托管 `web/dist/`。

## 命令行流水线

推荐顺序：

```bash
uv run python -m stages.extract_pdf --mode auto *.pdf
uv run python -m stages.extract_exports
uv run python -m stages.match_credit_card
uv run python -m stages.match_bank
uv run python -m stages.build_unified
node stages/classify_openrouter.mjs
uv run python -m stages.finalize
```

PDF 解析模式：
- `--list-modes`：查看支持的解析器列表
- `--mode cmb`：强制使用“招商银行（信用卡对账单/交易流水）”解析器

分类阶段：
- 分类规则放在 `config/classifier.json`
- 推荐本地覆盖 `config/classifier.local.json`（避免误提交）
- 需要 `OPENROUTER_API_KEY`（参考 `.env.example`）
- LSP 可自配：默认示例脚本基于 OpenRouter，可替换 `stages/classify_openrouter.mjs` 接入你的 LSP

## 输出产物（摘要）

- `output/*.transactions.csv`：PDF 提取结果
- `output/credit_card.enriched.csv` / `output/bank.enriched.csv`：回填后的明细
- `output/unified.transactions.csv` / `.xlsx`：统一交易表
- `output/unified.transactions.categorized.xlsx`：最终分类结果
- `output/pending_review.csv`：仍需审核的清单

完整产物清单：见 `runs/<run_id>/output/` 与 `runs/<run_id>/logs/`。

## 目录结构

```text
openledger/   后端服务与解析器
stages/       流水线阶段入口（CLI）
tools/        开发/维护工具
web/          前端 UI
docs/         文档
tests/        测试
```

## 开发工具（tools）

```bash
uv run python -m tools.probe_pdf <pdf路径> --max-pages 2 --render-pages 1
uv run python -m tools.probe_inputs --wechat <xlsx> --alipay <csv>
uv run python -m tools.batch_ignore_review_before_date --review <path> --cutoff 2024-01-01
```

## 隐私与安全

本项目会处理 PDF/CSV/XLSX 等账单文件以及派生输出，均可能包含敏感个人信息。请勿将以下内容提交到版本控制或发到 Issue：
- `.env`（密钥）
- `bills/`、`output/`、`runs/`、`tmp/`（账单与产物）
- `config/classifier.local.json`（个人规则）

## 贡献

请阅读 `CONTRIBUTING.md`。

## License

MIT License. 详见 `LICENSE`。
