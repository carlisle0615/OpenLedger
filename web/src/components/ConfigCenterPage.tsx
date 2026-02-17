import React from "react";
import { api } from "@/utils/helpers";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { RefreshCw, Save, Plus, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };

type Category = { id: string; name: string };

type RuleWhen = {
    primary_source?: string;
};

type IgnoreRule = {
    id: string;
    reason?: string;
    enabled?: boolean;
    when?: RuleWhen;
    fields?: string[];
    pattern?: string;
    flags?: string;
};

type RegexCategoryRule = {
    id: string;
    category_id?: string;
    confidence?: number;
    uncertain?: boolean;
    fields?: string[];
    pattern?: string;
    flags?: string;
    note?: string;
};

type LspConfig = {
    provider?: string;
    model?: string;
    api_key_env?: string;
    base_url?: string;
    temperature?: number;
    max_tokens?: number | null;
    minimax_group_id?: string;
    openrouter_referer?: string;
    openrouter_title?: string;
};

type ClassifierConfigShape = {
    model?: string;
    batch_size?: number;
    max_concurrency?: number;
    uncertain_threshold?: number;
    lsp?: LspConfig;
    categories?: Category[];
    ignore_rules?: IgnoreRule[];
    regex_category_rules?: RegexCategoryRule[];
    debit_card_aliases?: Record<string, string[]>;
    prompt_columns?: string[];
    review_columns?: string[];
    drop_output_columns?: string[];
    [key: string]: unknown;
};

type CardAliasRow = {
    primary: string;
    aliasesText: string;
};

const RULE_FIELD_OPTIONS: Array<{ id: string; label: string }> = [
    { id: "merchant", label: "商户" },
    { id: "item", label: "项目" },
    { id: "remark", label: "备注" },
    { id: "category", label: "原始分类" },
    { id: "pay_method", label: "支付方式" },
    { id: "flow", label: "流水方向" },
    { id: "sources", label: "来源" },
    { id: "account", label: "账户" },
];

const LSP_PROVIDER_OPTIONS: Array<{ id: string; name: string }> = [
    { id: "openrouter", name: "OpenRouter" },
    { id: "ollama", name: "Ollama" },
    { id: "tongyi", name: "通义千问" },
    { id: "deepseek", name: "DeepSeek" },
    { id: "kimi", name: "Kimi" },
    { id: "minimax", name: "MiniMax" },
];

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
    if (typeof value === "string") return value;
    if (value === null || value === undefined) return fallback;
    return String(value);
}

function asNumber(value: unknown): number | undefined {
    if (value === null || value === undefined || value === "") return undefined;
    const n = Number(value);
    return Number.isFinite(n) ? n : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
    if (value === null || value === undefined) return undefined;
    if (typeof value === "boolean") return value;
    const s = String(value).trim().toLowerCase();
    if (["true", "1", "yes", "y"].includes(s)) return true;
    if (["false", "0", "no", "n"].includes(s)) return false;
    return undefined;
}

function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value.map((v) => asString(v).trim()).filter(Boolean);
}

function normalizeCardLast4(raw: unknown): string {
    const text = asString(raw).trim();
    if (!text) return "";
    if (/^\d{4}$/.test(text)) return text;
    const compact = text.replace(/\s+/g, "");
    const fullCardMatch = compact.match(/\d{8,}$/);
    if (fullCardMatch) {
        return compact.slice(-4);
    }
    const tailMatch = compact.match(/(\d{4})$/);
    return tailMatch ? tailMatch[1] : "";
}

function asCategoryArray(value: unknown): Category[] {
    if (!Array.isArray(value)) return [];
    return value
        .map((item) => {
            if (!isObject(item)) return null;
            return {
                id: asString(item.id).trim(),
                name: asString(item.name).trim(),
            };
        })
        .filter((item): item is Category => Boolean(item && item.id));
}

function asIgnoreRules(value: unknown): IgnoreRule[] {
    if (!Array.isArray(value)) return [];
    return value
        .map((item, index): IgnoreRule | null => {
            if (!isObject(item)) return null;
            const when = isObject(item.when)
                ? { primary_source: asString(item.when.primary_source).trim() }
                : undefined;
            return {
                id: asString(item.id).trim() || `ignore_rule_${index + 1}`,
                reason: asString(item.reason).trim(),
                enabled: asBoolean(item.enabled),
                when,
                fields: asStringArray(item.fields),
                pattern: asString(item.pattern),
                flags: asString(item.flags),
            };
        })
        .filter((item): item is IgnoreRule => Boolean(item));
}

function asRegexRules(value: unknown): RegexCategoryRule[] {
    if (!Array.isArray(value)) return [];
    return value
        .map((item, index): RegexCategoryRule | null => {
            if (!isObject(item)) return null;
            return {
                id: asString(item.id).trim() || `regex_rule_${index + 1}`,
                category_id: asString(item.category_id).trim(),
                confidence: asNumber(item.confidence),
                uncertain: asBoolean(item.uncertain),
                fields: asStringArray(item.fields),
                pattern: asString(item.pattern),
                flags: asString(item.flags),
                note: asString(item.note),
            };
        })
        .filter((item): item is RegexCategoryRule => Boolean(item));
}

function asLspConfig(value: unknown): LspConfig {
    if (!isObject(value)) return {};
    const maxTokensRaw = value.max_tokens;
    return {
        provider: asString(value.provider).trim(),
        model: asString(value.model).trim(),
        api_key_env: asString(value.api_key_env).trim(),
        base_url: asString(value.base_url).trim(),
        temperature: asNumber(value.temperature),
        max_tokens: maxTokensRaw === null ? null : asNumber(maxTokensRaw),
        minimax_group_id: asString(value.minimax_group_id).trim(),
        openrouter_referer: asString(value.openrouter_referer).trim(),
        openrouter_title: asString(value.openrouter_title).trim(),
    };
}

function normalizeConfig(raw: unknown): ClassifierConfigShape {
    if (!isObject(raw)) {
        throw new Error("全局配置必须是 JSON 对象（object）。");
    }
    return {
        ...raw,
        model: asString(raw.model),
        batch_size: asNumber(raw.batch_size),
        max_concurrency: asNumber(raw.max_concurrency),
        uncertain_threshold: asNumber(raw.uncertain_threshold),
        lsp: asLspConfig(raw.lsp),
        categories: asCategoryArray(raw.categories),
        ignore_rules: asIgnoreRules(raw.ignore_rules),
        regex_category_rules: asRegexRules(raw.regex_category_rules),
        debit_card_aliases: normalizeDebitCardAliases(raw.debit_card_aliases),
        prompt_columns: asStringArray(raw.prompt_columns),
        review_columns: asStringArray(raw.review_columns),
        drop_output_columns: asStringArray(raw.drop_output_columns),
    };
}

function toggleField(fields: string[] | undefined, fieldId: string): string[] {
    const current = new Set(fields || []);
    if (current.has(fieldId)) {
        current.delete(fieldId);
    } else {
        current.add(fieldId);
    }
    return Array.from(current);
}

function validateConfig(config: ClassifierConfigShape): string | null {
    const categories = config.categories || [];
    const categoryIds = categories.map((c) => c.id.trim()).filter(Boolean);

    if (!categoryIds.length) return "请至少配置一个分类，并包含“其他”。";
    if (!categoryIds.includes("other")) return "分类中必须包含 id=other（名称可为“其他”）。";
    if (new Set(categoryIds).size !== categoryIds.length) return "分类 id 存在重复，请修正后保存。";

    const threshold = config.uncertain_threshold;
    if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
        return "不确定阈值必须在 0 到 1 之间。";
    }

    const batchSize = config.batch_size;
    if (batchSize !== undefined && batchSize <= 0) return "批处理大小必须大于 0。";

    const maxConcurrency = config.max_concurrency;
    if (maxConcurrency !== undefined && maxConcurrency <= 0) return "并发数必须大于 0。";

    const regexRules = config.regex_category_rules || [];
    const categorySet = new Set(categoryIds);
    for (const rule of regexRules) {
        const cid = (rule.category_id || "").trim();
        if (!cid) return `自动分类规则 ${rule.id} 需要选择分类。`;
        if (!categorySet.has(cid)) return `自动分类规则 ${rule.id} 引用了不存在的分类：${cid}`;
    }
    return null;
}

function normalizeDebitCardAliases(raw: unknown): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    if (Array.isArray(raw)) {
        raw.forEach((item) => {
            if (!isObject(item)) return;
            const key = normalizeCardLast4(item.primary);
            if (!key) return;
            const rawAliases = Array.isArray(item.aliases) ? item.aliases : [item.aliases];
            const aliases = rawAliases
                .map((value) => normalizeCardLast4(value))
                .filter((value) => value && value !== key);
            if (!aliases.length) return;
            out[key] = Array.from(new Set([...(out[key] || []), ...aliases]));
        });
        return out;
    }
    if (!isObject(raw)) {
        return {};
    }
    Object.entries(raw).forEach(([k, v]) => {
        const key = normalizeCardLast4(k);
        if (!key) return;
        const values = Array.isArray(v) ? v : [v];
        const aliases = values
            .map((item) => normalizeCardLast4(item))
            .filter((item) => item && item !== key);
        if (!aliases.length) return;
        out[key] = Array.from(new Set([...(out[key] || []), ...aliases]));
    });
    return out;
}

function aliasesToRows(aliases: Record<string, string[]>): CardAliasRow[] {
    return Object.entries(aliases)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([primary, aliases]) => ({
            primary,
            aliasesText: aliases.join(", "),
        }));
}

function rowsToAliasMap(rows: CardAliasRow[]): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    rows.forEach((row) => {
        const rawPrimary = row.primary.trim();
        if (!rawPrimary) return;
        const primary = normalizeCardLast4(rawPrimary);
        if (!primary) {
            throw new Error(`主卡请填写 4 位尾号或完整卡号：${rawPrimary}`);
        }
        const aliases = row.aliasesText
            .split(/[,\s，]+/)
            .map((item) => normalizeCardLast4(item))
            .filter(Boolean);
        const normalized = Array.from(
            new Set(aliases.filter((item) => item !== primary)),
        );
        if (!normalized.length) {
            throw new Error(`请为主卡尾号 ${primary} 至少填写一个续卡尾号`);
        }
        out[primary] = normalized;
    });
    return out;
}

function classifierConfigPath(useCacheBust: boolean): string {
    if (!useCacheBust) {
        return "/api/v2/config/classifier";
    }
    return `/api/v2/config/classifier?_ts=${Date.now()}`;
}

function TextListEditor(props: {
    title: string;
    description: string;
    values: string[];
    onChange: (next: string[]) => void;
    placeholder: string;
}) {
    const { title, description, values, onChange, placeholder } = props;
    const [draft, setDraft] = React.useState("");

    function addItem() {
        const value = draft.trim();
        if (!value) return;
        if (values.includes(value)) {
            setDraft("");
            return;
        }
        onChange([...values, value]);
        setDraft("");
    }

    function removeItem(index: number) {
        onChange(values.filter((_, i) => i !== index));
    }

    return (
        <div className="space-y-2">
            <div>
                <div className="text-xs font-medium">{title}</div>
                <div className="text-[11px] text-muted-foreground">{description}</div>
            </div>
            <div className="flex items-center gap-2">
                <Input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === "Enter") {
                            e.preventDefault();
                            addItem();
                        }
                    }}
                    placeholder={placeholder}
                    className="h-8 text-xs"
                />
                <Button size="sm" variant="outline" className="h-8 px-2" onClick={addItem}>
                    <Plus className="h-3.5 w-3.5" />
                </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
                {values.length ? values.map((item, idx) => (
                    <Badge key={`${item}_${idx}`} variant="outline" className="text-[10px] px-2 py-1 gap-1">
                        <span className="font-mono">{item}</span>
                        <button className="text-destructive" onClick={() => removeItem(idx)} title="移除">
                            ×
                        </button>
                    </Badge>
                )) : <span className="text-[11px] text-muted-foreground">暂无配置</span>}
            </div>
        </div>
    );
}

export function ConfigCenterPage({ baseUrl }: { baseUrl: string }) {
    const [config, setConfig] = React.useState<ClassifierConfigShape | null>(null);
    const [cardAliasRows, setCardAliasRows] = React.useState<CardAliasRow[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [saving, setSaving] = React.useState(false);
    const [error, setError] = React.useState("");
    const [success, setSuccess] = React.useState("");
    const [loadedAt, setLoadedAt] = React.useState("");
    const [jsonText, setJsonText] = React.useState("{}");

    const categories = config?.categories || [];
    const ignoreRules = config?.ignore_rules || [];
    const regexRules = config?.regex_category_rules || [];

    const categoryOptions = React.useMemo(() => {
        return categories.map((c) => ({ id: c.id, name: c.name || c.id }));
    }, [categories]);

    const providerOptions = React.useMemo(() => {
        const current = config?.lsp?.provider?.trim() || "";
        const map = new Map<string, string>();
        LSP_PROVIDER_OPTIONS.forEach((item) => map.set(item.id, item.name));
        if (current && !map.has(current)) {
            map.set(current, current);
        }
        return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
    }, [config?.lsp?.provider]);

    const loadConfig = React.useCallback(async () => {
        if (!baseUrl.trim()) return;
        setLoading(true);
        setError("");
        setSuccess("");
        try {
            const rawClassifier = await api<unknown>(baseUrl, classifierConfigPath(true));
            const normalized = normalizeConfig(rawClassifier);
            setConfig(normalized);
            setCardAliasRows(aliasesToRows(normalized.debit_card_aliases || {}));
            setJsonText(JSON.stringify(normalized, null, 2));
            setLoadedAt(new Date().toLocaleString());
        } catch (e) {
            setError(String(e));
            setConfig(null);
            setCardAliasRows([]);
        } finally {
            setLoading(false);
        }
    }, [baseUrl]);

    React.useEffect(() => {
        void loadConfig();
    }, [loadConfig]);

    function updateConfig(patch: Partial<ClassifierConfigShape>) {
        setConfig((prev) => {
            if (!prev) return prev;
            return { ...prev, ...patch };
        });
        setSuccess("");
    }

    function updateLspField<K extends keyof LspConfig>(key: K, value: LspConfig[K]) {
        setConfig((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                lsp: {
                    ...(prev.lsp || {}),
                    [key]: value,
                },
            };
        });
        setSuccess("");
    }

    function updateCategory(index: number, patch: Partial<Category>) {
        const next = categories.map((item, i) => (i === index ? { ...item, ...patch } : item));
        updateConfig({ categories: next });
    }

    function addCategory() {
        const n = categories.length + 1;
        updateConfig({ categories: [...categories, { id: `new_category_${n}`, name: `新分类${n}` }] });
    }

    function removeCategory(index: number) {
        updateConfig({ categories: categories.filter((_, i) => i !== index) });
    }

    function updateIgnoreRule(index: number, patch: Partial<IgnoreRule>) {
        const next = ignoreRules.map((item, i) => (i === index ? { ...item, ...patch } : item));
        updateConfig({ ignore_rules: next });
    }

    function addIgnoreRule() {
        const n = ignoreRules.length + 1;
        updateConfig({
            ignore_rules: [
                ...ignoreRules,
                {
                    id: `ignore_rule_${n}`,
                    reason: "",
                    fields: ["merchant"],
                    pattern: "",
                    flags: "i",
                },
            ],
        });
    }

    function removeIgnoreRule(index: number) {
        updateConfig({ ignore_rules: ignoreRules.filter((_, i) => i !== index) });
    }

    function updateRegexRule(index: number, patch: Partial<RegexCategoryRule>) {
        const next = regexRules.map((item, i) => (i === index ? { ...item, ...patch } : item));
        updateConfig({ regex_category_rules: next });
    }

    function addRegexRule() {
        const n = regexRules.length + 1;
        updateConfig({
            regex_category_rules: [
                ...regexRules,
                {
                    id: `regex_rule_${n}`,
                    category_id: categoryOptions[0]?.id || "other",
                    confidence: 0.9,
                    uncertain: false,
                    fields: ["merchant"],
                    pattern: "",
                    flags: "i",
                    note: "",
                },
            ],
        });
    }

    function removeRegexRule(index: number) {
        updateConfig({ regex_category_rules: regexRules.filter((_, i) => i !== index) });
    }

    function configWithAliases(base: ClassifierConfigShape): ClassifierConfigShape {
        return {
            ...base,
            debit_card_aliases: rowsToAliasMap(cardAliasRows),
        };
    }

    function syncJsonFromUi() {
        if (!config) return;
        try {
            setJsonText(JSON.stringify(configWithAliases(config), null, 2));
        } catch (e) {
            setError(String(e));
            return;
        }
        setError("");
        setSuccess("已将可视化配置同步到 JSON。")
    }

    function applyJsonToUi() {
        setError("");
        setSuccess("");
        try {
            const parsed = JSON.parse(jsonText) as unknown;
            const normalized = normalizeConfig(parsed);
            setConfig(normalized);
            setCardAliasRows(aliasesToRows(normalized.debit_card_aliases || {}));
            setSuccess("已将 JSON 应用到可视化配置。")
        } catch (e) {
            setError(String(e));
        }
    }

    async function saveConfig() {
        if (!config) return;
        const validateError = validateConfig(config);
        if (validateError) {
            setError(validateError);
            setSuccess("");
            return;
        }

        setSaving(true);
        setError("");
        setSuccess("");
        try {
            const payload = configWithAliases(config);
            await api<{ ok: boolean }>(baseUrl, "/api/v2/config/classifier", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const rawClassifier = await api<unknown>(baseUrl, classifierConfigPath(true));
            const normalized = normalizeConfig(rawClassifier);
            setConfig(normalized);
            setCardAliasRows(aliasesToRows(normalized.debit_card_aliases || {}));
            setJsonText(JSON.stringify(normalized, null, 2));
            setSuccess("全局配置已保存。")
            setLoadedAt(new Date().toLocaleString());
        } catch (e) {
            setError(String(e));
        } finally {
            setSaving(false);
        }
    }

    function updateCardAliasRow(index: number, patch: Partial<CardAliasRow>) {
        setCardAliasRows((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
        setSuccess("");
    }

    function addCardAliasRow() {
        setCardAliasRows((prev) => [...prev, { primary: "", aliasesText: "" }]);
        setSuccess("");
    }

    function removeCardAliasRow(index: number) {
        setCardAliasRows((prev) => prev.filter((_, i) => i !== index));
        setSuccess("");
    }

    async function saveCardAliases() {
        if (!config) return;
        setSaving(true);
        setError("");
        setSuccess("");
        try {
            const aliasMap = rowsToAliasMap(cardAliasRows);
            const payload = { ...config, debit_card_aliases: aliasMap };
            await api<{ ok: boolean }>(baseUrl, "/api/v2/config/classifier", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const rawClassifier = await api<unknown>(baseUrl, classifierConfigPath(true));
            const normalized = normalizeConfig(rawClassifier);
            setConfig(normalized);
            setCardAliasRows(aliasesToRows(normalized.debit_card_aliases || {}));
            setJsonText(JSON.stringify(normalized, null, 2));
            setSuccess("续卡映射已保存。")
            setLoadedAt(new Date().toLocaleString());
        } catch (e) {
            setError(String(e));
        } finally {
            setSaving(false);
        }
    }

    if (!config) {
        return (
            <div className="h-full overflow-auto p-4">
                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base">配置中心</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        {loading ? "加载中..." : error || "暂无配置"}
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="h-full overflow-auto p-4 space-y-4">
            <Card>
                <CardHeader className="py-3">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <CardTitle className="text-base">配置中心</CardTitle>
                            <div className="text-xs text-muted-foreground mt-1">
                                可视化调整全局分类配置（`/api/v2/config/classifier`）。
                                {loadedAt ? ` 最近加载：${loadedAt}` : ""}
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button size="sm" variant="outline" onClick={() => void loadConfig()} disabled={loading || saving}>
                                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                                重新加载
                            </Button>
                            <Button size="sm" onClick={() => void saveConfig()} disabled={loading || saving}>
                                <Save className="h-3.5 w-3.5 mr-1" />
                                保存全局配置
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-2">
                    {error ? (
                        <div className="text-xs text-destructive flex items-center gap-1.5">
                            <AlertCircle className="h-3.5 w-3.5" />
                            <span>{error}</span>
                        </div>
                    ) : null}
                    {success ? (
                        <div className="text-xs text-green-600 flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>{success}</span>
                        </div>
                    ) : null}
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base">基础参数</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-1">
                            <div className="text-xs font-medium">默认模型</div>
                            <Input
                                value={config.model || ""}
                                onChange={(e) => updateConfig({ model: e.target.value })}
                                placeholder="例如：google/gemini-3-flash-preview"
                                className="h-8 text-xs"
                            />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                            <div className="space-y-1">
                                <div className="text-xs font-medium">批处理大小</div>
                                <Input
                                    type="number"
                                    value={config.batch_size ?? ""}
                                    onChange={(e) => updateConfig({ batch_size: asNumber(e.target.value) })}
                                    className="h-8 text-xs"
                                />
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs font-medium">并发数</div>
                                <Input
                                    type="number"
                                    value={config.max_concurrency ?? ""}
                                    onChange={(e) => updateConfig({ max_concurrency: asNumber(e.target.value) })}
                                    className="h-8 text-xs"
                                />
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs font-medium">不确定阈值</div>
                                <Input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    max="1"
                                    value={config.uncertain_threshold ?? ""}
                                    onChange={(e) => updateConfig({ uncertain_threshold: asNumber(e.target.value) })}
                                    className="h-8 text-xs"
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base">模型连接（LSP）</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                                <div className="text-xs font-medium">服务商</div>
                                <Select
                                    value={config.lsp?.provider || "__none__"}
                                    onValueChange={(v) => updateLspField("provider", v === "__none__" ? "" : v)}
                                >
                                    <SelectTrigger className="h-8 text-xs">
                                        <SelectValue placeholder="选择服务商" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="__none__">未设置</SelectItem>
                                        {providerOptions.map((item) => (
                                            <SelectItem key={item.id} value={item.id} className="text-xs">
                                                {item.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs font-medium">模型（LSP）</div>
                                <Input
                                    value={config.lsp?.model || ""}
                                    onChange={(e) => updateLspField("model", e.target.value)}
                                    className="h-8 text-xs"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                                <div className="text-xs font-medium">API Key 环境变量</div>
                                <Input
                                    value={config.lsp?.api_key_env || ""}
                                    onChange={(e) => updateLspField("api_key_env", e.target.value)}
                                    className="h-8 text-xs font-mono"
                                />
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs font-medium">Base URL</div>
                                <Input
                                    value={config.lsp?.base_url || ""}
                                    onChange={(e) => updateLspField("base_url", e.target.value)}
                                    className="h-8 text-xs font-mono"
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <div className="space-y-1">
                                <div className="text-xs font-medium">温度</div>
                                <Input
                                    type="number"
                                    step="0.1"
                                    value={config.lsp?.temperature ?? ""}
                                    onChange={(e) => updateLspField("temperature", asNumber(e.target.value))}
                                    className="h-8 text-xs"
                                />
                            </div>
                            <div className="space-y-1">
                                <div className="text-xs font-medium">最大输出 Token</div>
                                <Input
                                    type="number"
                                    value={config.lsp?.max_tokens ?? ""}
                                    onChange={(e) => updateLspField("max_tokens", e.target.value.trim() ? asNumber(e.target.value) ?? null : null)}
                                    className="h-8 text-xs"
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="xl:col-span-2">
                    <CardHeader className="py-3">
                        <div className="flex items-center justify-between gap-2">
                            <div>
                                <CardTitle className="text-base">借记卡续卡映射</CardTitle>
                                <div className="text-xs text-muted-foreground mt-1">
                                    处理“换卡/续卡后尾号变化”导致的匹配失败。例如：主卡 1234，历史尾号 5678。
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button size="sm" variant="outline" className="h-7 px-2" onClick={addCardAliasRow} disabled={loading || saving}>
                                    <Plus className="h-3.5 w-3.5 mr-1" />新增映射
                                </Button>
                                <Button size="sm" className="h-7 px-2" onClick={() => void saveCardAliases()} disabled={loading || saving}>
                                    <Save className="h-3.5 w-3.5 mr-1" />保存映射
                                </Button>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <div className="grid grid-cols-[160px_1fr_auto] gap-2 text-xs text-muted-foreground">
                            <div>当前主卡尾号</div>
                            <div>同一卡历史/续卡尾号（逗号分隔）</div>
                            <div>操作</div>
                        </div>
                        <ScrollArea className="h-[180px] pr-2">
                            <div className="space-y-2">
                                {cardAliasRows.length ? cardAliasRows.map((row, idx) => (
                                    <div key={`card_alias_${idx}`} className="grid grid-cols-[160px_1fr_auto] gap-2 items-center">
                                        <Input
                                            value={row.primary}
                                            onChange={(e) => updateCardAliasRow(idx, { primary: e.target.value })}
                                            placeholder="例如 1234"
                                            className="h-8 text-xs font-mono"
                                        />
                                        <Input
                                            value={row.aliasesText}
                                            onChange={(e) => updateCardAliasRow(idx, { aliasesText: e.target.value })}
                                            placeholder="例如 5678, 9012"
                                            className="h-8 text-xs font-mono"
                                        />
                                        <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => removeCardAliasRow(idx)}>
                                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                        </Button>
                                    </div>
                                )) : <div className="text-xs text-muted-foreground">暂无映射，默认严格按同尾号匹配。</div>}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader className="py-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">分类列表</CardTitle>
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px]">{categories.length} 项</Badge>
                            <Button size="sm" variant="outline" className="h-7 px-2" onClick={addCategory}>
                                <Plus className="h-3.5 w-3.5 mr-1" />新增分类
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <ScrollArea className="h-[280px] pr-2">
                        <div className="space-y-2">
                            {categories.map((item, idx) => (
                                <div key={`${item.id}_${idx}`} className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center">
                                    <Input
                                        value={item.id}
                                        onChange={(e) => updateCategory(idx, { id: e.target.value })}
                                        placeholder="分类编码（如 dining）"
                                        className="h-8 text-xs font-mono"
                                    />
                                    <Input
                                        value={item.name}
                                        onChange={(e) => updateCategory(idx, { name: e.target.value })}
                                        placeholder="分类名称（如 餐饮）"
                                        className="h-8 text-xs"
                                    />
                                    <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => removeCategory(idx)}>
                                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                    <div className="text-[11px] text-muted-foreground mt-2">注意：必须保留 `id=other` 作为兜底分类。</div>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <Card>
                    <CardHeader className="py-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">忽略规则</CardTitle>
                            <Button size="sm" variant="outline" className="h-7 px-2" onClick={addIgnoreRule}>
                                <Plus className="h-3.5 w-3.5 mr-1" />新增规则
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-[480px] pr-2">
                            <div className="space-y-3">
                                {ignoreRules.map((rule, idx) => (
                                    <div key={`${rule.id}_${idx}`} className="border rounded-md p-3 space-y-2">
                                        <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-center">
                                            <Input
                                                value={rule.id}
                                                onChange={(e) => updateIgnoreRule(idx, { id: e.target.value })}
                                                placeholder="规则编码"
                                                className="h-8 text-xs font-mono"
                                            />
                                            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                                <Checkbox
                                                    checked={rule.enabled !== false}
                                                    onCheckedChange={(v) => updateIgnoreRule(idx, { enabled: v === true })}
                                                />
                                                启用
                                            </label>
                                            <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => removeIgnoreRule(idx)}>
                                                <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                            </Button>
                                        </div>
                                        <Input
                                            value={rule.reason || ""}
                                            onChange={(e) => updateIgnoreRule(idx, { reason: e.target.value })}
                                            placeholder="规则说明（例如：还款不记账）"
                                            className="h-8 text-xs"
                                        />
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                value={rule.pattern || ""}
                                                onChange={(e) => updateIgnoreRule(idx, { pattern: e.target.value })}
                                                placeholder="匹配表达式"
                                                className="h-8 text-xs font-mono"
                                            />
                                            <Input
                                                value={rule.flags || ""}
                                                onChange={(e) => updateIgnoreRule(idx, { flags: e.target.value })}
                                                placeholder="flags（如 i）"
                                                className="h-8 text-xs font-mono"
                                            />
                                        </div>
                                        <Input
                                            value={rule.when?.primary_source || ""}
                                            onChange={(e) => updateIgnoreRule(idx, {
                                                when: { primary_source: e.target.value },
                                            })}
                                            placeholder="限定来源（可空，如 ^cmb_statement$）"
                                            className="h-8 text-xs font-mono"
                                        />
                                        <div className="grid grid-cols-2 gap-2">
                                            {RULE_FIELD_OPTIONS.map((field) => {
                                                const checked = (rule.fields || []).includes(field.id);
                                                return (
                                                    <label key={field.id} className="flex items-center gap-1.5 text-xs">
                                                        <Checkbox
                                                            checked={checked}
                                                            onCheckedChange={() => {
                                                                updateIgnoreRule(idx, { fields: toggleField(rule.fields, field.id) });
                                                            }}
                                                        />
                                                        {field.label}
                                                    </label>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                                {!ignoreRules.length ? <div className="text-xs text-muted-foreground">暂无规则</div> : null}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">自动分类规则</CardTitle>
                            <Button size="sm" variant="outline" className="h-7 px-2" onClick={addRegexRule}>
                                <Plus className="h-3.5 w-3.5 mr-1" />新增规则
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-[480px] pr-2">
                            <div className="space-y-3">
                                {regexRules.map((rule, idx) => (
                                    <div key={`${rule.id}_${idx}`} className="border rounded-md p-3 space-y-2">
                                        <div className="grid grid-cols-[1fr_auto] gap-2 items-center">
                                            <Input
                                                value={rule.id}
                                                onChange={(e) => updateRegexRule(idx, { id: e.target.value })}
                                                placeholder="规则编码"
                                                className="h-8 text-xs font-mono"
                                            />
                                            <Button size="sm" variant="ghost" className="h-8 px-2" onClick={() => removeRegexRule(idx)}>
                                                <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                            </Button>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Select
                                                value={rule.category_id || "__none__"}
                                                onValueChange={(v) => updateRegexRule(idx, { category_id: v === "__none__" ? "" : v })}
                                            >
                                                <SelectTrigger className="h-8 text-xs">
                                                    <SelectValue placeholder="目标分类" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="__none__">未选择</SelectItem>
                                                    {categoryOptions.map((c) => (
                                                        <SelectItem key={c.id} value={c.id} className="text-xs">
                                                            {c.name} ({c.id})
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <Input
                                                type="number"
                                                step="0.01"
                                                value={rule.confidence ?? ""}
                                                onChange={(e) => updateRegexRule(idx, { confidence: asNumber(e.target.value) })}
                                                placeholder="置信度 0~1"
                                                className="h-8 text-xs"
                                            />
                                        </div>
                                        <div className="grid grid-cols-2 gap-2">
                                            <Input
                                                value={rule.pattern || ""}
                                                onChange={(e) => updateRegexRule(idx, { pattern: e.target.value })}
                                                placeholder="匹配表达式"
                                                className="h-8 text-xs font-mono"
                                            />
                                            <Input
                                                value={rule.flags || ""}
                                                onChange={(e) => updateRegexRule(idx, { flags: e.target.value })}
                                                placeholder="flags（如 i）"
                                                className="h-8 text-xs font-mono"
                                            />
                                        </div>
                                        <Input
                                            value={rule.note || ""}
                                            onChange={(e) => updateRegexRule(idx, { note: e.target.value })}
                                            placeholder="备注（可空）"
                                            className="h-8 text-xs"
                                        />
                                        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                            <Checkbox
                                                checked={rule.uncertain === true}
                                                onCheckedChange={(v) => updateRegexRule(idx, { uncertain: v === true })}
                                            />
                                            标记为不确定（需要人工复核）
                                        </label>
                                        <div className="grid grid-cols-2 gap-2">
                                            {RULE_FIELD_OPTIONS.map((field) => {
                                                const checked = (rule.fields || []).includes(field.id);
                                                return (
                                                    <label key={field.id} className="flex items-center gap-1.5 text-xs">
                                                        <Checkbox
                                                            checked={checked}
                                                            onCheckedChange={() => {
                                                                updateRegexRule(idx, { fields: toggleField(rule.fields, field.id) });
                                                            }}
                                                        />
                                                        {field.label}
                                                    </label>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                                {!regexRules.length ? <div className="text-xs text-muted-foreground">暂无规则</div> : null}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader className="py-3">
                    <CardTitle className="text-base">列设置</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <TextListEditor
                        title="提示列"
                        description="发送给模型用于分类判断的列。"
                        values={config.prompt_columns || []}
                        onChange={(next) => updateConfig({ prompt_columns: next })}
                        placeholder="输入列名后回车，例如 merchant"
                    />
                    <Separator />
                    <TextListEditor
                        title="复核列"
                        description="复核页面默认展示的列。"
                        values={config.review_columns || []}
                        onChange={(next) => updateConfig({ review_columns: next })}
                        placeholder="输入列名后回车，例如 amount"
                    />
                    <Separator />
                    <TextListEditor
                        title="输出排除列"
                        description="在最终输出中需要移除的列（可空）。"
                        values={config.drop_output_columns || []}
                        onChange={(next) => updateConfig({ drop_output_columns: next })}
                        placeholder="输入列名后回车"
                    />
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="py-3">
                    <div className="flex items-center justify-between gap-2">
                        <CardTitle className="text-base">高级：原始 JSON</CardTitle>
                        <div className="flex items-center gap-2">
                            <Button size="sm" variant="outline" className="h-7 px-2" onClick={syncJsonFromUi}>
                                从界面生成 JSON
                            </Button>
                            <Button size="sm" variant="outline" className="h-7 px-2" onClick={applyJsonToUi}>
                                用 JSON 覆盖界面
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <textarea
                        value={jsonText}
                        onChange={(e) => setJsonText(e.target.value)}
                        className="w-full min-h-[260px] rounded-md border bg-muted/30 p-2 font-mono text-xs focus:outline-none"
                        spellCheck={false}
                    />
                </CardContent>
            </Card>
        </div>
    );
}
