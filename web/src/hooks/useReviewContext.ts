import React, { createContext, useContext, ReactNode, useState, useMemo } from "react";
import { ClassifierConfig, CsvPreview } from "@/types";
import { parseBoolish, isPendingRow, type RuleMatchMode, type RuleMatchField, type RuleAction } from "@/utils/helpers";

// ========== 类型定义 ==========

export interface ReviewState {
    // Review 数据
    reviewRows: Record<string, string>[];
    reviewEdits: Record<string, Partial<Record<string, string | boolean>>>;
    reviewPendingOnly: boolean;
    reviewQuery: string;
    reviewOpen: boolean;
    reviewSelectedTxnId: string;
    reviewSelectedTxnIds: Record<string, boolean>;

    // 批量操作
    bulkTarget: "selected" | "filtered";
    bulkIncludeReviewed: boolean;
    bulkCategoryId: string;
    bulkIgnored: boolean;
    bulkNote: string;
    bulkContinuousMode: boolean;

    // Quick Rule
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

    // 配置
    config: ClassifierConfig | null;
    configText: string;

    // UI 状态
    busy: boolean;
    error: string;
    runId: string;
}

export interface ReviewActions {
    setReviewRows: (rows: Record<string, string>[]) => void;
    setReviewEdits: React.Dispatch<React.SetStateAction<Record<string, Partial<Record<string, string | boolean>>>>>;
    setReviewPendingOnly: (v: boolean) => void;
    setReviewQuery: (v: string) => void;
    setReviewOpen: (v: boolean) => void;
    setReviewSelectedTxnId: (v: string) => void;
    setReviewSelectedTxnIds: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;

    setBulkTarget: (v: "selected" | "filtered") => void;
    setBulkIncludeReviewed: (v: boolean) => void;
    setBulkCategoryId: (v: string) => void;
    setBulkIgnored: (v: boolean) => void;
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

    setError: (v: string) => void;

    // 业务方法
    loadReview: () => Promise<void>;
    saveReviewEdits: () => Promise<boolean>;
    applyBulkLocal: () => Promise<void>;
    applyQuickRule: () => Promise<void>;
    addCategory: () => Promise<void>;
    requestCloseReview: () => Promise<boolean>;
}

export interface ReviewDerived {
    categories: Array<{ id: string; name: string }>;
    filteredReviewRows: Array<Record<string, string> & { __pending: string; __row_idx: string }>;
    filteredReviewTxnIds: string[];
    selectedTxnIds: string[];
    bulkEffectiveTxnIds: string[];
    selectedReviewRow: Record<string, string> | null;
    selectedReviewFields: Array<[string, string]>;
    reviewPendingCount: number;
    rulePreview: { matches: Record<string, string>[]; error: string };
}

export interface ReviewContextType extends ReviewState, ReviewActions, ReviewDerived { }

// ========== Context ==========

const ReviewContext = createContext<ReviewContextType | null>(null);

export function useReviewContext(): ReviewContextType {
    const ctx = useContext(ReviewContext);
    if (!ctx) {
        throw new Error("useReviewContext must be used within a ReviewProvider");
    }
    return ctx;
}

export { ReviewContext };

// ========== 派生计算 Hooks ==========

export function useFilteredReviewRows(
    reviewRows: Record<string, string>[],
    reviewEdits: Record<string, Partial<Record<string, string | boolean>>>,
    reviewPendingOnly: boolean,
    reviewQuery: string
): Array<Record<string, string> & { __pending: string; __row_idx: string }> {
    return useMemo(() => {
        const q = reviewQuery.trim().toLowerCase();

        const withMeta = reviewRows.map((r, idx) => {
            const pending = isPendingRow(r, reviewEdits);
            return { ...r, __pending: String(pending), __row_idx: String(idx) } as Record<string, string> & { __pending: string; __row_idx: string };
        });

        return withMeta.filter((r) => {
            if (!r) return false;
            if (reviewPendingOnly && String(r.__pending ?? "") !== "true") return false;
            if (q) {
                const hay = `${r.merchant ?? ""} ${r.item ?? ""} ${r.category ?? ""} ${r.pay_method ?? ""} ${r.remark ?? ""}`.toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        });
    }, [reviewRows, reviewEdits, reviewPendingOnly, reviewQuery]);
}

export function useReviewPendingCount(
    reviewRows: Record<string, string>[],
    reviewEdits: Record<string, Partial<Record<string, string | boolean>>>
): number {
    return useMemo(() => {
        return reviewRows.filter((r) => isPendingRow(r, reviewEdits)).length;
    }, [reviewRows, reviewEdits]);
}

export function useSelectedReviewFields(selectedReviewRow: Record<string, string> | null): Array<[string, string]> {
    return useMemo(() => {
        if (!selectedReviewRow) return [] as Array<[string, string]>;
        const priority = [
            "trade_date",
            "trade_time",
            "post_date",
            "account",
            "amount",
            "flow",
            "merchant",
            "item",
            "category",
            "pay_method",
            "sources",
            "remark",
            "suggested_category_id",
            "suggested_category_name",
            "suggested_confidence",
            "suggested_uncertain",
            "suggested_note",
            "suggested_source",
            "suggested_rule_id",
            "suggested_ignored",
            "suggested_ignore_reason",
            "final_category_id",
            "final_note",
            "final_ignored",
            "final_ignore_reason",
        ];
        const order = new Map(priority.map((k, i) => [k, i]));
        const entries = Object.entries(selectedReviewRow)
            .filter(([k]) => !k.startsWith("__"))
            .map(([k, v]) => [k, String(v ?? "")] as [string, string]);
        entries.sort((a, b) => {
            const ai = order.get(a[0]) ?? 999;
            const bi = order.get(b[0]) ?? 999;
            if (ai !== bi) return ai - bi;
            return a[0].localeCompare(b[0]);
        });
        return entries;
    }, [selectedReviewRow]);
}
