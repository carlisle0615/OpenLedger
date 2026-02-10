import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

/**
 * classify：对 unified.transactions.csv 进行规则/LLM 分类，并生成 review.csv 供人工审核。
 *
 * 输入：
 * - `--input`：统一抽象输出（通常是 `output/unified.transactions.csv` 或 `runs/<run_id>/output/unified.transactions.csv`）
 * - `--config`：分类器配置（优先 `config/classifier.local.json`，否则 `config/classifier.json`）
 *
 * 输出（在 `--out-dir` 下）：
 * - `unified.with_id.csv`：为每条交易生成稳定的 txn_id
 * - `suggestions.jsonl`：规则/LLM 的建议分类中间态
 * - `review.csv`：人工审核表（只改 `final_*` 列）
 * - `batches/batch_*.json`：LLM 批次审计（raw output、usage 等）
 */

const OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions";

const DEFAULT_PUBLIC_CONFIG = "config/classifier.json";
const DEFAULT_LOCAL_CONFIG = "config/classifier.local.json";

function defaultClassifierConfigPath() {
  // 优先使用本地覆盖配置（已被 gitignore），用于个人调参；否则使用仓库内的公共默认配置。
  if (fs.existsSync(DEFAULT_LOCAL_CONFIG)) return DEFAULT_LOCAL_CONFIG;
  return DEFAULT_PUBLIC_CONFIG;
}

function parseArgs(argv) {
  const args = {
    input: "output/unified.transactions.csv",
    outDir: "output/classify",
    config: defaultClassifierConfigPath(),
    apiKey: null,
    batchSize: null,
    maxConcurrency: null,
    model: null,
    ignoreCols: [],
    maxRows: null,
    dryRun: false,
    noStream: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const next = argv[i + 1];
    if (key === "--input") {
      args.input = next;
      i += 1;
    } else if (key === "--out-dir") {
      args.outDir = next;
      i += 1;
    } else if (key === "--config") {
      args.config = next;
      i += 1;
    } else if (key === "--api-key") {
      args.apiKey = next;
      i += 1;
    } else if (key === "--batch-size") {
      args.batchSize = Number(next);
      i += 1;
    } else if (key === "--max-concurrency" || key === "--concurrency") {
      args.maxConcurrency = Number(next);
      i += 1;
    } else if (key === "--model") {
      args.model = next;
      i += 1;
    } else if (key === "--ignore-cols") {
      args.ignoreCols = next.split(",").map((s) => s.trim()).filter(Boolean);
      i += 1;
    } else if (key === "--max-rows") {
      args.maxRows = Number(next);
      i += 1;
    } else if (key === "--dry-run") {
      args.dryRun = true;
    } else if (key === "--no-stream") {
      args.noStream = true;
    } else {
      throw new Error(`未知参数: ${key}`);
    }
  }
  return args;
}

function loadDotEnvIfNeeded(dotEnvPath = ".env") {
  if (process.env.OPENROUTER_API_KEY) return;
  if (!fs.existsSync(dotEnvPath)) return;

  const text = fs.readFileSync(dotEnvPath, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const k = line.slice(0, eq).trim();
    const v = line.slice(eq + 1).trim();
    if (!process.env[k]) process.env[k] = v;
  }
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function sha1Hex(s) {
  return crypto.createHash("sha1").update(s).digest("hex");
}

function makeTxnId(row) {
  const parts = [
    row.trade_date ?? "",
    row.trade_time ?? "",
    row.post_date ?? "",
    row.account ?? "",
    row.currency ?? "",
    row.amount ?? "",
    row.flow ?? "",
    row.merchant ?? "",
    row.item ?? "",
    row.primary_source ?? "",
    row.sources ?? "",
  ].map((v) => String(v).trim());
  return sha1Hex(parts.join("|"));
}

function testRegex(re, value) {
  re.lastIndex = 0;
  return re.test(value);
}

function compileWhenMatchers(whenObj) {
  if (!whenObj || typeof whenObj !== "object") return [];
  const out = [];
  for (const [field, pattern] of Object.entries(whenObj)) {
    if (typeof pattern !== "string") continue;
    out.push({ field, re: new RegExp(pattern, "i") });
  }
  return out;
}

function rowMatchesWhen(row, whenMatchers) {
  for (const m of whenMatchers) {
    const value = String(row[m.field] ?? "");
    if (!testRegex(m.re, value)) return false;
  }
  return true;
}

function compileTextRules(rawRules, { type, categoryIds, threshold }) {
  const rules = Array.isArray(rawRules) ? rawRules : [];
  const compiled = [];
  for (const r of rules) {
    if (!r || typeof r !== "object") continue;
    if (r.enabled === false) continue;
    const id = r.id ? String(r.id) : "";
    if (!id) throw new Error(`${type} 规则缺少 id`);
    const fields = Array.isArray(r.fields) ? r.fields.map((f) => String(f)).filter(Boolean) : [];
    const pattern = r.pattern != null ? String(r.pattern) : "";
    if (!pattern || fields.length === 0) {
      throw new Error(`${type} 规则 ${id} 缺少 fields/pattern`);
    }

    let flags = r.flags != null ? String(r.flags) : "";
    // 避免 RegExp.test 因 g/y 标志导致的有状态行为
    flags = flags.replaceAll("g", "").replaceAll("y", "");
    const re = new RegExp(pattern, flags);
    const whenMatchers = compileWhenMatchers(r.when);

    if (type === "regex_category_rules") {
      const categoryId = r.category_id ? String(r.category_id) : "";
      if (!categoryId) throw new Error(`regex_category_rules ${id} 缺少 category_id`);
      if (!categoryIds.has(categoryId)) {
        throw new Error(`regex_category_rules ${id} 的 category_id 无效: ${categoryId}`);
      }
      const confidence = Number(r.confidence ?? 0);
      const uncertainRaw = Boolean(r.uncertain ?? false);
      const uncertain = uncertainRaw || !(confidence >= threshold);
      compiled.push({
        type,
        id,
        category_id: categoryId,
        confidence: Number.isFinite(confidence) ? confidence : 0,
        uncertain,
        note: r.note ? String(r.note) : `正则:${id}`,
        fields,
        re,
        whenMatchers,
      });
      continue;
    }

    // ignore_rules（忽略规则）
    compiled.push({
      type,
      id,
      reason: r.reason ? String(r.reason) : id,
      fields,
      re,
      whenMatchers,
    });
  }
  return compiled;
}

function matchTextRule(row, rule) {
  if (!rowMatchesWhen(row, rule.whenMatchers)) return false;
  for (const f of rule.fields) {
    const value = String(row[f] ?? "");
    if (testRegex(rule.re, value)) return true;
  }
  return false;
}

function applyIgnoreRules(row, ignoreRules) {
  for (const rule of ignoreRules) {
    if (matchTextRule(row, rule)) {
      return { ignored: true, ignore_reason: rule.reason, rule_id: rule.id };
    }
  }
  return null;
}

function applyRegexCategoryRules(row, regexRules) {
  for (const rule of regexRules) {
    if (matchTextRule(row, rule)) {
      return {
        ignored: false,
        category_id: rule.category_id,
        confidence: rule.confidence,
        uncertain: rule.uncertain,
        note: rule.note,
        rule_id: rule.id,
      };
    }
  }
  return null;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        const next = text[i + 1];
        if (next === '"') {
          field += '"';
          i += 1;
          continue;
        }
        inQuotes = false;
        continue;
      }
      field += ch;
      continue;
    }

    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(field);
      field = "";
      continue;
    }
    if (ch === "\r") continue;
    if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }
    field += ch;
  }

  if (inQuotes) throw new Error("CSV 格式错误：引号未闭合");
  // 末尾字段
  row.push(field);
  // 文件以换行结尾时，避免额外追加一个空行
  const isTrailingEmpty = row.length === 1 && row[0] === "" && rows.length > 0;
  if (!isTrailingEmpty) rows.push(row);
  return rows;
}

function escapeCsvField(value) {
  const s = value == null ? "" : String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replaceAll('"', '""')}"`;
  return s;
}

function writeCsv(filePath, header, dataRows) {
  const lines = [];
  lines.push(header.map(escapeCsvField).join(","));
  for (const r of dataRows) {
    lines.push(r.map(escapeCsvField).join(","));
  }
  fs.writeFileSync(filePath, lines.join("\n") + "\n", "utf8");
}

function readCsvObjects(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const rows = parseCsv(text);
  if (rows.length === 0) return [];
  const header = rows[0];
  const out = [];
  for (let i = 1; i < rows.length; i += 1) {
    const r = rows[i];
    if (r.length === 1 && r[0] === "" && i === rows.length - 1) continue;
    const obj = {};
    for (let c = 0; c < header.length; c += 1) {
      obj[header[c]] = r[c] ?? "";
    }
    out.push(obj);
  }
  return out;
}

function readCsvHeader(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const rows = parseCsv(text);
  if (rows.length === 0) return [];
  return rows[0] ?? [];
}

function stripCodeFences(text) {
  let t = String(text).trim();
  if (t.startsWith("```")) {
    t = t.replace(/^```[a-zA-Z]*\n/, "");
    t = t.replace(/\n```$/, "");
  }
  return t.trim();
}

function extractJson(text) {
  const t = stripCodeFences(text);
  const first = Math.min(
    ...["[", "{"].map((ch) => {
      const idx = t.indexOf(ch);
      return idx === -1 ? Number.POSITIVE_INFINITY : idx;
    }),
  );
  if (!Number.isFinite(first)) return null;
  const lastArr = t.lastIndexOf("]");
  const lastObj = t.lastIndexOf("}");
  const last = Math.max(lastArr, lastObj);
  if (last < first) return null;
  const slice = t.slice(first, last + 1);
  try {
    return JSON.parse(slice);
  } catch {
    return null;
  }
}

async function chatOnce({ apiKey, model, messages, stream }) {
  const res = await fetch(OPENROUTER_ENDPOINT, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages,
      stream,
      temperature: 0,
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`OpenRouter 接口错误 ${res.status}: ${errText.slice(0, 4000)}`);
  }

  if (!stream) {
    const json = await res.json();
    return {
      content: json.choices?.[0]?.message?.content ?? "",
      usage: json.usage ?? null,
    };
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let content = "";
  let usage = null;

  for await (const chunk of res.body) {
    buffer += decoder.decode(chunk, { stream: true });
    while (true) {
      const sep = buffer.indexOf("\n\n");
      if (sep === -1) break;
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      for (const line of block.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const data = trimmed.slice(5).trim();
        if (data === "[DONE]") {
          return { content, usage };
        }
        let json;
        try {
          json = JSON.parse(data);
        } catch {
          continue;
        }
        const delta = json.choices?.[0]?.delta?.content;
        if (delta) content += delta;
        if (json.usage) usage = json.usage;
      }
    }
  }

  return { content, usage };
}

function buildPrompt({ categories, columns, rows }) {
  const catText = categories.map((c) => `- ${c.id}: ${c.name}`).join("\n");

  const txText = rows
    .map((r, idx) => {
      const parts = [`txn_id=${r.txn_id}`];
      for (const col of columns) {
        parts.push(`${col}=${String(r[col] ?? "").replaceAll("\n", " ").trim()}`);
      }
      return `${idx + 1}) ${parts.join(", ")}`;
    })
    .join("\n");

  const system = [
    "你是一个中文个人账单交易的分类助手。",
    "你必须为每条交易选择且仅选择一个 category_id（从给定列表中选）。",
    "当信息不足或多分类都合理时：仍然给出最可能的一个分类，但必须标记 uncertain=true，并降低 confidence。",
    "输出必须是严格 JSON（不要 markdown，不要多余解释）。",
  ].join("\n");

  const user = [
    "分类列表：",
    catText,
    "",
    "请返回 JSON 数组，每个元素对应一条交易：",
    '{ "txn_id": "...", "category_id": "...", "confidence": 0.0, "uncertain": false, "note": "简短原因" }',
    "",
    "交易：",
    txText,
  ].join("\n");

  return { system, user };
}

function validateAndNormalizeResults({ batchRows, rawResult, categoryIds, threshold }) {
  const map = new Map();
  const asArray = Array.isArray(rawResult) ? rawResult : null;
  if (!asArray) return map;

  const batchIds = new Set(batchRows.map((r) => r.txn_id));
  for (const item of asArray) {
    const txnId = item?.txn_id ? String(item.txn_id) : null;
    if (!txnId || !batchIds.has(txnId)) continue;
    const categoryId = item?.category_id ? String(item.category_id) : "other";
    const confidence = Number(item?.confidence ?? 0);
    const uncertain = Boolean(item?.uncertain ?? false) || !(confidence >= threshold);
    const note = item?.note ? String(item.note) : "";
    if (!categoryIds.has(categoryId)) {
      map.set(txnId, { category_id: "other", confidence: 0, uncertain: true, note: `非法分类：${categoryId}` });
    } else {
      map.set(txnId, { category_id: categoryId, confidence: Number.isFinite(confidence) ? confidence : 0, uncertain, note });
    }
  }
  return map;
}

function makeReviewRows({ unifiedWithId, suggestions, categoriesById, reviewColumns }) {
  return unifiedWithId.map((r) => {
    const s = suggestions.get(r.txn_id) ?? null;
    const suggestedCategoryId = s?.category_id ?? "";
    const suggestedCategoryName = suggestedCategoryId ? (categoriesById.get(suggestedCategoryId) ?? "") : "";
    const suggestedConfidence = s?.confidence ?? "";
    const suggestedUncertain = s?.uncertain ?? "";
    const suggestedNote = s?.note ?? "";
    const suggestedIgnored = s?.ignored ?? "";
    const suggestedIgnoreReason = s?.ignore_reason ?? "";
    const suggestedSource = s?.mapped_by ?? (s?.model ? "llm" : "");
    const suggestedRuleId = s?.rule_id ?? "";
    const base = {
      txn_id: r.txn_id,
      suggested_category_id: suggestedCategoryId,
      suggested_category_name: suggestedCategoryName,
      suggested_confidence: suggestedConfidence,
      suggested_uncertain: suggestedUncertain,
      suggested_note: suggestedNote,
      suggested_ignored: suggestedIgnored,
      suggested_ignore_reason: suggestedIgnoreReason,
      suggested_source: suggestedSource,
      suggested_rule_id: suggestedRuleId,
      final_category_id: "",
      final_note: "",
      final_ignored: "",
      final_ignore_reason: "",
    };

    for (const col of reviewColumns) {
      base[col] = r[col] ?? "";
    }
    return base;
  });
}

function readJsonlSuggestions(filePath) {
  if (!fs.existsSync(filePath)) return new Map();
  const map = new Map();
  const text = fs.readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const obj = JSON.parse(line);
    if (obj?.txn_id) map.set(String(obj.txn_id), obj);
  }
  return map;
}

function appendJsonl(filePath, obj) {
  fs.appendFileSync(filePath, JSON.stringify(obj) + "\n", "utf8");
}

async function runWithConcurrency(items, concurrency, fn) {
  const max = Math.max(1, Math.floor(concurrency));
  let next = 0;
  let err = null;

  const workers = Array.from({ length: max }, async () => {
    while (true) {
      if (err) return;
      const i = next;
      next += 1;
      if (i >= items.length) return;
      try {
        await fn(items[i], i);
      } catch (e) {
        err = e;
        return;
      }
    }
  });

  await Promise.all(workers);
  if (err) throw err;
}

async function main() {
  const args = parseArgs(process.argv);
  loadDotEnvIfNeeded();

  const config = readJson(args.config);
  const model = args.model ?? config.model;
  const batchSize = args.batchSize ?? config.batch_size ?? 10;
  const maxConcurrencyCfg = args.maxConcurrency ?? config.max_concurrency ?? 10;
  const maxConcurrency = Math.min(10, Math.max(1, Math.floor(Number(maxConcurrencyCfg) || 1)));
  const threshold = config.uncertain_threshold ?? 0.6;
  const categories = config.categories ?? [];
  const promptColumnsRaw = config.prompt_columns ?? [];
  const reviewColumnsRaw = config.review_columns ?? [];
  const ignoreCols = new Set([...(config.ignore_columns ?? []), ...(args.ignoreCols ?? [])]);
  const promptColumns = promptColumnsRaw.filter((c) => !ignoreCols.has(c));
  const reviewColumns = reviewColumnsRaw.filter((c) => !ignoreCols.has(c));

  const apiKey = args.apiKey ?? process.env.OPENROUTER_API_KEY;
  if (!args.dryRun && (!apiKey || !String(apiKey).trim())) {
    throw new Error("缺少 OPENROUTER_API_KEY（可写在 .env，或通过 --api-key 传入）。");
  }

  const outDir = args.outDir;
  ensureDir(outDir);
  ensureDir(path.join(outDir, "batches"));

  const categoryIds = new Set(categories.map((c) => c.id));
  if (!categoryIds.has("other")) {
    throw new Error("config.categories 必须包含 id=other，用作兜底分类。");
  }
  const categoriesById = new Map(categories.map((c) => [c.id, c.name]));

  const ignoreRules = compileTextRules(config.ignore_rules, {
    type: "ignore_rules",
    categoryIds,
    threshold,
  });
  const regexCategoryRules = compileTextRules(config.regex_category_rules, {
    type: "regex_category_rules",
    categoryIds,
    threshold,
  });

  const inputHeader = readCsvHeader(args.input);
  const unifiedRows = readCsvObjects(args.input);
  const unifiedLimited = args.maxRows ? unifiedRows.slice(0, args.maxRows) : unifiedRows;
  const unifiedWithId = unifiedLimited.map((r) => ({ ...r, txn_id: makeTxnId(r) }));

  const unifiedWithIdCsv = path.join(outDir, "unified.with_id.csv");
  {
    const baseHeader = inputHeader.length ? inputHeader : Object.keys(unifiedRows[0] ?? {});
    const header = [...baseHeader.filter(Boolean), "txn_id"].filter((v, idx, arr) => arr.indexOf(v) === idx);
    const dataRows = unifiedWithId.map((r) => header.map((h) => r[h] ?? ""));
    writeCsv(unifiedWithIdCsv, header, dataRows);
  }

  const suggestionsPath = path.join(outDir, "suggestions.jsonl");
  const suggestions = readJsonlSuggestions(suggestionsPath);

  const toClassify = unifiedWithId.filter((r) => !suggestions.has(r.txn_id));
  const llmQueue = [];
  let ignoredCount = 0;
  let regexCount = 0;

  for (const r of toClassify) {
    const ignoreHit = applyIgnoreRules(r, ignoreRules);
    if (ignoreHit) {
      const record = {
        txn_id: r.txn_id,
        category_id: "other",
        confidence: 1,
        uncertain: false,
        note: `已忽略: ${ignoreHit.ignore_reason}`,
        ignored: true,
        ignore_reason: ignoreHit.ignore_reason,
        mapped_by: "ignore_rule",
        rule_id: ignoreHit.rule_id,
        model: "",
        batch_size: 0,
        usage: null,
      };
      suggestions.set(r.txn_id, record);
      appendJsonl(suggestionsPath, record);
      ignoredCount += 1;
      continue;
    }

    const regexHit = applyRegexCategoryRules(r, regexCategoryRules);
    if (regexHit) {
      const record = {
        txn_id: r.txn_id,
        category_id: regexHit.category_id,
        confidence: regexHit.confidence,
        uncertain: regexHit.uncertain,
        note: regexHit.note,
        ignored: false,
        ignore_reason: "",
        mapped_by: "regex_category_rule",
        rule_id: regexHit.rule_id,
        model: "",
        batch_size: 0,
        usage: null,
      };
      suggestions.set(r.txn_id, record);
      appendJsonl(suggestionsPath, record);
      regexCount += 1;
      continue;
    }

    llmQueue.push(r);
  }

  console.log(
    `[分类] 输入=${args.input} 总数=${unifiedWithId.length} 待处理=${toClassify.length} 已忽略=${ignoredCount} 正则命中=${regexCount} LLM待处理=${llmQueue.length} 批大小=${batchSize} 并发=${maxConcurrency}`,
  );

  const batches = [];
  for (let offset = 0; offset < llmQueue.length; offset += batchSize) {
    batches.push(llmQueue.slice(offset, offset + batchSize));
  }

  await runWithConcurrency(batches, maxConcurrency, async (batchRows, batchIndex) => {
    const batchNo = batchIndex + 1;
    let resultByTxnId = new Map();
    let usage = null;

    if (args.dryRun) {
      for (const r of batchRows) {
        const flow = String(r.flow ?? "").trim();
        let categoryId = "other";
        if (flow === "refund") categoryId = "refund";
        else if (flow === "transfer") categoryId = "red_packet_transfer";
        const uncertain = categoryId === "other";
        resultByTxnId.set(r.txn_id, { category_id: categoryId, confidence: uncertain ? 0.3 : 0.9, uncertain, note: "演练" });
      }
    } else {
      const { system, user } = buildPrompt({ categories, columns: promptColumns, rows: batchRows });
      const messages = [
        { role: "system", content: system },
        { role: "user", content: user },
      ];

      console.log(`[分类] 批次 ${batchNo} 行数=${batchRows.length} 模型=${model}`);
      const startedAt = Date.now();
      const response = await chatOnce({ apiKey, model, messages, stream: !args.noStream });
      const elapsedMs = Date.now() - startedAt;
      usage = response.usage;

      const parsed = extractJson(response.content);
      resultByTxnId = validateAndNormalizeResults({
        batchRows,
        rawResult: parsed,
        categoryIds,
        threshold,
      });

      const auditPath = path.join(outDir, "batches", `batch_${String(batchNo).padStart(4, "0")}.json`);
      fs.writeFileSync(
        auditPath,
        JSON.stringify(
          {
            model,
            batch_no: batchNo,
            batch_size: batchRows.length,
            elapsed_ms: elapsedMs,
            txn_ids: batchRows.map((r) => r.txn_id),
            prompt_columns: promptColumns,
            usage,
            raw_output: response.content,
            parsed_ok: Boolean(parsed),
          },
          null,
          2,
        ),
        "utf8",
      );
    }

    for (const r of batchRows) {
      const item = resultByTxnId.get(r.txn_id) ?? { category_id: "other", confidence: 0, uncertain: true, note: "缺失" };
      const record = {
        txn_id: r.txn_id,
        category_id: item.category_id,
        confidence: item.confidence,
        uncertain: item.uncertain,
        note: item.note,
        ignored: false,
        ignore_reason: "",
        mapped_by: args.dryRun ? "dry_run" : "llm",
        rule_id: "",
        model,
        batch_size: batchRows.length,
        usage,
      };
      suggestions.set(r.txn_id, record);
      appendJsonl(suggestionsPath, record);
    }
  });

  const reviewRows = makeReviewRows({
    unifiedWithId,
    suggestions,
    categoriesById,
    reviewColumns,
  });
  const reviewHeader = reviewRows.length
    ? Object.keys(reviewRows[0] ?? {})
    : [
      "txn_id",
      "suggested_category_id",
      "suggested_category_name",
      "suggested_confidence",
      "suggested_uncertain",
      "suggested_note",
      "suggested_ignored",
      "suggested_ignore_reason",
      "suggested_source",
      "suggested_rule_id",
      "final_category_id",
      "final_note",
      "final_ignored",
      "final_ignore_reason",
      ...reviewColumns,
    ].filter((v, idx, arr) => arr.indexOf(v) === idx);
  const reviewPath = path.join(outDir, "review.csv");
  writeCsv(reviewPath, reviewHeader, reviewRows.map((r) => reviewHeader.map((h) => r[h] ?? "")));

  console.log(`[分类] 建议输出 -> ${suggestionsPath}`);
  console.log(`[分类] 审核表   -> ${reviewPath}`);
  console.log("[分类] 下一步：编辑 review.csv（填写 final_* 列），再运行 finalize 脚本。");
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exitCode = 1;
});
