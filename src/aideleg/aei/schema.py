"""Long-format panel schema shared by every AEI release parser.

AEI data are conversations matched to O*NET tasks; nothing here says anything about jobs.
"""

import re

PANEL_COLUMNS = [
    "release", "period_start", "period_end", "source", "geo_level", "geo_id",
    "taxonomy", "level", "node_id", "node_name", "metric", "value", "definition",
]

TAXONOMIES = {
    "overall", "onet_task", "onet_dwa", "onet_iwa", "onet_gwa",
    "soc_detailed", "soc_major", "request",
}

CANONICAL_METRICS = frozenset({
    "usage_pct", "pct", "automation_pct", "augmentation_pct", "directive_pct",
    "feedback_loop_pct", "task_iteration_pct", "validation_pct", "learning_pct",
    "none_pct", "filtered_pct", "not_classified_pct", "ai_autonomy_mean",
    "human_education_years_mean", "ai_education_years_mean", "human_only_time_mean",
    "human_with_ai_time_mean", "human_only_ability_pct", "use_case_work_pct",
    "use_case_personal_pct", "use_case_coursework_pct", "multitasking_pct",
    "usage_per_capita_index", "count",
})

_ARTIFACT = re.compile(r"artifact_[a-z_]+_pct")


def is_canonical(metric: str) -> bool:
    """True for a canonical metric or an `artifact_<label>_pct` metric (release r6)."""
    return metric in CANONICAL_METRICS or _ARTIFACT.fullmatch(metric) is not None
