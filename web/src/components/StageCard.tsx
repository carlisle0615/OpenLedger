import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { FileItem, MatchStats, Stage, StageIO } from "@/types";
import { fmtStatus, api } from "@/utils/helpers";
import { AlertCircle, ChevronDown, ChevronRight, FileText, Loader2, Play, Terminal } from "lucide-react";

interface StageCardProps {
    stage: Stage;
    runId: string;
    baseUrl: string;
    isActive?: boolean;
    onRun?: (stageId: string) => void;
    onSelectFile?: (file: FileItem) => void;
}



export function StageCard({ stage, runId, baseUrl, onRun, onSelectFile }: StageCardProps) {
    const [io, setIo] = useState<StageIO | null>(null);
    const [logText, setLogText] = useState<string>("");
    const [isLogOpen, setIsLogOpen] = useState(stage.status === "running" || stage.status === "failed");
    const [loadingLog, setLoadingLog] = useState(false);
    const [matchStats, setMatchStats] = useState<MatchStats | null>(null);
    const [loadingStats, setLoadingStats] = useState(false);
    const autoOpenedLog = useRef(false);
    const isMatchStage = stage.id === "match_credit_card" || stage.id === "match_bank";

    // Auto-fetch IO on mount or status change
    useEffect(() => {
        if (!runId || !stage.id) return;
        let mounted = true;
        api<StageIO>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/stages/${encodeURIComponent(stage.id)}/io`)
            .then(d => { if (mounted) setIo(d); })
            .catch(() => { if (mounted) setIo(null); });
        return () => { mounted = false; };
    }, [runId, stage.id, baseUrl, stage.status]);

    useEffect(() => {
        if (!runId || !stage.id || !isMatchStage) {
            setMatchStats(null);
            return;
        }
        let mounted = true;
        setLoadingStats(true);
        api<MatchStats>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/stats/match?stage=${encodeURIComponent(stage.id)}`)
            .then(d => { if (mounted) setMatchStats(d); })
            .catch(() => { if (mounted) setMatchStats(null); })
            .finally(() => { if (mounted) setLoadingStats(false); });
        return () => { mounted = false; };
    }, [runId, stage.id, baseUrl, stage.status, isMatchStage]);

    async function fetchLog() {
        if (!runId) return;
        setLoadingLog(true);
        try {
            const r = await api<{ text: string }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/logs/${encodeURIComponent(stage.id)}`);
            setLogText(r.text);
        } catch {
            setLogText("（日志加载失败）");
        } finally {
            setLoadingLog(false);
        }
    }

    useEffect(() => {
        if (!isLogOpen) return;

        let timer: number | null = null;
        void fetchLog();

        if (stage.status === "running") {
            timer = window.setInterval(() => void fetchLog(), 3000);
        }
        return () => {
            if (timer != null) window.clearInterval(timer);
        };
    }, [isLogOpen, stage.status, stage.id, runId, baseUrl]);

    useEffect(() => {
        if (autoOpenedLog.current) return;
        if (stage.status === "running" || stage.status === "failed") {
            setIsLogOpen(true);
            autoOpenedLog.current = true;
        }
    }, [stage.status]);

    const status = fmtStatus(stage.status);

    const matchRatePct = matchStats ? Math.round(matchStats.match_rate * 1000) / 10 : 0;
    const reasons = matchStats?.unmatched_reasons ?? [];
    const reasonsShown = reasons.slice(0, 5);
    const reasonsLeft = reasons.length - reasonsShown.length;

    return (
        <Card className={cn("transition-all duration-200 border-l-4", stage.status === "running" ? "border-l-blue-500 shadow-md ring-1 ring-blue-500/20" : "border-l-transparent")}>
            <CardHeader className="pb-3 pt-4 px-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={cn("p-1.5 rounded-full custom-icon-bg", status.color.replace("text-", "bg-").replace("-500", "-100").replace("animate-spin", ""))}>
                            <status.icon className={cn("h-4 w-4", status.color)} />
                        </div>
                        <div>
                            <CardTitle className="text-base leading-none">{stage.name}</CardTitle>
                            <CardDescription className="font-mono text-[10px] mt-1 text-muted-foreground/70">{stage.id}</CardDescription>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant={status.variant} className="mr-2 h-5 px-1.5 text-[10px]">{status.text}</Badge>
                        <Button size="sm" variant={stage.status === 'running' ? "secondary" : "outline"} onClick={() => onRun?.(stage.id)} disabled={stage.status === 'running'} className="h-7 text-xs px-2">
                            <Play className="h-3 w-3 mr-1" />
                            运行
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <Separator />

            <CardContent className="pt-3 px-4 pb-4 grid gap-3">
                {stage.error && (
                    <div className="bg-destructive/10 text-destructive text-xs p-2 rounded-md flex items-start gap-2">
                        <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                        <p>{stage.error}</p>
                    </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                        <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">输入</h4>
                        <div className="space-y-1">
                            {io?.inputs?.length ? (
                                io.inputs.map((f) => (
                                    <div
                                        key={f.path}
                                        className="group text-xs flex items-center gap-2 p-1.5 rounded-md hover:bg-accent cursor-pointer transition-colors border border-dashed border-transparent hover:border-border"
                                        onClick={() => onSelectFile?.(f)}
                                    >
                                        <FileText className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />
                                        <span className="truncate flex-1" title={f.name}>{f.name}</span>
                                        <span className="text-[10px] text-muted-foreground/50 font-mono">{f.exists ? Math.round((f.size || 0) / 1024) + 'KB' : '-'}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-[10px] text-muted-foreground italic p-1">暂无输入</div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <h4 className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">输出</h4>
                        <div className="space-y-1">
                            {io?.outputs?.length ? (
                                io.outputs.map((f) => (
                                    <div
                                        key={f.path}
                                        className="group text-xs flex items-center gap-2 p-1.5 rounded-md hover:bg-accent cursor-pointer transition-colors border border-dashed border-transparent hover:border-border"
                                        onClick={() => onSelectFile?.(f)}
                                    >
                                        <FileText className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />
                                        <span className="truncate flex-1" title={f.name}>{f.name}</span>
                                        <span className="text-[10px] text-muted-foreground/50 font-mono">{f.exists ? Math.round((f.size || 0) / 1024) + 'KB' : '-'}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-[10px] text-muted-foreground italic p-1">暂无输出</div>
                            )}
                        </div>
                    </div>
                </div>

                {isMatchStage && (
                    <div className="rounded-md border bg-muted/10 p-2">
                        <div className="flex items-center justify-between text-[11px]">
                            <span className="font-medium text-muted-foreground">匹配统计</span>
                            {loadingStats ? (
                                <span className="text-[10px] text-muted-foreground">加载中...</span>
                            ) : matchStats ? (
                                <span className="font-mono text-[10px]">{matchRatePct}%</span>
                            ) : (
                                <span className="text-[10px] text-muted-foreground">暂无</span>
                            )}
                        </div>
                        {matchStats && (
                            <>
                                <div className="mt-1 text-[10px] text-muted-foreground">已匹配 {matchStats.matched} / 未匹配 {matchStats.unmatched}</div>
                                <div className="mt-2 space-y-1">
                                    {reasonsShown.length ? (
                                        reasonsShown.map((r) => (
                                            <div key={r.reason} className="flex items-center justify-between text-[10px]">
                                                <span className="truncate" title={r.reason}>{r.reason}</span>
                                                <span className="font-mono text-muted-foreground">{r.count}</span>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-[10px] text-muted-foreground italic">暂无未匹配原因</div>
                                    )}
                                    {reasonsLeft > 0 && (
                                        <div className="text-[10px] text-muted-foreground">其他 {reasonsLeft} 项</div>
                                    )}
                                </div>
                            </>
                        )}
                    </div>
                )}

                <Collapsible open={isLogOpen} onOpenChange={setIsLogOpen} className="border rounded-md bg-muted/10">
                    <CollapsibleTrigger asChild>
                        <Button variant="ghost" size="sm" className="w-full justify-between h-8 px-3 hover:bg-muted/50 text-xs">
                            <span className="flex items-center gap-2 font-medium text-muted-foreground">
                                <Terminal className="h-3.5 w-3.5" />
                                阶段日志
                            </span>
                            {isLogOpen ? <ChevronDown className="h-3.5 w-3.5 opacity-50" /> : <ChevronRight className="h-3.5 w-3.5 opacity-50" />}
                        </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <div className="p-0 border-t">
                            <ScrollArea className="h-[200px] w-full bg-black/90 text-white rounded-b-md">
                                <div className="p-3 font-mono text-[10px] leading-tight whitespace-pre-wrap">
                                    {loadingLog ? <span className="text-muted-foreground">加载中...</span> : (logText || <span className="opacity-50">（暂无日志）</span>)}
                                </div>
                            </ScrollArea>
                        </div>
                    </CollapsibleContent>
                </Collapsible>
            </CardContent>
        </Card>
    );
}
