import { useState, useRef, useEffect } from "react";
import {
    ClassifierConfig,
    CsvPreview,
    FileItem,
    PdfMode,
    PdfPreview,
    RunState,
} from "@/types";
import { type RuleMatchMode, type RuleMatchField, type RuleAction, type RunMeta } from "@/utils/helpers";
import { useConfirm } from "@/hooks/useConfirm";

export type ReviewFeedback = {
    type: "success" | "info";
    text: string;
    ts: number;
};

export function useAppState() {
    const [baseUrl, setBaseUrl] = useState(
        () => localStorage.getItem("openledger_baseUrl") || "http://127.0.0.1:8000",
    );
    const [runs, setRuns] = useState<string[]>([]);
    const [runId, setRunId] = useState<string>("");
    const [runsMeta, setRunsMeta] = useState<RunMeta[]>([]);
    const [backendStatus, setBackendStatus] = useState<"idle" | "checking" | "ok" | "error">("idle");
    const [backendError, setBackendError] = useState<string>("");
    const [pdfModes, setPdfModes] = useState<PdfMode[]>([]);
    const [newRunName, setNewRunName] = useState<string>("");
    const [state, setState] = useState<RunState | null>(null);
    const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
    const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null);
    const [pdfPreview, setPdfPreview] = useState<PdfPreview | null>(null);
    const [textPreview, setTextPreview] = useState<string>("");
    const [previewError, setPreviewError] = useState<string>("");
    const [csvLimit] = useState<number>(200);
    const [config, setConfig] = useState<ClassifierConfig | null>(null);
    const [configText, setConfigText] = useState<string>("");
    const [cfgSaveToRun, setCfgSaveToRun] = useState(true);
    const [cfgSaveToGlobal, setCfgSaveToGlobal] = useState(true);
    const [reviewRows, setReviewRows] = useState<Record<string, string>[]>([]);
    const [reviewEdits, setReviewEdits] = useState<Record<string, Partial<Record<string, string | boolean>>>>({});
    const [reviewPendingOnly, setReviewPendingOnly] = useState(true);
    const [reviewQuery, setReviewQuery] = useState("");
    const [reviewOpen, setReviewOpen] = useState(false);
    const [reviewSelectedTxnId, setReviewSelectedTxnId] = useState<string>("");
    const [reviewSelectedTxnIds, setReviewSelectedTxnIds] = useState<Record<string, boolean>>({});
    const [bulkTarget, setBulkTarget] = useState<"selected" | "filtered">("selected");
    const [bulkIncludeReviewed, setBulkIncludeReviewed] = useState(false);
    const [bulkCategoryId, setBulkCategoryId] = useState<string>("");
    const [bulkIgnored, setBulkIgnored] = useState<boolean>(false);
    const [bulkNote, setBulkNote] = useState<string>("");
    const [bulkContinuousMode, setBulkContinuousMode] = useState<boolean>(false);

    const [ruleField, setRuleField] = useState<RuleMatchField>("merchant");
    const [ruleMode, setRuleMode] = useState<RuleMatchMode>("contains");
    const [ruleAction, setRuleAction] = useState<RuleAction>("categorize");
    const [rulePattern, setRulePattern] = useState("");
    const [ruleCategoryId, setRuleCategoryId] = useState("");
    const [ruleOnlyPending, setRuleOnlyPending] = useState(true);
    const [ruleOverwriteFinal, setRuleOverwriteFinal] = useState(false);
    const [ruleSaveToConfig, setRuleSaveToConfig] = useState(true);
    const [ruleSaveToGlobal, setRuleSaveToGlobal] = useState(true);
    const [ruleNote, setRuleNote] = useState("");
    const [newCategoryName, setNewCategoryName] = useState("");
    const [newCategoryId, setNewCategoryId] = useState("");
    const [reviewFeedback, setReviewFeedback] = useState<ReviewFeedback | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string>("");
    const [selectedStageId, setSelectedStageId] = useState<string>("");
    const lastOptionEdit = useRef<number>(0);
    const { confirm, confirmChoice, dialog } = useConfirm();

    // localStorage 同步
    useEffect(() => {
        localStorage.setItem("openledger_baseUrl", baseUrl);
    }, [baseUrl]);

    // 复核弹窗滚动锁
    useEffect(() => {
        if (!reviewOpen) return;
        const prev = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = prev;
        };
    }, [reviewOpen]);

    return {
        // 连接
        baseUrl, setBaseUrl,
        // 任务
        runs, setRuns, runId, setRunId, runsMeta, setRunsMeta,
        backendStatus, setBackendStatus, backendError, setBackendError,
        pdfModes, setPdfModes, newRunName, setNewRunName,
        // 运行状态
        state, setState, selectedFile, setSelectedFile,
        csvPreview, setCsvPreview, pdfPreview, setPdfPreview, textPreview, setTextPreview,
        previewError, setPreviewError, csvLimit,
        // 配置
        config, setConfig, configText, setConfigText,
        cfgSaveToRun, setCfgSaveToRun, cfgSaveToGlobal, setCfgSaveToGlobal,
        // 复核
        reviewRows, setReviewRows, reviewEdits, setReviewEdits,
        reviewPendingOnly, setReviewPendingOnly, reviewQuery, setReviewQuery,
        reviewOpen, setReviewOpen,
        reviewSelectedTxnId, setReviewSelectedTxnId,
        reviewSelectedTxnIds, setReviewSelectedTxnIds,
        // 批量
        bulkTarget, setBulkTarget, bulkIncludeReviewed, setBulkIncludeReviewed,
        bulkCategoryId, setBulkCategoryId, bulkIgnored, setBulkIgnored,
        bulkNote, setBulkNote, bulkContinuousMode, setBulkContinuousMode,
        // 规则
        ruleField, setRuleField, ruleMode, setRuleMode,
        ruleAction, setRuleAction, rulePattern, setRulePattern,
        ruleCategoryId, setRuleCategoryId, ruleOnlyPending, setRuleOnlyPending,
        ruleOverwriteFinal, setRuleOverwriteFinal,
        ruleSaveToConfig, setRuleSaveToConfig, ruleSaveToGlobal, setRuleSaveToGlobal,
        ruleNote, setRuleNote,
        // 新分类
        newCategoryName, setNewCategoryName, newCategoryId, setNewCategoryId,
        reviewFeedback, setReviewFeedback,
        // UI
        busy, setBusy, error, setError,
        selectedStageId, setSelectedStageId,
        lastOptionEdit,
        confirm, confirmChoice, dialog,
    };
}
