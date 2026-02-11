import React from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { StageCard } from "@/components/StageCard";
import { cn } from "@/lib/utils";
import { fmtStatus } from "@/utils/helpers";
import { FileItem, RunState } from "@/types";
import {
  Play, RotateCcw, Ban, FileText, FileInput, Download, CreditCard, Landmark, GitMerge, Fingerprint, Flag, AlertCircle
} from "lucide-react";

interface WorkflowPanelProps {
  state: RunState | null;
  runId: string;
  busy: boolean;
  selectedStageId: string;
  setSelectedStageId: (id: string) => void;
  startWorkflow: (ids?: string[]) => Promise<void>;
  resetClassify: () => Promise<void>;
  cancelRun: () => Promise<void>;
  baseUrl: string;
  selectFile: (file: FileItem) => void;
  className?: string;
}

export function WorkflowPanel({
  state, runId, busy, selectedStageId, setSelectedStageId,
  startWorkflow, resetClassify, cancelRun, baseUrl, selectFile, className
}: WorkflowPanelProps) {
  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold">流程</h3>
        <div className="flex gap-2">
          <Button variant="default" size="sm" onClick={() => startWorkflow(undefined)} disabled={!runId || busy}>
            <Play className="mr-2 h-3.5 w-3.5" /> 运行全部
          </Button>
          <Button variant="outline" size="sm" onClick={() => void resetClassify()} disabled={!runId || busy}>
            <RotateCcw className="mr-2 h-3.5 w-3.5" /> 重置分类产物
          </Button>
          <Button variant="destructive" size="sm" onClick={() => cancelRun()} disabled={!runId || busy}>
            <Ban className="mr-2 h-3.5 w-3.5" /> 停止
          </Button>
        </div>
      </div>

      {state?.stages?.length ? (
        <Tabs
          value={selectedStageId}
          onValueChange={setSelectedStageId}
          orientation="vertical"
          className="flex flex-col gap-4"
        >
          <ScrollArea className="w-full whitespace-nowrap rounded-md border">
            <TabsList className="h-auto p-1 bg-muted/50 w-full justify-start gap-1 flex-nowrap">
              {state.stages.map((st, idx) => {
                const isActive = selectedStageId === st.id;
                const status = fmtStatus(st.status);
                // Icon mapping
                let Icon = FileText;
                if (st.id.includes("pdf")) Icon = FileInput;
                if (st.id.includes("exports")) Icon = Download;
                if (st.id.includes("credit")) Icon = CreditCard;
                if (st.id.includes("bank")) Icon = Landmark;
                if (st.id.includes("unified")) Icon = GitMerge;
                if (st.id.includes("classify")) Icon = Fingerprint;
                if (st.id.includes("finalize")) Icon = Flag;

                return (
                  <TabsTrigger
                    key={st.id}
                    value={st.id}
                    className={cn(
                      "relative flex flex-col items-center gap-1.5 py-2 px-3 min-w-[108px] h-full shrink-0",
                      idx > 0 &&
                      "before:content-[''] before:absolute before:left-0 before:top-5 before:-translate-x-full before:w-3 before:h-[2px] before:bg-border/80",
                      isActive && "bg-background shadow-sm"
                    )}
                  >
                    <div className="relative">
                      <Icon className={cn("h-5 w-5", isActive ? "text-primary" : "text-muted-foreground")} />
                      {st.status !== 'idle' && st.status !== 'pending' && (
                        <span className={cn("absolute -top-1 -right-1 block h-2 w-2 rounded-full ring-1 ring-background",
                          status.variant === 'default' && "bg-green-500",
                          status.variant === 'destructive' && "bg-red-500",
                          status.variant === 'secondary' && "bg-blue-500",
                        )} />
                      )}
                    </div>
                    <span className="text-[10px] truncate w-full text-center" title={st.name}>{st.name}</span>
                  </TabsTrigger>
                )
              })}
            </TabsList>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>

          {state.stages.map((st) => (
            <TabsContent key={st.id} value={st.id} className="mt-0">
              <StageCard
                stage={st}
                runId={runId}
                baseUrl={baseUrl}
                onRun={(id) => startWorkflow([id])}
                onSelectFile={selectFile}
              />
            </TabsContent>
          ))}
        </Tabs>
      ) : (
        <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border-dashed border-2 rounded-lg bg-muted/5">
          <Ban className="h-8 w-8 mb-2 opacity-20" />
          <p>暂无可用阶段</p>
        </div>
      )}
    </div>
  );
}
