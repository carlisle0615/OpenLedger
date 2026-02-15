import { useMemo, useState } from "react";
import { TrendLineCard } from "@/components/profile-review/TrendLineCard";
import { createExpenseYoyTrendDataSource } from "@/components/profile-review/TrendDataSources";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ReviewMonthlyPoint } from "@/types";

interface ReviewTrendChartProps {
    points: ReviewMonthlyPoint[];
}

const ALL_CATEGORY = "__all__";

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

    const headerExtra = (
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
    );

    const dataSource = useMemo(
        () =>
            createExpenseYoyTrendDataSource({
                points,
                activeCategory,
                activeCategoryLabel,
                headerExtra,
            }),
        [activeCategory, activeCategoryLabel, headerExtra, points],
    );

    return <TrendLineCard dataSource={dataSource} />;
}
