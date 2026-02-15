import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ReviewMonthlyPoint } from "@/types";

interface IncomeTrendChartProps {
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

const series = [
    { key: "salary_income", label: "工资", color: "#2563eb" },
    { key: "subsidy_income", label: "补贴", color: "#0891b2" },
    { key: "other_income", label: "其他", color: "#f59e0b" },
] as const;

export function IncomeTrendChart({ points }: IncomeTrendChartProps) {
    const ordered = [...points].sort((a, b) => {
        if (a.year !== b.year) return a.year - b.year;
        return a.month - b.month;
    });
    const maxVal = Math.max(
        1,
        ...ordered.flatMap((item) => [
            item.salary_income,
            item.subsidy_income,
            item.other_income,
        ]),
    );

    const width = Math.max(680, ordered.length * 60);
    const height = 280;
    const left = 44;
    const right = 16;
    const top = 14;
    const bottom = 52;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const baseY = top + chartH;
    const step = ordered.length > 1 ? chartW / (ordered.length - 1) : 0;
    const xAt = (index: number) =>
        ordered.length > 1 ? left + step * index : left + chartW / 2;
    const yAt = (value: number) => top + (1 - value / maxVal) * chartH;
    const labelStep = ordered.length > 12 ? Math.ceil(ordered.length / 12) : 1;

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3">
                <CardTitle className="text-sm">收入结构月度趋势</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {!ordered.length ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        暂无收入趋势数据
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <svg className="w-full min-w-[680px]" viewBox={`0 0 ${width} ${height}`} aria-label="收入趋势图">
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
                                            {ratio > 0 ? (
                                                <text x={4} y={y + 4} className="fill-muted-foreground text-[10px]">
                                                    {fmtMoney(maxVal * ratio)}
                                                </text>
                                            ) : null}
                                        </g>
                                    );
                                })}

                                {ordered.map((item, idx) => {
                                    const show = idx === 0 || idx === ordered.length - 1 || idx % labelStep === 0;
                                    if (!show) return null;
                                    return (
                                        <text
                                            key={`${item.period_key}-${idx}`}
                                            x={xAt(idx)}
                                            y={baseY + 16}
                                            textAnchor="middle"
                                            className="fill-muted-foreground text-[10px]"
                                        >
                                            {item.period_key}
                                        </text>
                                    );
                                })}

                                {series.map((line) => {
                                    const d = ordered
                                        .map((item, idx) => {
                                            const x = xAt(idx).toFixed(2);
                                            const y = yAt(Number(item[line.key] || 0)).toFixed(2);
                                            return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
                                        })
                                        .join(" ");
                                    return (
                                        <path
                                            key={line.key}
                                            d={d}
                                            fill="none"
                                            stroke={line.color}
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                        />
                                    );
                                })}

                                {series.map((line) =>
                                    ordered.map((item, idx) => {
                                        const value = Number(item[line.key] || 0);
                                        return (
                                            <circle
                                                key={`${line.key}-${item.period_key}-${idx}`}
                                                cx={xAt(idx)}
                                                cy={yAt(value)}
                                                r="3"
                                                fill="#fff"
                                                stroke={line.color}
                                                strokeWidth="1.5"
                                            >
                                                <title>{`${line.label} ${item.period_key}: ${fmtMoney(value)}`}</title>
                                            </circle>
                                        );
                                    }),
                                )}
                            </svg>
                        </div>
                        <div className="flex flex-wrap items-center justify-center gap-4 text-[11px] text-muted-foreground">
                            {series.map((line) => (
                                <div key={line.key} className="inline-flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-1 rounded-full" style={{ backgroundColor: line.color }} />
                                    <span>{line.label}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
