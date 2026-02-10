import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { RunState } from "@/types";

interface SettingsCardProps {
  state: RunState | null;
  busy: boolean;
  saveOptions: (updates: Partial<any>) => void;
}

export function SettingsCard({ state, busy, saveOptions }: SettingsCardProps) {
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-base">Settings</CardTitle>
      </CardHeader>
      <CardContent className="py-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Mode</span>
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
              <SelectItem value="dry_run">Dry Run</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="allow_unreviewed"
            checked={Boolean(state?.options?.allow_unreviewed)}
            onCheckedChange={(chk: boolean | string) => saveOptions({ allow_unreviewed: chk === true })}
            disabled={!state || busy}
          />
          <label htmlFor="allow_unreviewed" className="text-xs leading-none">
            Allow no review
          </label>
        </div>
        <Separator />
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Statement</span>
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
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
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
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
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
              return `Cycle: ${start} ~ ${end}`;
            })() : "No date filter (cycle is prev month 21 ~ selected month 20)"}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
