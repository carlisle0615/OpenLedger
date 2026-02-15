import type { ReactNode } from "react";
import type { ReviewMonthlyPoint } from "@/types";
import type {
    TrendLineDataSource,
    TrendTooltipData,
    TrendTooltipDetail,
    TrendTooltipItem,
} from "@/components/profile-review/TrendLineCard";

const cnyFmt = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
});

function fmtMoney(value: number): string {
    return cnyFmt.format(Number.isFinite(value) ? value : 0);
}

const incomeSeries = [
    { key: "salary_income", label: "工资", color: "#2563eb" },
    { key: "subsidy_income", label: "补贴", color: "#0891b2" },
    { key: "transfer_income", label: "转账", color: "#0f766e" },
    { key: "other_income", label: "其他", color: "#f59e0b" },
] as const;

type IncomeSeriesKey = (typeof incomeSeries)[number]["key"];
type IncomeBucket = "salary" | "subsidy" | "transfer" | "other";

const incomeBucketBySeries: Record<IncomeSeriesKey, IncomeBucket> = {
    salary_income: "salary",
    subsidy_income: "subsidy",
    transfer_income: "transfer",
    other_income: "other",
};

const YEAR_COLORS = [
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#9333ea",
    "#db2777",
    "#0891b2",
];

function sortMonthlyPoints(points: ReviewMonthlyPoint[]): ReviewMonthlyPoint[] {
    return [...points].sort((a, b) => {
        if (a.year !== b.year) return a.year - b.year;
        return a.month - b.month;
    });
}

type ExpenseYoySourceParams = {
    points: ReviewMonthlyPoint[];
    activeCategory: string;
    activeCategoryLabel: string;
    headerExtra?: ReactNode;
};

function pointExpenseByCategory(point: ReviewMonthlyPoint, categoryId: string): number {
    if (categoryId === "__all__") {
        return Number(point.expense) || 0;
    }
    const hit = point.category_expense_breakdown.find((item) => item.category_id === categoryId);
    return Number(hit?.expense || 0);
}

export function createIncomeTrendDataSource(points: ReviewMonthlyPoint[]): TrendLineDataSource {
    const ordered = sortMonthlyPoints(points);
    return {
        title: "收入结构月度趋势",
        xLabels: ordered.map((item) => item.period_key),
        series: incomeSeries.map((line) => ({
            key: line.key,
            label: line.label,
            color: line.color,
            values: ordered.map((item) => Number(item[line.key] || 0)),
        })),
        emptyText: "暂无收入趋势数据",
        ariaLabel: "收入趋势图",
        valueFormatter: fmtMoney,
        tooltipWidth: 320,
        tooltipHeight: 220,
        getTooltipData: (hover) => {
            const point = ordered[hover.pointIndex];
            if (!point) return null;
            const items: TrendTooltipItem[] = incomeSeries.map((line) => ({
                key: line.key,
                label: line.label,
                value: Number(point[line.key] || 0),
                color: line.color,
            }));
            const bucket = incomeBucketBySeries[hover.seriesKey as IncomeSeriesKey];
            const details: TrendTooltipDetail[] = bucket
                ? (point.income_top_transactions?.[bucket] || []).slice(0, 10).map((row, idx) => ({
                    key: `${row.txn_id}-${row.run_id}-${idx}`,
                    label: row.trade_date || "-",
                    subLabel: row.merchant || "-",
                    value: Number(row.amount || 0),
                }))
                : [];
            const tooltip: TrendTooltipData = {
                title: `${hover.seriesLabel} ${point.period_key}`,
                subtitle: `当月收入：${fmtMoney(Number(point.income || 0))}`,
                items,
                detailsTitle: "Top 10 明细",
                details,
                emptyDetailsText: "暂无可展示明细",
            };
            return tooltip;
        },
    };
}

export function createExpenseYoyTrendDataSource({
    points,
    activeCategory,
    activeCategoryLabel,
    headerExtra,
}: ExpenseYoySourceParams): TrendLineDataSource {
    const grouped = new Map<number, ReviewMonthlyPoint[]>();
    points.forEach((point) => {
        if (!grouped.has(point.year)) {
            grouped.set(point.year, []);
        }
        grouped.get(point.year)?.push(point);
    });
    const years = Array.from(grouped.keys()).sort((a, b) => a - b);
    const series = years.map((year, idx) => {
        const monthMap = new Map<number, number>();
        (grouped.get(year) || []).forEach((point) => {
            monthMap.set(point.month, pointExpenseByCategory(point, activeCategory));
        });
        return {
            key: String(year),
            label: `${year}年`,
            color: YEAR_COLORS[idx % YEAR_COLORS.length],
            values: Array.from({ length: 12 }).map((_, monthIdx) => monthMap.get(monthIdx + 1) ?? 0),
        };
    });

    return {
        title: "月度支出趋势（同比）",
        xLabels: Array.from({ length: 12 }).map((_, idx) => `${idx + 1}月`),
        series,
        emptyText: "暂无月度账期数据",
        ariaLabel: "月度趋势图",
        minChartWidth: 720,
        valueFormatter: fmtMoney,
        headerExtra,
        legendNote: `Legend: 颜色代表年份，当前分类为 ${activeCategoryLabel}`,
        tooltipWidth: 320,
        tooltipHeight: 180,
        getTooltipData: (hover) => {
            const items: TrendTooltipItem[] = series
                .map((line) => ({
                    key: line.key,
                    label: line.label,
                    value: Number(line.values[hover.pointIndex] || 0),
                    color: line.color,
                }))
                .sort((a, b) => b.value - a.value);
            const point = points.find(
                (row) => row.year === Number(hover.seriesKey) && row.month === hover.pointIndex + 1,
            );
            const byCategory = point?.expense_top_transactions || {};
            let rawDetails = byCategory[activeCategory] || [];
            if (activeCategory !== "__all__" && rawDetails.length === 0) {
                rawDetails = (byCategory["__all__"] || []).filter(
                    (row) => row.category_id === activeCategory,
                );
            }
            const details: TrendTooltipDetail[] = rawDetails.slice(0, 10).map((row, idx) => ({
                key: `${row.txn_id}-${row.run_id}-${idx}`,
                label: row.trade_date || "-",
                subLabel: row.merchant || row.category_name || "-",
                value: Number(row.amount || 0),
            }));
            return {
                title: `${hover.pointLabel} ${activeCategoryLabel}`,
                subtitle: "同比年度分布",
                items,
                detailsTitle: "Top 10 支出明细",
                details,
                emptyDetailsText: "暂无可展示明细",
            };
        },
        pointTitleFormatter: (point) =>
            `${point.seriesLabel}${point.pointLabel} ${activeCategoryLabel}: ${fmtMoney(point.value)}`,
    };
}
