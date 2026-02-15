# Command Recipes

以下命令默认在仓库根目录执行。

## 1) 找出目标用户与账期 run

```bash
sqlite3 profiles.db "select id,name from profiles;"
sqlite3 -header -csv profiles.db "select profile_id,year,month,run_id from bills where year=2025 order by profile_id,month;"
```

## 2) 检查配置与规则实现位置

```bash
nl -ba config/classifier.local.json | sed -n '1,260p'
rg -n "ignore_rules|regex_category_rules|applyIgnoreRules|applyRegexCategoryRules" stages/classify_llm.mjs -n -S
```

## 3) 同步全局配置到 run 配置

```bash
RID=20260212_091429_e66a8c02
cp config/classifier.local.json runs/$RID/config/classifier.json
```

## 4) 清理旧 suggestions 中指定规则（避免复用旧结论）

```bash
SUG="runs/$RID/output/classify/suggestions.jsonl"
python - "$SUG" <<'PY'
import json,sys
p=sys.argv[1]
remove_rule_ids={
  'ignore_skipped_non_payment',
  'ignore_skipped_non_payment_transfer_investment',
}
keep=[]
with open(p,encoding='utf-8') as f:
    for line in f:
        line=line.strip()
        if not line:
            continue
        obj=json.loads(line)
        if obj.get('mapped_by')=='ignore_rule' and str(obj.get('rule_id') or '') in remove_rule_ids:
            continue
        keep.append(obj)
with open(p,'w',encoding='utf-8') as f:
    for obj in keep:
        f.write(json.dumps(obj,ensure_ascii=False)+'\n')
print('kept',len(keep))
PY
```

## 5) 单 run 重刷

```bash
node stages/classify_llm.mjs \
  --input runs/$RID/output/unified.transactions.csv \
  --out-dir runs/$RID/output/classify \
  --config runs/$RID/config/classifier.json

uv run python - <<'PY' "$RID"
from pathlib import Path
from stages.finalize import finalize
import sys
rid=sys.argv[1]
base=Path('runs')/rid/'output'
finalize(
    config_path=Path('runs')/rid/'config'/'classifier.json',
    unified_with_id_csv=base/'classify'/'unified.with_id.csv',
    review_csv=base/'classify'/'review.csv',
    out_dir=base,
    drop_cols=[],
    require_review=False,
)
print('done',rid)
PY
```

## 6) 批量重刷整年 run

```bash
RUNS=(rid1 rid2 rid3)
for RID in "${RUNS[@]}"; do
  cp config/classifier.local.json "runs/$RID/config/classifier.json"
  # 可选：先清理旧建议
  node stages/classify_llm.mjs --input "runs/$RID/output/unified.transactions.csv" --out-dir "runs/$RID/output/classify" --config "runs/$RID/config/classifier.json"
  uv run python - <<'PY' "$RID"
from pathlib import Path
from stages.finalize import finalize
import sys
rid=sys.argv[1]
base=Path('runs')/rid/'output'
finalize(config_path=Path('runs')/rid/'config'/'classifier.json', unified_with_id_csv=base/'classify'/'unified.with_id.csv', review_csv=base/'classify'/'review.csv', out_dir=base, drop_cols=[], require_review=False)
print('done',rid)
PY
done
```

## 7) 回灌到 profile 指定年月

```bash
python - <<'PY'
from pathlib import Path
import json
from openledger.profiles import add_bill_from_run
root=Path('.').resolve()
profile_id='profile_e323bc'
run_ids=['rid1','rid2']
for rid in run_ids:
    s=json.loads((root/'runs'/rid/'state.json').read_text(encoding='utf-8'))
    y=int(s.get('options',{}).get('period_year'))
    m=int(s.get('options',{}).get('period_month'))
    add_bill_from_run(root, profile_id, rid, period_year=y, period_month=m)
    print('archived',rid,y,m)
PY
```

## 8) 复核“转账类（排除基金）仍被 ignore”

```bash
python - <<'PY'
import csv,re,os
fund_pat=re.compile(r'基金|理财|朝朝宝|赎回|申购',re.I)
transfer_like={'transfer','income','expense'}
rid='20260212_091429_e66a8c02'
p=f'runs/{rid}/output/unified.transactions.categorized.csv'
rows=[]
for r in csv.DictReader(open(p,newline='',encoding='utf-8-sig')):
    flow=(r.get('flow') or '').strip().lower()
    if flow not in transfer_like:
        continue
    text='|'.join((r.get('merchant') or '',r.get('item') or '',r.get('category') or '',r.get('remark') or ''))
    if fund_pat.search(text):
        continue
    if str(r.get('ignored') or '').strip().lower()=='true':
        rows.append(r)
print('ignored_transfer_nonfund',len(rows))
PY
```

## 9) 判断是否需要代码改造

出现以下需求时，不要继续堆配置，直接标记“需代码实现”：

- 同时检查两条或多条交易关系（配对、时间窗口、比例匹配）
- 依赖跨月累计行为识别
- 需要可解释的分摊归因链路
