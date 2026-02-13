import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ProfileReviewResponse } from "@/types";
import { api } from "@/utils/helpers";
import { ReviewAnomalyTable } from "@/components/profile-review/ReviewAnomalyTable";
import { ReviewDonutChart } from "@/components/profile-review/ReviewDonutChart";
import { ReviewKpiCards } from "@/components/profile-review/ReviewKpiCards";
import { ReviewTrendChart } from "@/components/profile-review/ReviewTrendChart";

interface ProfileReviewTabProps {
    baseUrl: string;
    selectedProfileId: string;
    selectedProfileName: string;
    active: boolean;
}

const cnyFmt = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
});

function fmtMoney(value: number): string {
    return cnyFmt.format(Number.isFinite(value) ? value : 0);
}

function issueLabel(issue: string): string {
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
}

export function ProfileReviewTab({
    baseUrl,
    selectedProfileId,
    selectedProfileName,
    active,
}: ProfileReviewTabProps) {
    const [timeRange, setTimeRange] = useState<string>("all_time");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [data, setData] = useState<ProfileReviewResponse | null>(null);

    const loadReview = useCallback(async () => {
        if (!baseUrl.trim() || !selectedProfileId || !active) return;
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams();

            // Parse timeRange
            if (timeRange.startsWith("year_")) {
                const y = timeRange.replace("year_", "");
                params.set("year", y);
                params.set("months", "12");
            } else if (timeRange === "all_time") {
                params.set("months", "120"); // Max supported by backend
            } else if (timeRange.startsWith("last_")) {
                const m = timeRange.replace("last_", "");
                params.set("months", m);
            } else {
                // Fallback
                params.set("months", "12");
            }

            const query = params.toString();
            const path = `/api/profiles/${encodeURIComponent(selectedProfileId)}/review${query ? `?${query}` : ""}`;
            const payload = await api<ProfileReviewResponse>(baseUrl, path);
            setData(payload);
        } catch (e) {
            setError(String(e));
        } finally {
            setLoading(false);
        }
    }, [baseUrl, selectedProfileId, active, timeRange]);

    useEffect(() => {
        if (!selectedProfileId) {
            setData(null);
            setError("");
            return;
        }
        if (!active) return;
        loadReview().catch(() => { });
    }, [selectedProfileId, active, loadReview]);

    const availableYears = useMemo(() => {
        const set = new Set<string>();
        (data?.yearly_points ?? []).forEach((item) => set.add(String(item.year)));
        return Array.from(set).sort((a, b) => Number(b) - Number(a));
    }, [data?.yearly_points]);

    const yearlyPoints = data?.yearly_points ?? [];
    const yearlyChart = useMemo(() => {
        if (!yearlyPoints.length) return null;
        const width = 680;
        const height = 260;
        const left = 40;
        const right = 20;
        const top = 16;
        const bottom = 38;
        const chartW = width - left - right;
        const chartH = height - top - bottom;
        const maxValue = Math.max(
            1,
            ...yearlyPoints.map((item) => Math.max(item.expense, item.income)),
        );
        const groupW = chartW / yearlyPoints.length;
        const barW = Math.max(10, Math.min(18, groupW * 0.25));
        const baseY = top + chartH;
        const yAt = (value: number) => top + (1 - value / maxValue) * chartH;

        return (
            <div className="overflow-x-auto">
                <svg className="min-w-[620px] w-full" viewBox={`0 0 ${width} ${height}`} aria-label="年度汇总图">
                    {[0.25, 0.5, 0.75, 1].map((ratio) => {
                        const y = top + chartH * (1 - ratio);
                        return (
                            <line
                                key={ratio}
                                x1={left}
                                y1={y}
                                x2={left + chartW}
                                y2={y}
                                stroke="#e2e8f0"
                                strokeWidth="1"
                                strokeDasharray="3 4"
                            />
                        );
                    })}
                    {yearlyPoints.map((item, idx) => {
                        const center = left + groupW * idx + groupW / 2;
                        const expenseY = yAt(item.expense);
                        const incomeY = yAt(item.income);
                        return (
                            <g key={item.year}>
                                <rect
                                    x={center - barW - 2}
                                    y={expenseY}
                                    width={barW}
                                    height={Math.max(1, baseY - expenseY)}
                                    rx="2"
                                    fill="#1d4ed8"
                                />
                                <rect
                                    x={center + 2}
                                    y={incomeY}
                                    width={barW}
                                    height={Math.max(1, baseY - incomeY)}
                                    rx="2"
                                    fill="#059669"
                                />
                                <text x={center} y={baseY + 14} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                                    {item.year}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            </div>
        );
    }, [yearlyPoints]);

    if (!selectedProfileId) {
        return (
            <Card>
                <CardContent className="py-10 text-center text-sm text-muted-foreground">
                    请先在顶部选择用户，再查看账期审阅。
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-4">
            <Card className="border border-border/80 shadow-sm">
                <CardHeader className="py-3">
                    <CardTitle className="text-sm">账期审阅范围</CardTitle>
                </CardHeader>
                <CardContent className="pt-0 space-y-3">
                    <div className="text-xs text-muted-foreground">
                        当前用户：<span className="font-medium text-foreground">{selectedProfileName || selectedProfileId}</span>
                        <span className="font-mono ml-2">{selectedProfileId}</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-[240px_auto] gap-2 items-center">
                        <Select
                            value={timeRange}
                            onValueChange={(val) => {
                                setTimeRange(val);
                            }}
                        >
                            <SelectTrigger className="h-8 text-xs">
                                <SelectValue placeholder="时间范围" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="last_12" className="text-xs">最近 12 个月</SelectItem>
                                <SelectItem value="last_24" className="text-xs">最近 24 个月</SelectItem>
                                <SelectItem value="last_36" className="text-xs">最近 36 个月</SelectItem>
                                <SelectItem value="all_time" className="text-xs">全部年份（最多 10 年）</SelectItem>
                                {availableYears.length > 0 && <div className="h-px bg-border my-1" />}
                                {availableYears.map((year) => (
                                    <SelectItem key={year} value={`year_${year}`} className="text-xs font-mono">
                                        {year} 年
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <div className="flex md:justify-end">
                            <Button
                                size="sm"
                                variant="outline"
                                className="h-8 text-xs"
                                disabled={loading}
                                onClick={() => void loadReview()}
                            >
                                <RefreshCw className="h-3.5 w-3.5 mr-1" />
                                刷新
                            </Button>
                        </div>
                    </div>
                    {error ? <div className="text-xs text-destructive">{error}</div> : null}
                </CardContent>
            </Card>

            {loading && !data ? (
                <Card>
                    <CardContent className="py-10 text-center text-sm text-muted-foreground">加载中…</CardContent>
                </Card>
            ) : null}

            {data ? (
                <>
                    <ReviewKpiCards overview={data.overview} />

                    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                        <div className="xl:col-span-5">
                            <ReviewDonutChart slices={data.category_slices} totalExpense={data.overview.total_expense} />
                        </div>
                        <div className="xl:col-span-7">
                            <ReviewTrendChart points={data.monthly_points} />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                        <Card className="xl:col-span-5 border border-border/80 shadow-sm">
                            <CardHeader className="py-3">
                                <CardTitle className="text-sm">年度汇总</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {yearlyChart ?? (
                                    <div className="h-[240px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                                        暂无年度汇总数据
                                    </div>
                                )}
                                {yearlyPoints.length ? (
                                    <div className="space-y-1">
                                        {yearlyPoints.map((item) => (
                                            <div
                                                key={`year-row-${item.year}`}
                                                className="flex items-center justify-between text-[11px] border-b border-border/50 pb-1"
                                            >
                                                <span className="font-mono">{item.year}</span>
                                                <span className="text-muted-foreground">
                                                    支出 {fmtMoney(item.expense)} / 收入 {fmtMoney(item.income)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                            </CardContent>
                        </Card>
                        <div className="xl:col-span-7">
                            <ReviewAnomalyTable anomalies={data.anomalies} />
                        </div>
                    </div>

                    <Card className="border border-border/80 shadow-sm">
                        <CardHeader className="py-3">
                            <CardTitle className="text-sm">一致性问题</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {data.integrity_issues.length ? (
                                <div className="space-y-2">
                                    {data.integrity_issues.map((issue, idx) => (
                                        <div
                                            key={`${issue.run_id}-${issue.issue}-${idx}`}
                                            className="text-xs border rounded-md px-2 py-1.5 bg-muted/20"
                                        >
                                            <div className="font-medium">{issueLabel(issue.issue)}</div>
                                            <div className="text-muted-foreground mt-0.5">
                                                账期：<span className="font-mono">{issue.period_key || "-"}</span>
                                                <span className="mx-2">|</span>
                                                run：<span className="font-mono" title={issue.run_id}>{issue.run_id || "-"}</span>
                                            </div>
                                            {issue.path ? (
                                                <div className="text-[11px] text-muted-foreground break-all mt-0.5">
                                                    path: {issue.path}
                                                </div>
                                            ) : null}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-xs text-muted-foreground">未发现一致性问题。</div>
                            )}
                        </CardContent>
                    </Card>
                </>
            ) : null}
        </div>
    );
}
