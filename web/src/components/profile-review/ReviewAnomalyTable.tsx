import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ReviewAnomaly, ReviewSeverity } from "@/types";

interface ReviewAnomalyTableProps {
    anomalies: ReviewAnomaly[];
}

function severityLabel(level: ReviewSeverity): string {
    if (level === "high") return "高";
    if (level === "medium") return "中";
    return "低";
}

function severityVariant(level: ReviewSeverity): "destructive" | "secondary" | "outline" {
    if (level === "high") return "destructive";
    if (level === "medium") return "secondary";
    return "outline";
}

function fmtMetric(value: number | null): string {
    if (value === null) return "-";
    return Number.isFinite(value) ? value.toFixed(2) : "-";
}

function fmtRate(value: number | null): string {
    if (value === null) return "-";
    if (!Number.isFinite(value)) return "-";
    const pct = value * 100;
    const sign = pct > 0 ? "+" : "";
    return `${sign}${pct.toFixed(1)}%`;
}

export function ReviewAnomalyTable({ anomalies }: ReviewAnomalyTableProps) {
    const [severityFilter, setSeverityFilter] = useState<"all" | ReviewSeverity>("all");
    const rows = useMemo(() => {
        if (severityFilter === "all") return anomalies;
        return anomalies.filter((item) => item.severity === severityFilter);
    }, [anomalies, severityFilter]);

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3 flex flex-row items-center justify-between">
                <CardTitle className="text-sm">异常数据</CardTitle>
                <Select value={severityFilter} onValueChange={(v) => setSeverityFilter(v as "all" | ReviewSeverity)}>
                    <SelectTrigger className="h-8 w-[128px] text-xs">
                        <SelectValue placeholder="严重度筛选" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all" className="text-xs">全部</SelectItem>
                        <SelectItem value="high" className="text-xs">高</SelectItem>
                        <SelectItem value="medium" className="text-xs">中</SelectItem>
                        <SelectItem value="low" className="text-xs">低</SelectItem>
                    </SelectContent>
                </Select>
            </CardHeader>
            <CardContent>
                {!rows.length ? (
                    <div className="h-[280px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        当前筛选下无异常
                    </div>
                ) : (
                    <ScrollArea className="h-[300px] border rounded-md">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="h-8 text-xs w-[70px]">级别</TableHead>
                                    <TableHead className="h-8 text-xs">异常</TableHead>
                                    <TableHead className="h-8 text-xs w-[86px]">账期</TableHead>
                                    <TableHead className="h-8 text-xs w-[180px]">run_id</TableHead>
                                    <TableHead className="h-8 text-xs w-[170px]">指标</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map((item, idx) => (
                                    <TableRow key={`${item.code}-${item.period_key}-${item.run_id}-${idx}`} className="h-8">
                                        <TableCell className="text-xs">
                                            <Badge variant={severityVariant(item.severity)} className="text-[10px] h-5">
                                                {severityLabel(item.severity)}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-xs">
                                            <div className="font-medium">{item.title}</div>
                                            <div className="text-[11px] text-muted-foreground">{item.message}</div>
                                        </TableCell>
                                        <TableCell className="text-xs font-mono">{item.period_key || "-"}</TableCell>
                                        <TableCell className="text-xs font-mono truncate max-w-[170px]" title={item.run_id}>
                                            {item.run_id || "-"}
                                        </TableCell>
                                        <TableCell className="text-[11px] text-muted-foreground">
                                            <div>当前：{fmtMetric(item.value)}</div>
                                            <div>基线：{fmtMetric(item.baseline)}</div>
                                            <div>变化：{fmtRate(item.delta_rate)}</div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </ScrollArea>
                )}
            </CardContent>
        </Card>
    );
}
