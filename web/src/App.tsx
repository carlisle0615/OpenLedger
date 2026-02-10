import React, { useEffect, useMemo, useState, useRef } from "react";
import { StageCard } from "@/components/StageCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ClassifierConfig,
  CsvPreview,
  FileItem,
  RunState,
} from "@/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Play, Ban, RefreshCw, FileText, Upload, CheckCircle2, XCircle, AlertCircle, Clock, FileInput, CreditCard, Landmark, GitMerge, Fingerprint, Flag, Download, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils"; // Assuming cn utility is available
import { fmtStatus, api, isCsvFile, isTextFile, parseBoolish, escapeRegExp, slugifyId, suggestCategoryId, type RuleMatchMode, type RuleMatchField, type RuleAction, type RunMeta } from "@/utils/helpers";
import { useFilteredReviewRows, useReviewPendingCount, useSelectedReviewFields, ReviewContext, ReviewContextType } from "@/hooks/useReviewContext";
import { SettingsCard } from "@/components/SettingsCard";
import { PreviewArea } from "@/components/PreviewArea";
import { WorkflowPanel } from "@/components/WorkflowPanel";
import { ReviewModal } from "@/components/ReviewModal";


export default function App() {
  const [baseUrl, setBaseUrl] = useState(
    () => localStorage.getItem("openledger_baseUrl") || "http://127.0.0.1:8000",
  );
  const [apiToken, setApiToken] = useState(() => localStorage.getItem("openledger_apiToken") || "");
  const [runs, setRuns] = useState<string[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [runsMeta, setRunsMeta] = useState<RunMeta[]>([]);
  const [newRunName, setNewRunName] = useState<string>("");
  const [state, setState] = useState<RunState | null>(null);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);
  const [textPreview, setTextPreview] = useState<string>("");
  const [previewError, setPreviewError] = useState<string>("");
  const [csvLimit] = useState<number>(80);
  const [config, setConfig] = useState<ClassifierConfig | null>(null);
  const [configText, setConfigText] = useState<string>("");
  const [cfgSaveToRun, setCfgSaveToRun] = useState(true);
  const [cfgSaveToGlobal, setCfgSaveToGlobal] = useState(true);
  const [reviewRows, setReviewRows] = useState<Record<string, string>[]>([]);
  const [reviewEdits, setReviewEdits] = useState<Record<string, Partial<Record<string, string | boolean>>>>({});
  const [reviewPendingOnly, setReviewPendingOnly] = useState(true);
  const [reviewQuery, setReviewQuery] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewSelectedTxnId, setReviewSelectedTxnId] = useState<string>("");
  const [reviewSelectedTxnIds, setReviewSelectedTxnIds] = useState<Record<string, boolean>>({});
  const [bulkTarget, setBulkTarget] = useState<"selected" | "filtered">("selected");
  const [bulkIncludeReviewed, setBulkIncludeReviewed] = useState(false);
  const [bulkCategoryId, setBulkCategoryId] = useState<string>("");
  const [bulkIgnored, setBulkIgnored] = useState<boolean>(false);
  const [bulkNote, setBulkNote] = useState<string>("");
  const [bulkContinuousMode, setBulkContinuousMode] = useState<boolean>(false);

  const [ruleField, setRuleField] = useState<RuleMatchField>("merchant");
  const [ruleMode, setRuleMode] = useState<RuleMatchMode>("contains");
  const [ruleAction, setRuleAction] = useState<RuleAction>("categorize");
  const [rulePattern, setRulePattern] = useState("");
  const [ruleCategoryId, setRuleCategoryId] = useState("");
  const [ruleOnlyPending, setRuleOnlyPending] = useState(true);
  const [ruleOverwriteFinal, setRuleOverwriteFinal] = useState(false);
  const [ruleSaveToConfig, setRuleSaveToConfig] = useState(true);
  const [ruleSaveToGlobal, setRuleSaveToGlobal] = useState(true);
  const [ruleNote, setRuleNote] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [newCategoryId, setNewCategoryId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>("");
  const [selectedStageId, setSelectedStageId] = useState<string>("");
  const lastOptionEdit = useRef<number>(0);

  useEffect(() => {
    localStorage.setItem("openledger_baseUrl", baseUrl);
  }, [baseUrl]);

  useEffect(() => {
    localStorage.setItem("openledger_apiToken", apiToken);
  }, [apiToken]);

  useEffect(() => {
    if (!reviewOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [reviewOpen]);

  useEffect(() => {
    const sync = () => {
      const open = window.location.hash === "#review";
      setReviewOpen(open);
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    if (!reviewOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (window.location.hash === "#review") {
          window.history.replaceState(null, "", window.location.pathname + window.location.search);
        }
        setReviewOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reviewOpen]);

  const runName = useMemo(() => {
    const n = String(state?.name ?? "").trim();
    if (n) return n;
    const hit = runsMeta.find((m) => m.id === runId);
    return String(hit?.name ?? "").trim();
  }, [state, runsMeta, runId]);

  async function refreshRuns() {
    const r = await api<{ runs: string[]; runs_meta?: RunMeta[] }>(baseUrl, "/api/runs");
    setRuns(r.runs);
    setRunsMeta(Array.isArray(r.runs_meta) ? r.runs_meta : []);
  }

  async function loadRun(id: string) {
    if (!id) return;
    const s = await api<RunState>(baseUrl, `/api/runs/${encodeURIComponent(id)}`);
    setState(s);
    setSelectedFile(null);
    setCsvPreview(null);
    setTextPreview("");
    setPreviewError("");
    try {
      const cfg = await api<ClassifierConfig>(baseUrl, `/api/runs/${encodeURIComponent(id)}/config/classifier`);
      setConfig(cfg);
      setConfigText(JSON.stringify(cfg, null, 2));
    } catch {
      setConfig(null);
      setConfigText("");
    }
  }

  useEffect(() => {
    refreshRuns().catch((e) => setError(String(e)));
  }, [baseUrl]);

  useEffect(() => {
    if (!runId) return;
    loadRun(runId).catch((e) => setError(String(e)));
    const timer = window.setInterval(() => {
      api<RunState>(baseUrl, `/api/runs/${encodeURIComponent(runId)}`)
        .then((s) => {
          // If user edited options recently (< 10s), do not overwrite with polled state options
          if (Date.now() - lastOptionEdit.current < 10000) {
            setState((prev) => {
              if (!prev) return s;
              return {
                ...s,
                options: { ...s.options, ...prev.options }
              };
            });
          } else {
            setState(s);
          }
        })
        .catch(() => { });
    }, 1500);
    return () => window.clearInterval(timer);
  }, [baseUrl, runId]);

  useEffect(() => {
    if (state?.stages?.length && !selectedStageId) {
      setSelectedStageId(state.stages[0].id);
    }
  }, [state, selectedStageId]);

  const categories = useMemo(() => config?.categories ?? [], [config]);

  // 使用提取的 Hook 替代内联 useMemo
  const filteredReviewRows = useFilteredReviewRows(reviewRows, reviewEdits, reviewPendingOnly, reviewQuery);

  const filteredReviewTxnIds = useMemo(() => {
    const uniq = new Set<string>();
    for (const r of filteredReviewRows) {
      const txnId = String(r.txn_id ?? "").trim();
      if (txnId) uniq.add(txnId);
    }
    return Array.from(uniq);
  }, [filteredReviewRows]);

  const selectedTxnIds = useMemo(
    () => Object.entries(reviewSelectedTxnIds).filter(([, v]) => v).map(([k]) => k),
    [reviewSelectedTxnIds],
  );

  const bulkEffectiveTxnIds = useMemo(() => {
    if (bulkTarget === "selected") return selectedTxnIds;
    if (!bulkIncludeReviewed) return filteredReviewTxnIds;

    // Apply to "current search filter", ignoring pending-only.
    const q = reviewQuery.trim().toLowerCase();
    const uniq = new Set<string>();
    for (const r of reviewRows) {
      if (!r) continue;
      if (q) {
        const hay = `${r.merchant ?? ""} ${r.item ?? ""} ${r.category ?? ""} ${r.pay_method ?? ""} ${r.remark ?? ""}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      const txnId = String(r.txn_id ?? "").trim();
      if (txnId) uniq.add(txnId);
    }
    return Array.from(uniq);
  }, [bulkTarget, bulkIncludeReviewed, selectedTxnIds, filteredReviewTxnIds, reviewQuery, reviewRows]);

  useEffect(() => {
    if (!reviewOpen) return;
    const ids = filteredReviewRows.map((r) => String(r.txn_id ?? "")).filter(Boolean);
    if (ids.length === 0) {
      setReviewSelectedTxnId("");
      return;
    }
    if (!reviewSelectedTxnId || !ids.includes(reviewSelectedTxnId)) {
      setReviewSelectedTxnId(ids[0]);
    }
  }, [reviewOpen, filteredReviewRows, reviewSelectedTxnId]);

  const selectedReviewRow = useMemo(() => {
    if (!reviewSelectedTxnId) return null;
    const hit = reviewRows.find((r) => String(r.txn_id ?? "") === reviewSelectedTxnId);
    return hit ?? null;
  }, [reviewRows, reviewSelectedTxnId]);

  // 使用提取的 Hook 替代内联 useMemo
  const selectedReviewFields = useSelectedReviewFields(selectedReviewRow);

  const reviewPendingCount = useReviewPendingCount(reviewRows, reviewEdits);

  const rulePreview = useMemo(() => {
    const pattern = rulePattern.trim();
    if (!pattern) return { matches: [] as Record<string, string>[], error: "" };

    let re: RegExp | null = null;
    if (ruleMode === "regex") {
      try {
        re = new RegExp(pattern, "i");
      } catch (e) {
        return { matches: [] as Record<string, string>[], error: String(e) };
      }
    }

    const lowerNeedle = pattern.toLowerCase();

    const getOverride = (txnId: string, key: string): string | boolean | undefined =>
      reviewEdits[txnId]?.[key];

    const isPendingRow = (r: Record<string, string>) => {
      const txnId = String(r.txn_id ?? "");
      const suggestedUncertain = parseBoolish(r.suggested_uncertain);

      const finalCatOverride = getOverride(txnId, "final_category_id");
      const finalCat = String(finalCatOverride ?? r.final_category_id ?? "").trim();

      const finalIgnoredOverride = getOverride(txnId, "final_ignored");
      const finalIgnoredRaw = String(finalIgnoredOverride ?? r.final_ignored ?? "").trim();
      const ignored = finalIgnoredRaw !== ""
        ? parseBoolish(finalIgnoredRaw)
        : parseBoolish(r.suggested_ignored);

      return suggestedUncertain && !finalCat && !ignored;
    };

    const baseRows = ruleOnlyPending ? reviewRows.filter(isPendingRow) : reviewRows;
    const matches: Record<string, string>[] = [];
    for (const r of baseRows) {
      if (!r) continue;
      const txnId = String(r.txn_id ?? "").trim();
      if (!txnId) continue;

      const currentFinal = String(getOverride(txnId, "final_category_id") ?? r.final_category_id ?? "").trim();
      const currentIgnored = parseBoolish(String(getOverride(txnId, "final_ignored") ?? r.final_ignored ?? ""));
      if (!ruleOverwriteFinal) {
        if (ruleAction === "categorize" && currentFinal) continue;
        if (ruleAction === "ignore" && currentIgnored) continue;
      }

      const value = String((r as Record<string, string>)[ruleField] ?? "");
      const ok = ruleMode === "contains"
        ? value.toLowerCase().includes(lowerNeedle)
        : Boolean(re && re.test(value));
      if (ok) matches.push(r);
    }

    return { matches, error: "" };
  }, [rulePattern, ruleMode, ruleField, ruleAction, ruleOnlyPending, ruleOverwriteFinal, reviewRows, reviewEdits]);

  async function onCreateRun() {
    setBusy(true);
    setError("");
    try {
      const name = newRunName.trim();
      const s = await api<RunState>(baseUrl, "/api/runs", {
        method: "POST",
        headers: name ? { "Content-Type": "application/json" } : undefined,
        body: name ? JSON.stringify({ name }) : undefined,
      });
      await refreshRuns();
      setRunId(s.run_id);
      setState(s);
      setNewRunName("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(files: FileList | null) {
    if (!files || !runId) return;
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      for (const f of Array.from(files)) {
        fd.append("files", f, f.name);
      }
      await api<{ saved: unknown[] }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/upload`, {
        method: "POST",
        body: fd,
      });
      await loadRun(runId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function downloadHref(relPath: string) {
    return `${baseUrl}/api/runs/${encodeURIComponent(runId)}/artifact?path=${encodeURIComponent(relPath)}`;
  }

  async function startWorkflow(stages?: string[]) {
    if (!runId) return;
    setBusy(true);
    setError("");
    try {
      const options = state?.options ?? { classify_mode: "llm", allow_unreviewed: false, period_year: null, period_month: null };
      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stages, options }),
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function cancelRun() {
    if (!runId) return;
    setBusy(true);
    setError("");
    try {
      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function resetClassify() {
    if (!runId) return;
    setBusy(true);
    setError("");
    try {
      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "classify" }),
      });
      await loadRun(runId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadCsv(relPath: string, offset: number) {
    setPreviewError("");
    const r = await api<CsvPreview>(
      baseUrl,
      `/api/runs/${encodeURIComponent(runId)}/preview?path=${encodeURIComponent(relPath)}&limit=${encodeURIComponent(String(csvLimit))}&offset=${encodeURIComponent(String(offset))}`,
    );
    setCsvPreview(r);
  }

  async function selectFile(file: FileItem) {
    if (!file.exists) return;
    setSelectedFile(file);
    setCsvPreview(null);
    setTextPreview("");
    setPreviewError("");

    if (!runId) return;
    if (isCsvFile(file.name)) {
      await loadCsv(file.path, 0);
      return;
    }
    if (isTextFile(file.name)) {
      try {
        const res = await fetch(downloadHref(file.path));
        const text = await res.text();
        setTextPreview(text.length > 400_000 ? text.slice(0, 400_000) + "\n\n...(truncated)..." : text);
      } catch (e) {
        setPreviewError(String(e));
      }
      return;
    }
    setPreviewError("该文件类型暂不支持预览，请下载查看。");
  }

  async function saveConfig() {
    try {
      const next = JSON.parse(configText) as ClassifierConfig;
      await saveConfigObject(next);
    } catch (e) {
      setError(String(e));
    }
  }

  async function saveConfigObject(next: unknown) {
    if (!runId) return;
    setBusy(true);
    setError("");
    try {
      if (!cfgSaveToRun && !cfgSaveToGlobal) {
        throw new Error("请至少选择一个保存目标：本次任务 / 默认配置。");
      }
      if (cfgSaveToRun) {
        await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/config/classifier`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        });
      }
      if (cfgSaveToGlobal) {
        await api<{ ok: boolean }>(baseUrl, "/api/config/classifier", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        });
      }
      setConfig(next as ClassifierConfig);
      setConfigText(JSON.stringify(next, null, 2));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function loadReview() {
    if (!runId) return;
    const path = "output/classify/review.csv";
    setBusy(true);
    setError("");
    try {
      const limit = 2000;
      let offset = 0;
      const rows: Record<string, string>[] = [];
      for (let guard = 0; guard < 1000; guard += 1) {
        const r = await api<CsvPreview>(
          baseUrl,
          `/api/runs/${encodeURIComponent(runId)}/preview?path=${encodeURIComponent(path)}&limit=${limit}&offset=${offset}`,
        );
        rows.push(...r.rows);
        if (!r.has_more || r.next_offset == null) break;
        offset = r.next_offset;
        if (rows.length > 200_000) break;
      }
      setReviewRows(rows);
      setReviewEdits({});
      setReviewSelectedTxnIds({});
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function openReview() {
    setReviewOpen(true);
    if (window.location.hash !== "#review") {
      window.location.hash = "review";
    }
    if (!runId) return;
    if (reviewRows.length) return;
    try {
      await loadReview();
    } catch (e) {
      setError(String(e));
    }
  }

  function setEdit(txnId: string, key: string, value: string | boolean) {
    setReviewEdits((prev) => ({
      ...prev,
      [txnId]: { ...(prev[txnId] ?? {}), [key]: value },
    }));
  }

  function isTxnIgnored(txnId: string, row?: Record<string, string>) {
    const ignoredOverride = reviewEdits[txnId]?.final_ignored;
    if (ignoredOverride !== undefined) return Boolean(ignoredOverride);
    const raw = String(row?.final_ignored ?? "").trim();
    if (raw !== "") return parseBoolish(raw);
    return parseBoolish(row?.suggested_ignored);
  }

  function applyLocalEdits(txnIds: string[], patch: Partial<Record<string, string | boolean>>) {
    const uniq = Array.from(new Set(txnIds.map((x) => String(x ?? "").trim()).filter(Boolean)));
    if (!uniq.length) return;
    setReviewEdits((prev) => {
      const next = { ...prev };
      for (const txnId of uniq) {
        next[txnId] = { ...(next[txnId] ?? {}), ...patch };
      }
      return next;
    });
  }

  function jumpToNextFiltered(afterTxnId: string) {
    const ids = filteredReviewTxnIds;
    if (!ids.length) return;
    const idx = ids.indexOf(afterTxnId);
    const next = idx >= 0 ? ids[Math.min(idx + 1, ids.length - 1)] : ids[0];
    setReviewSelectedTxnId(next);
  }

  async function applyBulkLocal() {
    const txnIds = bulkContinuousMode
      ? [reviewSelectedTxnId].map((x) => String(x ?? "").trim()).filter(Boolean)
      : bulkEffectiveTxnIds;
    if (!txnIds.length) return;

    if (!bulkIgnored && !bulkCategoryId.trim()) {
      setError("请先选择分类（或切换为“不记账”）。");
      return;
    }

    const note = bulkNote.trim();
    const patch: Partial<Record<string, string | boolean>> = {};
    if (bulkIgnored) {
      patch.final_ignored = true;
      if (note) {
        patch.final_ignore_reason = note;
        patch.final_note = note;
      }
    } else {
      patch.final_ignored = false;
      patch.final_ignore_reason = "";
      patch.final_category_id = bulkCategoryId.trim();
      if (note) patch.final_note = note;
    }

    applyLocalEdits(txnIds, patch);

    if (bulkContinuousMode && txnIds.length === 1) {
      jumpToNextFiltered(txnIds[0]);
    }
  }

  useEffect(() => {
    if (!reviewOpen) return;
    if (!bulkContinuousMode) return;

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = String(target?.tagName ?? "").toLowerCase();
      const isTyping = tag === "input" || tag === "textarea" || Boolean((target as any)?.isContentEditable);
      if (isTyping) return;

      const ids = filteredReviewTxnIds;
      if (!ids.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const idx = ids.indexOf(reviewSelectedTxnId);
        setReviewSelectedTxnId(ids[Math.min(Math.max(idx, 0) + 1, ids.length - 1)]);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        const idx = ids.indexOf(reviewSelectedTxnId);
        setReviewSelectedTxnId(ids[Math.max(Math.max(idx, 0) - 1, 0)]);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        void applyBulkLocal();
        return;
      }
      if (e.key === "i" || e.key === "I") {
        e.preventDefault();
        setBulkIgnored((prev) => !prev);
        return;
      }
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= 9) {
        const cat = categories[n - 1];
        if (!cat?.id) return;
        e.preventDefault();
        setBulkIgnored(false);
        setBulkCategoryId(String(cat.id));
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reviewOpen, bulkContinuousMode, filteredReviewTxnIds, reviewSelectedTxnId, categories, applyBulkLocal]);

  async function saveOptions(updates: Partial<NonNullable<RunState["options"]>>) {
    if (!runId) return;
    lastOptionEdit.current = Date.now();
    // Optimistic update
    setState((prev) => (prev ? { ...prev, options: { ...prev.options, ...updates } } : prev));
    setBusy(true);
    setError("");
    try {
      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/options`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveReviewEdits() {
    if (!runId) return;
    const updates = Object.entries(reviewEdits).map(([txn_id, patch]) => ({ txn_id, ...patch }));
    if (updates.length === 0) return;
    setBusy(true);
    setError("");
    try {
      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/review/updates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      });
      await loadReview();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function addCategory() {
    if (!runId) return;
    const name = newCategoryName.trim();
    if (!name) return;
    const id = (newCategoryId.trim() || suggestCategoryId(name)).trim();
    if (!id) {
      setError("Category id is empty.");
      return;
    }
    const cfg = config ?? (configText ? JSON.parse(configText) : null);
    if (!cfg || typeof cfg !== "object") {
      setError("Missing classifier config; please Load a run first.");
      return;
    }

    const next = JSON.parse(JSON.stringify(cfg)) as any;
    const cats = Array.isArray(next.categories) ? next.categories : [];
    const byName = cats.find((c: any) => String(c?.name ?? "").trim() === name);
    if (byName?.id) {
      setRuleCategoryId(String(byName.id));
      setNewCategoryName("");
      setNewCategoryId("");
      return;
    }
    const byId = cats.find((c: any) => String(c?.id ?? "").trim() === id);
    if (byId) {
      setRuleCategoryId(id);
      setNewCategoryName("");
      setNewCategoryId("");
      return;
    }
    cats.push({ id, name });
    next.categories = cats;
    await saveConfigObject(next);
    setRuleCategoryId(id);
    setNewCategoryName("");
    setNewCategoryId("");
  }

  async function applyQuickRule() {
    if (!runId) return;
    const patternRaw = rulePattern.trim();
    if (!patternRaw) return;
    if (rulePreview.error) {
      setError(rulePreview.error);
      return;
    }

    const matches = rulePreview.matches;
    if (!matches.length) return;

    setBusy(true);
    setError("");
    try {
      const fields = [ruleField];
      const pattern = ruleMode === "contains" ? escapeRegExp(patternRaw) : patternRaw;
      const flags = "i";
      const computedNote = (ruleNote.trim() || `rule:${ruleAction}:${ruleField}:${ruleMode}:${patternRaw}`).slice(0, 200);
      const categoryId = ruleCategoryId.trim();

      const cfgFromState = config ?? (configText ? (JSON.parse(configText) as any) : null);
      const runCfg = cfgFromState && typeof cfgFromState === "object" ? (cfgFromState as any) : null;

      const patchConfig = (input: any): any => {
        const next = JSON.parse(JSON.stringify(input ?? {})) as any;
        if (ruleAction === "categorize") {
          if (!categoryId) throw new Error("请选择分类（final_category_id）。");
          const cats = Array.isArray(next.categories) ? next.categories : [];
          const categoryExists = cats.some((c: any) => String(c?.id ?? "") === categoryId);
          if (!categoryExists) throw new Error(`Category id not found in config: ${categoryId}`);
          const rules = Array.isArray(next.regex_category_rules) ? next.regex_category_rules : [];
          const exists = rules.some((r: any) =>
            String(r?.category_id ?? "") === categoryId
            && JSON.stringify(r?.fields ?? []) === JSON.stringify(fields)
            && String(r?.pattern ?? "") === pattern
            && String(r?.flags ?? "") === flags
          );
          if (!exists) {
            const rule = {
              id: `ui_rule_${Date.now()}`,
              category_id: categoryId,
              confidence: 0.98,
              uncertain: false,
              fields,
              pattern,
              flags,
              note: computedNote,
            };
            next.regex_category_rules = [rule, ...rules];
          }
          return next;
        }

        // ignore
        const rules = Array.isArray(next.ignore_rules) ? next.ignore_rules : [];
        const reason = computedNote || `ui:ignore:${ruleField}:${patternRaw}`;
        const exists = rules.some((r: any) =>
          JSON.stringify(r?.fields ?? []) === JSON.stringify(fields)
          && String(r?.pattern ?? "") === pattern
          && String(r?.flags ?? "") === flags
          && String(r?.reason ?? "") === reason
        );
        if (!exists) {
          const rule = {
            id: `ui_ignore_${Date.now()}`,
            reason,
            fields,
            pattern,
            flags,
          };
          next.ignore_rules = [rule, ...rules];
        }
        return next;
      };

      if (ruleSaveToConfig) {
        if (!runCfg) throw new Error("Missing classifier config; please Load a run first.");
        const nextRunCfg = patchConfig(runCfg);
        await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/config/classifier`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextRunCfg),
        });
        setConfig(nextRunCfg as ClassifierConfig);
        setConfigText(JSON.stringify(nextRunCfg, null, 2));
      }

      if (ruleSaveToGlobal) {
        const globalCfg = await api<any>(baseUrl, "/api/config/classifier");
        let globalBase: any = globalCfg;
        if (ruleAction === "categorize") {
          const cats = Array.isArray(globalBase.categories) ? globalBase.categories : [];
          const hasCat = cats.some((c: any) => String(c?.id ?? "") === categoryId);
          if (!hasCat) {
            const fromRun = runCfg?.categories?.find((c: any) => String(c?.id ?? "") === categoryId);
            if (!fromRun) throw new Error(`Global config missing category: ${categoryId}`);
            globalBase = { ...globalBase, categories: [...cats, { id: String(fromRun.id), name: String(fromRun.name ?? fromRun.id) }] };
          }
        }
        const nextGlobalCfg = patchConfig(globalBase);
        await api<{ ok: boolean }>(baseUrl, "/api/config/classifier", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(nextGlobalCfg),
        });
      }

      const updates = matches.map((r) => {
        const txnId = String(r.txn_id ?? "").trim();
        const existingFinalNote = String(reviewEdits[txnId]?.final_note ?? r.final_note ?? "").trim();
        const patch: Record<string, unknown> = { txn_id: txnId };
        if (ruleAction === "categorize") {
          if (!categoryId) return patch;
          patch.final_category_id = categoryId;
          const currentIgnored = parseBoolish(String(reviewEdits[txnId]?.final_ignored ?? r.final_ignored ?? ""));
          if (ruleOverwriteFinal || currentIgnored) {
            patch.final_ignored = false;
            patch.final_ignore_reason = "";
          }
        } else {
          patch.final_ignored = true;
          patch.final_ignore_reason = computedNote;
          if (ruleOverwriteFinal) patch.final_category_id = "";
        }
        if (!existingFinalNote) patch.final_note = computedNote;
        return patch;
      });

      await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/review/updates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      });
      await loadReview();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const runStatus = state ? fmtStatus(state.status) : null;

  const reviewContextValue: ReviewContextType = {
    // State
    reviewRows, reviewEdits, reviewPendingOnly, reviewQuery, reviewOpen,
    reviewSelectedTxnId, reviewSelectedTxnIds,
    bulkTarget, bulkIncludeReviewed, bulkCategoryId, bulkIgnored, bulkNote, bulkContinuousMode,
    ruleField, ruleMode, ruleAction, rulePattern, ruleCategoryId, ruleOnlyPending,
    ruleOverwriteFinal, ruleSaveToConfig, ruleSaveToGlobal, ruleNote,
    newCategoryName, newCategoryId,
    config, configText, busy, error, runId,

    // Actions
    setReviewRows, setReviewEdits, setReviewPendingOnly, setReviewQuery, setReviewOpen,
    setReviewSelectedTxnId, setReviewSelectedTxnIds,
    setBulkTarget, setBulkIncludeReviewed, setBulkCategoryId, setBulkIgnored, setBulkNote, setBulkContinuousMode,
    setRuleField, setRuleMode, setRuleAction, setRulePattern, setRuleCategoryId, setRuleOnlyPending,
    setRuleOverwriteFinal, setRuleSaveToConfig, setRuleSaveToGlobal, setRuleNote,
    setNewCategoryName, setNewCategoryId,
    setError,
    loadReview, saveReviewEdits, applyBulkLocal, applyQuickRule, addCategory,

    // Derived
    categories, filteredReviewRows, filteredReviewTxnIds, selectedTxnIds, bulkEffectiveTxnIds,
    selectedReviewRow, selectedReviewFields, reviewPendingCount, rulePreview
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-4 font-sans antialiased">
      <div className="w-full px-4 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">OpenLedger</h1>
          <div className="flex items-center gap-4">
            <span className="text-xs text-muted-foreground font-mono">{runId || "No Run Selected"}</span>
            {runName ? (
              <span className="text-xs text-muted-foreground truncate max-w-[260px]" title={runName}>
                {runName}
              </span>
            ) : null}
            <Badge variant="outline" className="font-mono">v0.2</Badge>
          </div>
        </div>

        {/* Top Control Bar */}
        <div className="flex flex-wrap items-center gap-4 p-4 border rounded-lg bg-card shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Backend</span>
            <Input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-[200px] h-8 font-mono text-xs"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">Token</span>
            <Input
              value={apiToken}
              onChange={(e) => setApiToken(e.target.value)}
              placeholder="(optional)"
              type="password"
              className="w-[180px] h-8 font-mono text-xs"
            />
          </div>
          <Separator orientation="vertical" className="h-6" />
          <div className="flex items-center gap-2 flex-1">
            <Select value={runId} onValueChange={setRunId}>
              <SelectTrigger className="w-[240px] h-8 font-mono text-xs">
                <SelectValue placeholder="Select Run" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((r) => (
                  <SelectItem key={r} value={r} className="text-xs">
                    <span className="font-mono">{r}</span>
                    {(() => {
                      const name = String(runsMeta.find((m) => m.id === r)?.name ?? "").trim();
                      return name ? <span className="ml-2 text-muted-foreground">{name}</span> : null;
                    })()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="h-8 w-8 p-0" onClick={() => refreshRuns().catch((e) => setError(String(e)))} disabled={busy}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
            <Input
              value={newRunName}
              onChange={(e) => setNewRunName(e.target.value)}
              placeholder="新任务名称（可选）"
              className="w-[220px] h-8 text-xs"
              disabled={busy}
            />
            <Button size="sm" className="h-8" onClick={onCreateRun} disabled={busy}>
              <Play className="mr-2 h-3.5 w-3.5" /> New Run
            </Button>
          </div>
          {runStatus && (
            <Badge variant={runStatus.variant} className="gap-1 pl-2 h-7 px-2">
              {runStatus.icon && <runStatus.icon className="h-3.5 w-3.5" />}
              {runStatus.text}
            </Badge>
          )}
        </div>

        {error && <div className="text-sm text-destructive flex items-center gap-2 p-2 border border-destructive/20 bg-destructive/10 rounded-md"><AlertCircle className="h-4 w-4" /> {error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Pipeline Stages */}
          <WorkflowPanel
            state={state}
            runId={runId}
            busy={busy}
            selectedStageId={selectedStageId}
            setSelectedStageId={setSelectedStageId}
            startWorkflow={startWorkflow}
            resetClassify={resetClassify}
            cancelRun={cancelRun}
            baseUrl={baseUrl}
            selectFile={selectFile}
          />

          {/* Right Column: Configuration & Preview */}
          <div className="lg:col-span-8 space-y-6">
            {/* File Upload & Config Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="py-3">
                  <CardTitle className="text-base">Uploads</CardTitle>
                </CardHeader>
                <CardContent className="py-3">
                  <div className="flex items-center gap-2">
                    <Input
                      type="file"
                      multiple
                      onChange={(e) => onUpload(e.target.files)}
                      disabled={!runId || busy}
                      className="flex-1 cursor-pointer text-xs h-8"
                    />
                  </div>
                  {state?.inputs?.length ? (
                    <div className="mt-2 text-xs text-muted-foreground">
                      {state.inputs.length} files uploaded
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <SettingsCard state={state} busy={busy} saveOptions={saveOptions} />
            </div>

            {/* Preview Area */}
            {/* Preview Area */}
            <PreviewArea
              selectedFile={selectedFile}
              downloadHref={downloadHref}
              previewError={previewError}
              csvPreview={csvPreview}
              textPreview={textPreview}
              loadCsv={loadCsv}
            />

            {/* Specific Config/Review Cards (Optional/Contextual) */}
            <div className="grid gap-4">
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="outline" size="sm" className="w-full justify-between">
                    高级：分类器配置
                    <Clock className="h-3 w-3 opacity-50" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-2">
                  <Card>
                    <CardContent className="p-2">
                      <textarea
                        className="w-full min-h-[200px] p-2 rounded-md border bg-muted/50 font-mono text-xs focus:outline-none"
                        value={configText}
                        onChange={(e) => setConfigText(e.target.value)}
                      />
                      <div className="flex flex-wrap items-center gap-4 mt-2">
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id="cfg_save_run"
                            checked={cfgSaveToRun}
                            onCheckedChange={(chk: boolean | string) => setCfgSaveToRun(chk === true)}
                          />
                          <label
                            htmlFor="cfg_save_run"
                            className="text-xs leading-none text-muted-foreground"
                            title="写入当前任务 runs/<run_id>/config/classifier.json（只影响本任务的重跑）"
                          >
                            保存到本次任务
                          </label>
                        </div>
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id="cfg_save_global"
                            checked={cfgSaveToGlobal}
                            onCheckedChange={(chk: boolean | string) => setCfgSaveToGlobal(chk === true)}
                          />
                          <label
                            htmlFor="cfg_save_global"
                            className="text-xs leading-none text-muted-foreground"
                            title="写入全局 config/classifier.local.json（本地覆盖，避免误提交；影响后续新建任务）"
                          >
                            保存为默认（永久）
                          </label>
                        </div>
                      </div>
                      <Button size="sm" onClick={saveConfig} className="mt-2 w-full">保存配置</Button>
                    </CardContent>
                  </Card>
                </CollapsibleContent>
              </Collapsible>

              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="outline" size="sm" className="w-full justify-between">
                    Manual Review
                    <CheckCircle2 className="h-3 w-3 opacity-50" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-2">
                  <Card>
                    <CardContent className="p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={() => void loadReview()} disabled={!runId || busy}>Load</Button>
                        <Button size="sm" onClick={() => void openReview()} disabled={!runId || busy}>Open</Button>
                        <Badge variant="outline" className="h-7 text-[10px] font-mono">
                          pending {reviewPendingCount}
                        </Badge>
                        <Badge variant="outline" className="h-7 text-[10px] font-mono">
                          edited {Object.keys(reviewEdits).length}
                        </Badge>
                        <Badge variant="outline" className="h-7 text-[10px] font-mono ml-auto">
                          loaded {reviewRows.length}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        在弹窗里查看完整字段、批量应用规则，并保存到 <span className="font-mono">review.csv</span>。
                      </div>
                    </CardContent>
                  </Card>
                </CollapsibleContent>
              </Collapsible>
            </div>
          </div>
        </div>
      </div>

      <ReviewContext.Provider value={reviewContextValue}>
        <ReviewModal />
      </ReviewContext.Provider>
    </div>
  );
}
