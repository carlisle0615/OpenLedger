import { useCallback, useEffect, useMemo, useRef } from "react";
import { ClassifierConfig, CsvPreview, RunState } from "@/types";
import {
    api, parseBoolish, isPendingRow, escapeRegExp, suggestCategoryId,
    type RuleMatchMode, type RuleMatchField, type RuleAction,
} from "@/utils/helpers";
import { type ConfirmChoice } from "@/hooks/useConfirm";
import {
    useFilteredReviewRows, useReviewPendingCount, useSelectedReviewFields,
    ReviewContext, type ReviewContextType,
} from "@/hooks/useReviewContext";

/** useReviewActions 的依赖参数类型 */
export interface ReviewActionsDeps {
    baseUrl: string;
    runId: string;
    config: ClassifierConfig | null;
    configText: string;
    reviewFeedback: { type: "success" | "info"; text: string; ts: number } | null;
    busy: boolean;
    error: string;

    reviewRows: Record<string, string>[];
    reviewEdits: Record<string, Partial<Record<string, string | boolean>>>;
    reviewPendingOnly: boolean;
    reviewQuery: string;
    reviewOpen: boolean;
    reviewSelectedTxnId: string;
    reviewSelectedTxnIds: Record<string, boolean>;

    bulkTarget: "selected" | "filtered";
    bulkIncludeReviewed: boolean;
    bulkCategoryId: string;
    bulkIgnored: boolean;
    bulkNote: string;
    bulkContinuousMode: boolean;

    ruleField: RuleMatchField;
    ruleMode: RuleMatchMode;
    ruleAction: RuleAction;
    rulePattern: string;
    ruleCategoryId: string;
    ruleOnlyPending: boolean;
    ruleOverwriteFinal: boolean;
    ruleSaveToConfig: boolean;
    ruleSaveToGlobal: boolean;
    ruleNote: string;
    newCategoryName: string;
    newCategoryId: string;

    confirm: (opts: { title: string; description: string; confirmText: string; cancelText: string; tone: "default" | "danger" }) => Promise<boolean>;
    confirmChoice: (opts: {
        title: string;
        description: string;
        confirmText: string;
        cancelText: string;
        extraText: string;
        tone: "default" | "danger";
    }) => Promise<ConfirmChoice>;

    // setters
    setReviewRows: (v: Record<string, string>[]) => void;
    setReviewEdits: React.Dispatch<React.SetStateAction<Record<string, Partial<Record<string, string | boolean>>>>>;
    setReviewPendingOnly: (v: boolean) => void;
    setReviewQuery: (v: string) => void;
    setReviewOpen: (v: boolean) => void;
    setReviewSelectedTxnId: (v: string) => void;
    setReviewSelectedTxnIds: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
    setBulkTarget: (v: "selected" | "filtered") => void;
    setBulkIncludeReviewed: (v: boolean) => void;
    setBulkCategoryId: (v: string) => void;
    setBulkIgnored: React.Dispatch<React.SetStateAction<boolean>>;
    setBulkNote: (v: string) => void;
    setBulkContinuousMode: (v: boolean) => void;
    setRuleField: (v: RuleMatchField) => void;
    setRuleMode: (v: RuleMatchMode) => void;
    setRuleAction: (v: RuleAction) => void;
    setRulePattern: (v: string) => void;
    setRuleCategoryId: (v: string) => void;
    setRuleOnlyPending: (v: boolean) => void;
    setRuleOverwriteFinal: (v: boolean) => void;
    setRuleSaveToConfig: (v: boolean) => void;
    setRuleSaveToGlobal: (v: boolean) => void;
    setRuleNote: (v: string) => void;
    setNewCategoryName: (v: string) => void;
    setNewCategoryId: (v: string) => void;
    setReviewFeedback: (v: { type: "success" | "info"; text: string; ts: number } | null) => void;
    setConfig: (v: ClassifierConfig | null) => void;
    setConfigText: (v: string) => void;
    setBusy: (v: boolean) => void;
    setError: (v: string) => void;

    // 外部依赖
    saveConfigObject: (next: unknown) => Promise<void>;
}

export function useReviewActions(deps: ReviewActionsDeps) {
    const {
        baseUrl, runId, config, configText, reviewFeedback, busy, error,
        reviewRows, reviewEdits, reviewPendingOnly, reviewQuery, reviewOpen,
        reviewSelectedTxnId, reviewSelectedTxnIds,
        bulkTarget, bulkIncludeReviewed, bulkCategoryId, bulkIgnored, bulkNote, bulkContinuousMode,
        ruleField, ruleMode, ruleAction, rulePattern, ruleCategoryId,
        ruleOnlyPending, ruleOverwriteFinal, ruleSaveToConfig, ruleSaveToGlobal, ruleNote,
        newCategoryName, newCategoryId,
        confirm, confirmChoice, saveConfigObject,
        setReviewRows, setReviewEdits, setReviewSelectedTxnIds,
        setReviewOpen, setReviewSelectedTxnId,
        setRuleCategoryId, setNewCategoryName, setNewCategoryId,
        setReviewFeedback,
        setConfig, setConfigText,
        setBusy, setError, setBulkIgnored, setBulkCategoryId,
    } = deps;

    // ---- 派生数据 ----

    const categories = useMemo(() => config?.categories ?? [], [config]);

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

    const selectedReviewRow = useMemo(() => {
        if (!reviewSelectedTxnId) return null;
        const hit = reviewRows.find((r) => String(r.txn_id ?? "") === reviewSelectedTxnId);
        return hit ?? null;
    }, [reviewRows, reviewSelectedTxnId]);

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

        const baseRows = ruleOnlyPending
            ? reviewRows.filter((r) => isPendingRow(r, reviewEdits))
            : reviewRows;
        const matches: Record<string, string>[] = [];
        for (const r of baseRows) {
            if (!r) continue;
            const txnId = String(r.txn_id ?? "").trim();
            if (!txnId) continue;

            const currentFinal = String(reviewEdits[txnId]?.final_category_id ?? r.final_category_id ?? "").trim();
            const currentIgnored = parseBoolish(String(reviewEdits[txnId]?.final_ignored ?? r.final_ignored ?? ""));
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

    // ---- 核心函数 ----

    const requestCloseReview = useCallback(async () => {
        const hasEdits = Object.keys(reviewEdits).length > 0;
        if (hasEdits) {
            const choice = await confirmChoice({
                title: "关闭前保存修改？",
                description: "检测到未保存的复核修改，请选择如何处理。",
                confirmText: "保存并关闭",
                cancelText: "放弃并关闭",
                extraText: "继续编辑",
                tone: "danger",
            });
            if (choice === "confirm") {
                const ok = await saveReviewEdits();
                if (!ok) return false;
            } else if (choice === "cancel") {
                setReviewEdits({});
                setReviewFeedback({ type: "info", text: "已放弃未保存修改。", ts: Date.now() });
            } else {
                return false;
            }
        }
        if (window.location.hash === "#review") {
            window.history.replaceState(null, "", window.location.pathname + window.location.search);
        }
        setReviewOpen(false);
        return true;
    }, [confirmChoice, reviewEdits, saveReviewEdits, setReviewEdits, setReviewFeedback]);

    const loadReview = useCallback(async () => {
        if (!runId) return;
        const path = "output/classify/review.csv";
        setBusy(true);
        setError("");
        setReviewFeedback(null);
        try {
            const limit = 2000;
            let offset = 0;
            const rows: Record<string, string>[] = [];
            for (let guard = 0; guard < 1000; guard += 1) {
                const r = await api<CsvPreview>(
                    baseUrl,
                    `/api/v2/runs/${encodeURIComponent(runId)}/preview/table?path=${encodeURIComponent(path)}&limit=${limit}&offset=${offset}`,
                );
                rows.push(...r.rows);
                if (!r.has_more || r.next_offset == null) break;
                offset = r.next_offset;
                if (rows.length > 200_000) break;
            }
            setReviewRows(rows);
            setReviewEdits({});
            setReviewSelectedTxnIds({});
            setReviewFeedback({ type: "success", text: `已加载 ${rows.length} 条复核记录。`, ts: Date.now() });
        } catch (e) {
            setError(String(e));
            setReviewFeedback(null);
        } finally {
            setBusy(false);
        }
    }, [baseUrl, runId, setBusy, setError, setReviewRows, setReviewEdits, setReviewSelectedTxnIds, setReviewFeedback]);

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
        if (txnIds.length >= 100) {
            const ok = await confirm({
                title: "确认批量应用？",
                description: `将应用到 ${txnIds.length} 条记录。`,
                confirmText: "确认应用",
                cancelText: "取消",
                tone: "danger",
            });
            if (!ok) return;
        }

        if (!bulkIgnored && !bulkCategoryId.trim()) {
            setError("请先选择分类（或切换为\u201c不记账\u201d）。");
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
        setReviewFeedback({
            type: "info",
            text: `已本地应用 ${txnIds.length} 条，记得点击“保存”提交。`,
            ts: Date.now(),
        });

        if (bulkContinuousMode && txnIds.length === 1) {
            jumpToNextFiltered(txnIds[0]);
        }
    }

    async function saveReviewEdits(): Promise<boolean> {
        if (!runId) return false;
        const updates = Object.entries(reviewEdits).map(([txn_id, patch]) => ({ txn_id, ...patch }));
        if (updates.length === 0) return true;
        setBusy(true);
        setError("");
        setReviewFeedback(null);
        try {
            await api<{ ok: boolean }>(baseUrl, `/api/v2/runs/${encodeURIComponent(runId)}/review/updates`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ updates }),
            });
            await loadReview();
            setReviewFeedback({ type: "success", text: `已保存 ${updates.length} 条修改。`, ts: Date.now() });
            return true;
        } catch (e) {
            setError(String(e));
            setReviewFeedback(null);
            return false;
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
            setError("分类 ID 不能为空。");
            return;
        }
        const cfg = config ?? (configText ? JSON.parse(configText) : null);
        if (!cfg || typeof cfg !== "object") {
            setError("缺少分类器配置，请先加载任务。");
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
        setReviewFeedback({ type: "success", text: `已新增分类 ${name}。`, ts: Date.now() });
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
        if (matches.length >= 50 || ruleOverwriteFinal || ruleSaveToGlobal) {
            const notes: string[] = [];
            if (ruleOverwriteFinal) notes.push("覆盖已填写的最终结果");
            if (ruleSaveToGlobal) notes.push("写入全局默认配置");
            const extra = notes.length ? `，并${notes.join("、")}` : "";
            const ok = await confirm({
                title: "确认应用快速规则？",
                description: `将应用到 ${matches.length} 条记录${extra}。`,
                confirmText: "确认应用",
                cancelText: "取消",
                tone: "danger",
            });
            if (!ok) return;
        }

        setBusy(true);
        setError("");
        setReviewFeedback(null);
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
                    if (!categoryExists) throw new Error(`配置中未找到分类 ID：${categoryId}`);
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
                if (!runCfg) throw new Error("缺少分类器配置，请先加载任务。");
                const nextRunCfg = patchConfig(runCfg);
                await api<{ ok: boolean }>(baseUrl, `/api/v2/runs/${encodeURIComponent(runId)}/config/classifier`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(nextRunCfg),
                });
                setConfig(nextRunCfg as ClassifierConfig);
                setConfigText(JSON.stringify(nextRunCfg, null, 2));
            }

            if (ruleSaveToGlobal) {
                const globalCfg = await api<any>(baseUrl, "/api/v2/config/classifier");
                let globalBase: any = globalCfg;
                if (ruleAction === "categorize") {
                    const cats = Array.isArray(globalBase.categories) ? globalBase.categories : [];
                    const hasCat = cats.some((c: any) => String(c?.id ?? "") === categoryId);
                    if (!hasCat) {
                        const fromRun = runCfg?.categories?.find((c: any) => String(c?.id ?? "") === categoryId);
                        if (!fromRun) throw new Error(`全局配置缺少分类 ID：${categoryId}`);
                        globalBase = { ...globalBase, categories: [...cats, { id: String(fromRun.id), name: String(fromRun.name ?? fromRun.id) }] };
                    }
                }
                const nextGlobalCfg = patchConfig(globalBase);
                await api<{ ok: boolean }>(baseUrl, "/api/v2/config/classifier", {
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

            // 保留当前本地未保存编辑，并叠加本次规则写入的字段，避免 loadReview 后被清空。
            const preservedEdits: Record<string, Partial<Record<string, string | boolean>>> = {
                ...reviewEdits,
            };
            for (const item of updates) {
                const txnId = String(item.txn_id ?? "").trim();
                if (!txnId) continue;
                const nextPatch: Partial<Record<string, string | boolean>> = {
                    ...(preservedEdits[txnId] ?? {}),
                };
                for (const key of ["final_category_id", "final_note", "final_ignored", "final_ignore_reason"] as const) {
                    if (Object.prototype.hasOwnProperty.call(item, key)) {
                        nextPatch[key] = item[key] as string | boolean;
                    }
                }
                preservedEdits[txnId] = nextPatch;
            }

            await api<{ ok: boolean }>(baseUrl, `/api/v2/runs/${encodeURIComponent(runId)}/review/updates`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ updates }),
            });
            await loadReview();
            setReviewEdits(preservedEdits);
            setReviewFeedback({ type: "success", text: `规则已应用到 ${matches.length} 条记录。`, ts: Date.now() });
        } catch (e) {
            setError(String(e));
            setReviewFeedback(null);
        } finally {
            setBusy(false);
        }
    }

    // ---- 副作用 ----

    const autoLoadRef = useRef<string>("");

    // hash 同步
    useEffect(() => {
        const sync = () => {
            const open = window.location.hash === "#review";
            if (open) {
                setReviewOpen(true);
            } else if (reviewOpen) {
                void (async () => {
                    const closed = await requestCloseReview();
                    if (!closed && window.location.hash !== "#review") {
                        window.location.hash = "review";
                    }
                })();
            }
        };
        sync();
        window.addEventListener("hashchange", sync);
        return () => window.removeEventListener("hashchange", sync);
    }, [reviewOpen, requestCloseReview]);

    // 自动加载
    useEffect(() => {
        if (!reviewOpen) {
            autoLoadRef.current = "";
            return;
        }
        if (!runId) return;
        if (autoLoadRef.current === runId) return;
        autoLoadRef.current = runId;
        void loadReview();
    }, [reviewOpen, runId, loadReview]);

    // Escape 关闭
    useEffect(() => {
        if (!reviewOpen) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                void requestCloseReview();
            }
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [reviewOpen, requestCloseReview]);

    // 自动选中第一条
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

    // 连续模式键盘导航
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
                setBulkIgnored((prev: boolean) => !prev);
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

    // ---- 组装 Context Value ----

    const reviewContextValue: ReviewContextType = {
        // State
        reviewRows, reviewEdits, reviewPendingOnly, reviewQuery, reviewOpen,
        reviewSelectedTxnId, reviewSelectedTxnIds,
        bulkTarget, bulkIncludeReviewed, bulkCategoryId, bulkIgnored, bulkNote, bulkContinuousMode,
        ruleField, ruleMode, ruleAction, rulePattern, ruleCategoryId, ruleOnlyPending,
        ruleOverwriteFinal, ruleSaveToConfig, ruleSaveToGlobal, ruleNote,
        newCategoryName, newCategoryId,
        reviewFeedback,
        config, configText, busy, error, runId,

        // Actions
        setReviewRows: deps.setReviewRows,
        setReviewEdits: deps.setReviewEdits,
        setReviewPendingOnly: deps.setReviewPendingOnly,
        setReviewQuery: deps.setReviewQuery,
        setReviewOpen: deps.setReviewOpen,
        setReviewSelectedTxnId: deps.setReviewSelectedTxnId,
        setReviewSelectedTxnIds: deps.setReviewSelectedTxnIds,
        setBulkTarget: deps.setBulkTarget,
        setBulkIncludeReviewed: deps.setBulkIncludeReviewed,
        setBulkCategoryId: deps.setBulkCategoryId,
        setBulkIgnored: deps.setBulkIgnored,
        setBulkNote: deps.setBulkNote,
        setBulkContinuousMode: deps.setBulkContinuousMode,
        setRuleField: deps.setRuleField,
        setRuleMode: deps.setRuleMode,
        setRuleAction: deps.setRuleAction,
        setRulePattern: deps.setRulePattern,
        setRuleCategoryId: deps.setRuleCategoryId,
        setRuleOnlyPending: deps.setRuleOnlyPending,
        setRuleOverwriteFinal: deps.setRuleOverwriteFinal,
        setRuleSaveToConfig: deps.setRuleSaveToConfig,
        setRuleSaveToGlobal: deps.setRuleSaveToGlobal,
        setRuleNote: deps.setRuleNote,
        setNewCategoryName: deps.setNewCategoryName,
        setNewCategoryId: deps.setNewCategoryId,
        setReviewFeedback: deps.setReviewFeedback,
        setError: deps.setError,
        loadReview, saveReviewEdits, applyBulkLocal, applyQuickRule, addCategory, requestCloseReview,

        // Derived
        categories, filteredReviewRows, filteredReviewTxnIds, selectedTxnIds, bulkEffectiveTxnIds,
        selectedReviewRow, selectedReviewFields, reviewPendingCount, rulePreview,
    };

    return {
        // 导出供 App 使用的函数和数据
        loadReview,
        openReview,
        setEdit,
        isTxnIgnored,
        applyLocalEdits,
        requestCloseReview,
        reviewContextValue,

        // 派生数据
        categories,
        filteredReviewRows,
        reviewPendingCount,
    };
}

export { ReviewContext };
