from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_rows(paths: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw in paths:
        path = Path(raw).expanduser()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            for item in payload:
                item = dict(item)
                item["_source"] = str(path)
                rows.append(item)
        elif isinstance(payload, dict):
            item = dict(payload)
            item["_source"] = str(path)
            rows.append(item)
        else:
            raise ValueError(f"Unsupported payload type in {path}")
    return rows


def _score_aggregate(aggregate: dict[str, object]) -> float:
    avg_sharpe = float(aggregate.get("avg_sharpe", 0.0))
    pass_rate = float(aggregate.get("pass_rate", 0.0))
    avg_drawdown = float(aggregate.get("avg_max_drawdown", 1.0))
    avg_trade_rate = float(aggregate.get("avg_trade_rate_1k", 0.0))
    score = avg_sharpe
    score += 0.1 * pass_rate
    score -= 0.1 * max(0.0, avg_drawdown - 0.15)
    if avg_trade_rate < 5.0:
        score -= 0.05
    if avg_trade_rate > 120.0:
        score -= 0.05
    return score


def _pick_best(rows: list[dict[str, object]]) -> dict[str, object] | None:
    best = None
    best_score = float("-inf")
    for row in rows:
        aggregate = row.get("aggregate")
        if not isinstance(aggregate, dict):
            continue
        score = _score_aggregate(aggregate)
        if score > best_score:
            best_score = score
            best = row
    return best


def _readiness(
    best_heuristic: dict[str, object] | None,
    best_supervised: dict[str, object] | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    verdict = "STOP"
    candidates = [item for item in (best_heuristic, best_supervised) if item]
    if not candidates:
        reasons.append("No valid baseline aggregates were provided.")
        return verdict, reasons
    best_sharpe = max(
        float(item["aggregate"]["avg_sharpe"])
        for item in candidates
        if isinstance(item.get("aggregate"), dict)
    )
    best_pass_rate = max(
        float(item["aggregate"]["pass_rate"])
        for item in candidates
        if isinstance(item.get("aggregate"), dict)
    )
    best_drawdown = min(
        float(item["aggregate"]["avg_max_drawdown"])
        for item in candidates
        if isinstance(item.get("aggregate"), dict)
    )
    if best_sharpe < 0.05:
        reasons.append(f"Best baseline avg_sharpe is only {best_sharpe:.4f}.")
    if best_pass_rate < 0.34:
        reasons.append(f"Best baseline pass_rate is only {best_pass_rate:.2f}.")
    if best_drawdown > 0.15:
        reasons.append(
            "No baseline keeps average max drawdown under 15% "
            f"(best {best_drawdown:.4f})."
        )
    if best_sharpe >= 0.05 and best_pass_rate >= 0.34 and best_drawdown <= 0.15:
        verdict = "GO"
        reasons.append("At least one baseline clears the minimum readiness thresholds.")
    else:
        reasons.append("Current evidence does not justify advancing to RL.")
    return verdict, reasons


def _format_candidate(title: str, row: dict[str, object] | None) -> list[str]:
    if row is None:
        return [f"## {title}", "", "No candidate."]
    aggregate = dict(row.get("aggregate", {}))
    strategy = row.get("strategy", "-")
    session = row.get("session", "-")
    source = row.get("_source", "-")
    return [
        f"## {title}",
        "",
        f"- strategy: `{strategy}`",
        f"- session: `{session}`",
        f"- source: `{source}`",
        f"- avg_return: `{float(aggregate.get('avg_return', 0.0)):.6f}`",
        f"- avg_sharpe: `{float(aggregate.get('avg_sharpe', 0.0)):.6f}`",
        f"- avg_max_drawdown: `{float(aggregate.get('avg_max_drawdown', 0.0)):.6f}`",
        f"- avg_trade_rate_1k: `{float(aggregate.get('avg_trade_rate_1k', 0.0)):.2f}`",
        f"- pass_rate: `{float(aggregate.get('pass_rate', 0.0)):.2f}`",
    ]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize heuristic/supervised baseline outputs "
            "into an RL readiness verdict."
        )
    )
    parser.add_argument(
        "--heuristic-json",
        action="append",
        default=[],
        help="Heuristic baseline JSON output path. Repeatable.",
    )
    parser.add_argument(
        "--supervised-json",
        action="append",
        default=[],
        help="Supervised baseline JSON output path. Repeatable.",
    )
    parser.add_argument("--markdown-out", default="", help="Optional markdown report output path.")
    parser.add_argument("--json-out", default="", help="Optional JSON summary output path.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    heuristic_rows = _load_rows(list(args.heuristic_json))
    supervised_rows = _load_rows(list(args.supervised_json))
    best_heuristic = _pick_best(heuristic_rows)
    best_supervised = _pick_best(supervised_rows)
    verdict, reasons = _readiness(best_heuristic, best_supervised)

    summary = {
        "verdict": verdict,
        "reasons": reasons,
        "best_heuristic": best_heuristic,
        "best_supervised": best_supervised,
    }

    print("Verdict:", verdict)
    for reason in reasons:
        print("-", reason)

    markdown_lines = [
        "# Research Readiness Report",
        "",
        "## Verdict",
        "",
        f"`{verdict}`",
        "",
        "## Reasons",
        "",
    ]
    markdown_lines.extend([f"- {reason}" for reason in reasons])
    markdown_lines.append("")
    markdown_lines.extend(_format_candidate("Best Heuristic", best_heuristic))
    markdown_lines.append("")
    markdown_lines.extend(_format_candidate("Best Supervised", best_supervised))
    markdown = "\n".join(markdown_lines) + "\n"

    if args.markdown_out.strip():
        out = Path(args.markdown_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    if args.json_out.strip():
        out = Path(args.json_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
