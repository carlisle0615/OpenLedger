from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def _dedupe_columns(columns: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in columns:
        col = str(raw).strip()
        if not col or col in seen:
            continue
        seen.add(col)
        out.append(col)
    return tuple(out)


def merge_columns(*groups: Iterable[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw in group:
            col = str(raw).strip()
            if not col or col in seen:
                continue
            seen.add(col)
            merged.append(col)
    return merged


@dataclass(frozen=True)
class TabularContract:
    artifact_id: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...] = ()
    allow_extra_columns: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        req = _dedupe_columns(self.required_columns)
        opt = tuple(c for c in _dedupe_columns(self.optional_columns) if c not in req)
        object.__setattr__(self, "required_columns", req)
        object.__setattr__(self, "optional_columns", opt)

    @property
    def all_columns(self) -> tuple[str, ...]:
        return self.required_columns + self.optional_columns

    def missing_required(self, columns: Sequence[str]) -> tuple[str, ...]:
        present = {str(c).strip() for c in columns if str(c).strip()}
        return tuple(c for c in self.required_columns if c not in present)


@dataclass(frozen=True)
class StageContract:
    stage_id: str
    input_artifacts: tuple[str, ...]
    output_artifacts: tuple[str, ...]


# =========
# Artifact IDs
# =========
ART_TX_CREDIT_CARD = "tx.credit_card.csv"
ART_TX_BANK = "tx.bank_statement.csv"
ART_WECHAT_NORMALIZED = "wechat.normalized.csv"
ART_ALIPAY_NORMALIZED = "alipay.normalized.csv"

ART_CC_ENRICHED = "credit_card.enriched.csv"
ART_CC_UNMATCHED = "credit_card.unmatched.csv"
ART_CC_MATCH_DEBUG = "credit_card.match_debug.csv"

ART_BANK_ENRICHED = "bank.enriched.csv"
ART_BANK_UNMATCHED = "bank.unmatched.csv"
ART_BANK_MATCH_DEBUG = "bank.match_debug.csv"

ART_UNIFIED_TX = "unified.transactions.csv"
ART_UNIFIED_WITH_ID = "classify/unified.with_id.csv"
ART_REVIEW = "classify/review.csv"

ART_CATEGORIZED_TX = "unified.transactions.categorized.csv"
ART_CATEGORY_SUMMARY = "category.summary.csv"
ART_PENDING_REVIEW = "pending_review.csv"


# =========
# Column Contracts
# =========

COLUMNS_TX_CREDIT_CARD = (
    "source",
    "section",
    "trans_date",
    "post_date",
    "description",
    "amount_rmb",
    "card_last4",
    "original_amount",
    "original_region",
)

COLUMNS_TX_BANK = (
    "source",
    "account_last4",
    "trans_date",
    "currency",
    "amount",
    "balance",
    "summary",
    "counterparty",
)

COLUMNS_WECHAT_NORMALIZED = (
    "channel",
    "trans_time",
    "trans_date",
    "trans_type",
    "counterparty",
    "item",
    "direction",
    "amount",
    "pay_method",
    "status",
    "trade_no",
    "merchant_no",
    "remark",
)

COLUMNS_ALIPAY_NORMALIZED = (
    "channel",
    "trans_time",
    "trans_date",
    "category",
    "counterparty",
    "counterparty_account",
    "item",
    "direction",
    "amount",
    "pay_method",
    "status",
    "trade_no",
    "merchant_no",
    "remark",
)

COLUMNS_CC_ENRICHED_EXTRA = (
    "match_status",
    "match_method",
    "match_sources",
    "detail_channel",
    "detail_trans_time",
    "detail_trans_date",
    "detail_direction",
    "detail_counterparty",
    "detail_item",
    "detail_pay_method",
    "detail_trade_no",
    "detail_merchant_no",
    "detail_status",
    "detail_category_or_type",
    "detail_remark",
    "match_date_diff_days",
    "match_direction_penalty",
    "match_text_similarity",
    "match_confidence",
)

COLUMNS_CC_UNMATCHED_EXTRA = (
    "match_status",
    "match_channels_tried",
    "match_method",
    "match_confidence",
)

COLUMNS_CC_MATCH_DEBUG = (
    "row_index",
    "section",
    "trans_date",
    "post_date",
    "amount_rmb",
    "card_last4",
    "description",
    "channels_tried",
    "base_date",
    "date_window",
    "candidate_count_exact",
    "candidate_count_sum",
    "candidate_count_fuzzy",
    "best_date_diff_days",
    "best_direction_penalty",
    "best_text_similarity",
    "best_amount_diff",
    "match_method",
    "match_status",
    "match_confidence",
    "chosen_count",
    "chosen_channels",
    "match_sources",
    "chosen_trade_no",
    "chosen_merchant_no",
)

COLUMNS_BANK_ENRICHED_EXTRA = (
    "match_status",
    "match_method",
    "match_sources",
    "detail_channel",
    "detail_trans_time",
    "detail_trans_date",
    "detail_direction",
    "detail_counterparty",
    "detail_item",
    "detail_pay_method",
    "detail_trade_no",
    "detail_merchant_no",
    "detail_status",
    "detail_category_or_type",
    "detail_remark",
    "match_date_diff_days",
    "match_direction_penalty",
    "match_text_similarity",
    "match_confidence",
)

COLUMNS_BANK_UNMATCHED_EXTRA = (
    "match_status",
    "match_method",
    "match_confidence",
)

COLUMNS_BANK_MATCH_DEBUG = (
    "row_index",
    "account_last4",
    "trans_date",
    "amount",
    "summary",
    "counterparty",
    "date_window",
    "candidate_count_exact",
    "candidate_count_sum",
    "candidate_count_fuzzy",
    "best_date_diff_days",
    "best_direction_penalty",
    "best_text_similarity",
    "best_amount_diff",
    "match_method",
    "match_status",
    "match_confidence",
    "chosen_count",
    "chosen_channels",
    "match_sources",
    "chosen_trade_no",
    "chosen_merchant_no",
)

COLUMNS_UNIFIED_TX = (
    "trade_time",
    "trade_date",
    "post_date",
    "account",
    "currency",
    "amount",
    "amount_abs",
    "flow",
    "merchant",
    "item",
    "category",
    "pay_method",
    "primary_source",
    "sources",
    "match_status",
    "match_group_id",
    "remark",
)

COLUMNS_REVIEW_REQUIRED = (
    "txn_id",
    "suggested_category_id",
    "suggested_uncertain",
    "suggested_confidence",
    "suggested_note",
    "final_category_id",
    "final_note",
)

COLUMNS_REVIEW_OPTIONAL = (
    "suggested_category_name",
    "suggested_ignored",
    "suggested_ignore_reason",
    "suggested_source",
    "suggested_rule_id",
    "final_ignored",
    "final_ignore_reason",
)

COLUMNS_CATEGORIZED_REQUIRED = (
    "txn_id",
    "category_id",
    "category_name",
    "category_source",
    "category_confidence",
    "category_uncertain",
    "category_note",
    "ignored",
    "ignore_reason",
)

COLUMNS_CATEGORY_SUMMARY = (
    "category_id",
    "category_name",
    "count",
    "sum_amount",
    "sum_expense",
    "sum_income",
    "sum_refund",
    "sum_transfer",
)


TABLE_CONTRACTS: dict[str, TabularContract] = {
    ART_TX_CREDIT_CARD: TabularContract(
        artifact_id=ART_TX_CREDIT_CARD,
        required_columns=COLUMNS_TX_CREDIT_CARD,
        allow_extra_columns=True,
        description="extract_pdf 产出的信用卡交易 CSV",
    ),
    ART_TX_BANK: TabularContract(
        artifact_id=ART_TX_BANK,
        required_columns=COLUMNS_TX_BANK,
        allow_extra_columns=True,
        description="extract_pdf 产出的借记卡流水 CSV",
    ),
    ART_WECHAT_NORMALIZED: TabularContract(
        artifact_id=ART_WECHAT_NORMALIZED,
        required_columns=COLUMNS_WECHAT_NORMALIZED,
        allow_extra_columns=False,
        description="extract_exports 产出的微信标准化 CSV",
    ),
    ART_ALIPAY_NORMALIZED: TabularContract(
        artifact_id=ART_ALIPAY_NORMALIZED,
        required_columns=COLUMNS_ALIPAY_NORMALIZED,
        allow_extra_columns=False,
        description="extract_exports 产出的支付宝标准化 CSV",
    ),
    ART_CC_ENRICHED: TabularContract(
        artifact_id=ART_CC_ENRICHED,
        required_columns=merge_columns(COLUMNS_TX_CREDIT_CARD, COLUMNS_CC_ENRICHED_EXTRA),
        allow_extra_columns=True,
        description="match_credit_card 产出的已匹配结果",
    ),
    ART_CC_UNMATCHED: TabularContract(
        artifact_id=ART_CC_UNMATCHED,
        required_columns=merge_columns(COLUMNS_TX_CREDIT_CARD, COLUMNS_CC_UNMATCHED_EXTRA),
        allow_extra_columns=True,
        description="match_credit_card 产出的未匹配结果",
    ),
    ART_CC_MATCH_DEBUG: TabularContract(
        artifact_id=ART_CC_MATCH_DEBUG,
        required_columns=COLUMNS_CC_MATCH_DEBUG,
        allow_extra_columns=False,
        description="match_credit_card 调试明细",
    ),
    ART_BANK_ENRICHED: TabularContract(
        artifact_id=ART_BANK_ENRICHED,
        required_columns=merge_columns(COLUMNS_TX_BANK, COLUMNS_BANK_ENRICHED_EXTRA),
        allow_extra_columns=True,
        description="match_bank 产出的已匹配结果",
    ),
    ART_BANK_UNMATCHED: TabularContract(
        artifact_id=ART_BANK_UNMATCHED,
        required_columns=merge_columns(COLUMNS_TX_BANK, COLUMNS_BANK_UNMATCHED_EXTRA),
        allow_extra_columns=True,
        description="match_bank 产出的未匹配结果",
    ),
    ART_BANK_MATCH_DEBUG: TabularContract(
        artifact_id=ART_BANK_MATCH_DEBUG,
        required_columns=COLUMNS_BANK_MATCH_DEBUG,
        allow_extra_columns=False,
        description="match_bank 调试明细",
    ),
    ART_UNIFIED_TX: TabularContract(
        artifact_id=ART_UNIFIED_TX,
        required_columns=COLUMNS_UNIFIED_TX,
        allow_extra_columns=False,
        description="build_unified 产出的统一交易表",
    ),
    ART_UNIFIED_WITH_ID: TabularContract(
        artifact_id=ART_UNIFIED_WITH_ID,
        required_columns=("txn_id",),
        optional_columns=COLUMNS_UNIFIED_TX,
        allow_extra_columns=True,
        description="classify 产出的带 txn_id 交易表",
    ),
    ART_REVIEW: TabularContract(
        artifact_id=ART_REVIEW,
        required_columns=COLUMNS_REVIEW_REQUIRED,
        optional_columns=COLUMNS_REVIEW_OPTIONAL,
        allow_extra_columns=True,
        description="classify 产出的审核表",
    ),
    ART_CATEGORIZED_TX: TabularContract(
        artifact_id=ART_CATEGORIZED_TX,
        required_columns=COLUMNS_CATEGORIZED_REQUIRED,
        optional_columns=merge_columns(COLUMNS_UNIFIED_TX, COLUMNS_REVIEW_OPTIONAL),
        allow_extra_columns=True,
        description="finalize 产出的分类明细",
    ),
    ART_CATEGORY_SUMMARY: TabularContract(
        artifact_id=ART_CATEGORY_SUMMARY,
        required_columns=COLUMNS_CATEGORY_SUMMARY,
        allow_extra_columns=False,
        description="finalize 产出的分类汇总",
    ),
    ART_PENDING_REVIEW: TabularContract(
        artifact_id=ART_PENDING_REVIEW,
        required_columns=COLUMNS_REVIEW_REQUIRED,
        optional_columns=merge_columns(
            COLUMNS_REVIEW_OPTIONAL,
            ("category_id", "invalid_category_bool", "invalid_category_id"),
        ),
        allow_extra_columns=True,
        description="finalize 产出的待复核清单",
    ),
}


STAGE_CONTRACTS: dict[str, StageContract] = {
    "extract_pdf": StageContract(
        stage_id="extract_pdf",
        input_artifacts=(),
        output_artifacts=(ART_TX_CREDIT_CARD, ART_TX_BANK),
    ),
    "extract_exports": StageContract(
        stage_id="extract_exports",
        input_artifacts=(),
        output_artifacts=(ART_WECHAT_NORMALIZED, ART_ALIPAY_NORMALIZED),
    ),
    "match_credit_card": StageContract(
        stage_id="match_credit_card",
        input_artifacts=(ART_TX_CREDIT_CARD, ART_WECHAT_NORMALIZED, ART_ALIPAY_NORMALIZED),
        output_artifacts=(ART_CC_ENRICHED, ART_CC_UNMATCHED, ART_CC_MATCH_DEBUG),
    ),
    "match_bank": StageContract(
        stage_id="match_bank",
        input_artifacts=(ART_TX_BANK, ART_WECHAT_NORMALIZED, ART_ALIPAY_NORMALIZED),
        output_artifacts=(ART_BANK_ENRICHED, ART_BANK_UNMATCHED, ART_BANK_MATCH_DEBUG),
    ),
    "build_unified": StageContract(
        stage_id="build_unified",
        input_artifacts=(
            ART_CC_ENRICHED,
            ART_CC_UNMATCHED,
            ART_BANK_ENRICHED,
            ART_BANK_UNMATCHED,
            ART_WECHAT_NORMALIZED,
            ART_ALIPAY_NORMALIZED,
        ),
        output_artifacts=(ART_UNIFIED_TX,),
    ),
    "classify": StageContract(
        stage_id="classify",
        input_artifacts=(ART_UNIFIED_TX,),
        output_artifacts=(ART_UNIFIED_WITH_ID, ART_REVIEW),
    ),
    "finalize": StageContract(
        stage_id="finalize",
        input_artifacts=(ART_UNIFIED_WITH_ID, ART_REVIEW),
        output_artifacts=(ART_CATEGORIZED_TX, ART_CATEGORY_SUMMARY, ART_PENDING_REVIEW),
    ),
}


def get_table_contract(artifact_id: str) -> TabularContract:
    if artifact_id not in TABLE_CONTRACTS:
        known = ", ".join(sorted(TABLE_CONTRACTS.keys()))
        raise KeyError(f"未知 artifact contract: {artifact_id}（已知: {known}）")
    return TABLE_CONTRACTS[artifact_id]


def get_stage_contract(stage_id: str) -> StageContract:
    if stage_id not in STAGE_CONTRACTS:
        known = ", ".join(sorted(STAGE_CONTRACTS.keys()))
        raise KeyError(f"未知 stage contract: {stage_id}（已知: {known}）")
    return STAGE_CONTRACTS[stage_id]


def table_columns(artifact_id: str) -> list[str]:
    return list(get_table_contract(artifact_id).all_columns)


def required_columns(artifact_id: str) -> list[str]:
    return list(get_table_contract(artifact_id).required_columns)


def merge_with_contract_columns(base_columns: Sequence[str], artifact_id: str) -> list[str]:
    return merge_columns(base_columns, get_table_contract(artifact_id).all_columns)


def assert_required_columns(
    columns: Sequence[str],
    artifact_id: str,
    *,
    stage_id: str,
    file_path: str | None = None,
) -> None:
    contract = get_table_contract(artifact_id)
    missing = contract.missing_required(columns)
    if not missing:
        return
    target = file_path or artifact_id
    raise ValueError(
        f"[{stage_id}] {target} 不符合字段契约 {artifact_id}；缺少列: {list(missing)}；"
        f"实际列: {list(columns)}"
    )
