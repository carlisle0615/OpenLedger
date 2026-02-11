import { useEffect, useMemo, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Profile, ProfileIntegrityIssue, ProfileIntegrityResult, ProfileListItem, RunState } from "@/types";
import { api } from "@/utils/helpers";
import { RefreshCw, UserPlus, Users, Link2, FolderPlus, AlertCircle, Trash2 } from "lucide-react";

interface ProfilesPageProps {
    baseUrl: string;
    runId: string;
    currentProfileId?: string;
    busy: boolean;
    saveOptions: (updates: Partial<{ profile_id: string }>) => Promise<void> | void;
    runState: RunState | null;
}

export function ProfilesPage({ baseUrl, runId, currentProfileId, busy, saveOptions, runState }: ProfilesPageProps) {
    const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
    const [selectedId, setSelectedId] = useState<string>("");
    const [selected, setSelected] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadingProfile, setLoadingProfile] = useState(false);
    const [createName, setCreateName] = useState("");
    const [runToAttach, setRunToAttach] = useState("");
    const [error, setError] = useState("");
    const [integrityIssues, setIntegrityIssues] = useState<ProfileIntegrityIssue[]>([]);
    const [integrityCheckedAt, setIntegrityCheckedAt] = useState("");
    const [integrityLoading, setIntegrityLoading] = useState(false);
    const lastArchiveStamp = useRef<string>("");

    const effectiveSelectedId = selectedId || currentProfileId || "";

    const bills = useMemo(() => {
        const list = selected?.bills ?? [];
        return [...list].sort((a, b) => String(a.period_key || "").localeCompare(String(b.period_key || "")));
    }, [selected]);

    const periodStats = useMemo(() => {
        const keys = bills.map((b) => String(b.period_key || "")).filter(Boolean);
        const counts = new Map<string, number>();
        keys.forEach((k) => counts.set(k, (counts.get(k) || 0) + 1));
        const conflicts = Array.from(counts.entries()).filter(([, v]) => v > 1).map(([k]) => k);

        const parseKey = (k: string) => {
            const m = /^(\d{4})-(\d{2})$/.exec(k);
            if (!m) return null;
            return { y: Number(m[1]), m: Number(m[2]) };
        };
        const parsed = keys.map(parseKey).filter(Boolean) as { y: number; m: number }[];
        if (!parsed.length) {
            return { conflicts, missing: [] as string[] };
        }
        const toIndex = (y: number, m: number) => y * 12 + (m - 1);
        const min = parsed.reduce((a, b) => (toIndex(a.y, a.m) < toIndex(b.y, b.m) ? a : b));
        const max = parsed.reduce((a, b) => (toIndex(a.y, a.m) > toIndex(b.y, b.m) ? a : b));
        const minIdx = toIndex(min.y, min.m);
        const maxIdx = toIndex(max.y, max.m);
        const present = new Set(keys);
        const missing: string[] = [];
        for (let idx = minIdx; idx <= maxIdx; idx++) {
            const y = Math.floor(idx / 12);
            const m = (idx % 12) + 1;
            const key = `${y}-${String(m).padStart(2, "0")}`;
            if (!present.has(key)) missing.push(key);
        }
        return { conflicts, missing };
    }, [bills]);

    async function loadProfiles() {
        if (!baseUrl.trim()) return;
        setLoading(true);
        setError("");
        try {
            const res = await api<{ profiles: ProfileListItem[] }>(baseUrl, "/api/profiles");
            setProfiles(Array.isArray(res.profiles) ? res.profiles : []);
        } catch (e) {
            setError(String(e));
        } finally {
            setLoading(false);
        }
    }

    async function loadProfile(id: string) {
        if (!id || !baseUrl.trim()) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(id)}`);
            setSelected(profile);
            setSelectedId(id);
            setIntegrityIssues([]);
            setIntegrityCheckedAt("");
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    async function checkIntegrity(id?: string) {
        const targetId = id || selected?.id || "";
        if (!targetId || !baseUrl.trim()) return;
        setIntegrityLoading(true);
        setError("");
        try {
            const res = await api<ProfileIntegrityResult>(baseUrl, `/api/profiles/${encodeURIComponent(targetId)}/check`);
            setIntegrityIssues(Array.isArray(res.issues) ? res.issues : []);
            setIntegrityCheckedAt(new Date().toISOString());
        } catch (e) {
            setError(String(e));
        } finally {
            setIntegrityLoading(false);
        }
    }

    useEffect(() => {
        loadProfiles().catch(() => { });
    }, [baseUrl]);

    useEffect(() => {
        if (!effectiveSelectedId) {
            setSelected(null);
            return;
        }
        if (selected?.id === effectiveSelectedId) return;
        loadProfile(effectiveSelectedId).catch(() => { });
    }, [effectiveSelectedId]);

    useEffect(() => {
        const info = runState?.profile_archive;
        if (!info || !info.updated_at) return;
        if (info.updated_at === lastArchiveStamp.current) return;
        lastArchiveStamp.current = info.updated_at;
        if (info.status === "ok") {
            if (info.profile_id) {
                loadProfiles().catch(() => { });
                if (info.profile_id === effectiveSelectedId) {
                    loadProfile(info.profile_id).catch(() => { });
                }
            }
        }
    }, [runState?.profile_archive?.updated_at, effectiveSelectedId]);

    async function handleCreate() {
        const name = createName.trim();
        if (!name) return;
        setLoading(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, "/api/profiles", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
            });
            setCreateName("");
            await loadProfiles();
            setSelected(profile);
            setSelectedId(profile.id);
        } catch (e) {
            setError(String(e));
        } finally {
            setLoading(false);
        }
    }

    async function attachRun(runIdToUse: string) {
        if (!selected?.id || !runIdToUse) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selected.id)}/bills`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ run_id: runIdToUse }),
            });
            setSelected(profile);
            setRunToAttach("");
            await loadProfiles();
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    async function deletePeriod(periodKey: string) {
        if (!selected?.id || !periodKey) return;
        const ok = window.confirm(`确认删除账期 ${periodKey}？该账期下的所有记录将被移除。`);
        if (!ok) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selected.id)}/bills/remove`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ period_key: periodKey }),
            });
            setSelected(profile);
            await loadProfiles();
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    async function reimportPeriod(periodKey: string) {
        if (!selected?.id || !periodKey || !runId) return;
        const ok = window.confirm(`确认删除并重导账期 ${periodKey}？将使用当前任务 ${runId} 重新归档。`);
        if (!ok) return;
        setLoadingProfile(true);
        setError("");
        try {
            const profile = await api<Profile>(baseUrl, `/api/profiles/${encodeURIComponent(selected.id)}/bills/reimport`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ period_key: periodKey, run_id: runId }),
            });
            setSelected(profile);
            await loadProfiles();
        } catch (e) {
            setError(String(e));
        } finally {
            setLoadingProfile(false);
        }
    }

    const selectedMeta = profiles.find((p) => p.id === (selected?.id || effectiveSelectedId));
    const archiveInfo = runState?.profile_archive;
    const archiveMatches = archiveInfo && archiveInfo.profile_id && archiveInfo.profile_id === (selected?.id || currentProfileId);
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
                    <CardHeader className="py-3 flex flex-row items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Users className="h-4 w-4" /> 用户
                        </CardTitle>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7 px-2"
                            onClick={() => loadProfiles().catch(() => { })}
                            disabled={loading || busy}
                        >
                            <RefreshCw className="h-3.5 w-3.5 mr-1" />
                            刷新
                        </Button>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex items-center gap-2">
                            <Input
                                value={createName}
                                onChange={(e) => setCreateName(e.target.value)}
                                placeholder="新用户名称"
                                className="h-8 text-xs"
                                disabled={loading || busy}
                            />
                            <Button size="sm" className="h-8" onClick={handleCreate} disabled={loading || busy || !createName.trim()}>
                                <UserPlus className="h-3.5 w-3.5 mr-1" />
                                创建
                            </Button>
                        </div>
                        <Separator />
                        <div className="space-y-1">
                            {profiles.length ? (
                                profiles.map((p) => (
                                    <button
                                        key={p.id}
                                        type="button"
                                        onClick={() => loadProfile(p.id)}
                                        className={`w-full text-left px-2 py-2 rounded-md border text-xs transition-colors ${effectiveSelectedId === p.id ? "border-primary bg-primary/10" : "border-transparent hover:border-border hover:bg-accent"}`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="font-medium truncate">{p.name || p.id}</span>
                                            <Badge variant="outline" className="text-[10px]">{p.bill_count} 账单</Badge>
                                        </div>
                                        <div className="text-[10px] text-muted-foreground font-mono mt-1 truncate">{p.id}</div>
                                    </button>
                                ))
                            ) : (
                                <div className="text-[11px] text-muted-foreground italic">暂无用户</div>
                            )}
                        </div>
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
                            当前任务：{runId ? <span className="font-mono">{runId}</span> : "未选择"}
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                size="sm"
                                className="h-8"
                                disabled={!runId || !selected?.id || busy}
                                onClick={() => saveOptions({ profile_id: selected?.id || "" })}
                            >
                                绑定到当前任务
                            </Button>
                            {currentProfileId && (
                                <Badge variant="secondary" className="text-[10px]">
                                    已绑定：{currentProfileId}
                                </Badge>
                            )}
                        </div>
                        {archiveInfo && archiveMatches ? (
                            <div className={`text-[11px] ${archiveInfo.status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>
                                {archiveInfo.status === "failed"
                                    ? `自动归档失败：${archiveInfo.error || "未知错误"}`
                                    : "自动归档成功"}
                            </div>
                        ) : null}
                    </CardContent>
                </Card>
            </div>

            <div className="lg:col-span-8 space-y-4">
                <Card>
                    <CardHeader className="py-3">
                        <CardTitle className="text-base">
                            {selected?.name || selectedMeta?.name || "用户详情"}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {selected ? (
                            <>
                                <div className="text-[11px] text-muted-foreground font-mono">{selected.id}</div>
                                <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                                    <span>创建时间：{selected.created_at || "-"}</span>
                                    <span>更新时间：{selected.updated_at || "-"}</span>
                                </div>
                            </>
                        ) : (
                            <div className="text-[11px] text-muted-foreground italic">请选择用户</div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3 flex flex-row items-center justify-between">
                        <CardTitle className="text-base">一致性检查</CardTitle>
                        <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2"
                            onClick={() => checkIntegrity()}
                            disabled={!selected?.id || integrityLoading || busy}
                        >
                            <RefreshCw className="h-3.5 w-3.5 mr-1" />
                            检查
                        </Button>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {!selected?.id ? (
                            <div className="text-[11px] text-muted-foreground italic">请选择用户后检查</div>
                        ) : integrityCheckedAt ? (
                            <>
                                <div className="text-[11px] text-muted-foreground">
                                    最近检查：{integrityCheckedAt}
                                </div>
                                {integrityIssues.length ? (
                                    <div className="space-y-1">
                                        {integrityIssues.slice(0, 6).map((issue, idx) => (
                                            <div key={`${issue.run_id}-${issue.issue}-${idx}`} className="text-[11px] text-muted-foreground">
                                                <span className="font-mono">{issue.period_key || "-"}</span>
                                                <span className="ml-2">{issueLabel(issue.issue)}</span>
                                                {issue.run_id ? <span className="ml-2 font-mono">run={issue.run_id}</span> : null}
                                            </div>
                                        ))}
                                        {integrityIssues.length > 6 ? (
                                            <div className="text-[11px] text-muted-foreground">还有 {integrityIssues.length - 6} 条问题</div>
                                        ) : null}
                                    </div>
                                ) : (
                                    <div className="text-[11px] text-muted-foreground">未发现问题</div>
                                )}
                            </>
                        ) : (
                            <div className="text-[11px] text-muted-foreground">未检查</div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="py-3 flex flex-row items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2">
                            <FolderPlus className="h-4 w-4" /> 账单归档
                        </CardTitle>
                        <div className="text-[11px] text-muted-foreground">
                            {selected ? `${bills.length} 条` : "—"}
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="flex items-center gap-2">
                            <Input
                                value={runToAttach}
                                onChange={(e) => setRunToAttach(e.target.value)}
                                placeholder="输入 run_id 归档"
                                className="h-8 text-xs"
                                disabled={!selected?.id || busy}
                            />
                            <Button
                                size="sm"
                                className="h-8"
                                onClick={() => attachRun(runToAttach.trim())}
                                disabled={!selected?.id || busy || !runToAttach.trim()}
                            >
                                归档
                            </Button>
                            {runId ? (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8"
                                    onClick={() => attachRun(runId)}
                                    disabled={!selected?.id || busy}
                                >
                                    使用当前任务
                                </Button>
                            ) : null}
                        </div>
                        {error ? (
                            <div className="text-xs text-destructive">{error}</div>
                        ) : null}
                        {(periodStats.conflicts.length > 0 || periodStats.missing.length > 0) && (
                            <div className="text-[11px] text-muted-foreground flex items-start gap-2">
                                <AlertCircle className="h-3.5 w-3.5 mt-0.5 text-amber-500" />
                                <div className="space-y-1">
                                    {periodStats.conflicts.length > 0 && (
                                        <div>账期冲突：{periodStats.conflicts.join(", ")}</div>
                                    )}
                                    {periodStats.missing.length > 0 && (
                                        <div>账期缺失：{periodStats.missing.join(", ")}</div>
                                    )}
                                </div>
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
                                            <TableRow key={`${b.run_id}-${b.period_key}`} className="h-8">
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
                                                                onClick={() => reimportPeriod(String(b.period_key || ""))}
                                                                disabled={!b.period_key}
                                                            >
                                                                重导
                                                            </Button>
                                                        ) : null}
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-7 px-2"
                                                            disabled={!b.period_key}
                                                            onClick={() => deletePeriod(String(b.period_key || ""))}
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
