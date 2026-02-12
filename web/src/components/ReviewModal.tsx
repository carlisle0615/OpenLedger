import React, { useEffect, useRef } from "react";
import { useReviewContext } from "@/hooks/useReviewContext";
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
import { ScrollArea } from "@/components/ui/scroll-area";
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
  Loader2, Play, Ban, RefreshCw, FileText, Upload, CheckCircle2, XCircle, AlertCircle, Clock, FileInput, CreditCard, Landmark, GitMerge, Fingerprint, Flag, Download, RotateCcw, ChevronDown, ChevronRight, Check
} from "lucide-react";
import { Search, ListChecks, Plus, Save } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtStatus, api, isCsvFile, isTextFile, parseBoolish, escapeRegExp, slugifyId, suggestCategoryId, type RuleMatchMode, type RuleMatchField, type RuleAction } from "@/utils/helpers";

function fmtMoney(value: unknown) {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  const cleaned = raw.replace(/[￥¥,]/g, "");
  const num = Number(cleaned);
  if (!Number.isFinite(num)) return raw;
  return num.toFixed(2);
}

const REVIEW_RECENT_CATEGORY_KEY = "openledger.review.recent_categories";

export function ReviewModal() {
  const {
    // State
    reviewRows, reviewEdits, reviewPendingOnly, reviewQuery, reviewOpen,
    reviewSelectedTxnId, reviewSelectedTxnIds,
    bulkTarget, bulkIncludeReviewed, bulkCategoryId, bulkIgnored, bulkNote, bulkContinuousMode,
    ruleField, ruleMode, ruleAction, rulePattern, ruleCategoryId, ruleOnlyPending,
    ruleOverwriteFinal, ruleSaveToConfig, ruleSaveToGlobal, ruleNote,
    newCategoryName, newCategoryId,
    reviewFeedback, config, configText, busy, error, runId,

    // Actions
    setReviewRows, setReviewEdits, setReviewPendingOnly, setReviewQuery, setReviewOpen,
    setReviewSelectedTxnId, setReviewSelectedTxnIds,
    setBulkTarget, setBulkIncludeReviewed, setBulkCategoryId, setBulkIgnored, setBulkNote, setBulkContinuousMode,
    setRuleField, setRuleMode, setRuleAction, setRulePattern, setRuleCategoryId, setRuleOnlyPending,
    setRuleOverwriteFinal, setRuleSaveToConfig, setRuleSaveToGlobal, setRuleNote,
    setNewCategoryName, setNewCategoryId,
    setReviewFeedback,
    setError,
    loadReview, saveReviewEdits, applyBulkLocal, applyQuickRule, addCategory,
    requestCloseReview,

    // Derived
    categories, filteredReviewRows, filteredReviewTxnIds, selectedTxnIds, bulkEffectiveTxnIds,
    selectedReviewRow, selectedReviewFields, reviewPendingCount, rulePreview
  } = useReviewContext();

  type DragSelectMode = "select" | "deselect";
  const dragSelectRef = useRef<{ active: boolean; mode: DragSelectMode } | null>(null);

  useEffect(() => {
    const stop = () => {
      dragSelectRef.current = null;
    };
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, []);

  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const [finalCategoryQuery, setFinalCategoryQuery] = React.useState("");
  const [recentCategoryIds, setRecentCategoryIds] = React.useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem(REVIEW_RECENT_CATEGORY_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed.map((v) => String(v)).filter(Boolean).slice(0, 8);
    } catch {
      return [];
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(REVIEW_RECENT_CATEGORY_KEY, JSON.stringify(recentCategoryIds.slice(0, 8)));
    } catch {
      // ignore
    }
  }, [recentCategoryIds]);

  const rememberRecentCategory = React.useCallback((categoryId: string) => {
    const id = String(categoryId ?? "").trim();
    if (!id) return;
    setRecentCategoryIds((prev) => [id, ...prev.filter((x) => x !== id)].slice(0, 8));
  }, []);

  useEffect(() => {
    setFinalCategoryQuery("");
  }, [reviewSelectedTxnId]);

  // Helper functions
  const isTxnIgnored = (txnId: string, row?: Record<string, string>) => {
    const r = row ?? reviewRows.find((x) => x.txn_id === txnId);
    if (!r) return false;
    const override = reviewEdits[txnId]?.final_ignored;
    const raw = String(override ?? r.final_ignored ?? "").trim();
    if (raw !== "") return parseBoolish(raw);
    return parseBoolish(r.suggested_ignored);
  };

  const setEdit = (txnId: string, key: string, val: string | boolean) => {
    setReviewEdits((prev) => ({
      ...prev,
      [txnId]: { ...(prev[txnId] || {}), [key]: val },
    }));
  };

  const applyLocalEdits = (ids: string[], patch: Partial<Record<string, string | boolean>>) => {
    setReviewEdits((prev) => {
      const next = { ...prev };
      ids.forEach((id) => {
        next[id] = { ...(next[id] || {}), ...patch };
      });
      return next;
    });
  };

  const setTxnSelected = (txnId: string, on: boolean) => {
    setReviewSelectedTxnIds((prev) => {
      const alreadyOn = Boolean(prev[txnId]);
      if (alreadyOn === on) return prev;
      const next: Record<string, boolean> = { ...prev };
      if (on) next[txnId] = true;
      else delete next[txnId];
      return next;
    });
  };

  const startDragSelect = (txnId: string) => {
    const mode: DragSelectMode = reviewSelectedTxnIds[txnId] ? "deselect" : "select";
    dragSelectRef.current = { active: true, mode };
    setTxnSelected(txnId, mode === "select");
  };

  const continueDragSelect = (txnId: string) => {
    const st = dragSelectRef.current;
    if (!st?.active) return;
    setTxnSelected(txnId, st.mode === "select");
  };

  const jumpToNextFiltered = (currId: string, direction: number = 1) => {
    const idx = filteredReviewTxnIds.indexOf(currId);
    if (idx === -1) return;
    const nextIdx = idx + direction;
    if (nextIdx >= 0 && nextIdx < filteredReviewTxnIds.length) {
      setReviewSelectedTxnId(filteredReviewTxnIds[nextIdx]);
    }
  };

  const selectedFinalCategoryId = String(
    (reviewEdits[reviewSelectedTxnId]?.final_category_id as string)
    ?? selectedReviewRow?.final_category_id
    ?? "",
  ).trim();
  const selectedFinalIgnoredRaw = String(
    (reviewEdits[reviewSelectedTxnId]?.final_ignored as any)
    ?? selectedReviewRow?.final_ignored
    ?? "",
  ).trim();
  const selectedIgnored = selectedFinalIgnoredRaw !== ""
    ? parseBoolish(selectedFinalIgnoredRaw)
    : parseBoolish(selectedReviewRow?.suggested_ignored);
  const selectedPending = Boolean(selectedReviewRow)
    && parseBoolish(selectedReviewRow?.suggested_uncertain)
    && !selectedFinalCategoryId
    && !selectedIgnored;
  const suggestedCategoryId = String(selectedReviewRow?.suggested_category_id ?? "").trim();
  const suggestedCategoryName = String(
    selectedReviewRow?.suggested_category_name
    ?? selectedReviewRow?.suggested_category_id
    ?? "",
  ).trim();
  const finalCategoryOptions = React.useMemo(() => {
    const categories = config?.categories ?? [];
    if (!selectedPending || !suggestedCategoryId) return categories;
    const idx = categories.findIndex((c) => String(c.id) === suggestedCategoryId);
    if (idx === -1) {
      return [{ id: suggestedCategoryId, name: suggestedCategoryName || suggestedCategoryId }, ...categories];
    }
    const suggested = categories[idx];
    return [suggested, ...categories.filter((_, i) => i !== idx)];
  }, [config?.categories, selectedPending, suggestedCategoryId, suggestedCategoryName]);
  const finalCategoryQueryLower = finalCategoryQuery.trim().toLowerCase();
  const filteredFinalCategoryOptions = React.useMemo(() => {
    if (!finalCategoryQueryLower) return finalCategoryOptions;
    return finalCategoryOptions.filter((c) => {
      const name = String(c.name ?? "").toLowerCase();
      const id = String(c.id ?? "").toLowerCase();
      return name.includes(finalCategoryQueryLower) || id.includes(finalCategoryQueryLower);
    });
  }, [finalCategoryOptions, finalCategoryQueryLower]);
  const recentFinalCategoryOptions = React.useMemo(() => {
    const map = new Map(finalCategoryOptions.map((c) => [String(c.id), c]));
    const visible = new Set(filteredFinalCategoryOptions.map((c) => String(c.id)));
    return recentCategoryIds
      .map((id) => map.get(id))
      .filter((c): c is { id: string; name: string } => {
        if (!c) return false;
        const id = String(c.id);
        if (!visible.has(id)) return false;
        if (selectedPending && id === suggestedCategoryId) return false;
        return true;
      });
  }, [finalCategoryOptions, filteredFinalCategoryOptions, recentCategoryIds, selectedPending, suggestedCategoryId]);
  const recentFinalCategorySet = React.useMemo(
    () => new Set(recentFinalCategoryOptions.map((c) => String(c.id))),
    [recentFinalCategoryOptions],
  );
  const commonFinalCategoryOptions = React.useMemo(
    () => filteredFinalCategoryOptions.filter((c) => {
      const id = String(c.id);
      if (selectedPending && id === suggestedCategoryId) return false;
      return !recentFinalCategorySet.has(id);
    }),
    [filteredFinalCategoryOptions, selectedPending, suggestedCategoryId, recentFinalCategorySet],
  );

  if (!reviewOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background">
      <div className="fixed inset-0 flex">
        <div className="w-full h-full bg-background overflow-hidden flex flex-col min-h-0">
          <div className="p-3 border-b flex items-center gap-2">
            <div className="font-semibold">人工复核</div>
            <Badge variant="outline" className="h-6 text-[10px] font-mono">待复核 {reviewPendingCount}</Badge>
            <Badge variant="outline" className="h-6 text-[10px] font-mono">已编辑 {Object.keys(reviewEdits).length}</Badge>
            <Badge variant="outline" className="h-6 text-[10px] font-mono">已加载 {reviewRows.length}</Badge>
            <div className="ml-auto flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => void loadReview()} disabled={!runId || busy}>重新加载</Button>
              <Button size="sm" onClick={saveReviewEdits} disabled={!Object.keys(reviewEdits).length || busy}>保存</Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void requestCloseReview()}
                disabled={busy}
              >
                关闭
              </Button>
            </div>
          </div>

          {error ? (
            <div className="mx-3 mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="truncate">{error}</span>
            </div>
          ) : null}
          {reviewFeedback ? (
            <div className={cn(
              "mx-3 mt-3 rounded-md border px-3 py-2 text-xs flex items-center gap-2",
              reviewFeedback.type === "success"
                ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                : "border-blue-300 bg-blue-50 text-blue-700",
            )}>
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span className="flex-1 truncate">{reviewFeedback.text}</span>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[10px]"
                onClick={() => setReviewFeedback(null)}
              >
                关闭提示
              </Button>
            </div>
          ) : null}

          <div className="flex-1 flex overflow-hidden min-h-0">
            {/* Left: list */}
            <div className="w-[56%] border-r flex flex-col overflow-hidden min-h-0">
              <div className="p-3 border-b space-y-2">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="pending_only_modal"
                      checked={reviewPendingOnly}
                      onCheckedChange={(chk: boolean | string) => setReviewPendingOnly(chk === true)}
                    />
                    <label
                      htmlFor="pending_only_modal"
                      className="text-xs leading-none text-muted-foreground"
                      title="只显示“需要人工确认”的记录（建议不确定、未填写最终分类且未被忽略）"
                    >
                      仅待复核
                    </label>
                  </div>
                  <Input
                    value={reviewQuery}
                    onChange={(e) => setReviewQuery(e.target.value)}
                    placeholder="搜索：商户/商品/备注..."
                    className="h-7 text-xs w-[260px]"
                  />
                  <Badge variant="outline" className="h-7 text-[10px] font-mono ml-auto" title="当前列表数量 / 总加载数量">
                    {filteredReviewRows.length}/{reviewRows.length}
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="h-7 text-[10px] font-mono" title="当前已勾选的交易 ID 数量（用于批量操作）">
                    已选 {selectedTxnIds.length}
                  </Badge>

                  <Select value={bulkTarget} onValueChange={(v: "selected" | "filtered") => setBulkTarget(v)}>
                    <SelectTrigger className="h-7 text-xs w-[150px]" title="选择批量操作的作用范围">
                      <SelectValue placeholder="应用到..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="selected">应用到：已选行</SelectItem>
                      <SelectItem value="filtered">应用到：当前筛选结果</SelectItem>
                    </SelectContent>
                  </Select>

                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="bulk_include_reviewed"
                      checked={bulkIncludeReviewed}
                      disabled={bulkTarget !== "filtered"}
                      onCheckedChange={(chk: boolean | string) => setBulkIncludeReviewed(chk === true)}
                    />
                    <label
                      htmlFor="bulk_include_reviewed"
                      className={cn("text-xs leading-none text-muted-foreground", bulkTarget !== "filtered" && "opacity-60")}
                      title="当选择“当前筛选结果”时：是否包含已复核的行（忽略“仅待复核”筛选）"
                    >
                      包含已复核
                    </label>
                  </div>

                  <Select
                    value={bulkCategoryId || "__none__"}
                    onValueChange={(v: string) => setBulkCategoryId(v === "__none__" ? "" : v)}
                    disabled={bulkIgnored}
                  >
                    <SelectTrigger
                      className="h-7 text-xs w-[180px]"
                      title={bulkIgnored ? "已选择「不记账」，分类将被忽略" : "选择要写入 final_category_id 的分类"}
                    >
                      <SelectValue placeholder="选择分类..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">(未选择)</SelectItem>
                      {config?.categories?.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="bulk_ignored"
                      checked={bulkIgnored}
                      onCheckedChange={(chk: boolean | string) => setBulkIgnored(chk === true)}
                    />
                    <label htmlFor="bulk_ignored" className="text-xs leading-none text-muted-foreground" title="勾选后将写入 final_ignored=true（本条不计入统计）">
                      不记账
                    </label>
                  </div>

                  <Input
                    value={bulkNote}
                    onChange={(e) => setBulkNote(e.target.value)}
                    placeholder="备注/原因（可选）"
                    className="h-7 text-xs w-[240px]"
                    title="批量写入：记账时写到 final_note；不记账时写到 final_note 和 final_ignore_reason"
                  />

                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="bulk_continuous"
                      checked={bulkContinuousMode}
                      onCheckedChange={(chk: boolean | string) => setBulkContinuousMode(chk === true)}
                    />
                    <label
                      htmlFor="bulk_continuous"
                      className="text-xs leading-none text-muted-foreground"
                      title="开启后：点击一行即应用当前设置，并自动跳到下一条；支持快捷键"
                    >
                      连续标注
                    </label>
                  </div>

                  <Button
                    size="sm"
                    className="h-7"
                    onClick={() => void applyBulkLocal()}
                    disabled={
                      busy
                      || (bulkContinuousMode ? !reviewSelectedTxnId : bulkEffectiveTxnIds.length === 0)
                      || (!bulkIgnored && !bulkCategoryId.trim())
                    }
                    title={bulkContinuousMode ? "应用到当前选中行，并自动跳到下一条" : "应用到选定范围"}
                  >
                    {bulkContinuousMode ? "应用并下一条" : `批量应用（${bulkEffectiveTxnIds.length}）`}
                  </Button>

                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7"
                    onClick={() => setReviewSelectedTxnIds({})}
                    disabled={selectedTxnIds.length === 0 || busy}
                    title="清空勾选"
                  >
                    清空选择
                  </Button>
                </div>

                {bulkContinuousMode ? (
                  <div className="text-xs text-muted-foreground">
                    快捷键：<span className="font-mono">1~9</span> 选分类，<span className="font-mono">I</span> 切换不记账，<span className="font-mono">回车</span> 应用，<span className="font-mono">↑/↓</span> 移动
                  </div>
                ) : null}
              </div>

              <ScrollArea className="flex-1">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="h-9 text-xs w-[42px]">
                        <Checkbox
                          checked={filteredReviewTxnIds.length > 0 && filteredReviewTxnIds.every((id) => Boolean(reviewSelectedTxnIds[id]))}
                          onCheckedChange={(chk: boolean | string) => {
                            const on = chk === true;
                            setReviewSelectedTxnIds((prev) => {
                              const next: Record<string, boolean> = { ...prev };
                              if (on) {
                                for (const id of filteredReviewTxnIds) next[id] = true;
                              } else {
                                for (const id of filteredReviewTxnIds) delete next[id];
                              }
                              return next;
                            });
                          }}
                          title="全选/取消全选：当前筛选结果"
                        />
                      </TableHead>
                      <TableHead className="h-9 text-xs w-[90px]">日期</TableHead>
                      <TableHead className="h-9 text-xs text-right w-[90px]">金额</TableHead>
                      <TableHead className="h-9 text-xs">商户</TableHead>
                      <TableHead className="h-9 text-xs">商品</TableHead>
                      <TableHead className="h-9 text-xs w-[120px]">建议</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredReviewRows.map((r) => {
                      const pending = String(r.__pending ?? "") === "true";
                      const txnId = String(r.txn_id ?? "");
                      const rowKey = `${txnId}-${String(r.__row_idx ?? "")}`;
                      const ignored = isTxnIgnored(txnId, r);
                      const active = txnId && txnId === reviewSelectedTxnId;
                      return (
                        <TableRow
                          key={rowKey}
                          className={cn(
                            "h-9 cursor-pointer",
                            ignored && !active && "bg-muted/30",
                            pending && "bg-[hsl(var(--warning))]/5",
                            active && "bg-accent"
                          )}
                          onClick={() => {
                            if (!txnId) return;
                            if (bulkContinuousMode) {
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
                              applyLocalEdits([txnId], patch);
                              jumpToNextFiltered(txnId);
                              return;
                            }
                            setReviewSelectedTxnId(txnId);
                          }}
                        >
                          <TableCell
                            className="py-1"
                            onPointerDown={(e) => {
                              e.stopPropagation();
                              if (!txnId) return;
                              if (e.button !== 0) return;
                              startDragSelect(txnId);
                            }}
                            onPointerEnter={(e) => {
                              if (!txnId) return;
                              if (e.buttons !== 1) return;
                              continueDragSelect(txnId);
                            }}
                          >
                            <div onClick={(e) => e.stopPropagation()}>
                              <Checkbox
                                className="pointer-events-none"
                                checked={Boolean(reviewSelectedTxnIds[txnId])}
                                onCheckedChange={(chk: boolean | string) => {
                                  const on = chk === true;
                                  setTxnSelected(txnId, on);
                                }}
                                title="勾选后可批量应用分类/忽略"
                              />
                            </div>
                          </TableCell>
                          <TableCell className="font-mono whitespace-nowrap py-1">{String(r.trade_date ?? "")}</TableCell>
                          <TableCell className="font-mono whitespace-nowrap text-right py-1">{fmtMoney(r.amount)}</TableCell>
                          <TableCell className="truncate max-w-[220px] py-1" title={String(r.merchant ?? "")}>{String(r.merchant ?? "")}</TableCell>
                          <TableCell className="truncate max-w-[220px] py-1" title={String(r.item ?? "")}>{String(r.item ?? "")}</TableCell>
                          <TableCell className="py-1">
                            <div className="text-[10px] text-muted-foreground truncate max-w-[150px]" title={String(r.suggested_category_name ?? r.suggested_category_id ?? "")}>
                              <div className="flex items-center gap-2">
                                <span className="truncate">{String(r.suggested_category_name ?? r.suggested_category_id ?? "")}</span>
                                {ignored ? (
                                  <Badge variant="secondary" className="h-5 text-[10px]" title="该条已标记为不记账（低饱和提示，不计入统计）">
                                    不记账
                                  </Badge>
                                ) : null}
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </ScrollArea>
            </div>

            {/* Right: details + quick rules */}
            <div className="flex-1 flex flex-col overflow-hidden min-h-0">
              {!selectedReviewRow ? (
                <div className="flex-1 flex items-center justify-center text-muted-foreground">
                  先加载 <span className="font-mono mx-1">review.csv</span>，再选择一条记录。
                </div>
              ) : (
                <ScrollArea className="flex-1 min-h-0">
                  <div className="p-4 space-y-4">
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-base">
                          {String(selectedReviewRow.merchant ?? "") || "（无商户）"}
                        </CardTitle>
                        <CardDescription className="font-mono text-[10px] text-muted-foreground/70">
                          交易 ID={String(selectedReviewRow.txn_id ?? "")}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="py-3 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            ["trade_date", "交易日期"],
                            ["trade_time", "交易时间"],
                            ["post_date", "入账日期"],
                            ["account", "账户"],
                            ["amount", "金额"],
                            ["flow", "收支"],
                            ["pay_method", "支付方式"],
                            ["category", "原始分类"],
                          ].map(([k, label]) => (
                            <div key={k} className="space-y-1">
                              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
                              <div className="text-xs font-mono break-words">{String((selectedReviewRow as any)[k] ?? "") || "-"}</div>
                            </div>
                          ))}
                        </div>

                        <Separator />

                        <div className="space-y-2">
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">建议</div>
                              <div className="text-xs">
                                <span className="font-mono">{String(selectedReviewRow.suggested_category_name ?? selectedReviewRow.suggested_category_id ?? "") || "-"}</span>
                                <span className="text-muted-foreground ml-2 font-mono text-[11px]">
                                  置信度={String(selectedReviewRow.suggested_confidence ?? "") || "-"}
                                </span>
                                {parseBoolish(selectedReviewRow.suggested_uncertain) ? (
                                  <Badge variant="secondary" className="ml-2 h-5 text-[10px]">不确定</Badge>
                                ) : null}
                              </div>
                              <div className="text-xs text-muted-foreground whitespace-pre-wrap break-words">
                                {String(selectedReviewRow.suggested_note ?? "")}
                              </div>
                            </div>
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">最终</div>
                                <Badge variant="outline" className="h-5 text-[10px] font-mono">
                                  {String(selectedReviewRow.trade_date ?? "")}
                                </Badge>
                              </div>
                              <Select
                                value={String((reviewEdits[reviewSelectedTxnId]?.final_category_id as string) ?? selectedReviewRow.final_category_id ?? "")}
                                onValueChange={(v: string) => {
                                  const val = v === "__clear__" ? "" : v;
                                  setEdit(reviewSelectedTxnId, "final_category_id", val);
                                  if (val) rememberRecentCategory(val);
                                }}
                              >
                                <SelectTrigger className="h-8 text-xs w-full">
                                  <SelectValue placeholder="（使用建议）" />
                                </SelectTrigger>
                                <SelectContent>
                                  <div className="px-2 py-1.5 border-b sticky top-0 bg-popover z-10">
                                    <Input
                                      value={finalCategoryQuery}
                                      onChange={(e) => setFinalCategoryQuery(e.target.value)}
                                      onKeyDown={(e) => e.stopPropagation()}
                                      placeholder="搜索分类名称/ID..."
                                      className="h-7 text-xs"
                                    />
                                  </div>
                                  {!selectedPending ? <SelectItem value="__clear__">（清空）</SelectItem> : null}
                                  {selectedPending && suggestedCategoryId && filteredFinalCategoryOptions.some((c) => String(c.id) === suggestedCategoryId) ? (
                                    <SelectItem value={suggestedCategoryId}>
                                      {`建议：${String((filteredFinalCategoryOptions.find((c) => String(c.id) === suggestedCategoryId)?.name ?? suggestedCategoryName) || suggestedCategoryId)}`}
                                    </SelectItem>
                                  ) : null}
                                  {!finalCategoryQueryLower && recentFinalCategoryOptions.length > 0 ? (
                                    <div className="px-2 pt-1 pb-0.5 text-[10px] text-muted-foreground">最近使用</div>
                                  ) : null}
                                  {(!finalCategoryQueryLower ? recentFinalCategoryOptions : []).map((c) => (
                                    <SelectItem key={`recent-${c.id}`} value={c.id}>
                                      {c.name}
                                    </SelectItem>
                                  ))}
                                  {commonFinalCategoryOptions.map((c) => (
                                    <SelectItem key={c.id} value={c.id}>
                                      {c.name}
                                    </SelectItem>
                                  ))}
                                  {filteredFinalCategoryOptions.length === 0 ? (
                                    <div className="px-2 py-2 text-xs text-muted-foreground">无匹配分类</div>
                                  ) : null}
                                  {selectedPending ? <SelectItem value="__clear__">（清空）</SelectItem> : null}
                                </SelectContent>
                              </Select>
                              <div className="flex items-center gap-2">
                                <Checkbox
                                  id="final_ignored"
                                  checked={parseBoolish((reviewEdits[reviewSelectedTxnId]?.final_ignored as any) ?? selectedReviewRow.final_ignored ?? "")}
                                  onCheckedChange={(chk: boolean | string) => setEdit(reviewSelectedTxnId, "final_ignored", chk === true)}
                                />
                                <label htmlFor="final_ignored" className="text-xs leading-none text-muted-foreground">
                                  不记账
                                </label>
                                <Input
                                  value={String((reviewEdits[reviewSelectedTxnId]?.final_ignore_reason as any) ?? selectedReviewRow.final_ignore_reason ?? "")}
                                  onChange={(e) => setEdit(reviewSelectedTxnId, "final_ignore_reason", e.target.value)}
                                  placeholder="不记账原因（可选）"
                                  className="h-7 text-xs"
                                />
                              </div>
                              <textarea
                                className="w-full min-h-[70px] p-2 rounded-md border bg-muted/50 font-mono text-xs focus:outline-none"
                                value={String((reviewEdits[reviewSelectedTxnId]?.final_note as any) ?? selectedReviewRow.final_note ?? "")}
                                onChange={(e) => setEdit(reviewSelectedTxnId, "final_note", e.target.value)}
                                placeholder="最终备注（可选）"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">备注 / 来源</div>
                            <div className="text-xs whitespace-pre-wrap break-words">
                              {String(selectedReviewRow.remark ?? "")}
                            </div>
                            <div className="text-[11px] text-muted-foreground font-mono break-words">
                              {String(selectedReviewRow.sources ?? "")}
                            </div>
                          </div>

                          <Separator />

                          <Collapsible defaultOpen>
                            <CollapsibleTrigger asChild>
                              <Button variant="outline" size="sm" className="h-8 w-full justify-between text-xs">
                                全部字段（便于判断）
                                <Clock className="h-3 w-3 opacity-50" />
                              </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent className="mt-2">
                              <div className="border rounded-md overflow-hidden">
                                <ScrollArea className="h-[260px]">
                                  <Table>
                                    <TableHeader>
                                      <TableRow>
                                        <TableHead className="h-8 text-xs w-[220px]">字段</TableHead>
                                        <TableHead className="h-8 text-xs">值</TableHead>
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {selectedReviewFields.map(([k, v]) => (
                                        <TableRow key={k} className="h-8">
                                          <TableCell className="py-1 text-xs font-mono whitespace-nowrap">{k}</TableCell>
                                          <TableCell className="py-1 text-xs font-mono break-words">{v || "-"}</TableCell>
                                        </TableRow>
                                      ))}
                                    </TableBody>
                                  </Table>
                                </ScrollArea>
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        </div>
                      </CardContent>
                    </Card>

                    <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
                      <CollapsibleTrigger asChild>
                        <Button variant="outline" size="sm" className="h-8 w-full justify-between text-xs">
                          高级规则（批量改写/落配置）
                          {advancedOpen ? <ChevronDown className="h-3 w-3 opacity-60" /> : <ChevronRight className="h-3 w-3 opacity-60" />}
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent className="mt-2">
                        <Card>
                          <CardHeader className="py-3">
                            <CardTitle className="text-base">快速规则（试运行）</CardTitle>
                            <CardDescription className="text-xs">
                              配置规则后会批量更新当前账期匹配行，并可选写入 <span className="font-mono">regex_category_rules</span>/<span className="font-mono">ignore_rules</span>（后续任务自动生效）。
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="py-3 space-y-3">
                            <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">操作</div>
                            <Select value={ruleAction} onValueChange={(v: string) => setRuleAction(v as RuleAction)}>
                              <SelectTrigger className="h-8 text-xs w-full"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="categorize">分类</SelectItem>
                                <SelectItem value="ignore">不记账</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">字段</div>
                            <Select value={ruleField} onValueChange={(v: string) => setRuleField(v as RuleMatchField)}>
                              <SelectTrigger className="h-8 text-xs w-full"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="merchant">商户</SelectItem>
                                <SelectItem value="item">商品</SelectItem>
                                <SelectItem value="remark">备注</SelectItem>
                                <SelectItem value="category">分类</SelectItem>
                                <SelectItem value="pay_method">支付方式</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">匹配方式</div>
                            <Select value={ruleMode} onValueChange={(v: string) => setRuleMode(v as RuleMatchMode)}>
                              <SelectTrigger className="h-8 text-xs w-full"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="contains">包含</SelectItem>
                                <SelectItem value="regex">正则</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="col-span-2 space-y-1">
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">规则</div>
                            <div className="flex gap-2">
                              <Input
                                value={rulePattern}
                                onChange={(e) => setRulePattern(e.target.value)}
                                placeholder="例如：一家打面"
                                className="h-8 text-xs flex-1"
                              />
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setRuleField("merchant");
                                  setRuleMode("contains");
                                  setRulePattern(String(selectedReviewRow.merchant ?? ""));
                                }}
                              >
                                使用商户
                              </Button>
                            </div>
                            {rulePreview.error ? (
                              <div className="text-xs text-destructive">{rulePreview.error}</div>
                            ) : null}
                          </div>
                          {ruleAction === "categorize" ? (
                            <>
                              <div className="space-y-1">
                                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">分类</div>
                                <Select value={ruleCategoryId} onValueChange={setRuleCategoryId}>
                                  <SelectTrigger className="h-8 text-xs w-full">
                                    <SelectValue placeholder="选择分类" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {config?.categories?.map((c) => (
                                      <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                              <div className="space-y-1">
                                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">新增分类</div>
                                <div className="flex gap-2">
                                  <Input
                                    value={newCategoryName}
                                    onChange={(e) => setNewCategoryName(e.target.value)}
                                    placeholder="名称（例如：餐饮）"
                                    className="h-8 text-xs"
                                  />
                                  <Input
                                    value={newCategoryId}
                                    onChange={(e) => setNewCategoryId(e.target.value)}
                                    placeholder="ID（可选）"
                                    className="h-8 text-xs font-mono"
                                  />
                                  <Button size="sm" variant="outline" onClick={() => void addCategory()} disabled={busy}>
                                    新增
                                  </Button>
                                </div>
                              </div>
                            </>
                          ) : (
                            <div className="col-span-2 text-xs text-muted-foreground">
                              不记账规则会写入 <span className="font-mono">ignore_rules</span>，并批量设置 <span className="font-mono">final_ignored=true</span>。
                            </div>
                          )}
                            </div>

                            <div className="flex flex-wrap items-center gap-4">
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id="rule_only_pending"
                              checked={ruleOnlyPending}
                              onCheckedChange={(chk: boolean | string) => setRuleOnlyPending(chk === true)}
                            />
                            <label
                              htmlFor="rule_only_pending"
                              className="text-xs leading-none text-muted-foreground"
                              title="仅对左侧列表中“待复核（黄色背景）”的行生效；取消勾选可匹配全部行"
                            >
                              仅待复核
                            </label>
                          </div>
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id="rule_overwrite"
                              checked={ruleOverwriteFinal}
                              onCheckedChange={(chk: boolean | string) => setRuleOverwriteFinal(chk === true)}
                            />
                            <label
                              htmlFor="rule_overwrite"
                              className="text-xs leading-none text-muted-foreground"
                              title="勾选后会覆盖已填写的最终结果（final_category_id/不记账等）"
                            >
                              覆盖已填结果
                            </label>
                          </div>
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id="rule_save_cfg"
                              checked={ruleSaveToConfig}
                              onCheckedChange={(chk: boolean | string) => setRuleSaveToConfig(chk === true)}
                            />
                            <label
                              htmlFor="rule_save_cfg"
                              className="text-xs leading-none text-muted-foreground"
                              title="把规则写入本次任务的 classifier.json（仅影响当前任务）"
                            >
                              保存到本次任务
                            </label>
                          </div>
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id="rule_save_global"
                              checked={ruleSaveToGlobal}
                              onCheckedChange={(chk: boolean | string) => setRuleSaveToGlobal(chk === true)}
                            />
                            <label
                              htmlFor="rule_save_global"
                              className="text-xs leading-none text-muted-foreground"
                              title="把规则写入全局 config/classifier.local.json（本地覆盖，避免误提交；以后新建任务自动生效）"
                            >
                              保存为默认
                            </label>
                          </div>
                          <Badge
                            variant="outline"
                            className="h-6 text-[10px] font-mono ml-auto"
                            title="当前规则在本次加载的 review.csv 中匹配到的行数"
                          >
                            匹配 {rulePreview.matches.length}
                          </Badge>
                            </div>

                            <div className="space-y-1">
                          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">备注 / 原因（可选）</div>
                          <Input
                            value={ruleNote}
                            onChange={(e) => setRuleNote(e.target.value)}
                            placeholder={ruleAction === "ignore" ? "不记账原因（写入 final_ignore_reason）" : "原因（final_note 为空时写入）"}
                            className="h-8 text-xs"
                          />
                            </div>

                            <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => void applyQuickRule()}
                            disabled={busy || !rulePattern.trim() || (ruleAction === "categorize" && !ruleCategoryId) || rulePreview.matches.length === 0}
                          >
                            应用到 {rulePreview.matches.length} 条
                          </Button>
                          <span className="text-xs text-muted-foreground">
                            例如：<span className="font-mono">一家打面</span> → <span className="font-mono">餐饮</span>
                          </span>
                            </div>

                            {rulePreview.matches.length ? (
                              <div className="border rounded-md overflow-hidden">
                                <ScrollArea className="h-[140px]">
                                  <Table>
                                    <TableHeader>
                                      <TableRow>
                                        <TableHead className="h-8 text-xs">日期</TableHead>
                                        <TableHead className="h-8 text-xs text-right">金额</TableHead>
                                        <TableHead className="h-8 text-xs">商户</TableHead>
                                        <TableHead className="h-8 text-xs">商品</TableHead>
                                      </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                      {rulePreview.matches.slice(0, 50).map((r, idx) => (
                                        <TableRow key={`${String(r.txn_id ?? "")}-${idx}`} className="h-8">
                                          <TableCell className="py-1 text-xs font-mono whitespace-nowrap">{String(r.trade_date ?? "")}</TableCell>
                                          <TableCell className="py-1 text-xs font-mono whitespace-nowrap text-right">{fmtMoney(r.amount)}</TableCell>
                                          <TableCell className="py-1 text-xs truncate max-w-[220px]" title={String(r.merchant ?? "")}>{String(r.merchant ?? "")}</TableCell>
                                          <TableCell className="py-1 text-xs truncate max-w-[220px]" title={String(r.item ?? "")}>{String(r.item ?? "")}</TableCell>
                                        </TableRow>
                                      ))}
                                    </TableBody>
                                  </Table>
                                </ScrollArea>
                              </div>
                            ) : null}
                          </CardContent>
                        </Card>
                      </CollapsibleContent>
                    </Collapsible>
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
