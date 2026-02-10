import { Loader2, CheckCircle2, XCircle, Ban, AlertCircle, Clock } from "lucide-react";

// 状态格式化
export function fmtStatus(s: string) {
    if (s === "succeeded") return { text: "Success", variant: "default" as const, icon: CheckCircle2 };
    if (s === "failed") return { text: "Failed", variant: "destructive" as const, icon: XCircle };
    if (s === "running") return { text: "Running", variant: "secondary" as const, icon: Loader2 };
    if (s === "canceled") return { text: "Canceled", variant: "destructive" as const, icon: Ban };
    if (s === "needs_review") return { text: "Needs Review", variant: "secondary" as const, icon: AlertCircle };
    if (s === "idle") return { text: "Idle", variant: "outline" as const, icon: Clock };
    if (s === "pending") return { text: "Pending", variant: "outline" as const, icon: Clock };
    return { text: s, variant: "outline" as const, icon: AlertCircle };
}

// API 请求封装
export async function api<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
    const token = localStorage.getItem("openledger_apiToken") || "";
    const headers = new Headers(init?.headers || undefined);
    if (token.trim()) headers.set("X-OpenLedger-Token", token.trim());
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
