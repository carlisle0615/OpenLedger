import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ReviewCategorySlice } from "@/types";

interface ReviewDonutChartProps {
    slices: ReviewCategorySlice[];
    totalExpense: number;
}

const palette = [
    "#0f172a",
    "#1d4ed8",
    "#0ea5e9",
    "#0f766e",
    "#65a30d",
    "#ca8a04",
    "#dc2626",
    "#9333ea",
    "#64748b",
];

const cnyFmt = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function fmtMoney(value: number): string {
    return cnyFmt.format(Number.isFinite(value) ? value : 0);
}

export function ReviewDonutChart({ slices, totalExpense }: ReviewDonutChartProps) {
    const data = slices.filter((item) => item.expense > 0);
    const radius = 54;
    const circumference = 2 * Math.PI * radius;
    let strokeOffset = 0;

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3">
                <CardTitle className="text-sm">分类支出分布</CardTitle>
            </CardHeader>
            <CardContent>
                {!data.length ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        暂无可展示的分类支出数据
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-4 items-center">
                        <div className="mx-auto">
                            <svg width="160" height="160" viewBox="0 0 160 160" role="img" aria-label="分类支出环图">
                                <circle cx="80" cy="80" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="18" />
                                {data.map((slice, idx) => {
                                    const share = Math.max(0, Math.min(1, slice.share_expense));
                                    const seg = circumference * share;
                                    const node = (
                                        <circle
                                            key={`${slice.category_id}-${idx}`}
                                            cx="80"
                                            cy="80"
                                            r={radius}
                                            fill="none"
                                            stroke={palette[idx % palette.length]}
                                            strokeWidth="18"
                                            strokeLinecap="butt"
                                            strokeDasharray={`${seg} ${circumference - seg}`}
                                            strokeDashoffset={-strokeOffset}
                                            transform="rotate(-90 80 80)"
                                        />
                                    );
                                    strokeOffset += seg;
                                    return node;
                                })}
                                <text x="80" y="76" textAnchor="middle" className="fill-muted-foreground text-[10px]">
                                    总支出
                                </text>
                                <text x="80" y="95" textAnchor="middle" className="fill-foreground text-[11px] font-semibold">
                                    {fmtMoney(totalExpense)}
                                </text>
                            </svg>
                        </div>
                        <div className="space-y-2">
                            {data.map((slice, idx) => (
                                <div
                                    key={`${slice.category_id}-${idx}`}
                                    className="flex items-center justify-between gap-3 border-b border-border/40 pb-1.5"
                                >
                                    <div className="min-w-0 flex items-center gap-2">
                                        <span
                                            className="h-2.5 w-2.5 rounded-full shrink-0"
                                            style={{ backgroundColor: palette[idx % palette.length] }}
                                        />
                                        <span className="text-xs truncate" title={slice.category_name}>
                                            {slice.category_name}
                                        </span>
                                    </div>
                                    <div className="text-[11px] text-muted-foreground whitespace-nowrap">
                                        {fmtMoney(slice.expense)} / {(slice.share_expense * 100).toFixed(1)}%
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
