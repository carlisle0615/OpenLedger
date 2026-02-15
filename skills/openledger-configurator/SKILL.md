---
name: openledger-configurator
description: 为 OpenLedger 项目快速制定和调整分类配置（ignore_rules、regex_category_rules、run 级 classifier.json），并执行账期重刷与结果核对。用于“取消/收紧 ignore 规则”“区分工资和补贴”“处理复杂转账场景（含非基金过滤）”“按年份批量重刷数据”“判断当前配置模式是否支持某类规则”等请求。
---

# OpenLedger 配置执行手册

按下面流程执行，优先交付可落地结果，不做空泛建议。

## 1. 先收敛目标

先明确以下最小信息（缺失时按仓库现状自动探测）：

- 目标用户：`profile_id` 或姓名
- 时间范围：年份/月份/具体 `run_id`
- 目标动作：放开 ignore、收紧 ignore、改分类映射、重刷数据
- 排除口径：是否排除基金/理财/证券

## 2. 执行前的关键事实

- 工作流跑批时使用 `runs/<run_id>/config/classifier.json`，不是直接读取全局文件。
- 手动 CLI 默认优先 `config/classifier.local.json`。
- 规则执行顺序：先 `ignore_rules`，后 `regex_category_rules`。
- 当前配置能力是“单条交易匹配”；不支持仅靠配置完成“跨两条交易配对”逻辑（例如出 10000、回 5000 自动成对）。

## 3. 标准执行流程

1. 先基线统计：拉出“目标范围内被 ignore 的交易”并分组（flow/merchant/reason）。
2. 修改 `config/classifier.local.json`：
   - 用 `when + fields + pattern + flags` 精确收敛。
   - 不要用过宽正则一次性放开全部。
3. 把全局配置同步到目标 run：覆盖 `runs/<run_id>/config/classifier.json`。
4. 重跑分类与合并：`classify -> finalize`。
5. 回灌账期：把 run 重新绑定到目标 profile 的指定年月。
6. 复核结果：输出“已取消 ignore 清单 / 仍 ignore 清单 / 风险项”。

详细命令参考：`references/command-recipes.md`。

## 4. 复杂场景优先模板

### 模板 A：`skipped_non_payment` 误伤亲友转账

目标：放开亲友往来转账，但保留理财/证券类转账忽略。

做法：拆成两条规则。

- 规则 1：仅对 `flow != transfer` 生效，继续忽略非支付流水。
- 规则 2：仅对 `flow == transfer` 且命中基金/理财/证券关键词时忽略。

关键点：

- 在规则 1 的 `when.merchant` 里加入白名单排除（常见人名/公积金发放方）。
- 规则 2 的关键词放在 `fields: [merchant, item, category]`，避免只看 merchant 漏判。

### 模板 B：收入拆分（工资 vs 补贴）

用 `regex_category_rules` 按稳定字段优先映射：

- `flow == 代发工资` -> `salary_wages`
- 公积金/住建相关关键词 -> `government_subsidy`

注意：

- 置信度固定高值（如 0.98）仅用于稳定规则。
- 若同条可能命中多条规则，靠规则顺序与 pattern 收敛避免冲突。

## 5. 结果验收标准

最少交付以下文件或等价表格：

- 取消 ignore 清单（本次放开的交易）
- 仍被 ignore 清单（含原因）
- 汇总对比（变更前后数量、按商户和 flow 分布）

并给出一句结论：

- 当前配置是否已覆盖目标
- 哪些场景仍需代码实现（通常是跨交易配对）

## 6. 常见失败与修复

- `classify` 显示待处理为 0：旧 `suggestions.jsonl` 被复用，需按规则 ID 清理对应建议后重跑。
- `finalize` 因 pending review 退出：批量回刷时可用 `require_review=False` 生成产物，再单独做人工审核闭环。
- 回灌冲突：同 profile 同月只能绑定一个 run，先删除旧绑定或改用 reimport。
