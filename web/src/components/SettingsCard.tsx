import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { PdfMode, RunState } from "@/types";

interface SettingsCardProps {
  state: RunState | null;
  pdfModes: PdfMode[];
  busy: boolean;
  saveOptions: (updates: Partial<any>) => void;
  onAllowUnreviewedChange: (next: boolean) => void;
}

export function SettingsCard({ state, pdfModes, busy, saveOptions, onAllowUnreviewedChange }: SettingsCardProps) {
  const modes = pdfModes?.length ? pdfModes : [{ id: "auto", name: "自动识别（推荐）" }];
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
        <div className="flex items-center space-x-2">
          <Checkbox
            id="allow_unreviewed"
            checked={Boolean(state?.options?.allow_unreviewed)}
            onCheckedChange={(chk: boolean | string) => onAllowUnreviewedChange(chk === true)}
            disabled={!state || busy}
          />
          <label htmlFor="allow_unreviewed" className="text-xs leading-none">
            允许跳过人工复核
          </label>
        </div>
        <div className="text-[11px] text-destructive">
          开启后将跳过人工复核，可能导致分类错误无法被发现。
        </div>
        <Separator />
        <div className="space-y-1">
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
              const prevY = m === 1 ? y - 1 : y;
              const prevM = m === 1 ? 12 : m - 1;
              const start = `${prevY}-${String(prevM).padStart(2, "0")}-21`;
              const end = `${y}-${String(m).padStart(2, "0")}-20`;
              return `账期范围：${start} ~ ${end}`;
            })() : "未设置账期筛选（默认范围：上月21日 ~ 本月20日）"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
