## OpenLedger（本地多渠道交叉记账小工具）

目标：把「招行信用卡账单里的 财付通/支付宝」用微信/支付宝导出明细回填成更细的商户/商品描述，并输出匹配结果与未匹配清单。

### 隐私与安全（重要）

本项目会处理 PDF/CSV/XLSX 等账单文件以及派生输出，均可能包含敏感个人信息。请勿将以下内容提交到版本控制或发到 Issue：
- `.env`（密钥）
- `bills/`、`output/`、`runs/`、`tmp/`（账单与产物）
- `config/classifier.local.json`（个人规则）

### 文档

- 架构说明：`docs/architecture.md`
- 方案思路：`docs/strategy.zh-CN.md`

### 推荐：Workflow UI（导入/查看每阶段输出/审核）

1) 启动后端（会自动打开浏览器到 `http://127.0.0.1:8000`）：

```bash
uv run python main.py
```

2) 启动前端（pnpm）：

```bash
cd web
pnpm install
pnpm dev
```

打开 `http://127.0.0.1:5173`，在页面里：
- 上传 PDF + 微信 xlsx + 支付宝 csv
- 一键跑全流程（每个 stage 都会留下日志和产物）
- 选择「账单月份」筛选周期（信用卡周期：上月 21 ~ 本月 20）
- 编辑 `classifier.json`（规则/分类列表/批大小等；建议用 `config/classifier.local.json` 做本地覆盖，避免误提交）
- 审核 `review.csv`（可直接在页面里改 `final_category_id` / `final_ignored`）
- 生成最终明细 + 聚合汇总

> 可选：如果你不想开 `pnpm dev`，可以 `pnpm build` 生成静态资源后，直接用后端 `http://127.0.0.1:8000` 访问（后端会自动托管 `web/dist/`）。
>
> 调整了 `ignore_rules` / `regex_category_rules` 后，建议在 UI 里点「重置分类产物」再重新跑 `classify`，确保新规则生效。
>
> 后端会用 `loguru`（若未安装会降级为简单输出）打印当前执行到哪个 stage；可用 `OPENLEDGER_LOG_LEVEL=DEBUG` 提升日志详细度。

### 环境

- Python：3.13（本项目用 `uv` 管理，已生成 `.python-version` 与 `uv.lock`）
- 依赖安装：

```bash
uv sync
```

### 把导出文件放到项目根目录

当前脚本已对以下导出格式做了适配：

- 微信：`微信支付账单流水文件*.xlsx`
- 支付宝：`支付宝交易明细*.csv`
- 招行信用卡对账单：`*信用卡账单*.pdf`
- 招行交易流水：`招商银行交易流水*.pdf`

### 快速跑通（推荐顺序）

1) **提取 PDF 交易明细**（信用卡 + 交易流水）

```bash
uv run python scripts/extract_pdf_transactions.py --mode auto *.pdf
```

可选：
- `--list-modes`：查看当前支持的 PDF 解析器模式
- `--mode cmb`：强制使用“招商银行（信用卡对账单/交易流水）”解析器

2) **解析并标准化微信/支付宝导出**

```bash
uv run python scripts/extract_payment_exports.py
```

3) **信用卡账单 ↔ 微信/支付宝 明细匹配回填**

```bash
uv run python scripts/match_credit_card_details.py
```

4) **借记卡流水 ↔ 微信/支付宝 明细匹配回填（含退款）**

```bash
uv run python scripts/match_bank_statement_details.py
```

5) **生成统一抽象字段输出（单文件）**

```bash
uv run python scripts/build_unified_output.py
```

6) **LLM 分类（可配置，支持批处理 + 人工复核）**

先在 `config/classifier.json` 配好分类列表（可改 `model` / `batch_size` / `prompt_columns` 等）。如果存在 `config/classifier.local.json`，脚本与 Workflow UI 会优先读取它作为本地覆盖（推荐把你的个人规则放这里，避免误提交）。
并确保环境变量里有 `OPENROUTER_API_KEY`（可用根目录 `.env` 加载，但不要提交；参考 `.env.example`）。
支持 `max_concurrency` 并行调用（最多 10 个请求同时进行）。

运行分类（默认 `batch_size=10`）：

```bash
node scripts/classify_unified_openrouter.mjs
```

分类脚本会生成：
- `output/classify/suggestions.jsonl`：中间态（每条交易的分类建议）
- `output/classify/review.csv`：人工审核文件（填 `final_category_id` / `final_note`）

当你把 `review.csv` 审核完后，生成最终「带分类明细 + 聚合结果」：

```bash
uv run python scripts/finalize_classification.py
```

### 忽略列（可选）

- **不把某些列发送给 LLM**（例如隐私字段）：  
  `node scripts/classify_unified_openrouter.mjs --ignore-cols remark,sources`
- **最终明细输出里删除某些列**：  
  `uv run python scripts/finalize_classification.py --drop-cols trade_time,post_date`

### 输出文件

> Workflow UI 模式下，每次运行都会落在 `runs/<run_id>/output/`（而不是项目根目录的 `output/`）。
> 同时会在 `runs/<run_id>/logs/<stage_id>.log` 里保留每个阶段的完整日志。

- `output/wechat.normalized.csv`：微信标准化明细
- `output/alipay.normalized.csv`：支付宝标准化明细
- `output/*.transactions.csv`：PDF 提取结果（信用卡账单/银行流水）
- `output/credit_card.enriched.csv`：已匹配并回填的信用卡明细（附 `detail_*` 字段）
- `output/credit_card.unmatched.csv`：未匹配/跳过的信用卡明细（含 `match_status`）
- `output/credit_card.match.xlsx`：Excel 汇总（`enriched` / `unmatched` 两个 Sheet）
- `output/bank.enriched.csv`：已匹配并回填的借记卡流水（附 `detail_*` 字段）
- `output/bank.unmatched.csv`：未匹配/跳过的借记卡流水（含 `match_status`）
- `output/bank.match.xlsx`：Excel 汇总（`enriched` / `unmatched` 两个 Sheet）
- `output/unified.transactions.xlsx`：统一抽象字段汇总（单文件，推荐查看）
- `output/unified.transactions.csv`：统一抽象字段汇总（CSV 版）
- `output/unified.transactions.categorized.xlsx`：最终结果 Excel（`明细` / `汇总` 两个 Sheet，审核完成后生成）

### Workflow 各 Stage 产物（对应 `runs/<run_id>/output/`）

- `extract_pdf`
  - `*.transactions.csv`：从 PDF 提取出的原始交易流水（信用卡账单/银行流水各一份或多份）
- `extract_exports`
  - `wechat.normalized.csv`：微信导出标准化
  - `alipay.normalized.csv`：支付宝导出标准化
- `match_credit_card`
  - `credit_card.enriched.csv`：信用卡账单行 + 回填的微信/支付宝明细（`detail_*` 字段）
  - `credit_card.unmatched.csv`：未匹配/跳过（含 `match_status` 与原因）
  - `credit_card.match.xlsx`：Excel 汇总（方便人工 spot-check）
- `match_bank`
  - `bank.enriched.csv` / `bank.unmatched.csv` / `bank.match.xlsx`：与信用卡一致，但针对借记卡流水
- `build_unified`
  - `unified.transactions.csv` / `unified.transactions.xlsx`：统一字段后的“单表输出”（如设置账期，则为筛选后的账期数据）
  - `unified.transactions.all.csv` / `unified.transactions.all.xlsx`：未筛选的全量（仅当设置账期时生成）
- `classify`
  - `classify/unified.with_id.csv`：为每条交易生成稳定 `txn_id`（后续 review / finalize 都用它对齐）
  - `classify/suggestions.jsonl`：每条交易的“建议分类”中间态（来源可能是 ignore_rule/regex_category_rule/llm）
  - `classify/review.csv`：人工审核表（只改 `final_*` 列）
  - `classify/batches/batch_*.json`：LLM 批次审计（raw output、usage、txn_ids 等）
- `finalize`
  - `unified.transactions.categorized.csv` / `unified.transactions.categorized.xlsx`：最终结果（Excel 内含 `明细` / `汇总` 两个 Sheet）
  - `category.summary.csv`：按分类聚合结果（CSV，默认排除 ignored）
  - `pending_review.csv`：仍需人工确认的清单（存在则该阶段会提示 Needs Review）

### PDF 解析可视化（可选）

如果你想肉眼核对 PDF 版式/表格提取效果：

```bash
uv run python scripts/probe_pdf.py <你的pdf路径> --max-pages 2 --render-pages 1
```

渲染图片会落在 `tmp/pdfs/`。

### 匹配规则（当前实现）

- 仅针对信用卡账单中的 `消费` / `退款` 两类行做匹配；`还款` 默认跳过
- 通过 `卡号末四位 + 金额(绝对值) + 日期窗口(±1天)` 找候选
- 如果同条件下有多条候选，用描述相似度做 tie-break（`rapidfuzz`）

> 提示：如果信用卡账单覆盖了 12 月，但你导出的微信账单从 1 月开始，那么 12 月的「财付通」交易自然无法回填；补导对应时间段的微信账单即可提升命中率。
