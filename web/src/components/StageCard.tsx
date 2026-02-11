import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { FileItem, Stage, StageIO } from "@/types";
import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight, Clock, FileText, Loader2, Play, Terminal, XCircle } from "lucide-react";

interface StageCardProps {
    stage: Stage;
    runId: string;
    baseUrl: string;
    isActive?: boolean;
    onRun?: (stageId: string) => void;
    onSelectFile?: (file: FileItem) => void;
}

function fmtStatus(s: string) {
    if (s === "succeeded") return { text: "成功", variant: "default" as const, icon: CheckCircle2, color: "text-green-500" };
    if (s === "failed") return { text: "失败", variant: "destructive" as const, icon: XCircle, color: "text-red-500" };
    if (s === "running") return { text: "运行中", variant: "secondary" as const, icon: Loader2, color: "text-blue-500 animate-spin" };
    if (s === "needs_review") return { text: "需复核", variant: "secondary" as const, icon: AlertCircle, color: "text-amber-500" };
    if (s === "canceled") return { text: "已取消", variant: "destructive" as const, icon: XCircle, color: "text-gray-500" };
    if (s === "pending") return { text: "排队中", variant: "outline" as const, icon: Clock, color: "text-muted-foreground" };
    return { text: s, variant: "outline" as const, icon: AlertCircle, color: "text-muted-foreground" };
}

async function api<T>(baseUrl: string, path: string): Promise<T> {
    const res = await fetch(`${baseUrl}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
}

export function StageCard({ stage, runId, baseUrl, onRun, onSelectFile }: StageCardProps) {
    const [io, setIo] = useState<StageIO | null>(null);
    const [logText, setLogText] = useState<string>("");
    const [isLogOpen, setIsLogOpen] = useState(stage.status === "running" || stage.status === "failed");
    const [loadingLog, setLoadingLog] = useState(false);
    const autoOpenedLog = useRef(false);

    // Auto-fetch IO on mount or status change
    useEffect(() => {
        if (!runId || !stage.id) return;
        let mounted = true;
        api<StageIO>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/stages/${encodeURIComponent(stage.id)}/io`)
            .then(d => { if (mounted) setIo(d); })
            .catch(() => { if (mounted) setIo(null); });
        return () => { mounted = false; };
    }, [runId, stage.id, baseUrl, stage.status]);

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
