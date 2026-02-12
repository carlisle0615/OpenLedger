import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Profile, ProfileIntegrityIssue, ProfileIntegrityResult, RunState } from "@/types";
import { api } from "@/utils/helpers";
import { RefreshCw, Link2, FolderPlus, AlertCircle, Trash2, User } from "lucide-react";

interface ProfilesPageProps {
    baseUrl: string;
    runId: string;
    currentProfileId?: string;
    busy: boolean;
    setRunProfileBinding: (profileId: string) => Promise<void> | void;
    runState: RunState | null;
    confirmAction: (opts: {
        title: string;
        description: string;
        confirmText: string;
        cancelText: string;
        tone: "default" | "danger";
    }) => Promise<boolean>;
}

export function ProfilesPage({ baseUrl, runId, currentProfileId, busy, setRunProfileBinding, runState, confirmAction }: ProfilesPageProps) {
    const [selected, setSelected] = useState<Profile | null>(null);
    const [loadingProfile, setLoadingProfile] = useState(false);
    const [runToAttach, setRunToAttach] = useState("");
    const [attachYear, setAttachYear] = useState("");
    const [attachMonth, setAttachMonth] = useState("");
    const [error, setError] = useState("");
    const [integrityIssues, setIntegrityIssues] = useState<ProfileIntegrityIssue[]>([]);
    const [integrityCheckedAt, setIntegrityCheckedAt] = useState("");
    const [integrityLoading, setIntegrityLoading] = useState(false);
    const lastArchiveStamp = useRef<string>("");

    const selectedProfileId = String(currentProfileId || "").trim();
    const normalizedRunId = String(runId || "").trim();
    const bills = useMemo(() => {
        const list = selected?.bills ?? [];
        return [...list].sort((a, b) => String(a.period_key || "").localeCompare(String(b.period_key || "")));
    }, [selected]);
    const archivedRunBill = normalizedRunId
        ? bills.find((b) => String(b.run_id || "").trim() === normalizedRunId)
        : undefined;
    const boundProfileId = String(runState?.profile_binding?.profile_id || "").trim();
    const isCurrentRunBoundToSelected = Boolean(normalizedRunId) && Boolean(selectedProfileId) && boundProfileId === selectedProfileId;
    const isCurrentRunArchivedToSelected = Boolean(archivedRunBill);
    const isCurrentRunEffectivelyBound = isCurrentRunBoundToSelected || isCurrentRunArchivedToSelected;
    const archiveInfo = runState?.profile_archive;
    const archiveMatches = archiveInfo && archiveInfo.profile_id && archiveInfo.profile_id === selectedProfileId;
    const nowYear = new Date().getFullYear();
    const yearOptions = useMemo(() => {
        const set = new Set<number>([nowYear - 1, nowYear, nowYear + 1]);
        if (runState?.options?.period_year) set.add(runState.options.period_year);
        const arr = Array.from(set);
        arr.sort((a, b) => a - b);
        return arr;
    }, [nowYear, runState?.options?.period_year]);

    const periodStats = useMemo(() => {
        const keys = bills.map((b) => String(b.period_key || "")).filter(Boolean);
        const counts = new Map<string, number>();
        keys.forEach((k) => counts.set(k, (counts.get(k) || 0) + 1));
        const conflicts = Array.from(counts.entries()).filter(([, v]) => v > 1).map(([k]) => k);
        return { conflicts };
    }, [bills]);

    async function loadProfile(id: string) {
        if (!id || !baseUrl.trim()) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(id)}`);
            setSelected(profile);
            setIntegrityIssues([]);
            setIntegrityCheckedAt("");
        } catch (e) {
            setError(String(e));
            setSelected(null);
        } finally {
            setLoadingProfile(false);
        }
    }

    async function checkIntegrity() {
        if (!selectedProfileId || !baseUrl.trim()) return;
        setIntegrityLoading(true);
        setError("");
        try {
            const res = await api<ProfileIntegrityResult>(baseUrl, `/api/profiles/${encodeURIComponent(selectedProfileId)}/check`);
            setIntegrityIssues(Array.isArray(res.issues) ? res.issues : []);
            setIntegrityCheckedAt(new Date().toISOString());
        } catch (e) {
            setError(String(e));
        } finally {
            setIntegrityLoading(false);
        }
    }

    useEffect(() => {
        if (!selectedProfileId) {
            setSelected(null);
            setIntegrityIssues([]);
            setIntegrityCheckedAt("");
            return;
        }
        loadProfile(selectedProfileId).catch(() => { });
    }, [selectedProfileId, baseUrl]);

    useEffect(() => {
        const info = runState?.profile_archive;
        if (!info || !info.updated_at) return;
        if (info.updated_at === lastArchiveStamp.current) return;
        lastArchiveStamp.current = info.updated_at;
        if (info.profile_id && info.profile_id === selectedProfileId) {
            loadProfile(info.profile_id).catch(() => { });
        }
    }, [runState?.profile_archive?.updated_at, selectedProfileId]);

    async function bindCurrentRun() {
        if (!runId || !selectedProfileId) return;
        setError("");
        try {
            await setRunProfileBinding(selectedProfileId);
        } catch (e) {
            setError(String(e));
        }
    }

    async function attachRun(runIdToUse: string) {
        if (!selectedProfileId || !runIdToUse) return;
        const y = attachYear.trim();
        const m = attachMonth.trim();
        if ((y && !m) || (!y && m)) {
            setError("请选择完整的归属年月（年+月），或都不选。");
            return;
        }
        setLoadingProfile(true);
        setError("");
        try {
            const payload: Record<string, unknown> = { run_id: runIdToUse };
            if (y && m) {
                payload.period_year = Number(y);
                payload.period_month = Number(m);
            } else {
                payload.period_year = null;
                payload.period_month = null;
            }
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selectedProfileId)}/bills`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            setSelected(profile);
            setRunToAttach("");
            setAttachYear("");
            setAttachMonth("");
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    async function deleteBill(periodKey: string, billRunId: string) {
        if (!selectedProfileId || (!periodKey && !billRunId)) return;
        const ok = await confirmAction({
            title: "确认删除归档？",
            description: periodKey
                ? `将删除账期 ${periodKey} 下的所有归档记录。`
                : `将删除 run ${billRunId} 的归档记录。`,
            confirmText: "确认删除",
            cancelText: "取消",
            tone: "danger",
        });
        if (!ok) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selectedProfileId)}/bills/remove`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(periodKey ? { period_key: periodKey } : { run_id: billRunId }),
            });
            setSelected(profile);
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    async function reimportPeriod(periodKey: string) {
        if (!selectedProfileId || !periodKey || !runId) return;
        const ok = await confirmAction({
            title: "确认重导账期？",
            description: `将删除账期 ${periodKey} 的现有归档，并使用当前任务 ${runId} 重新归档。`,
            confirmText: "确认重导",
            cancelText: "取消",
            tone: "danger",
        });
        if (!ok) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selectedProfileId)}/bills/reimport`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ period_key: periodKey, run_id: runId }),
            });
            setSelected(profile);
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    const issueLabel = (issue: string) => {
        switch (issue) {
            case "missing_period_key":
                return "账期缺失";
            case "missing_run_dir":
                return "run 目录缺失";
            case "missing_summary_csv":
                return "缺少 category.summary.csv";
            case "empty_summary_csv":
                return "category.summary.csv 为空";
            case "missing_categorized_csv":
                return "缺少 unified.transactions.categorized.csv";
            case "empty_categorized_csv":
                return "unified.transactions.categorized.csv 为空";
            default:
                return issue || "unknown";
        }
    };

    const fmtMoney = (value: unknown) => {
        if (value === null || value === undefined || value === "") return "-";
        const num = Number(value);
        if (!Number.isFinite(num)) return String(value);
        return num.toFixed(2);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 space-y-4">
                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <User className="h-4 w-4" /> 当前归属用户
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {selectedProfileId ? (
                            <>
                                <div className="text-sm font-medium">{selected?.name || selectedProfileId}</div>
                                <div className="text-[11px] text-muted-foreground font-mono break-all">{selectedProfileId}</div>
                            </>
                        ) : (
                            <div className="text-[11px] text-muted-foreground">
                                请先在顶部选择用户。
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Link2 className="h-4 w-4" /> 绑定任务
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <div className="text-[11px] text-muted-foreground">
                            当前任务：{runId ? <span className="font-mono" title={runId}>{runId}</span> : "未选择"}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                            当前已绑定：{boundProfileId ? <span className="font-mono" title={boundProfileId}>{boundProfileId}</span> : "未绑定"}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                            当前任务归档：{isCurrentRunArchivedToSelected ? "已归档到该用户" : "未归档到该用户"}
                        </div>
                        <Button
                            size="sm"
                            className="h-8 w-full"
                            disabled={!normalizedRunId || !selectedProfileId || busy || loadingProfile || isCurrentRunEffectivelyBound}
                            onClick={() => void bindCurrentRun()}
                        >
                            {isCurrentRunEffectivelyBound ? "已绑定当前任务" : "绑定当前任务到该用户"}
                        </Button>
                        <div className="text-[11px] text-muted-foreground">
                            该绑定用于 finalize 自动归档；归档记录存在也会视为已绑定显示。
                        </div>
                        {isCurrentRunArchivedToSelected ? (
                            <div className="text-[11px] text-muted-foreground">
                                已归档账期：{archivedRunBill?.period_key || "未指定月"}
                            </div>
                        ) : null}
                        {archiveInfo && archiveMatches ? (
                            <div className={`text-[11px] ${archiveInfo.status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>
                                {archiveInfo.status === "failed"
                                    ? `自动归档失败：${archiveInfo.error || "未知错误"}`
                                    : "自动归档成功"}
                            </div>
                        ) : null}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <FolderPlus className="h-4 w-4" /> 手动归档 Run
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <Input
                            value={runToAttach}
                            onChange={(e) => setRunToAttach(e.target.value)}
                            placeholder="输入 run_id 归档"
                            className="h-8 text-xs"
                            disabled={!selectedProfileId || busy}
                        />
                        <div className="grid grid-cols-2 gap-2">
                            <Select value={attachYear || "__none__"} onValueChange={(v) => setAttachYear(v === "__none__" ? "" : v)}>
                                <SelectTrigger className="h-8 text-xs">
                                    <SelectValue placeholder="归属年（可空）" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="__none__">不指定年份</SelectItem>
                                    {yearOptions.map((y) => (
                                        <SelectItem key={y} value={String(y)} className="text-xs font-mono">
                                            {y}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Select value={attachMonth || "__none__"} onValueChange={(v) => setAttachMonth(v === "__none__" ? "" : v)}>
                                <SelectTrigger className="h-8 text-xs">
                                    <SelectValue placeholder="归属月（可空）" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="__none__">不指定月份</SelectItem>
                                    {Array.from({ length: 12 }).map((_, i) => (
                                        <SelectItem key={i + 1} value={String(i + 1)} className="text-xs">
                                            {i + 1}月
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                            同一用户下同一个年/月只能绑定一个 run。
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                size="sm"
                                className="h-8"
                                onClick={() => void attachRun(runToAttach.trim())}
                                disabled={!selectedProfileId || busy || !runToAttach.trim()}
                            >
                                归档 run_id
                            </Button>
                            {runId ? (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8"
                                    onClick={() => void attachRun(runId)}
                                    disabled={!selectedProfileId || busy}
                                >
                                    使用当前任务
                                </Button>
                            ) : null}
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="lg:col-span-8 space-y-4">
                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base">归档详情</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {selected ? (
                            <>
                                <div className="text-[11px] text-muted-foreground font-mono">{selected.id}</div>
                                <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                                    <span>创建时间：{selected.created_at || "-"}</span>
                                    <span>更新时间：{selected.updated_at || "-"}</span>
                                </div>
                            </>
                        ) : (
                            <div className="text-[11px] text-muted-foreground italic">请先在顶部选择用户</div>
                        )}

                        <div className="pt-2 border-t space-y-2">
                            <div className="flex items-center justify-between">
                                <div className="text-xs font-medium">一致性检查</div>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 px-2"
                                    onClick={() => void checkIntegrity()}
                                    disabled={!selectedProfileId || integrityLoading || busy}
                                >
                                    <RefreshCw className="h-3.5 w-3.5 mr-1" />
                                    检查
                                </Button>
                            </div>
                            {!selectedProfileId ? (
                                <div className="text-[11px] text-muted-foreground italic">请选择用户后检查</div>
                            ) : integrityCheckedAt ? (
                                <>
                                    <div className="text-[11px] text-muted-foreground">
                                        最近检查：{integrityCheckedAt}
                                    </div>
                                    {integrityIssues.length ? (
                                        <div className="space-y-1">
                                            {integrityIssues.slice(0, 4).map((issue, idx) => (
                                                <div key={`${issue.run_id}-${issue.issue}-${idx}`} className="text-[11px] text-muted-foreground">
                                                    <span className="font-mono">{issue.period_key || "-"}</span>
                                                    <span className="ml-2">{issueLabel(issue.issue)}</span>
                                                    {issue.run_id ? <span className="ml-2 font-mono" title={issue.run_id}>run={issue.run_id}</span> : null}
                                                </div>
                                            ))}
                                            {integrityIssues.length > 4 ? (
                                                <div className="text-[11px] text-muted-foreground">还有 {integrityIssues.length - 4} 条问题</div>
                                            ) : null}
                                        </div>
                                    ) : (
                                        <div className="text-[11px] text-muted-foreground">未发现问题</div>
                                    )}
                                </>
                            ) : (
                                <div className="text-[11px] text-muted-foreground">未检查</div>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {error ? (
                    <div className="text-xs text-destructive">{error}</div>
                ) : null}

                <Card>
                    <CardHeader className="py-3 flex flex-row items-center justify-between">
                        <CardTitle className="text-base">归档账单列表</CardTitle>
                        <div className="text-[11px] text-muted-foreground">
                            {selected ? `${bills.length} 条` : "—"}
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {periodStats.conflicts.length > 0 && (
                            <div className="text-[11px] text-muted-foreground flex items-start gap-2">
                                <AlertCircle className="h-3.5 w-3.5 mt-0.5 text-[hsl(var(--warning))]" />
                                <div>账期冲突：{periodStats.conflicts.join(", ")}</div>
                            </div>
                        )}
                        <ScrollArea className="h-[420px] border rounded-md">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="h-8 text-xs w-[90px]">账期</TableHead>
                                        <TableHead className="h-8 text-xs w-[220px]">范围</TableHead>
                                        <TableHead className="h-8 text-xs w-[90px]">模式</TableHead>
                                        <TableHead className="h-8 text-xs w-[120px]">标识</TableHead>
                                        <TableHead className="h-8 text-xs text-right w-[96px]">支出</TableHead>
                                        <TableHead className="h-8 text-xs text-right w-[96px]">收入</TableHead>
                                        <TableHead className="h-8 text-xs text-right w-[96px]">净额</TableHead>
                                        <TableHead className="h-8 text-xs text-right w-[70px]">条数</TableHead>
                                        <TableHead className="h-8 text-xs w-[180px]">run_id</TableHead>
                                        <TableHead className="h-8 text-xs text-right w-[110px]">操作</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loadingProfile ? (
                                        <TableRow>
                                            <TableCell colSpan={10} className="text-xs text-muted-foreground">加载中…</TableCell>
                                        </TableRow>
                                    ) : bills.length ? (
                                        bills.map((b) => (
                                            <TableRow key={`${b.run_id}-${b.period_key}-${b.year ?? "none"}-${b.month ?? "none"}`} className="h-8">
                                                <TableCell className="text-xs font-mono whitespace-nowrap">{b.period_key || "-"}</TableCell>
                                                <TableCell className="text-xs font-mono whitespace-nowrap">
                                                    {b.period_start && b.period_end ? `${b.period_start} ~ ${b.period_end}` : "-"}
                                                </TableCell>
                                                <TableCell className="text-xs">{b.period_mode || "-"}</TableCell>
                                                <TableCell className="text-xs">
                                                    <div className="flex items-center gap-1 flex-wrap">
                                                        {b.cross_month ? <Badge variant="outline" className="text-[10px]">跨月</Badge> : null}
                                                        {periodStats.conflicts.includes(String(b.period_key || "")) ? (
                                                            <Badge variant="destructive" className="text-[10px]">冲突</Badge>
                                                        ) : null}
                                                        {!b.period_key ? (
                                                            <Badge variant="outline" className="text-[10px]">未指定月</Badge>
                                                        ) : null}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-xs text-right font-mono">{fmtMoney(b.totals?.sum_expense)}</TableCell>
                                                <TableCell className="text-xs text-right font-mono">{fmtMoney(b.totals?.sum_income)}</TableCell>
                                                <TableCell className="text-xs text-right font-mono">{fmtMoney(b.totals?.net ?? b.totals?.sum_amount)}</TableCell>
                                                <TableCell className="text-xs text-right font-mono">{b.totals?.count ?? "-"}</TableCell>
                                                <TableCell className="text-xs font-mono truncate max-w-[170px]" title={b.run_id}>{b.run_id}</TableCell>
                                                <TableCell className="text-xs text-right">
                                                    <div className="flex items-center justify-end gap-1">
                                                        {runId ? (
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                className="h-7 px-2 text-[10px]"
                                                                onClick={() => void reimportPeriod(String(b.period_key || ""))}
                                                                disabled={!b.period_key}
                                                            >
                                                                重导
                                                            </Button>
                                                        ) : null}
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-7 px-2"
                                                            disabled={!b.period_key && !b.run_id}
                                                            onClick={() => void deleteBill(String(b.period_key || ""), String(b.run_id || ""))}
                                                        >
                                                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={10} className="text-xs text-muted-foreground italic">暂无账单</TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </ScrollArea>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
