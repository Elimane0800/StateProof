#!/usr/bin/env python3
"""
Independent trigger — Module C (PDF generation). Zero LLM calls.

Usage:
    # Render with 100% mocked data, no A/B/D dependency:
    uv run scripts/run_agent_c.py --mock --output rapport_mock.pdf

    # Full pipeline from files produced by other modules:
    uv run scripts/run_agent_c.py \\
        --entry-graph entry_graph.json --exit-graph exit_graph.json \\
        --edges edges.json --score 0.87 --output rapport.pdf \\
        [--legal legal.json] [--address "12 rue de la Paix"] \\
        [--entry-date 2023-01-01] [--exit-date 2026-01-01] \\
        [--composites-dir composites/]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.Agent_C.graph import build_report, render_pdf  # noqa: E402
from agents.common.schemas import (  # noqa: E402
    AlignmentEdge,
    DetailedSection,
    Graph,
    LegalQualification,
    ReportData,
    SummaryRow,
)


def _mock_report() -> ReportData:
    return ReportData(
        property_id="appt-12",
        address="12 rue de la Paix, 75002 Paris",
        entry_date="2025-01-01",
        exit_date="2026-01-01",
        confidence_score=0.87,
        summary_rows=[
            SummaryRow(checkpoint_id="mur_nord", room="salon", status="damage", severity="high", cost_eur=45, responsibility="locataire"),
            SummaryRow(checkpoint_id="sol", room="chambre", status="normal_wear", severity="low", cost_eur=0),
            SummaryRow(checkpoint_id="prise_electrique", room="salon", status="—", severity="—", cost_eur=0, data_available=False),
        ],
        detailed_sections=[
            DetailedSection(checkpoint_id="mur_nord", room="salon", reasoning="Localized impact incompatible with normal aging.", cost_eur=45),
            DetailedSection(checkpoint_id="sol", room="chambre", reasoning="Diffuse wear consistent with occupancy duration.", cost_eur=0),
            DetailedSection(checkpoint_id="prise_electrique", room="salon", reasoning="", cost_eur=0, data_available=False),
        ],
        unchanged_checkpoints=["mur_sud", "fenetre"],
        total_cost_eur=45,
        negotiation_points=["salon / mur_nord: Localized impact incompatible with normal aging. (~45 €)"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Module C — prepare_report_data + render_pdf")
    parser.add_argument("--mock", action="store_true", help="Render with mocked data (step 3).")
    parser.add_argument("--entry-graph", default=None)
    parser.add_argument("--exit-graph", default=None)
    parser.add_argument("--edges", default=None)
    parser.add_argument("--score", type=float, default=0.0)
    parser.add_argument("--legal", default=None, help="JSON {node_id: LegalQualification}")
    parser.add_argument("--address", default=None)
    parser.add_argument("--entry-date", default=None)
    parser.add_argument("--exit-date", default=None)
    parser.add_argument("--composites-dir", default=None)
    parser.add_argument("--output", default="rapport.pdf")
    args = parser.parse_args()

    if args.mock or not (args.entry_graph and args.exit_graph and args.edges):
        if not args.mock:
            print("[Module C] Incomplete arguments (--entry-graph/--exit-graph/--edges): "
                  "smoke test with mocked report (step 3).")
        render_pdf(_mock_report(), args.output)
        print(f"[Module C] Mock PDF -> {args.output}")
        return

    entry_graph = Graph.model_validate_json(Path(args.entry_graph).read_text())
    exit_graph = Graph.model_validate_json(Path(args.exit_graph).read_text())
    edges = [AlignmentEdge.model_validate(e) for e in json.loads(Path(args.edges).read_text())]

    legal_qualifications = None
    if args.legal:
        raw_legal = json.loads(Path(args.legal).read_text())
        legal_qualifications = {k: LegalQualification.model_validate(v) for k, v in raw_legal.items()}

    build_report(
        entry_graph, exit_graph, edges, args.score, args.output,
        legal_qualifications=legal_qualifications,
        address=args.address, entry_date=args.entry_date, exit_date=args.exit_date,
        composites_dir=args.composites_dir,
    )
    print(f"[Module C] Report -> {args.output}")


if __name__ == "__main__":
    main()
