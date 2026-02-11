import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { PdfMode, RunState } from "@/types";

interface SettingsCardProps {
  state: RunState | null;
  pdfModes: PdfMode[];
  busy: boolean;
  saveOptions: (updates: Partial<any>) => void;
}

export function SettingsCard({ state, pdfModes, busy, saveOptions }: SettingsCardProps) {
  const modes = pdfModes?.length ? pdfModes : [{ id: "auto", name: "自动识别（推荐）" }];
  const periodMode = state?.options?.period_mode ?? "billing";
  const periodDay = state?.options?.period_day ?? 20;
  const [customDay, setCustomDay] = useState(String(periodDay));
  const presetDays = useMemo(() => [5, 10, 15, 20, 25], []);

  useEffect(() => {
    setCustomDay(String(periodDay));
  }, [periodDay]);

  const applyCustomDay = () => {
    const raw = customDay.trim();
    if (!raw) return;
    const num = Number(raw);
    if (!Number.isFinite(num)) return;
    const day = Math.min(Math.max(Math.round(num), 1), 31);
    saveOptions({ period_day: day });
  };

  const handleCustomDayKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      applyCustomDay();
    }
  };

  const formatDate = (y: number, m: number, d: number) => (
    `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`
  );
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-base">设置</CardTitle>
      </CardHeader>
      <CardContent className="py-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">模式</span>
          <Select
            value={state?.options?.classify_mode ?? "llm"}
            onValueChange={(val: string) => saveOptions({ classify_mode: val as "llm" | "dry_run" })}
            disabled={!state || busy}
          >
            <SelectTrigger className="w-[120px] h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="llm">LLM</SelectItem>
              <SelectItem value="dry_run">试运行</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">PDF 解析模式</span>
          <Select
            value={state?.options?.pdf_mode ?? "auto"}
            onValueChange={(val: string) => saveOptions({ pdf_mode: val })}
            disabled={!state || busy}
          >
            <SelectTrigger className="w-[240px] h-7 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {modes.map((m) => (
                <SelectItem key={m.id} value={m.id} className="text-xs">
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Separator />
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">账期方式</span>
            <Select
              value={periodMode}
              onValueChange={(val: string) => saveOptions({ period_mode: val })}
              disabled={!state || busy}
            >
              <SelectTrigger className="w-[220px] h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="billing" className="text-xs">信用卡账期（上月21 ~ 本月20）</SelectItem>
                <SelectItem value="calendar" className="text-xs">自然月（1 ~ 月末）</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {periodMode === "billing" ? (
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">账单日</span>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  {presetDays.map((d) => (
                    <Button
                      key={d}
                      type="button"
                      size="sm"
                      variant={periodDay === d ? "default" : "outline"}
                      className="h-7 px-2 text-xs"
                      onClick={() => saveOptions({ period_day: d })}
                      disabled={!state || busy}
                    >
                      {d}日
                    </Button>
                  ))}
                </div>
                <Input
                  type="number"
                  min={1}
                  max={31}
                  value={customDay}
                  onChange={(e) => setCustomDay(e.target.value)}
                  onBlur={applyCustomDay}
                  onKeyDown={handleCustomDayKeyDown}
                  className="w-[84px] h-7 text-xs"
                  placeholder="自定义"
                  disabled={!state || busy}
                />
              </div>
            </div>
          ) : null}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">账期</span>
            <div className="flex items-center gap-2">
              <Select
                value={state?.options?.period_year ? String(state.options.period_year) : "__all__"}
                onValueChange={(val: string) => {
                  const year = val === "__all__" ? null : Number(val);
                  if (!year) {
                    saveOptions({ period_year: null, period_month: null });
                    return;
                  }
                  saveOptions({
                    period_year: year,
                    period_month: state?.options?.period_month ?? null,
                  });
                }}
                disabled={!state || busy}
              >
                <SelectTrigger className="w-[92px] h-7 text-xs">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">全部</SelectItem>
                  {Array.from({ length: 11 }).map((_, i) => {
                    const y = 2020 + i;
                    return (
                      <SelectItem key={y} value={String(y)} className="text-xs font-mono">
                        {y}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
              <Select
                value={state?.options?.period_month ? String(state.options.period_month) : "__all__"}
                onValueChange={(val: string) => {
                  const month = val === "__all__" ? null : Number(val);
                  saveOptions({ period_month: month });
                }}
                disabled={!state || busy || !state?.options?.period_year}
              >
                <SelectTrigger className="w-[84px] h-7 text-xs">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">全部</SelectItem>
                  {Array.from({ length: 12 }).map((_, i) => (
                    <SelectItem key={i + 1} value={String(i + 1)} className="text-xs">
                      {i + 1}月
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="text-[11px] text-muted-foreground">
            {state?.options?.period_year && state?.options?.period_month ? (() => {
              const y = state.options.period_year!;
              const m = state.options.period_month!;
              if (periodMode === "calendar") {
                const lastDay = new Date(y, m, 0).getDate();
                const start = formatDate(y, m, 1);
                const end = formatDate(y, m, lastDay);
                return `账期范围：${start} ~ ${end}`;
              }
              const prevY = m === 1 ? y - 1 : y;
              const prevM = m === 1 ? 12 : m - 1;
              const prevLastDay = new Date(prevY, prevM, 0).getDate();
              const endDay = Math.min(periodDay, new Date(y, m, 0).getDate());
              const prevEndDay = Math.min(periodDay, prevLastDay);
              const startDate = new Date(prevY, prevM - 1, prevEndDay + 1);
              const start = formatDate(startDate.getFullYear(), startDate.getMonth() + 1, startDate.getDate());
              const end = formatDate(y, m, endDay);
              return `账期范围：${start} ~ ${end}`;
            })() : "未设置账期筛选"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
