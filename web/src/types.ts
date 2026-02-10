export type Stage = {
    id: string;
    name: string;
    status: string;
    started_at: string;
    ended_at: string;
    log_path: string;
    error: string;
};

export type RunState = {
    run_id: string;
    name?: string;
    status: string;
    created_at: string;
    updated_at: string;
    cancel_requested: boolean;
    current_stage: string | null;
    inputs: { name: string; path: string; size: number }[];
    options: {
        classify_mode: "llm" | "dry_run";
        allow_unreviewed: boolean;
        period_year: number | null;
        period_month: number | null;
    };
    stages: Stage[];
};

export type ClassifierConfig = {
    model?: string;
    batch_size?: number;
    uncertain_threshold?: number;
    categories?: { id: string; name: string }[];
    [k: string]: unknown;
};

export type FileItem = { path: string; name: string; exists: boolean; size?: number };
export type StageIO = { stage_id: string; inputs: FileItem[]; outputs: FileItem[] };

export type CsvPreview = {
    columns: string[];
    rows: Record<string, string>[];
    offset: number;
    limit: number;
    has_more: boolean;
    next_offset: number | null;
    prev_offset: number | null;
};
