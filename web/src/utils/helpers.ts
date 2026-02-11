import { Loader2, CheckCircle2, XCircle, Ban, AlertCircle, Clock } from "lucide-react";

// 状态格式化
export function fmtStatus(s: string) {
    if (s === "succeeded") return { text: "成功", variant: "default" as const, icon: CheckCircle2, color: "text-green-500" };
    if (s === "failed") return { text: "失败", variant: "destructive" as const, icon: XCircle, color: "text-red-500" };
    if (s === "running") return { text: "运行中", variant: "secondary" as const, icon: Loader2, color: "text-blue-500 animate-spin" };
    if (s === "canceled") return { text: "已取消", variant: "destructive" as const, icon: Ban, color: "text-gray-500" };
    if (s === "needs_review") return { text: "需复核", variant: "secondary" as const, icon: AlertCircle, color: "text-amber-500" };
    if (s === "idle") return { text: "空闲", variant: "outline" as const, icon: Clock, color: "text-muted-foreground" };
    if (s === "pending") return { text: "排队中", variant: "outline" as const, icon: Clock, color: "text-muted-foreground" };
    return { text: s, variant: "outline" as const, icon: AlertCircle, color: "text-muted-foreground" };
}

// API 请求封装
export async function api<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers || undefined);
    const res = await fetch(`${baseUrl}${path}`, { ...init, headers });
    if (!res.ok) {
        const txt = await res.text();
        throw new Error(`HTTP ${res.status}: ${txt.slice(0, 3000)}`);
    }
    return (await res.json()) as T;
}

// 文件类型判断
export function isCsvFile(name: string) {
    return name.toLowerCase().endsWith(".csv");
}

export function isExcelFile(name: string) {
    const lower = name.toLowerCase();
    return lower.endsWith(".xlsx") || lower.endsWith(".xls");
}

export function isPdfFile(name: string) {
    return name.toLowerCase().endsWith(".pdf");
}

export function isTextFile(name: string) {
    const lower = name.toLowerCase();
    return lower.endsWith(".json") || lower.endsWith(".jsonl") || lower.endsWith(".log") || lower.endsWith(".txt") || lower.endsWith(".md");
}

// 布尔值解析
export function parseBoolish(value: unknown): boolean {
    const s = String(value ?? "").trim().toLowerCase();
    return s === "true" || s === "1" || s === "yes" || s === "y";
}

// 类型定义
export type RuleMatchMode = "contains" | "regex";
export type RuleMatchField = "merchant" | "item" | "remark" | "category" | "pay_method";
export type RuleAction = "categorize" | "ignore";
export type RunMeta = { id: string; name: string; status?: string; created_at?: string };

// 正则转义
export function escapeRegExp(s: string): string {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ID 生成
export function slugifyId(s: string): string {
    return s
        .trim()
        .toLowerCase()
        .replace(/\s+/g, "_")
        .replace(/[^a-z0-9_]/g, "");
}

export function suggestCategoryId(name: string): string {
    const n = String(name ?? "").trim();
    if (!n) return "";
    if (n === "餐饮") return "dining";
    const slug = slugifyId(n);
    if (slug) return slug;
    return `cat_${Date.now()}`;
}

// 判断交易行是否为「待复核」状态
export function isPendingRow(
    r: Record<string, string>,
    edits?: Record<string, Partial<Record<string, string | boolean>>>,
): boolean {
    const txnId = String(r.txn_id ?? "");
    const suggestedUncertain = parseBoolish(r.suggested_uncertain);

    const finalCatOverride = edits?.[txnId]?.final_category_id;
    const finalCat = String(finalCatOverride ?? r.final_category_id ?? "").trim();

    const finalIgnoredOverride = edits?.[txnId]?.final_ignored;
    const finalIgnoredRaw = String(finalIgnoredOverride ?? r.final_ignored ?? "").trim();
    const ignored = finalIgnoredRaw !== ""
        ? parseBoolish(finalIgnoredRaw)
        : parseBoolish(r.suggested_ignored);

    return suggestedUncertain && !finalCat && !ignored;
}
