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
  const hasInputs = (state?.inputs?.length ?? 0) > 0;
  const runInProgress = state?.status === "running";
  const runDisabledReason = !runId
    ? "请先选择任务"
    : busy
      ? "当前有操作正在执行"
      : runInProgress
        ? "流程运行中，请先停止或等待完成"
        : !hasInputs
          ? "请先上传至少一个文件"
          : "";
  const canStartRun = !runDisabledReason;
  const canCancel = Boolean(runId) && !busy && runInProgress;
  const cancelDisabledReason = !runId
    ? "请先选择任务"
    : busy
      ? "当前有操作正在执行"
      : !runInProgress
        ? "当前没有运行中的任务"
        : "";

  const actionButtons = (
    <div className="ml-auto flex items-center gap-1.5 overflow-x-auto">
      <Button
        variant="default"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => startWorkflow(undefined)}
        disabled={!canStartRun}
        title={canStartRun ? "按当前设置执行完整流程" : runDisabledReason}
      >
        <Play className="mr-1.5 h-3 w-3" /> 运行全部
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => void resetClassify()}
        disabled={!runId || busy}
        title={!runId ? "请先选择任务" : busy ? "当前有操作正在执行" : "清空分类产物后重跑"}
      >
        <RotateCcw className="mr-1.5 h-3 w-3" /> 重置分类产物
      </Button>
      <Button
        variant="destructive"
        size="sm"
        className="h-7 px-2 text-xs"
        onClick={() => cancelRun()}
        disabled={!canCancel}
        title={canCancel ? "停止当前任务" : cancelDisabledReason}
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
            runDisabled={!canStartRun}
            runDisabledReason={runDisabledReason}
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border-dashed border-2 rounded-md bg-muted/5">
            <AlertCircle className="h-8 w-8 mb-2 opacity-20" />
            <p>请选择一个阶段查看详情</p>
          </div>
        )
      ) : (
        <div className="flex flex-col items-center justify-center p-12 text-muted-foreground border-dashed border-2 rounded-md bg-muted/5">
          <Ban className="h-8 w-8 mb-2 opacity-20" />
          <p>暂无可用阶段</p>
        </div>
      )}
    </div>
  );
}
