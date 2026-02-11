import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { AlertCircle, Play, RefreshCw } from "lucide-react";
import { type RunMeta } from "@/utils/helpers";

interface HeaderBarProps {
    baseUrl: string;
    setBaseUrl: (v: string) => void;
    backendStatus: "idle" | "checking" | "ok" | "error";
    backendError: string;
    runs: string[];
    runId: string;
    setRunId: (v: string) => void;
    runsMeta: RunMeta[];
    newRunName: string;
    setNewRunName: (v: string) => void;
    busy: boolean;
    runStatus: { text: string; variant: string; icon: React.ComponentType<any> } | null;
    runName: string;
    refreshRuns: () => Promise<any>;
    onCreateRun: (name: string) => Promise<void>;
    activeView: "workspace" | "profiles";
    setActiveView: (v: "workspace" | "profiles") => void;
}

export function HeaderBar({
    baseUrl, setBaseUrl,
    backendStatus, backendError,
    runs, runId, setRunId, runsMeta, newRunName, setNewRunName,
    busy, runStatus, runName,
    refreshRuns, onCreateRun,
    activeView, setActiveView,
}: HeaderBarProps) {
    return (
        <>
            <div className="flex items-center justify-between py-2">
                <h1 className="text-xl font-semibold tracking-tight">OpenLedger</h1>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1 rounded-md border bg-card p-1">
                        <Button
                            size="sm"
                            variant={activeView === "workspace" ? "default" : "ghost"}
                            className="h-7 px-3 text-xs"
                            onClick={() => setActiveView("workspace")}
                        >
                            工作台
                        </Button>
                        <Button
                            size="sm"
                            variant={activeView === "profiles" ? "default" : "ghost"}
                            className="h-7 px-3 text-xs"
                            onClick={() => setActiveView("profiles")}
                        >
                            用户
                        </Button>
                    </div>
                    <span className="text-xs text-muted-foreground font-mono">{runId || "未选择任务"}</span>
                    {runName ? (
                        <span className="text-xs text-muted-foreground truncate max-w-[260px]" title={runName}>
                            {runName}
                        </span>
                    ) : null}
                    <Badge variant="outline" className="font-mono">v0.2</Badge>
                </div>
            </div>

            {/* Top Control Bar */}
            <div className="flex flex-wrap items-center gap-4 px-4 py-2 border rounded-lg bg-card shadow-sm">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">后端</span>
                    <Input
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        className="w-[200px] h-8 font-mono text-xs"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-8"
                        onClick={() => refreshRuns().catch(() => { })}
                        disabled={busy || backendStatus === "checking" || !baseUrl.trim()}
                    >
                        <RefreshCw className="mr-2 h-3.5 w-3.5" />
                        测试连接
                    </Button>
                    <Badge
                        variant={
                            backendStatus === "error"
                                ? "destructive"
                                : backendStatus === "ok"
                                    ? "default"
                                    : backendStatus === "checking"
                                        ? "secondary"
                                        : "outline"
                        }
                        className="h-7"
                        title={backendStatus === "error" ? backendError : undefined}
                    >
                        {backendStatus === "checking"
                            ? "连接中…"
                            : backendStatus === "ok"
                                ? "已连接"
                                : backendStatus === "error"
                                    ? "连接失败"
                                    : "未检测"}
                    </Badge>
                </div>
                <Separator orientation="vertical" className="h-6" />
                <div className="flex items-center gap-2 flex-1">
                    <Select value={runId} onValueChange={setRunId}>
                        <SelectTrigger className="w-[240px] h-8 font-mono text-xs">
                            <SelectValue placeholder="选择任务" />
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
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-8 w-8 p-0"
                        onClick={() => refreshRuns().catch(() => { })}
                        disabled={busy}
                        title="刷新任务列表"
                    >
                        <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                    <Input
                        value={newRunName}
                        onChange={(e) => setNewRunName(e.target.value)}
                        placeholder="新任务名称（可选）"
                        className="w-[220px] h-8 text-xs"
                        disabled={busy}
                    />
                    <Button size="sm" className="h-8" onClick={() => onCreateRun(newRunName)} disabled={busy}>
                        <Play className="mr-2 h-3.5 w-3.5" /> 新建任务
                    </Button>
                    {!runId ? (
                        <span className="relative inline-flex items-center text-amber-500 animate-pulse group">
                            <AlertCircle className="h-4 w-4" aria-label="新手提示" />
                            <span className="pointer-events-none absolute left-1/2 top-full z-10 mt-2 w-56 -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-[11px] text-popover-foreground shadow-md opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                                新手提示：先测试连接，再新建任务，上传文件后运行流程。
                            </span>
                        </span>
                    ) : null}
                </div>
                {runStatus && (
                    <Badge variant={runStatus.variant as any} className="gap-1 pl-2 h-7 px-2">
                        {runStatus.icon && <runStatus.icon className="h-3.5 w-3.5" />}
                        {runStatus.text}
                    </Badge>
                )}
            </div>
        </>
    );
}
