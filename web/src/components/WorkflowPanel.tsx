import React from "react";
import { Button } from "@/components/ui/button";
import { StageCard } from "@/components/StageCard";
import { cn } from "@/lib/utils";
import { FileItem, RunState } from "@/types";
import {
  Play, RotateCcw, Ban, AlertCircle
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
  const currentStage = state?.stages?.find(s => s.id === selectedStageId);

  const actionButtons = (
    <div className="ml-auto flex items-center gap-1.5 overflow-x-auto">
      <Button
        variant="default"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => startWorkflow(undefined)}
        disabled={!runId || busy}
      >
        <Play className="mr-1.5 h-3 w-3" /> 运行全部
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => void resetClassify()}
        disabled={!runId || busy}
      >
        <RotateCcw className="mr-1.5 h-3 w-3" /> 重置分类产物
      </Button>
      <Button
        variant="destructive"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => cancelRun()}
        disabled={!runId || busy}
      >
        <Ban className="mr-1.5 h-3 w-3" /> 停止
      </Button>
    </div>
  );

  return (
    <div className={cn("space-y-4", className)}>
      <div className="mb-2 flex items-center gap-2 overflow-hidden">
        <h3 className="shrink-0 text-base font-semibold">流程详情</h3>
        {actionButtons}
      </div>

      {state?.stages?.length ? (
        currentStage ? (
          <StageCard
            stage={currentStage}
            runId={runId}
            baseUrl={baseUrl}
            onRun={(id) => startWorkflow([id])}
            onSelectFile={selectFile}
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border-dashed border-2 rounded-lg bg-muted/5">
            <AlertCircle className="h-8 w-8 mb-2 opacity-20" />
            <p>请选择一个阶段查看详情</p>
          </div>
        )
      ) : (
        <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border-dashed border-2 rounded-lg bg-muted/5">
          <Ban className="h-8 w-8 mb-2 opacity-20" />
          <p>暂无可用阶段</p>
        </div>
      )}
    </div>
  );
}
