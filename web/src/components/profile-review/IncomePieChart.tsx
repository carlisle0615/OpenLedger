import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ReviewOverview } from "@/types";

interface IncomePieChartProps {
    overview: ReviewOverview;
}

const cnyFmt = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function fmtMoney(value: number): string {
    return cnyFmt.format(Number.isFinite(value) ? value : 0);
}

function fmtPercent(value: number): string {
    if (!Number.isFinite(value)) return "0.0%";
    return `${(value * 100).toFixed(1)}%`;
}

function polar(cx: number, cy: number, r: number, angle: number): { x: number; y: number } {
    return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
}

function piePath(cx: number, cy: number, r: number, start: number, end: number): string {
    const s = polar(cx, cy, r, start);
    const e = polar(cx, cy, r, end);
    const largeArc = end - start > Math.PI ? 1 : 0;
    return `M ${cx} ${cy} L ${s.x} ${s.y} A ${r} ${r} 0 ${largeArc} 1 ${e.x} ${e.y} Z`;
}

const colors = ["#2563eb", "#0891b2", "#0f766e", "#f59e0b"];

export function IncomePieChart({ overview }: IncomePieChartProps) {
    const rows = [
        { key: "salary", label: "工资", value: Math.max(0, Number(overview.salary_income || 0)), color: colors[0] },
        { key: "subsidy", label: "补贴", value: Math.max(0, Number(overview.subsidy_income || 0)), color: colors[1] },
        { key: "transfer", label: "转账", value: Math.max(0, Number(overview.transfer_income || 0)), color: colors[2] },
        { key: "other", label: "其他", value: Math.max(0, Number(overview.other_income || 0)), color: colors[3] },
    ];
    const data = rows.filter((item) => item.value > 0);
    const total = data.reduce((sum, item) => sum + item.value, 0);

    const cx = 78;
    const cy = 78;
    const r = 62;

    let start = -Math.PI / 2;

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3">
                <CardTitle className="text-sm">收入结构饼图</CardTitle>
            </CardHeader>
            <CardContent>
                {total <= 0 ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        暂无可展示的收入结构数据
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] items-center gap-4">
                        <div className="mx-auto">
                            <svg width="156" height="156" viewBox="0 0 156 156" role="img" aria-label="收入结构饼图">
                                {data.length === 1 ? (
                                    <circle cx={cx} cy={cy} r={r} fill={data[0].color} />
                                ) : (
                                    data.map((item) => {
                                        const angle = (item.value / total) * Math.PI * 2;
                                        const end = start + angle;
                                        const d = piePath(cx, cy, r, start, end);
                                        start = end;
                                        return <path key={item.key} d={d} fill={item.color} />;
                                    })
                                )}
                            </svg>
                        </div>
                        <div className="space-y-2">
                            {data.map((item) => {
                                const share = item.value / total;
                                return (
                                    <div key={item.key} className="flex items-center justify-between gap-3 border-b border-border/40 pb-1.5">
                                        <div className="min-w-0 flex items-center gap-2">
                                            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                                            <span className="text-xs">{item.label}</span>
                                        </div>
                                        <div className="text-[11px] text-muted-foreground whitespace-nowrap">
                                            {fmtMoney(item.value)} / {fmtPercent(share)}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
