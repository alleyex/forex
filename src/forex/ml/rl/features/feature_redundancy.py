from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from forex.ml.rl.features.feature_snr import compute_feature_snr_report


def _connected_components(edges: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    groups: list[list[str]] = []
    for node in sorted(edges):
        if node in seen:
            continue
        stack = [node]
        members: list[str] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            members.append(current)
            stack.extend(sorted(edges.get(current, set()) - seen))
        groups.append(sorted(members))
    return groups


def compute_feature_redundancy_report(
    features: pd.DataFrame,
    closes: Sequence[float] | np.ndarray | pd.Series,
    *,
    horizons: Sequence[int] = (1, 5, 20),
    quantile: float = 0.2,
    min_samples: int = 50,
    corr_threshold: float = 0.90,
    noise_quantile: float = 0.35,
) -> dict[str, object]:
    if features.empty:
        return {
            "rows": 0,
            "feature_count": 0,
            "corr_threshold": float(corr_threshold),
            "noise_quantile": float(noise_quantile),
            "pair_rows": [],
            "feature_rows": [],
            "redundancy_groups": [],
            "redundant_candidates": [],
            "noise_candidates": [],
            "snr_report": compute_feature_snr_report(
                features,
                closes,
                horizons=horizons,
                quantile=quantile,
                min_samples=min_samples,
            ),
        }

    if not 0.0 < float(corr_threshold) < 1.0:
        raise ValueError("corr_threshold must be in (0, 1).")
    if not 0.0 < float(noise_quantile) < 1.0:
        raise ValueError("noise_quantile must be in (0, 1).")

    feature_frame = features.reset_index(drop=True).copy()
    snr_report = compute_feature_snr_report(
        feature_frame,
        closes,
        horizons=horizons,
        quantile=quantile,
        min_samples=min_samples,
    )
    summary_map = {str(row["feature"]): dict(row) for row in snr_report["feature_summary"]}

    corr_matrix = (
        feature_frame.corr(method="spearman", numeric_only=True)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    names = list(corr_matrix.columns)
    edges: dict[str, set[str]] = {name: set() for name in names}
    pair_rows: list[dict[str, object]] = []
    pair_lookup: dict[tuple[str, str], dict[str, object]] = {}

    for idx, left in enumerate(names):
        left_score = float(summary_map.get(left, {}).get("summary_score", 0.0))
        for jdx in range(idx + 1, len(names)):
            right = names[jdx]
            right_score = float(summary_map.get(right, {}).get("summary_score", 0.0))
            spearman = float(corr_matrix.iloc[idx, jdx])
            abs_spearman = abs(spearman)
            if abs_spearman >= float(corr_threshold):
                edges[left].add(right)
                edges[right].add(left)
            better_feature = left if left_score >= right_score else right
            row = {
                "feature_a": left,
                "feature_b": right,
                "spearman": float(spearman),
                "abs_spearman": float(abs_spearman),
                "score_a": float(left_score),
                "score_b": float(right_score),
                "better_feature": better_feature,
                "passes_threshold": bool(abs_spearman >= float(corr_threshold)),
            }
            pair_rows.append(row)
            pair_lookup[(left, right)] = row
            pair_lookup[(right, left)] = row

    feature_rows: list[dict[str, object]] = []
    for name in names:
        peers = [
            row
            for row in pair_rows
            if str(row["feature_a"]) == name or str(row["feature_b"]) == name
        ]
        max_pair = max(peers, key=lambda row: float(row["abs_spearman"]), default=None)
        stronger_peer = next(
            (
                row
                for row in sorted(peers, key=lambda item: float(item["abs_spearman"]), reverse=True)
                if bool(row["passes_threshold"])
                and str(row["better_feature"]) != name
            ),
            None,
        )
        feature_row = {
            "feature": name,
            "summary_score": float(summary_map.get(name, {}).get("summary_score", 0.0)),
            "avg_abs_ic": float(summary_map.get(name, {}).get("avg_abs_ic", 0.0)),
            "avg_abs_rank_ic": float(summary_map.get(name, {}).get("avg_abs_rank_ic", 0.0)),
            "avg_sign_sharpe": float(summary_map.get(name, {}).get("avg_sign_sharpe", 0.0)),
            "valid_horizons": int(summary_map.get(name, {}).get("valid_horizons", 0)),
            "max_abs_spearman": (
                float(max_pair["abs_spearman"]) if max_pair is not None else 0.0
            ),
            "most_similar_feature": (
                str(max_pair["feature_b"])
                if str(max_pair["feature_a"]) == name
                else str(max_pair["feature_a"])
            )
            if max_pair is not None
            else "",
            "stronger_correlated_feature": (
                str(stronger_peer["feature_b"])
                if str(stronger_peer["feature_a"]) == name
                else str(stronger_peer["feature_a"])
            )
            if stronger_peer is not None
            else "",
        }
        feature_rows.append(feature_row)

    groups = _connected_components(edges)
    redundancy_groups: list[dict[str, object]] = []
    redundant_candidates: list[dict[str, object]] = []
    feature_to_group: dict[str, int] = {}
    representatives: dict[str, str] = {}

    grouped_feature_rows = {str(row["feature"]): row for row in feature_rows}
    next_group_id = 1
    for members in groups:
        if len(members) <= 1:
            continue
        ranked_members = sorted(
            members,
            key=lambda name: (
                float(grouped_feature_rows.get(name, {}).get("summary_score", 0.0)),
                float(grouped_feature_rows.get(name, {}).get("avg_abs_rank_ic", 0.0)),
            ),
            reverse=True,
        )
        representative = ranked_members[0]
        group_members: list[dict[str, object]] = []
        for name in ranked_members:
            feature_to_group[name] = next_group_id
            representatives[name] = representative
            if name == representative:
                corr_to_rep = 1.0
            else:
                corr_to_rep = float(pair_lookup[(name, representative)]["abs_spearman"])
                redundant_candidates.append(
                    {
                        "feature": name,
                        "representative": representative,
                        "group_id": next_group_id,
                        "abs_spearman_to_representative": float(corr_to_rep),
                        "summary_score": float(grouped_feature_rows[name]["summary_score"]),
                        "representative_score": float(
                            grouped_feature_rows[representative]["summary_score"]
                        ),
                        "score_gap": float(
                            grouped_feature_rows[representative]["summary_score"]
                            - grouped_feature_rows[name]["summary_score"]
                        ),
                    }
                )
            group_members.append(
                {
                    "feature": name,
                    "summary_score": float(grouped_feature_rows[name]["summary_score"]),
                    "avg_abs_rank_ic": float(grouped_feature_rows[name]["avg_abs_rank_ic"]),
                    "abs_spearman_to_representative": float(corr_to_rep),
                }
            )
        redundancy_groups.append(
            {
                "group_id": next_group_id,
                "size": len(ranked_members),
                "representative": representative,
                "members": group_members,
            }
        )
        next_group_id += 1

    for row in feature_rows:
        row["group_id"] = int(feature_to_group.get(str(row["feature"]), 0))
        row["representative"] = representatives.get(str(row["feature"]), str(row["feature"]))

    scores = np.asarray([float(row["summary_score"]) for row in feature_rows], dtype=np.float64)
    rank_ics = np.asarray([float(row["avg_abs_rank_ic"]) for row in feature_rows], dtype=np.float64)
    score_cutoff = float(np.quantile(scores, float(noise_quantile))) if len(scores) else 0.0
    rank_ic_cutoff = float(np.quantile(rank_ics, float(noise_quantile))) if len(rank_ics) else 0.0

    noise_candidates: list[dict[str, object]] = []
    for row in sorted(feature_rows, key=lambda item: float(item["summary_score"])):
        feature_name = str(row["feature"])
        reasons: list[str] = []
        if float(row["summary_score"]) <= score_cutoff:
            reasons.append("low_summary_score")
        if float(row["avg_abs_rank_ic"]) <= rank_ic_cutoff:
            reasons.append("low_rank_ic")
        stronger_feature = str(row["stronger_correlated_feature"]).strip()
        if stronger_feature:
            reasons.append("redundant_to_stronger_feature")
        if not reasons:
            continue
        if "low_summary_score" not in reasons and "low_rank_ic" not in reasons:
            continue
        noise_candidates.append(
            {
                "feature": feature_name,
                "reasons": reasons,
                "summary_score": float(row["summary_score"]),
                "avg_abs_rank_ic": float(row["avg_abs_rank_ic"]),
                "max_abs_spearman": float(row["max_abs_spearman"]),
                "most_similar_feature": str(row["most_similar_feature"]),
                "stronger_correlated_feature": stronger_feature,
                "group_id": int(row["group_id"]),
                "representative": str(row["representative"]),
            }
        )

    pair_rows.sort(key=lambda row: float(row["abs_spearman"]), reverse=True)
    redundant_candidates.sort(
        key=lambda row: (
            float(row["abs_spearman_to_representative"]),
            -float(row["score_gap"]),
        ),
        reverse=True,
    )
    noise_candidates.sort(key=lambda row: float(row["summary_score"]))

    return {
        "rows": int(len(feature_frame)),
        "feature_count": int(feature_frame.shape[1]),
        "corr_threshold": float(corr_threshold),
        "noise_quantile": float(noise_quantile),
        "score_cutoff": float(score_cutoff),
        "rank_ic_cutoff": float(rank_ic_cutoff),
        "pair_rows": pair_rows,
        "feature_rows": feature_rows,
        "redundancy_groups": redundancy_groups,
        "redundant_candidates": redundant_candidates,
        "noise_candidates": noise_candidates,
        "snr_report": snr_report,
    }
