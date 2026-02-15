import { useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type TrendLineSeries = {
    key: string;
    label: string;
    color: string;
    values: number[];
};

export type TrendLinePointContext = {
    seriesKey: string;
    seriesLabel: string;
    seriesColor: string;
    pointIndex: number;
    pointLabel: string;
    value: number;
};

export type TrendLineHoverContext = TrendLinePointContext & {
    x: number;
    y: number;
};

export type TrendTooltipItem = {
    key?: string;
    label: string;
    value: number;
    color?: string;
    subLabel?: string;
};

export type TrendTooltipDetail = {
    key: string;
    label: string;
    value: number;
    subLabel?: string;
};

export type TrendTooltipData = {
    title: string;
    subtitle?: string;
    items?: TrendTooltipItem[];
    detailsTitle?: string;
    details?: TrendTooltipDetail[];
    emptyDetailsText?: string;
};

export type TrendLineDataSource = {
    title: string;
    xLabels: string[];
    series: TrendLineSeries[];
    emptyText: string;
    valueFormatter: (value: number) => string;
    headerExtra?: ReactNode;
    legendNote?: string;
    ariaLabel?: string;
    minChartWidth?: number;
    pointSpacing?: number;
    maxXLabels?: number;
    yTickRatios?: number[];
    pointTitleFormatter?: (point: TrendLinePointContext) => string;
    getTooltipData?: (point: TrendLineHoverContext) => TrendTooltipData | null;
    tooltipWidth?: number;
    tooltipHeight?: number;
};

interface TrendLineCardProps {
    dataSource: TrendLineDataSource;
}

const DEFAULT_Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

type HoverState = TrendLineHoverContext;

export function TrendLineCard({ dataSource }: TrendLineCardProps) {
    const {
        title,
        xLabels,
        series,
        emptyText,
        valueFormatter,
        headerExtra,
        legendNote,
        ariaLabel = "趋势图",
        minChartWidth = 680,
        pointSpacing = 60,
        maxXLabels = 12,
        yTickRatios = DEFAULT_Y_TICKS,
        pointTitleFormatter,
        getTooltipData,
        tooltipWidth = 320,
        tooltipHeight = 220,
    } = dataSource;
    const chartRef = useRef<HTMLDivElement | null>(null);
    const [hover, setHover] = useState<HoverState | null>(null);
    const pointCount = xLabels.length;
    const hasData = pointCount > 0 && series.length > 0;

    const normalizedSeries = useMemo(
        () =>
            series.map((line) => ({
                ...line,
                values: Array.from({ length: pointCount }).map((_, idx) => Number(line.values[idx] || 0)),
            })),
        [pointCount, series],
    );

    const maxVal = useMemo(() => {
        let peak = 1;
        normalizedSeries.forEach((line) => {
            line.values.forEach((value) => {
                peak = Math.max(peak, Number(value) || 0);
            });
        });
        return Math.max(1, peak);
    }, [normalizedSeries]);

    const width = Math.max(minChartWidth, Math.max(1, pointCount) * pointSpacing);
    const height = 280;
    const left = 44;
    const right = 16;
    const top = 14;
    const bottom = 52;
    const chartW = width - left - right;
    const chartH = height - top - bottom;
    const baseY = top + chartH;
    const step = pointCount > 1 ? chartW / (pointCount - 1) : 0;
    const xAt = (index: number) => (pointCount > 1 ? left + step * index : left + chartW / 2);
    const yAt = (value: number) => top + (1 - value / maxVal) * chartH;
    const labelStep = pointCount > maxXLabels ? Math.ceil(pointCount / maxXLabels) : 1;

    const renderPointTitle = (line: TrendLineSeries, pointIndex: number, value: number): string => {
        const pointLabel = xLabels[pointIndex] || String(pointIndex + 1);
        if (pointTitleFormatter) {
            return pointTitleFormatter({
                seriesKey: line.key,
                seriesLabel: line.label,
                seriesColor: line.color,
                pointIndex,
                pointLabel,
                value,
            });
        }
        return `${line.label} ${pointLabel}: ${valueFormatter(value)}`;
    };

    const defaultTooltipData = (point: TrendLineHoverContext): TrendTooltipData => {
        const items = normalizedSeries
            .map((line) => ({
                key: line.key,
                label: line.label,
                value: Number(line.values[point.pointIndex] || 0),
                color: line.color,
            }))
            .sort((a, b) => b.value - a.value);
        return {
            title: point.pointLabel,
            subtitle: `当前序列：${point.seriesLabel}`,
            items,
        };
    };

    const tooltipData = useMemo(() => {
        if (!hover) return null;
        return getTooltipData?.(hover) || defaultTooltipData(hover);
    }, [getTooltipData, hover, normalizedSeries]);

    const onPointHover = (
        evt: ReactMouseEvent<SVGCircleElement>,
        line: TrendLineSeries,
        pointIndex: number,
        value: number,
    ) => {
        const rect = chartRef.current?.getBoundingClientRect();
        setHover({
            x: rect ? evt.clientX - rect.left : 0,
            y: rect ? evt.clientY - rect.top : 0,
            seriesKey: line.key,
            seriesLabel: line.label,
            seriesColor: line.color,
            pointIndex,
            pointLabel: xLabels[pointIndex] || String(pointIndex + 1),
            value,
        });
    };

    return (
        <Card className="h-full border border-border/80 shadow-sm">
            <CardHeader className="py-3 flex flex-row items-center justify-between gap-3">
                <CardTitle className="text-sm">{title}</CardTitle>
                {headerExtra}
            </CardHeader>
            <CardContent className="space-y-3">
                {!hasData ? (
                    <div className="h-[260px] rounded-md border border-dashed text-xs text-muted-foreground flex items-center justify-center">
                        {emptyText}
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <div
                                ref={chartRef}
                                className="relative"
                                style={{ minWidth: `${minChartWidth}px` }}
                                onMouseLeave={() => setHover(null)}
                            >
                                <svg className="w-full" viewBox={`0 0 ${width} ${height}`} aria-label={ariaLabel}>
                                    {yTickRatios.map((ratio) => {
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
                                                        {valueFormatter(maxVal * ratio)}
                                                    </text>
                                                ) : null}
                                            </g>
                                        );
                                    })}

                                    {xLabels.map((label, idx) => {
                                        const show = idx === 0 || idx === pointCount - 1 || idx % labelStep === 0;
                                        if (!show) return null;
                                        return (
                                            <text
                                                key={`${label}-${idx}`}
                                                x={xAt(idx)}
                                                y={baseY + 16}
                                                textAnchor="middle"
                                                className="fill-muted-foreground text-[10px]"
                                            >
                                                {label}
                                            </text>
                                        );
                                    })}

                                    {normalizedSeries.map((line) => {
                                        const d = line.values
                                            .map((value, idx) => {
                                                const x = xAt(idx).toFixed(2);
                                                const y = yAt(value).toFixed(2);
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

                                    {normalizedSeries.map((line) =>
                                        line.values.map((value, idx) => (
                                            <g key={`${line.key}-${idx}`}>
                                                <circle
                                                    cx={xAt(idx)}
                                                    cy={yAt(value)}
                                                    r="10"
                                                    fill="transparent"
                                                    style={{ cursor: "pointer" }}
                                                    onMouseEnter={(evt) => onPointHover(evt, line, idx, value)}
                                                    onMouseMove={(evt) => onPointHover(evt, line, idx, value)}
                                                />
                                                <circle
                                                    cx={xAt(idx)}
                                                    cy={yAt(value)}
                                                    r="3"
                                                    fill="#fff"
                                                    stroke={line.color}
                                                    strokeWidth="1.5"
                                                    pointerEvents="none"
                                                >
                                                    <title>{renderPointTitle(line, idx, value)}</title>
                                                </circle>
                                            </g>
                                        )),
                                    )}
                                </svg>
                                {hover && tooltipData ? (
                                    <div
                                        className="absolute z-20 rounded-md border bg-background/95 p-3 shadow-lg backdrop-blur-sm"
                                        style={{
                                            width: `${tooltipWidth}px`,
                                            left: Math.max(
                                                8,
                                                Math.min(
                                                    hover.x + 12,
                                                    (chartRef.current?.clientWidth || minChartWidth) - tooltipWidth - 8,
                                                ),
                                            ),
                                            top: Math.max(
                                                8,
                                                Math.min(
                                                    hover.y + 12,
                                                    (chartRef.current?.clientHeight || height) - tooltipHeight - 8,
                                                ),
                                            ),
                                        }}
                                    >
                                        <div className="text-xs font-medium">{tooltipData.title}</div>
                                        {tooltipData.subtitle ? (
                                            <div className="mt-1 text-[11px] text-muted-foreground">{tooltipData.subtitle}</div>
                                        ) : null}
                                        {tooltipData.items?.length ? (
                                            <div className="mt-2 space-y-1 text-[11px]">
                                                {tooltipData.items.map((item) => (
                                                    <div
                                                        key={item.key || `${item.label}-${item.value}`}
                                                        className="flex items-center justify-between gap-2"
                                                    >
                                                        <div className="min-w-0 inline-flex items-center gap-1.5">
                                                            {item.color ? (
                                                                <span
                                                                    className="inline-block h-1.5 w-1.5 rounded-full"
                                                                    style={{ backgroundColor: item.color }}
                                                                />
                                                            ) : null}
                                                            <span className="truncate">{item.label}</span>
                                                            {item.subLabel ? (
                                                                <span className="truncate text-muted-foreground">{item.subLabel}</span>
                                                            ) : null}
                                                        </div>
                                                        <span className="font-medium">{valueFormatter(item.value)}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : null}
                                        {tooltipData.detailsTitle ? (
                                            <div className="mt-2 text-[11px] text-muted-foreground">{tooltipData.detailsTitle}</div>
                                        ) : null}
                                        {tooltipData.detailsTitle ? (
                                            <div className="mt-2 max-h-40 space-y-1 overflow-auto text-[11px]">
                                                {tooltipData.details?.length ? (
                                                    tooltipData.details.map((row) => (
                                                        <div
                                                            key={row.key}
                                                            className="rounded border border-border/50 px-2 py-1"
                                                        >
                                                            <div className="flex items-center justify-between gap-2">
                                                                <span className="truncate">{row.label}</span>
                                                                <span className="font-medium">
                                                                    {valueFormatter(row.value)}
                                                                </span>
                                                            </div>
                                                            {row.subLabel ? (
                                                                <div className="truncate text-muted-foreground">
                                                                    {row.subLabel}
                                                                </div>
                                                            ) : null}
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-muted-foreground">
                                                        {tooltipData.emptyDetailsText || "暂无可展示明细"}
                                                    </div>
                                                )}
                                            </div>
                                        ) : null}
                                    </div>
                                ) : null}
                            </div>
                        </div>
                        <div className="flex flex-wrap items-center justify-center gap-4 text-[11px] text-muted-foreground">
                            {normalizedSeries.map((line) => (
                                <div key={line.key} className="inline-flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-1 rounded-full" style={{ backgroundColor: line.color }} />
                                    <span>{line.label}</span>
                                </div>
                            ))}
                        </div>
                        {legendNote ? (
                            <div className="text-[11px] text-muted-foreground text-center">{legendNote}</div>
                        ) : null}
                    </>
                )}
            </CardContent>
        </Card>
    );
}
