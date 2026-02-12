
import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { RefreshCw, CheckCircle2, AlertTriangle, XCircle, Info, FileText, ChevronDown, ChevronRight, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCapabilities, SourceCoverage } from "@/hooks/useCapabilities";
import { RunState, PdfParserHealthItem } from "@/types";

interface CapabilitiesPanelProps {
    baseUrl: string;
    runState: RunState | null;
}

// 简单的 Skeleton 组件
function Skeleton({ className }: { className?: string }) {
    return <div className={cn("animate-pulse rounded bg-muted", className)} />;
}

export function CapabilitiesPanel({ baseUrl, runState }: CapabilitiesPanelProps) {
    const {
        loading,
        error,
        sourceMatrix,
        parserHealth,
        lastUpdated,
        refresh,
        coverage
    } = useCapabilities(baseUrl, runState ? { inputs: runState.inputs } : null);

    const hasRun = Boolean(runState);

    // 渲染数据源矩阵行
    const renderSourceRow = (s: SourceCoverage) => {
        const { source, matched, matchedFiles } = s;

        return (
            <TableRow key={source.id}>
                <TableCell className="font-medium">{source.name}</TableCell>
                <TableCell>
                    {source.file_types.map(ft => <Badge key={ft} variant="outline" className="mr-1">{ft}</Badge>)}
                </TableCell>
                <TableCell className="text-muted-foreground text-xs">
                    {source.filename_hints.join(", ")}
                </TableCell>
                {/* 新增列：阶段 */}
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {source.stage}
                </TableCell>
                {/* 新增列：解析器 */}
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {source.parser_mode || "-"}
                </TableCell>
                <TableCell>
                    <Badge variant={source.support_level === "stable" ? "secondary" : "outline"}>
                        {source.support_level}
                    </Badge>
                </TableCell>
                {hasRun && (
                    <TableCell>
                        {matched ? (
                            <div title={`匹配文件:\n${matchedFiles.join("\n")}`}>
                                <Badge className="bg-green-500 hover:bg-green-600 cursor-help">已满足</Badge>
                            </div>
                        ) : (
                            <Badge variant="outline" className="text-muted-foreground">缺失</Badge>
                        )}
                    </TableCell>
                )}
            </TableRow>
        );
    };

    // 渲染 Parser 健康状态
    const ParserItem = ({ item }: { item: PdfParserHealthItem }) => {
        const [isOpen, setIsOpen] = useState(false);
        const isError = item.status === "error";
        const isWarning = item.status === "warning";
        const statusColor = isError ? "text-red-500" : isWarning ? "text-amber-500" : "text-green-500";
        const StatusIcon = isError ? XCircle : isWarning ? AlertTriangle : CheckCircle2;

        return (
            <Collapsible open={isOpen} onOpenChange={setIsOpen} className="border-b last:border-b-0">
                <div className="flex items-center gap-2 w-full py-2 px-2 hover:bg-muted/50 transition-colors">
                    <CollapsibleTrigger asChild>
                        <Button variant="ghost" size="sm" className="p-0 w-6 h-6 h-auto hover:bg-transparent">
                            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </Button>
                    </CollapsibleTrigger>

                    <StatusIcon className={cn("w-4 h-4 flex-shrink-0", statusColor)} />
                    <span className="font-medium text-sm truncate">{item.mode_name}</span>
                    <span className="text-xs text-muted-foreground font-normal hidden sm:inline-block">({item.mode_id})</span>

                    <div className="ml-auto flex gap-2 overflow-hidden">
                        {item.kinds.map(k => <Badge key={k} variant="secondary" className="text-[10px] h-5 px-1">{k}</Badge>)}
                    </div>
                </div>

                <CollapsibleContent>
                    <div className="pl-10 pr-4 pb-3 space-y-2 text-sm text-muted-foreground">
                        {item.filename_hints.length > 0 && (
                            <div className="flex gap-2 items-start">
                                <FileText className="w-3 h-3 mt-1 flex-shrink-0" />
                                <span className="break-all">文件名提示: {item.filename_hints.join(", ")}</span>
                            </div>
                        )}

                        {item.errors.length > 0 && (
                            <div className="space-y-1">
                                <p className="text-red-500 font-medium text-xs">错误:</p>
                                <ul className="list-disc pl-4 text-red-500/80 text-xs">
                                    {item.errors.map((e, i) => <li key={i}>{e}</li>)}
                                </ul>
                            </div>
                        )}
                        {item.warnings.length > 0 && (
                            <div className="space-y-1">
                                <p className="text-amber-500 font-medium text-xs">警告:</p>
                                <ul className="list-disc pl-4 text-amber-500/80 text-xs">
                                    {item.warnings.map((e, i) => <li key={i}>{e}</li>)}
                                </ul>
                            </div>
                        )}
                        {item.sample_checks.length > 0 && (
                            <div className="border rounded p-2 bg-muted/30">
                                <p className="font-medium mb-1 text-xs">冒烟测试 ({item.sample_checks.filter(c => c.ok).length}/{item.sample_checks.length})</p>
                                <div className="grid grid-cols-1 gap-1">
                                    {item.sample_checks.map(sc => (
                                        <div key={sc.index} className="flex items-center gap-2 text-xs">
                                            {sc.ok ? <CheckCircle2 className="w-3 h-3 text-green-500" /> : <XCircle className="w-3 h-3 text-red-500" />}
                                            <span>Case {sc.index}: 期望 {sc.expected_kind}，实际 {sc.detected_kind || "None"}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </CollapsibleContent>
            </Collapsible>
        );
    };

    if (error) {
        return (
            <div className="p-4 rounded-md border border-destructive/50 bg-destructive/10 text-destructive text-sm flex flex-col gap-2">
                <div className="flex items-center gap-2 font-medium">
                    <AlertCircle className="h-4 w-4" />
                    加载能力配置失败
                </div>
                <div className="pl-6 flex items-center gap-2">
                    <span className="flex-1">{error}</span>
                    <Button variant="outline" size="sm" onClick={() => refresh()} className="h-7 text-xs border-destructive/30 hover:bg-destructive/20">重试</Button>
                </div>
            </div>
        );
    }

    return (
        <Card className="flex flex-col min-h-0 bg-background/50 shadow-sm">
            <CardHeader className="py-3 flex flex-row items-center justify-between space-y-0">
                <div>
                    <CardTitle className="text-base">能力支持 & 健康状态</CardTitle>
                    {lastUpdated > 0 ? (
                        <CardDescription className="text-xs mt-1">
                            已更新: {new Date(lastUpdated).toLocaleTimeString()}
                        </CardDescription>
                    ) : (
                        loading && <Skeleton className="h-4 w-24 mt-1" />
                    )}
                </div>
                <Button variant="ghost" size="icon" onClick={() => refresh()} disabled={loading} className="h-8 w-8">
                    <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
                </Button>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-hidden flex flex-col gap-4 py-0 pb-4">
                {/* 1. 数据源支持矩阵 */}
                <div className="flex-1 min-h-0 flex flex-col">
                    <h3 className="text-sm font-medium mb-2 flex items-center justify-between">
                        数据源支持
                        {hasRun && coverage ? (
                            <span className="text-xs font-normal text-muted-foreground">
                                已满足 {coverage.matchedSources} / {coverage.totalSources}
                            </span>
                        ) : loading && !sourceMatrix.length ? (
                            <Skeleton className="h-4 w-20" />
                        ) : null}
                    </h3>
                    <div className="border rounded-md overflow-hidden flex-1 relative bg-card">
                        <ScrollArea className="h-[200px] w-full">
                            <Table>
                                <TableHeader className="sticky top-0 bg-secondary/90 backdrop-blur z-10">
                                    <TableRow>
                                        <TableHead className="w-[120px]">数据源</TableHead>
                                        <TableHead className="w-[80px]">类型</TableHead>
                                        <TableHead className="min-w-[150px]">文件名提示</TableHead>
                                        <TableHead className="w-[80px]">阶段</TableHead>
                                        <TableHead className="w-[80px]">解析器</TableHead>
                                        <TableHead className="w-[80px]">等级</TableHead>
                                        {hasRun && <TableHead className="w-[80px]">状态</TableHead>}
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loading && !sourceMatrix.length ? (
                                        // Loading Skeleton Rows
                                        Array.from({ length: 3 }).map((_, i) => (
                                            <TableRow key={i}>
                                                <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                                                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                                                <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                                                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                                                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                                                <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                                                {hasRun && <TableCell><Skeleton className="h-4 w-12" /></TableCell>}
                                            </TableRow>
                                        ))
                                    ) : (
                                        <>
                                            {coverage?.matrix.map(renderSourceRow)}
                                            {!coverage && sourceMatrix.map(s => renderSourceRow({ source: s, matched: false, matchedFiles: [] }))}
                                            {sourceMatrix.length === 0 && !loading && (
                                                <TableRow>
                                                    <TableCell colSpan={hasRun ? 7 : 6} className="text-center h-20 text-muted-foreground">
                                                        暂无数据源配置
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </>
                                    )}
                                </TableBody>
                            </Table>
                        </ScrollArea>
                    </div>
                </div>

                {/* 2. Parser 健康状态 */}
                <div className="flex-shrink-0">
                    <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                        PDF 解析器健康
                        {parserHealth ? (
                            <div className="flex gap-1 ml-auto">
                                {parserHealth.summary.error > 0 && <Badge variant="destructive" className="h-5 px-1 text-[10px]">{parserHealth.summary.error} 错误</Badge>}
                                {parserHealth.summary.warning > 0 && <Badge variant="secondary" className="h-5 px-1 bg-amber-100 text-amber-800 hover:bg-amber-200 text-[10px]">{parserHealth.summary.warning} 警告</Badge>}
                                <Badge variant="outline" className="h-5 px-1 text-green-600 border-green-200 bg-green-50 text-[10px]">{parserHealth.summary.ok} 正常</Badge>
                            </div>
                        ) : loading && !parserHealth ? (
                            <div className="flex gap-2 ml-auto">
                                <Skeleton className="h-5 w-12 rounded-full" />
                                <Skeleton className="h-5 w-12 rounded-full" />
                            </div>
                        ) : null}
                    </h3>
                    <div className="border rounded-md bg-card">
                        <ScrollArea className="h-[150px]">
                            <div className="w-full">
                                {loading && !parserHealth ? (
                                    <div className="p-2 space-y-2">
                                        <Skeleton className="h-8 w-full" />
                                        <Skeleton className="h-8 w-full" />
                                        <Skeleton className="h-8 w-full" />
                                    </div>
                                ) : (
                                    <>
                                        {parserHealth?.parsers.map(p => <ParserItem key={p.mode_id} item={p} />)}
                                        {parserHealth?.parsers.length === 0 && !loading && (
                                            <div className="text-center py-8 text-muted-foreground text-sm">暂无解析器信息</div>
                                        )}
                                    </>
                                )}
                            </div>
                        </ScrollArea>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
