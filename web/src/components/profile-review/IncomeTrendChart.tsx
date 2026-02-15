import { useMemo } from "react";
import { TrendLineCard } from "@/components/profile-review/TrendLineCard";
import { createIncomeTrendDataSource } from "@/components/profile-review/TrendDataSources";
import { ReviewMonthlyPoint } from "@/types";

interface IncomeTrendChartProps {
    points: ReviewMonthlyPoint[];
}

export function IncomeTrendChart({ points }: IncomeTrendChartProps) {
    const dataSource = useMemo(() => createIncomeTrendDataSource(points), [points]);

    return <TrendLineCard dataSource={dataSource} />;
}
