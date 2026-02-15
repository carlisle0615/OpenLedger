import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ReviewOverview } from "@/types";

interface ReviewKpiCardsProps {
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

export function ReviewKpiCards({ overview }: ReviewKpiCardsProps) {
    const items = [
        { key: "expense", label: "总支出", value: fmtMoney(overview.total_expense), tone: "text-foreground" },
        { key: "income", label: "总收入", value: fmtMoney(overview.total_income), tone: "text-foreground" },
        {
            key: "net",
            label: "净额",
            value: fmtMoney(overview.net),
            tone: overview.net < 0 ? "text-destructive" : "text-foreground",
        },
        {
            key: "anomaly",
            label: "异常数",
            value: String(overview.anomaly_count),
            sub: `账期 ${overview.period_count} 个`,
            tone: overview.anomaly_count > 0 ? "text-destructive" : "text-foreground",
        },
    ];
    const totalIncome = Number.isFinite(overview.total_income) ? Math.max(0, overview.total_income) : 0;
    const incomeItems = [
        { key: "salary", label: "工资收入", value: overview.salary_income },
        { key: "subsidy", label: "补贴收入", value: overview.subsidy_income },
        { key: "transfer", label: "转账收入", value: overview.transfer_income },
        { key: "other", label: "其他收入", value: overview.other_income },
    ];

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                {items.map((item) => (
                    <Card key={item.key} className="border border-border/80 shadow-sm">
                        <CardHeader className="py-3">
                            <CardTitle className="text-xs text-muted-foreground font-medium">{item.label}</CardTitle>
                        </CardHeader>
                        <CardContent className="pt-0 pb-3">
                            <div className={`text-xl font-semibold tracking-tight ${item.tone}`}>{item.value}</div>
                            {item.sub ? <div className="text-[11px] text-muted-foreground mt-1">{item.sub}</div> : null}
                        </CardContent>
                    </Card>
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                {incomeItems.map((item) => {
                    const rawValue = Number.isFinite(item.value) ? Math.max(0, item.value) : 0;
                    const ratio = totalIncome > 0 ? rawValue / totalIncome : 0;
                    return (
                        <Card key={item.key} className="border border-border/80 shadow-sm">
                            <CardHeader className="py-3">
                                <CardTitle className="text-xs text-muted-foreground font-medium">{item.label}</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-0 pb-3">
                                <div className="text-lg font-semibold tracking-tight">{fmtMoney(rawValue)}</div>
                                <div className="text-[11px] text-muted-foreground mt-1">
                                    占总收入 {fmtPercent(ratio)}
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        </div>
    );
}
