"""Phase 7A: scores.json export for shields.io endpoint badge.

Q5 ruling: CI writes scores.json to gh-pages; README uses a shields.io endpoint badge.
Schema: {schemaVersion, label, message, color}
  - green  if success_delta > 0
  - yellow if success_delta == 0 or within noise (None/refused also yellow)
  - red    if success_delta < 0

This module is pure computation + serialisation — no I/O beyond what the caller
requests. It belongs in report/ (pure rendering / export layer), not store/.

Module DAG boundary: report/ does no aggregation; all numbers come from ScoreReport.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primer.eval.models import ScoreReport

# shields.io endpoint badge schema version (always 1)
SCHEMA_VERSION = 1

# Label displayed on the left half of the badge
BADGE_LABEL = "PRIMER"


def build_scores_json(report: "ScoreReport") -> dict:
    """Build the shields.io endpoint badge payload from a ScoreReport.

    Schema (Q5):
        {
            "schemaVersion": 1,
            "label":         "PRIMER",
            "message":       "<delta string>",
            "color":         "green" | "yellow" | "red"
        }

    Color rules (Q5):
        - green  : success_delta > 0
        - yellow : success_delta == 0 or None (refused / within noise)
        - red    : success_delta < 0

    Args:
        report: A fully-computed ScoreReport. No computation performed here;
                all values are read directly from the report.

    Returns:
        dict suitable for json.dumps().
    """
    delta = report.success_delta

    if delta is None:
        # Refused (provider/model mismatch) — conservative yellow
        message = "N/A (refused)"
        color = "yellow"
    elif delta > 0:
        pct = delta * 100.0
        message = f"+{pct:.1f} pp"
        color = "green"
    elif delta < 0:
        pct = delta * 100.0
        message = f"{pct:.1f} pp"
        color = "red"
    else:
        # Exactly zero
        message = "0.0 pp"
        color = "yellow"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "label": BADGE_LABEL,
        "message": message,
        "color": color,
    }


def write_scores_json(report: "ScoreReport", output_path: Path) -> dict:
    """Build and write scores.json to output_path.

    Args:
        report:      A fully-computed ScoreReport.
        output_path: Destination path (e.g. Path("scores.json") or a gh-pages dir).

    Returns:
        The payload dict that was written (for callers that want to inspect or log it).
    """
    payload = build_scores_json(report)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
