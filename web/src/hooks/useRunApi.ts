import { useCallback, useEffect, useMemo } from "react";
import { ClassifierConfig, CsvPreview, FileItem, PdfMode, PdfPreview, RunState } from "@/types";
import { api, fmtStatus, isCsvFile, isExcelFile, isPdfFile, isTextFile, type RunMeta } from "@/utils/helpers";

/** useRunApi 的依赖参数类型 */
export interface RunApiDeps {
    baseUrl: string;
    runId: string;
    state: RunState | null;
    csvLimit: number;
    config: ClassifierConfig | null;
    configText: string;
    cfgSaveToRun: boolean;
    cfgSaveToGlobal: boolean;
    lastOptionEdit: React.MutableRefObject<number>;
    confirm: (opts: { title: string; description: string; confirmText: string; cancelText: string; tone: "default" | "danger" }) => Promise<boolean>;

    // setters
    setRuns: (v: string[]) => void;
    setRunsMeta: (v: RunMeta[]) => void;
    setRunId: (v: string) => void;
    setBackendStatus: (v: "idle" | "checking" | "ok" | "error") => void;
    setBackendError: (v: string) => void;
    setPdfModes: (v: PdfMode[]) => void;
    setNewRunName: (v: string) => void;
    setState: React.Dispatch<React.SetStateAction<RunState | null>>;
    setSelectedFile: (v: FileItem | null) => void;
    setCsvPreview: (v: CsvPreview | null) => void;
    setPdfPreview: (v: PdfPreview | null) => void;
    setTextPreview: (v: string) => void;
    setPreviewError: (v: string) => void;
    setConfig: (v: ClassifierConfig | null) => void;
    setConfigText: (v: string) => void;
    setBusy: (v: boolean) => void;
    setError: (v: string) => void;
    setSelectedStageId: (v: string) => void;
}

export function useRunApi(deps: RunApiDeps) {
    const {
        baseUrl, runId, state, csvLimit,
        config, configText, cfgSaveToRun, cfgSaveToGlobal,
        lastOptionEdit, confirm,
        setRuns, setRunsMeta, setRunId, setBackendStatus, setBackendError,
        setPdfModes, setNewRunName,
        setState, setSelectedFile, setCsvPreview, setPdfPreview, setTextPreview, setPreviewError,
        setConfig, setConfigText,
        setBusy, setError, setSelectedStageId,
    } = deps;

    // ---- 核心 API 函数 ----

    async function refreshRuns(opts?: { silentError?: boolean }) {
        setBackendStatus("checking");
        setBackendError("");
        try {
            const r = await api<{ runs: string[]; runs_meta?: RunMeta[] }>(baseUrl, "/api/runs");
            setRuns(r.runs);
            setRunsMeta(Array.isArray(r.runs_meta) ? r.runs_meta : []);
            setBackendStatus("ok");
            return r;
        } catch (e) {
            const msg = String(e);
            setBackendStatus("error");
            setBackendError(msg);
            if (!opts?.silentError) {
                setError(msg);
            }
            throw e;
        }
    }

    async function loadRun(id: string) {
        if (!id) return;
        const s = await api<RunState>(baseUrl, `/api/runs/${encodeURIComponent(id)}`);
        setState(s);
        setSelectedFile(null);
        setCsvPreview(null);
        setPdfPreview(null);
        setTextPreview("");
        setPreviewError("");
        try {
            const cfg = await api<ClassifierConfig>(baseUrl, `/api/runs/${encodeURIComponent(id)}/config/classifier`);
            setConfig(cfg);
            setConfigText(JSON.stringify(cfg, null, 2));
        } catch {
            setConfig(null);
            setConfigText("");
        }
    }

    async function onCreateRun(newRunName: string) {
        setBusy(true);
        setError("");
        try {
            const name = newRunName.trim();
            const s = await api<RunState>(baseUrl, "/api/runs", {
                method: "POST",
                headers: name ? { "Content-Type": "application/json" } : undefined,
                body: name ? JSON.stringify({ name }) : undefined,
            });
            await refreshRuns();
            setRunId(s.run_id);
            setState(s);
            setNewRunName("");
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function onUpload(files: FileList | null) {
        if (!files || !runId) return;
        setBusy(true);
        setError("");
        try {
            const fd = new FormData();
            for (const f of Array.from(files)) {
                fd.append("files", f, f.name);
            }
            await api<{ saved: unknown[] }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/upload`, {
                method: "POST",
                body: fd,
            });
            await loadRun(runId);
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    function downloadHref(relPath: string) {
        return `${baseUrl}/api/runs/${encodeURIComponent(runId)}/artifact?path=${encodeURIComponent(relPath)}`;
    }

    function pdfPageHref(relPath: string, page: number, dpi = 120) {
        return `${baseUrl}/api/runs/${encodeURIComponent(runId)}/preview/pdf/page?path=${encodeURIComponent(relPath)}&page=${encodeURIComponent(String(page))}&dpi=${encodeURIComponent(String(dpi))}`;
    }

    async function loadPdfMeta(relPath: string) {
        return api<PdfPreview>(
            baseUrl,
            `/api/runs/${encodeURIComponent(runId)}/preview/pdf/meta?path=${encodeURIComponent(relPath)}`,
        );
    }

    async function startWorkflow(stages?: string[]) {
        if (!runId) return;
        const options = state?.options ?? {
            classify_mode: "llm" as const,
            period_mode: "billing",
            period_day: 20,
            period_year: null,
            period_month: null,
        };
        const stageIds = stages ?? state?.stages?.map((s) => s.id) ?? [];
        const includesClassify = !stages || stageIds.some((id) => id.includes("classify"));
        if (includesClassify && options.classify_mode === "llm") {
            const ok = await confirm({
                title: "确认运行分类阶段？",
                description: "当前分类模式为 LLM，可能产生费用。",
                confirmText: "继续运行",
                cancelText: "取消",
                tone: "danger",
            });
            if (!ok) return;
        }
        setBusy(true);
        setError("");
        try {
            await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ stages, options }),
            });
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function cancelRun() {
        if (!runId) return;
        const ok = await confirm({
            title: "确认停止当前任务？",
            description: "停止后需要重新运行才能继续生成产物。",
            confirmText: "确认停止",
            cancelText: "取消",
            tone: "danger",
        });
        if (!ok) return;
        setBusy(true);
        setError("");
        try {
            await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function resetClassify() {
        if (!runId) return;
        const ok = await confirm({
            title: "确认重置分类产物？",
            description: "将清空本次任务的分类产物，需要重新运行分类阶段。",
            confirmText: "确认重置",
            cancelText: "取消",
            tone: "danger",
        });
        if (!ok) return;
        setBusy(true);
        setError("");
        try {
            await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/reset`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ scope: "classify" }),
            });
            await loadRun(runId);
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function loadCsv(relPath: string, offset: number) {
        setPreviewError("");
        const r = await api<CsvPreview>(
            baseUrl,
            `/api/runs/${encodeURIComponent(runId)}/preview?path=${encodeURIComponent(relPath)}&limit=${encodeURIComponent(String(csvLimit))}&offset=${encodeURIComponent(String(offset))}`,
        );
        setCsvPreview(r);
    }

    async function selectFile(file: FileItem) {
        if (!file.exists) return;
        setSelectedFile(file);
        setCsvPreview(null);
        setPdfPreview(null);
        setTextPreview("");
        setPreviewError("");

        if (!runId) return;
        if (isCsvFile(file.name) || isExcelFile(file.name)) {
            await loadCsv(file.path, 0);
            return;
        }
        if (isPdfFile(file.name)) {
            try {
                const meta = await loadPdfMeta(file.path);
                setPdfPreview(meta);
            } catch (e) {
                setPreviewError(String(e));
            }
            return;
        }
        if (isTextFile(file.name)) {
            try {
                const res = await fetch(downloadHref(file.path));
                const text = await res.text();
                setTextPreview(text.length > 400_000 ? text.slice(0, 400_000) + "\n\n...(已截断)..." : text);
            } catch (e) {
                setPreviewError(String(e));
            }
            return;
        }
        setPreviewError("该文件类型暂不支持预览，请下载查看。");
    }

    async function saveConfigObject(next: unknown) {
        if (!runId) return;
        try {
            if (!cfgSaveToRun && !cfgSaveToGlobal) {
                throw new Error("请至少选择一个保存目标：本次任务 / 默认配置。");
            }
            if (cfgSaveToGlobal) {
                const ok = await confirm({
                    title: "确认保存为默认配置？",
                    description: "将写入全局 config/classifier.local.json，影响后续新任务。取消将不保存。",
                    confirmText: "确认保存",
                    cancelText: "取消",
                    tone: "danger",
                });
                if (!ok) return;
            }
            setBusy(true);
            setError("");
            if (cfgSaveToRun) {
                await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/config/classifier`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(next),
                });
            }
            if (cfgSaveToGlobal) {
                await api<{ ok: boolean }>(baseUrl, "/api/config/classifier", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(next),
                });
            }
            setConfig(next as ClassifierConfig);
            setConfigText(JSON.stringify(next, null, 2));
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function saveConfig() {
        try {
            const next = JSON.parse(configText) as ClassifierConfig;
            await saveConfigObject(next);
        } catch (e) {
            setError(String(e));
        }
    }

    async function saveOptions(updates: Partial<NonNullable<RunState["options"]>>) {
        if (!runId) return;
        lastOptionEdit.current = Date.now();
        const nextUpdates = { ...(updates as Record<string, unknown>) };
        delete nextUpdates.profile_id;
        if (!Object.keys(nextUpdates).length) return;
        // 乐观更新
        setState((prev) => (prev ? { ...prev, options: { ...prev.options, ...nextUpdates } } : prev));
        setBusy(true);
        setError("");
        try {
            await api<{ ok: boolean }>(baseUrl, `/api/runs/${encodeURIComponent(runId)}/options`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(nextUpdates),
            });
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }

    async function setRunProfileBinding(profileId: string) {
        if (!runId) return;
        const profile_id = String(profileId || "").trim();
        if (!profile_id) {
            throw new Error("缺少 profile_id");
        }
        const optimisticTs = new Date().toISOString();
        setState((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                profile_binding: {
                    run_id: runId,
                    profile_id,
                    updated_at: optimisticTs,
                },
            };
        });
        setBusy(true);
        setError("");
        try {
            await api<{ ok: boolean; binding: unknown }>(
                baseUrl,
                `/api/runs/${encodeURIComponent(runId)}/profile-binding`,
                {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ profile_id }),
                },
            );
        } catch (e) {
            setError(String(e));
            throw e;
        } finally {
            setBusy(false);
        }
    }

    // ---- 副作用 ----

    // 初始连接检测
    useEffect(() => {
        if (!baseUrl.trim()) {
            setBackendStatus("idle");
            setBackendError("");
            return;
        }
        const timer = window.setTimeout(() => {
            refreshRuns({ silentError: true }).catch(() => { });
        }, 500);
        return () => window.clearTimeout(timer);
    }, [baseUrl]);

    // 加载 PDF 解析模式
    useEffect(() => {
        api<{ modes: PdfMode[] }>(baseUrl, "/api/parsers/pdf")
            .then((r) => setPdfModes(Array.isArray(r?.modes) ? r.modes : []))
            .catch(() => setPdfModes([{ id: "auto", name: "自动识别（推荐）" }]));
    }, [baseUrl]);

    // 轮询运行状态
    useEffect(() => {
        if (!runId) return;
        loadRun(runId).catch((e) => setError(String(e)));
        const timer = window.setInterval(() => {
            api<RunState>(baseUrl, `/api/runs/${encodeURIComponent(runId)}`)
                .then((s) => {
                    if (Date.now() - lastOptionEdit.current < 10000) {
                        setState((prev) => {
                            if (!prev) return s;
                            return { ...s, options: { ...s.options, ...prev.options } };
                        });
                    } else {
                        setState(s);
                    }
                })
                .catch(() => { });
        }, 1500);
        return () => window.clearInterval(timer);
    }, [baseUrl, runId]);

    // 自动选中第一个阶段
    useEffect(() => {
        if (state?.stages?.length && !deps.selectedStageId) {
            setSelectedStageId(state.stages[0].id);
        }
    }, [state, deps.selectedStageId]);

    // 派生值
    const runStatus = state ? fmtStatus(state.status) : null;

    return {
        refreshRuns,
        loadRun,
        onCreateRun,
        onUpload,
        downloadHref,
        pdfPageHref,
        startWorkflow,
        cancelRun,
        resetClassify,
        loadCsv,
        selectFile,
        saveConfig,
        saveConfigObject,
        saveOptions,
        setRunProfileBinding,
        runStatus,
    };
}
