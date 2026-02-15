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
    profile_archive?: {
        status: "ok" | "failed";
        profile_id: string;
        run_id: string;
        error?: string;
        updated_at?: string;
    };
    profile_binding?: {
        run_id: string;
        profile_id: string;
        created_at?: string;
        updated_at?: string;
    } | null;
    inputs: { name: string; path: string; size: number }[];
    options: {
        pdf_mode?: string;
        classify_mode: "llm" | "dry_run";
        period_mode?: "billing" | "calendar";
        period_day?: number | null;
        period_year: number | null;
        period_month: number | null;
    };
    stages: Stage[];
};

export type PdfMode = { id: string; name: string };

export type ClassifierConfig = {
    model?: string;
    batch_size?: number;
    uncertain_threshold?: number;
    categories?: { id: string; name: string }[];
    [k: string]: unknown;
};

export type FileItem = { path: string; name: string; exists: boolean; size?: number };
export type StageIO = { stage_id: string; inputs: FileItem[]; outputs: FileItem[] };

export type MatchStats = {
    stage_id: string;
    matched: number;
    unmatched: number;
    total: number;
    match_rate: number;
    unmatched_reasons: { reason: string; count: number }[];
};

export type CsvPreview = {
    columns: string[];
    rows: Record<string, string>[];
    offset: number;
    limit: number;
    has_more: boolean;
    next_offset: number | null;
    prev_offset: number | null;
};

export type PdfPreview = {
    page_count: number;
};

export type ProfileListItem = {
    id: string;
    name: string;
    created_at: string;
    updated_at: string;
    bill_count: number;
};

export type ProfileBillTotals = {
    sum_amount: number;
    sum_expense: number;
    sum_income: number;
    sum_refund: number;
    sum_transfer: number;
    count: number;
    net?: number;
};

export type ProfileBill = {
    run_id: string;
    period_key: string;
    year: number | null;
    month: number | null;
    period_mode: string;
    period_day: number;
    period_start?: string;
    period_end?: string;
    period_label?: string;
    cross_month?: boolean;
    created_at: string;
    updated_at: string;
    outputs?: { summary_csv?: string; categorized_csv?: string };
    totals?: ProfileBillTotals;
    category_summary?: Record<string, string | number>[];
};

export type Profile = {
    id: string;
    name: string;
    created_at: string;
    updated_at: string;
    bills: ProfileBill[];
};

export type ProfileIntegrityIssue = {
    run_id: string;
    period_key: string;
    issue: string;
    path?: string;
};

export type ProfileIntegrityResult = {
    profile_id: string;
    ok: boolean;
    issues: ProfileIntegrityIssue[];
};

export type ReviewSeverity = "low" | "medium" | "high";

export type ReviewScope = {
    profile_id: string;
    profile_name: string;
    data_source: "profile_bills";
    year: number | null;
    months: number;
    total_bills: number;
    scoped_bills: number;
    complete_period_bills: number;
    unassigned_bills: number;
};

export type ReviewOverview = {
    total_expense: number;
    total_income: number;
    net: number;
    period_count: number;
    anomaly_count: number;
    salary_income: number;
    subsidy_income: number;
    other_income: number;
};

export type ReviewMonthlyPoint = {
    period_key: string;
    year: number;
    month: number;
    expense: number;
    income: number;
    net: number;
    tx_count: number;
    mom_expense_rate: number | null;
    yoy_expense_rate: number | null;
    salary_income: number;
    subsidy_income: number;
    other_income: number;
};

export type ReviewYearlyPoint = {
    year: number;
    expense: number;
    income: number;
    net: number;
    tx_count: number;
};

export type ReviewCategorySlice = {
    category_id: string;
    category_name: string;
    expense: number;
    income: number;
    tx_count: number;
    share_expense: number;
};

export type ReviewAnomaly = {
    code: string;
    severity: ReviewSeverity;
    title: string;
    period_key: string;
    run_id: string;
    message: string;
    value: number | null;
    baseline: number | null;
    delta_rate: number | null;
};

export type ProfileReviewResponse = {
    scope: ReviewScope;
    overview: ReviewOverview;
    monthly_points: ReviewMonthlyPoint[];
    yearly_points: ReviewYearlyPoint[];
    category_slices: ReviewCategorySlice[];
    anomalies: ReviewAnomaly[];
    integrity_issues: ProfileIntegrityIssue[];
};

export type SourceSupportItem = {
    id: string;
    name: string;
    channel: string;
    file_types: string[];
    filename_hints: string[];
    stage: string;
    parser_mode: string;
    support_level: "stable" | "beta" | "planned";
    notes: string;
};

export type ParserDetectSampleCheck = {
    index: number;
    expected_kind: string;
    detected_kind: string;
    ok: boolean;
};

export type PdfParserHealthItem = {
    mode_id: string;
    mode_name: string;
    status: "ok" | "warning" | "error";
    kinds: string[];
    filename_hints: string[];
    sample_checks: ParserDetectSampleCheck[];
    warnings: string[];
    errors: string[];
};

export type PdfParserHealthResponse = {
    summary: {
        total: number;
        ok: number;
        warning: number;
        error: number;
    };
    parsers: PdfParserHealthItem[];
};

export type CapabilitiesPayload = {
    generated_at: string;
    source_support_matrix: SourceSupportItem[];
    pdf_parser_health: PdfParserHealthResponse;
};
