import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ReviewMonthlyPoint } from "@/types";

interface ReviewTrendChartProps {
    points: ReviewMonthlyPoint[];
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

// 定义年份颜色映射
const YEAR_COLORS = [
    "#2563eb", // blue-600
    "#16a34a", // green-600
    "#d97706", // amber-600
    "#9333ea", // purple-600
    "#db2777", // pink-600
    "#0891b2", // cyan-600
];

const ALL_CATEGORY = "__all__";

function pointExpenseByCategory(point: ReviewMonthlyPoint, categoryId: string): number {
    if (categoryId === ALL_CATEGORY) {
        return Number(point.expense) || 0;
    }
    const hit = point.category_expense_breakdown.find((item) => item.category_id === categoryId);
    return Number(hit?.expense || 0);
}

export function ReviewTrendChart({ points }: ReviewTrendChartProps) {
    const [categoryFilter, setCategoryFilter] = useState<string>(ALL_CATEGORY);

    const categoryOptions = useMemo(() => {
        const rows = new Map<string, { id: string; name: string; total: number }>();
        points.forEach((point) => {
            point.category_expense_breakdown.forEach((item) => {
                const existing = rows.get(item.category_id);
                if (existing) {
                    existing.total += Number(item.expense) || 0;
                    if (!existing.name && item.category_name) {
                        existing.name = item.category_name;
                    }
                } else {
                    rows.set(item.category_id, {
                        id: item.category_id,
                        name: item.category_name || item.category_id,
                        total: Number(item.expense) || 0,
                    });
                }
            });
        });
        return Array.from(rows.values()).sort((a, b) => b.total - a.total);
    }, [points]);

    const activeCategory = useMemo(() => {
        if (categoryFilter === ALL_CATEGORY) return ALL_CATEGORY;
        return categoryOptions.some((item) => item.id === categoryFilter) ? categoryFilter : ALL_CATEGORY;
    }, [categoryFilter, categoryOptions]);

    const activeCategoryLabel = useMemo(() => {
        if (activeCategory === ALL_CATEGORY) return "全部分类";
        const hit = categoryOptions.find((item) => item.id === activeCategory);
        return hit?.name || activeCategory;
    }, [activeCategory, categoryOptions]);

    const pointsByYear = useMemo(() => {
        const grouped = new Map<number, ReviewMonthlyPoint[]>();
        points.forEach((point) => {
            if (!grouped.has(point.year)) {
                grouped.set(point.year, []);
            }
            grouped.get(point.year)?.push(point);
        });
        return grouped;
    }, [points]);

    const years = Array.from(pointsByYear.keys()).sort((a, b) => a - b);

    let maxVal = 0;
    years.forEach((year) => {
        const yearPoints = pointsByYear.get(year) || [];
        yearPoints.forEach((point) => {
            maxVal = Math.max(maxVal, pointExpenseByCategory(point, activeCategory));
        });
    });
    maxVal = Math.max(1, maxVal);

    const width = 720;
    const height = 280;
    const left = 42;
    const right = 18;
    const top = 16;
    const bottom = 44;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const baseY = top + chartH;

    const step = chartW / 11;
    const xAt = (monthIdx: number) => left + step * monthIdx;
    const yAt = (value: number) => top + (1 - value / maxVal) * chartH;

    const paths = years.map((year, i) => {
        const yearPoints = [...(pointsByYear.get(year) || [])].sort((a, b) => a.month - b.month);
        const color = YEAR_COLORS[i % YEAR_COLORS.length];

        const pathCommands: string[] = [];
        let hasStarted = false;
        const monthMap = new Map<number, number>();
        yearPoints.forEach((point) =>
            monthMap.set(point.month, pointExpenseByCategory(point, activeCategory)),
        );

        for (let m = 1; m <= 12; m++) {
            const val = monthMap.get(m) ?? 0;
            const x = xAt(m - 1);
            const y = yAt(val);
            if (!hasStarted) {
                pathCommands.push(`M ${x.toFixed(2)} ${y.toFixed(2)}`);
                hasStarted = true;
            } else {
                pathCommands.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
            }
        }
        return {
            year,
            d: pathCommands.join(" "),
            color,
            monthMap,
        };
    });

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3 flex flex-row items-center justify-between gap-3">
                <CardTitle className="text-sm">月度支出趋势（同比）</CardTitle>
                <Select value={activeCategory} onValueChange={setCategoryFilter}>
                    <SelectTrigger className="h-8 text-xs w-[180px]">
                        <SelectValue placeholder="分类筛选" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value={ALL_CATEGORY} className="text-xs">
                            全部分类
                        </SelectItem>
                        {categoryOptions.map((item) => (
                            <SelectItem key={item.id} value={item.id} className="text-xs">
                                {item.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </CardHeader>
            <CardContent className="space-y-3">
                {!points.length ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        暂无月度账期数据
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <svg className="min-w-[680px] w-full" viewBox={`0 0 ${width} ${height}`} aria-label="月度趋势图">
                                {/* Grid Lines */}
                                {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                                    const y = top + chartH * (1 - ratio);
                                    return (
                                        <g key={ratio}>
                                            <line
                                                x1={left}
                                                y1={y}
                                                x2={left + chartW}
                                                y2={y}
                                                stroke="#e2e8f0"
                                                strokeWidth="1"
                                                strokeDasharray="3 4"
                                            />
                                            {ratio > 0 && (
                                                <text x={4} y={y + 4} className="fill-muted-foreground text-[10px]">
                                                    {fmtMoney(maxVal * ratio)}
                                                </text>
                                            )}
                                        </g>
                                    );
                                })}

                                {/* X-axis Labels (Months) */}
                                {Array.from({ length: 12 }).map((_, i) => (
                                    <text
                                        key={i}
                                        x={xAt(i)}
                                        y={baseY + 15}
                                        textAnchor="middle"
                                        className="fill-muted-foreground text-[10px]"
                                    >
                                        {i + 1}月
                                    </text>
                                ))}

                                {/* Lines */}
                                {paths.map((p) => (
                                    <path
                                        key={p.year}
                                        d={p.d}
                                        fill="none"
                                        stroke={p.color}
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    />
                                ))}

                                {/* Points */}
                                {paths.map((p) => {
                                    return Array.from({ length: 12 }).map((_, i) => {
                                        const m = i + 1;
                                        const val = p.monthMap.get(m) || 0;
                                        return (
                                            <circle
                                                key={`${p.year}-${m}`}
                                                cx={xAt(i)}
                                                cy={yAt(val)}
                                                r="3"
                                                fill="white"
                                                stroke={p.color}
                                                strokeWidth="1.5"
                                            >
                                                <title>{`${p.year}年${m}月 ${activeCategoryLabel}: ${fmtMoney(val)}`}</title>
                                            </circle>
                                        );
                                    })
                                })}
                            </svg>
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground justify-center mt-2">
                            {paths.map(p => (
                                <div key={p.year} className="inline-flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-1 rounded-full" style={{ backgroundColor: p.color }} />
                                    <span>{p.year}年</span>
                                </div>
                            ))}
                        </div>
                        <div className="text-[11px] text-muted-foreground text-center">
                            Legend: 颜色代表年份，当前分类为 {activeCategoryLabel}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
