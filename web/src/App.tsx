import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";

import { useAppState } from "@/hooks/useAppState";
import { useRunApi } from "@/hooks/useRunApi";
import { useReviewActions, ReviewContext } from "@/hooks/useReviewActions";

import { HeaderBar } from "@/components/HeaderBar";
import { ReviewPanel } from "@/components/ReviewPanel";
import { ConfigPanel } from "@/components/ConfigPanel";
import { UploadCard } from "@/components/UploadCard";
import { SettingsCard } from "@/components/SettingsCard";
import { PreviewArea } from "@/components/PreviewArea";
import { WorkflowPanel } from "@/components/WorkflowPanel";
import { ReviewModal } from "@/components/ReviewModal";


export default function App() {
  const appState = useAppState();
  const {
    baseUrl, runs, runId, runsMeta,
    backendStatus, backendError, pdfModes, newRunName, setNewRunName,
    state, selectedFile, csvPreview, textPreview, previewError,
    pdfPreview,
    configText, setConfigText, cfgSaveToRun, setCfgSaveToRun, cfgSaveToGlobal, setCfgSaveToGlobal,
    reviewRows, reviewEdits,
    busy, error, selectedStageId, setSelectedStageId,
    dialog,
  } = appState;

  const runApi = useRunApi({
    ...appState,
  });
  const {
    refreshRuns, onCreateRun, onUpload, downloadHref,
    pdfPageHref,
    startWorkflow, cancelRun, resetClassify,
    loadCsv, selectFile, saveConfig, saveConfigObject,
    saveOptions, runStatus,
  } = runApi;

  const reviewActions = useReviewActions({
    ...appState,
    saveConfigObject,
  });
  const {
    loadReview, openReview,
    reviewContextValue,
    reviewPendingCount,
  } = reviewActions;

  // 派生状态
  const runName = useMemo(() => {
    const n = String(state?.name ?? "").trim();
    if (n) return n;
    const hit = runsMeta.find((m) => m.id === runId);
    return String(hit?.name ?? "").trim();
  }, [state, runsMeta, runId]);

  const finalizeStage = useMemo(
    () => state?.stages?.find((st) => st.id === "finalize") ?? null,
    [state],
  );

  const showReviewPanel = Boolean(runId) && (
    selectedStageId === "finalize"
    || state?.current_stage === "finalize"
    || state?.status === "needs_review"
    || finalizeStage?.status === "needs_review"
  );
  const showConfigPanel = Boolean(runId);
  const showUploadCard = Boolean(runId) && !(state?.inputs?.length ?? 0);
  const showSettingsCard = Boolean(state?.stages?.length);

  return (
    <div className="min-h-screen bg-background text-foreground p-4 font-sans antialiased">
      <div className="w-full px-4 space-y-4">
          <HeaderBar
          baseUrl={baseUrl} setBaseUrl={appState.setBaseUrl}
          backendStatus={backendStatus} backendError={backendError}
          runs={runs} runId={runId} setRunId={appState.setRunId}
          runsMeta={runsMeta} newRunName={newRunName} setNewRunName={setNewRunName}
          busy={busy} runStatus={runStatus} runName={runName}
          refreshRuns={refreshRuns} onCreateRun={onCreateRun}
        />

        {error && <div className="text-sm text-destructive flex items-center gap-2 p-2 border border-destructive/20 bg-destructive/10 rounded-md"><AlertCircle className="h-4 w-4" /> {error}</div>}

        {runId && !state?.inputs?.length ? (
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-base">下一步</CardTitle>
            </CardHeader>
            <CardContent className="py-3 text-sm text-muted-foreground">
              请上传 PDF/CSV/XLSX 文件以开始处理。
            </CardContent>
          </Card>
        ) : null}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 flex flex-col gap-4">
            {showReviewPanel ? (
              <ReviewPanel
                statusNeedsReview={state?.status === "needs_review"}
                reviewPendingCount={reviewPendingCount}
                reviewEditsCount={Object.keys(reviewEdits).length}
                reviewRowsCount={reviewRows.length}
                runId={runId}
                busy={busy}
                loadReview={loadReview}
                openReview={openReview}
              />
            ) : null}

            <WorkflowPanel
              state={state}
              runId={runId}
              busy={busy}
              selectedStageId={selectedStageId}
              setSelectedStageId={setSelectedStageId}
              startWorkflow={startWorkflow}
              resetClassify={resetClassify}
              cancelRun={cancelRun}
              baseUrl={baseUrl}
              selectFile={selectFile}
            />

            {showConfigPanel ? (
              <ConfigPanel
                configText={configText} setConfigText={setConfigText}
                cfgSaveToRun={cfgSaveToRun} setCfgSaveToRun={setCfgSaveToRun}
                cfgSaveToGlobal={cfgSaveToGlobal} setCfgSaveToGlobal={setCfgSaveToGlobal}
                saveConfig={saveConfig}
              />
            ) : null}

            {showSettingsCard ? (
              <div className="mt-auto">
                <SettingsCard
                  state={state}
                  pdfModes={pdfModes}
                  busy={busy}
                  saveOptions={saveOptions}
                />
              </div>
            ) : null}
          </div>

          <div className="lg:col-span-8 space-y-6">
            {showUploadCard ? (
              <UploadCard
                state={state}
                runId={runId}
                busy={busy}
                onUpload={onUpload}
              />
            ) : null}

            <PreviewArea
              selectedFile={selectedFile}
              runName={runName}
              downloadHref={downloadHref}
              previewError={previewError}
              csvPreview={csvPreview}
              pdfPreview={pdfPreview}
              textPreview={textPreview}
              loadCsv={loadCsv}
              pdfPageHref={pdfPageHref}
            />
          </div>
        </div>
      </div>

      <ReviewContext.Provider value={reviewContextValue}>
        <ReviewModal />
      </ReviewContext.Provider>
      {dialog}
    </div>
  );
}
