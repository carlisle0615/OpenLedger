import React, { useMemo, useEffect } from "react";
import { AlertCircle } from "lucide-react";
import { api } from "@/utils/helpers";
import { Profile, ProfileListItem } from "@/types";

import { useAppState } from "@/hooks/useAppState";
import { useRunApi } from "@/hooks/useRunApi";
import { useReviewActions, ReviewContext } from "@/hooks/useReviewActions";

import { HeaderBar } from "@/components/HeaderBar";
import { ProfilesPage } from "@/components/ProfilesPage";
import { ReviewPanel } from "@/components/ReviewPanel";
import { ConfigPanel } from "@/components/ConfigPanel";
import { UploadCard } from "@/components/UploadCard";
import { SettingsCard } from "@/components/SettingsCard";
import { PreviewArea } from "@/components/PreviewArea";
import { WorkflowPanel } from "@/components/WorkflowPanel";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { ReviewModal } from "@/components/ReviewModal";
import { CapabilitiesPanel } from "@/components/CapabilitiesPanel";


export default function App() {
  const [activeView, setActiveView] = React.useState<"workspace" | "profiles" | "capabilities">("workspace");
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
    profiles, setProfiles, currentProfileId, setCurrentProfileId,
  } = appState;

  const runApi = useRunApi({
    ...appState,
  });
  const {
    refreshRuns, onCreateRun, onUpload, downloadHref,
    pdfPageHref,
    startWorkflow, cancelRun, resetClassify,
    loadCsv, selectFile, saveConfig, saveConfigObject,
    saveOptions, setRunProfileBinding, runStatus,
  } = runApi;

  // Load profiles on mount
  useEffect(() => {
    if (!baseUrl) return;
    api<{ profiles: ProfileListItem[] }>(baseUrl, "/api/profiles")
      .then((res) => setProfiles(Array.isArray(res.profiles) ? res.profiles : []))
      .catch((err) => console.error("Failed to load profiles:", err));
  }, [baseUrl]);

  const boundProfileId = String(state?.profile_binding?.profile_id ?? "").trim();

  useEffect(() => {
    if (currentProfileId) return;
    if (boundProfileId) {
      setCurrentProfileId(boundProfileId);
      return;
    }
    if (profiles.length === 1) {
      setCurrentProfileId(profiles[0].id);
    }
  }, [currentProfileId, boundProfileId, profiles]);

  const handleCreateProfile = async (name: string) => {
    if (!name.trim()) return;
    try {
      const profile = await api<Profile>(baseUrl, "/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const newItem: ProfileListItem = {
        id: profile.id,
        name: profile.name,
        created_at: profile.created_at,
        updated_at: profile.updated_at,
        bill_count: 0,
      };
      setProfiles((prev) => [newItem, ...prev]);
      setCurrentProfileId(profile.id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectProfile = (id: string) => {
    setCurrentProfileId(id);
  };

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
  const showUploadCard = true;
  const showSettingsCard = Boolean(state?.stages?.length);

  return (
    <>
      <div className="h-screen overflow-hidden bg-background text-foreground font-sans antialiased flex flex-col">
        <HeaderBar
          baseUrl={baseUrl} setBaseUrl={appState.setBaseUrl}
          backendStatus={backendStatus} backendError={backendError}
          runs={runs} runId={runId} setRunId={appState.setRunId}
          runsMeta={runsMeta} newRunName={newRunName} setNewRunName={setNewRunName}
          busy={busy} runStatus={runStatus} runName={runName}
          refreshRuns={refreshRuns} onCreateRun={onCreateRun}
          activeView={activeView} setActiveView={setActiveView}
          profiles={profiles}
          currentProfileId={currentProfileId}
          onSelectProfile={handleSelectProfile}
          onCreateProfile={handleCreateProfile}
          profileSelectorDisabled={busy}
        />

        {error && (
          <div className="bg-destructive/10 border-b border-destructive/20 p-2 text-sm text-destructive flex items-center justify-center gap-2">
            <AlertCircle className="h-4 w-4" /> {error}
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-hidden relative">
          {activeView === "profiles" ? (
            <div className="h-full overflow-auto p-4">
              <ProfilesPage
                baseUrl={baseUrl}
                runId={runId}
                currentProfileId={currentProfileId}
                busy={busy}
                setRunProfileBinding={setRunProfileBinding}
                runState={state}
                confirmAction={appState.confirm}
              />
            </div>
          ) : activeView === "capabilities" ? (
            <div className="h-full overflow-auto p-4">
              <CapabilitiesPanel
                baseUrl={baseUrl}
                runState={state || null}
                mode="standalone"
              />
            </div>
          ) : (
            <div className="flex flex-col h-full bg-muted/10">
              {state?.stages?.length ? (
                <div className="bg-background border-b px-4 py-2 flex-shrink-0">
                  <WorkflowTimeline
                    state={state}
                    selectedStageId={selectedStageId}
                    setSelectedStageId={setSelectedStageId}
                  />
                </div>
              ) : null}

              <div className="flex-1 overflow-hidden p-4">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full min-h-0">
                  {/* Left Panel: Workflow & Config */}
                  <div className="lg:col-span-4 flex flex-col gap-4 h-full min-h-0 overflow-hidden">
                    <div className="flex-1 overflow-auto pr-1 space-y-4">
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
                        <SettingsCard
                          state={state}
                          pdfModes={pdfModes}
                          busy={busy}
                          saveOptions={saveOptions}
                        />
                      ) : null}
                    </div>
                  </div>

                  {/* Right Panel: Upload & Preview */}
                  <div className="lg:col-span-8 flex flex-col h-full min-h-0 gap-4 overflow-hidden">
                    {showUploadCard ? (
                      <div className="flex-shrink-0">
                        <UploadCard
                          state={state}
                          runId={runId}
                          busy={busy}
                          onUpload={onUpload}
                          boundProfileId={boundProfileId}
                          selectedProfileId={currentProfileId}
                          profiles={profiles}
                        />
                      </div>
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
            </div>
          )}
        </div>
      </div>

      <ReviewContext.Provider value={reviewContextValue}>
        <ReviewModal />
      </ReviewContext.Provider>
      {dialog}
    </>
  );
}
