import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Play, RefreshCw } from "lucide-react";
import { type RunMeta } from "@/utils/helpers";

interface HeaderBarProps {
    baseUrl: string;
    setBaseUrl: (v: string) => void;
    apiToken: string;
    setApiToken: (v: string) => void;
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
}

export function HeaderBar({
    baseUrl, setBaseUrl, apiToken, setApiToken,
    backendStatus, backendError,
    runs, runId, setRunId, runsMeta, newRunName, setNewRunName,
    busy, runStatus, runName,
    refreshRuns, onCreateRun,
}: HeaderBarProps) {
    return (
        <>
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-semibold tracking-tight">OpenLedger</h1>
                <div className="flex items-center gap-4">
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
            <div className="flex flex-wrap items-center gap-4 p-4 border rounded-lg bg-card shadow-sm">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">后端</span>
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
                        placeholder="（可选）"
                        type="password"
                        className="w-[180px] h-8 font-mono text-xs"
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
