import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export function ReviewTrendChart({ points }: ReviewTrendChartProps) {
    // 1. Group data by year
    const pointsByYear = new Map<number, ReviewMonthlyPoint[]>();
    points.forEach((p) => {
        if (!pointsByYear.has(p.year)) {
            pointsByYear.set(p.year, []);
        }
        pointsByYear.get(p.year)?.push(p);
    });

    const years = Array.from(pointsByYear.keys()).sort((a, b) => a - b);

    // Calculate global max value for scaling
    let maxVal = 0;
    years.forEach(year => {
        const yearPoints = pointsByYear.get(year) || [];
        yearPoints.forEach(p => {
            maxVal = Math.max(maxVal, p.expense); // Currently focusing on Expense trend
        });
    });
    maxVal = Math.max(1, maxVal);

    // Chart dimensions
    const width = 720;
    const height = 280;
    const left = 42;
    const right = 18;
    const top = 16;
    const bottom = 44;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const baseY = top + chartH;

    // X-axis: 12 months
    const step = chartW / 11; // 0 to 11 index for 12 months
    const xAt = (monthIdx: number) => left + step * monthIdx; // monthIdx 0-11
    const yAt = (value: number) => top + (1 - value / maxVal) * chartH;

    // Generate paths for each year
    const paths = years.map((year, i) => {
        const yearPoints = pointsByYear.get(year) || [];
        const color = YEAR_COLORS[i % YEAR_COLORS.length];

        // Fill missing months with null or 0 ? 
        // For line chart, we want 0 if we assume explicit 0 expense, 
        // but if data is missing, maybe we just skip? 
        // The previous step ensured we have data for known ranges, but this is a fresh view.
        // Let's assume we plot 1-12. If a month is missing in data, treat as 0 or ignore?
        // Since we did a "fill missing" previously, the `points` prop might already have gaps filled
        // BUT, that was for a linear timeline.
        // Here, let's just map 1-12.

        const pathCommands: string[] = [];
        let hasStarted = false;

        // Sort points by month just in case
        yearPoints.sort((a, b) => a.month - b.month);

        // We create a map for quick lookup
        const monthMap = new Map<number, number>();
        yearPoints.forEach(p => monthMap.set(p.month, p.expense));

        for (let m = 1; m <= 12; m++) {
            const val = monthMap.get(m);
            if (val !== undefined) {
                const x = xAt(m - 1);
                const y = yAt(val);
                if (!hasStarted) {
                    pathCommands.push(`M ${x.toFixed(2)} ${y.toFixed(2)}`);
                    hasStarted = true;
                } else {
                    pathCommands.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
                }
            } else {
                // If specific month is missing, we could break the line or assume 0.
                // Assuming 0 is safer for "Trends" so lines don't break.
                // However, strictly "no data" might be better represented by gaps if the future hasn't happened.
                // But for past data, 0 is likely implementation. 
                // Let's assume 0 for now to keep lines continuous.
                const x = xAt(m - 1);
                const y = yAt(0);
                if (!hasStarted) {
                    pathCommands.push(`M ${x.toFixed(2)} ${y.toFixed(2)}`);
                    hasStarted = true;
                } else {
                    pathCommands.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
                }
            }
        }

        return {
            year,
            d: pathCommands.join(" "),
            color,
            points: yearPoints
        };
    });

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3">
                <CardTitle className="text-sm">月度支出趋势（同比）</CardTitle>
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
                                    // Re-calculate points for circles
                                    const monthMap = new Map<number, number>();
                                    p.points.forEach(pt => monthMap.set(pt.month, pt.expense));

                                    return Array.from({ length: 12 }).map((_, i) => {
                                        const m = i + 1;
                                        const val = monthMap.get(m) || 0;
                                        // Only draw circle if data explicitly existed or handled
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
                                                <title>{`${p.year}年${m}月: ${fmtMoney(val)}`}</title>
                                            </circle>
                                        );
                                    })
                                })}
                            </svg>
                        </div>

                        {/* Legend */}
                        <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground justify-center mt-2">
                            {paths.map(p => (
                                <div key={p.year} className="inline-flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-1 rounded-full" style={{ backgroundColor: p.color }} />
                                    <span>{p.year}年</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
