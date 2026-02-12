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

function fmtRate(value: number | null): string {
    if (value === null || !Number.isFinite(value)) return "N/A";
    const pct = value * 100;
    const prefix = pct > 0 ? "+" : "";
    return `${prefix}${pct.toFixed(1)}%`;
}

export function ReviewTrendChart({ points }: ReviewTrendChartProps) {
    const data = points.slice();
    const width = 720;
    const height = 280;
    const left = 42;
    const right = 18;
    const top = 16;
    const bottom = 44;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const maxVal = Math.max(1, ...data.map((item) => Math.max(item.expense, item.income)));
    const baseY = top + chartH;
    const step = data.length > 1 ? chartW / (data.length - 1) : chartW / 2;
    const barW = Math.max(8, Math.min(30, step * 0.46));

    const xAt = (idx: number) => left + (data.length > 1 ? step * idx : chartW / 2);
    const yAt = (value: number) => top + (1 - value / maxVal) * chartH;

    const incomePath = data
        .map((item, idx) => `${idx === 0 ? "M" : "L"} ${xAt(idx).toFixed(2)} ${yAt(item.income).toFixed(2)}`)
        .join(" ");

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3">
                <CardTitle className="text-sm">月度趋势（含环比/同比）</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {!data.length ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        暂无月度账期数据
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <svg className="min-w-[680px] w-full" viewBox={`0 0 ${width} ${height}`} aria-label="月度趋势图">
                                {[0.25, 0.5, 0.75, 1].map((ratio) => {
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
                                            <text x={4} y={y + 4} className="fill-muted-foreground text-[10px]">
                                                {Math.round(maxVal * ratio)}
                                            </text>
                                        </g>
                                    );
                                })}
                                {data.map((item, idx) => {
                                    const x = xAt(idx);
                                    const y = yAt(item.expense);
                                    const h = baseY - y;
                                    return (
                                        <g key={`${item.period_key}-${idx}`}>
                                            <rect
                                                x={x - barW / 2}
                                                y={y}
                                                width={barW}
                                                height={Math.max(1, h)}
                                                rx="3"
                                                fill="#1d4ed8"
                                                opacity="0.85"
                                            />
                                            <text x={x} y={baseY + 15} textAnchor="middle" className="fill-muted-foreground text-[10px]">
                                                {item.period_key}
                                            </text>
                                        </g>
                                    );
                                })}
                                <path d={incomePath} fill="none" stroke="#059669" strokeWidth="2" />
                                {data.map((item, idx) => (
                                    <circle
                                        key={`${item.period_key}-income`}
                                        cx={xAt(idx)}
                                        cy={yAt(item.income)}
                                        r="2.8"
                                        fill="#059669"
                                    />
                                ))}
                            </svg>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {data.map((item) => (
                                <div key={`rate-${item.period_key}`} className="rounded-md border border-border/70 p-2 text-[11px]">
                                    <div className="font-mono text-muted-foreground">{item.period_key}</div>
                                    <div className="mt-1">支出：{fmtMoney(item.expense)} / 收入：{fmtMoney(item.income)}</div>
                                    <div className="mt-1 text-muted-foreground">
                                        环比：{fmtRate(item.mom_expense_rate)} / 同比：{fmtRate(item.yoy_expense_rate)}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                            <div className="inline-flex items-center gap-1.5">
                                <span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-700" />
                                <span>支出（柱）</span>
                            </div>
                            <div className="inline-flex items-center gap-1.5">
                                <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-600" />
                                <span>收入（线）</span>
                            </div>
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
