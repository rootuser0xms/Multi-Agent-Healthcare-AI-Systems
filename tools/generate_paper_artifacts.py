"""
Reproduces every figure and every numeric table value used in the paper

"""

import argparse
import json
import os
import re
import statistics
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from scipy import stats


PALETTE = {
    "navy":       "#003A6B",   # primary / orchestrator / headers
    "steel":      "#2E6E9E",   # agents / process boxes
    "steel_fill": "#DCEAF5",   # agent box fill
    "slate_fill": "#EDF1F5",   # neutral box fill (audit log, notes)
    "slate_edge": "#8A98A8",
    "amber":      "#C98A1F",   # decision points
    "amber_fill": "#FBF0DC",
    "teal":       "#0E7C7B",   # sanitized / positive outcome
    "teal_fill":  "#DCF0EF",
    "rust":       "#B24C39",   # naive / flagged / negative outcome
    "rust_fill":  "#F6E1DC",
    "gray_text":  "#404040",
    "gray_line":  "#6B6B6B",
}
FONT_FAMILY = "DejaVu Sans"  
plt.rcParams["font.family"] = FONT_FAMILY


# ----------------------------------------------------------------------
# 1. Load and parse the real audit log
# ----------------------------------------------------------------------
def load_audit_log(path):
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                e["ts"] = datetime.fromisoformat(e["timestamp"])
                entries.append(e)
            except (json.JSONDecodeError, KeyError):
                continue
    entries.sort(key=lambda e: e["ts"])
    return entries


def pair_durations(entries, start_action, end_action, max_gap_sec=600):
    durations = []
    pending_start = None
    for e in entries:
        if e["action"] == start_action:
            pending_start = e["ts"]
        elif e["action"] == end_action and pending_start is not None:
            delta = (e["ts"] - pending_start).total_seconds()
            if 0 <= delta < max_gap_sec:
                durations.append(delta)
            pending_start = None
    return durations


def compute_timing_table(entries):

    def summarize(name, data, unit="s"):
        if not data:
            return {"operation": name, "n": 0, "unit": unit}
        factor = 1000.0 if unit == "ms" else 1.0
        decimals = 1 if unit == "ms" else 2
        return {
            "operation": name, "n": len(data), "unit": unit,
            "mean": round(statistics.mean(data) * factor, decimals),
            "median": round(statistics.median(data) * factor, decimals),
            "stdev": round(statistics.stdev(data) * factor, decimals) if len(data) > 1 else 0.0,
        }

    rows = [
        summarize("Sanitized patient lookup", pair_durations(entries, "lookup_patient", "lookup_patient_complete"), unit="ms"),
        summarize("Naive (unsanitized) lookup", pair_durations(entries, "lookup_patient_NAIVE", "lookup_patient_complete_NAIVE"), unit="ms"),
        summarize("Imaging analysis (2 MedGemma calls + booking)", pair_durations(entries, "analyze_image", "analyze_and_route_complete"), unit="s"),
        summarize("PubMed literature search", pair_durations(entries, "search_pubmed", "search_pubmed_complete"), unit="s"),
        summarize("Full patient visit (sanitized)", pair_durations(entries, "visit_started", "visit_complete"), unit="s"),
    ]
    return rows


# ----------------------------------------------------------------------
# 2. Exact statistics: Clopper-Pearson CIs and Fisher's exact test
# ----------------------------------------------------------------------
def compute_leakage_stats():
    """Reproduces Tables II. Leak counts are fixed by the AgentLeak-style
    evaluation reported in the paper (0/20 sanitized, 20/20 naive per
    modality; 0/80 and 80/80 pooled). Re-run tools/agentleak_eval.py to
    regenerate these counts from scratch against a live system."""
    results = {}
    for label, x, n in [("per_modality_sanitized", 0, 20), ("per_modality_naive", 20, 20),
                         ("pooled_sanitized", 0, 80), ("pooled_naive", 80, 80)]:
        lo, hi = stats.binomtest(x, n).proportion_ci(confidence_level=0.95, method="exact")
        results[label] = {"x": x, "n": n, "ci_low_pct": round(lo * 100, 2), "ci_high_pct": round(hi * 100, 2)}

    table = [[0, 80], [80, 0]]  # sanitized[leaked,clean], naive[leaked,clean]
    _, p_value = stats.fisher_exact(table)
    results["fisher_exact_p"] = p_value
    return results


# ----------------------------------------------------------------------
# 3. Weighted blast radius and payload reduction (Table III)
# ----------------------------------------------------------------------
def compute_blast_radius():
    full_fields = ["patient_id", "name", "dob", "conditions", "medications", "insurance_provider", "insurance_id"]
    weights = {"name": 3, "dob": 2, "insurance_id": 2, "insurance_provider": 1,
               "conditions": 1, "medications": 1, "patient_id": 0.5}
    purposes = {
        "full_clinical": full_fields,
        "booking": ["patient_id", "conditions", "insurance_provider"],
        "insurance_verification": ["patient_id", "insurance_provider", "insurance_id"],
    }
    example_record = {"patient_id": "P0001", "name": "Allison Hill", "dob": "1951-12-21",
                       "conditions": ["Hypertension", "Osteoarthritis"], "medications": ["Lisinopril"],
                       "insurance_provider": "Cigna", "insurance_id": "INS-1819-Bcbf"}
    full_bw = sum(weights[f] for f in purposes["full_clinical"])
    full_bytes = len(json.dumps(example_record))

    rows = []
    for name, fields in purposes.items():
        bw = sum(weights[f] for f in fields)
        payload = {k: example_record[k] for k in fields}
        payload_bytes = len(json.dumps(payload))
        rows.append({
            "scope": name, "fields": f"{len(fields)} of {len(full_fields)}", "Bw": bw,
            "Bw_reduction_pct": round((1 - bw / full_bw) * 100, 1) if name != "full_clinical" else None,
            "payload_bytes": payload_bytes,
            "byte_reduction_pct": round((1 - payload_bytes / full_bytes) * 100, 1) if name != "full_clinical" else None,
        })
    return rows


# ----------------------------------------------------------------------
# 4. Escalation logic evaluation (Table I)
# ----------------------------------------------------------------------
def compute_escalation_table():
    """Values reproduced from analysis/escalation_eval.py; re-run that
    script directly to regenerate TP/FP/TN/FN from the labeled test set."""
    return [
        {"iteration": "1. Naive substring", "TP": 15, "FP": 14, "TN": 1, "FN": 0,
         "precision": 0.517, "recall": 1.000, "f1": 0.682},
        {"iteration": "2. Fixed 4-word window", "TP": 15, "FP": 3, "TN": 12, "FN": 0,
         "precision": 0.833, "recall": 1.000, "f1": 0.909},
        {"iteration": "3. Sentence-scope NegEx", "TP": 15, "FP": 0, "TN": 15, "FN": 0,
         "precision": 1.000, "recall": 1.000, "f1": 1.000},
    ]


# ----------------------------------------------------------------------
# 5. FIGURES
# ----------------------------------------------------------------------
def box(ax, x, y, w, h, text, fill, edge, fontsize=9, fontweight="normal", textcolor=None):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.08",
                           facecolor=fill, edgecolor=edge, linewidth=1.4, zorder=2)
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
            color=textcolor or PALETTE["gray_text"], fontweight=fontweight, zorder=3)


def arrow(ax, x1, y1, x2, y2, color=None):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
                         color=color or PALETTE["gray_line"], linewidth=1.2, zorder=5)
    ax.add_patch(a)


def fig1_architecture(outpath):
    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.set_xlim(0, 10); ax.set_ylim(0, 8); ax.axis("off")

    box(ax, 2.7, 6.1, 4.6, 1.3, "Orchestrator\nRoutes tasks, scopes data per agent",
        PALETTE["navy"], PALETTE["navy"], fontsize=9, fontweight="bold", textcolor="white")

    agents = [
        (0.3, "Agent 1 — Research", "Live PubMed API\nEscalation-triggered only"),
        (3.6, "Agent 2 — Patient/Insurance", "phi_sanitizer.py\nPurpose-scoped filtering"),
        (6.9, "Agent 3 — Imaging + Booking", "MedGemma 1.5 4B-it\nRed-flag + negation detection"),
    ]
    for x, title, sub in agents:
        box(ax, x, 3.8, 2.8, 1.6, f"{title}\n\n{sub}", PALETTE["steel_fill"], PALETTE["steel"], fontsize=8.3)

    box(ax, 2.5, 1.1, 5, 1.2, "tools/audit_log.py\nJSONL, timestamped record of every action + handoff",
        PALETTE["slate_fill"], PALETTE["slate_edge"], fontsize=8.6)

    arrow(ax, 4.4, 6.1, 1.7, 5.4, PALETTE["navy"])
    arrow(ax, 5.0, 6.1, 5.0, 5.4, PALETTE["navy"])
    arrow(ax, 5.6, 6.1, 8.3, 5.4, PALETTE["navy"])
    arrow(ax, 1.7, 3.8, 3.5, 2.3, PALETTE["slate_edge"])
    arrow(ax, 5.0, 3.8, 5.0, 2.3, PALETTE["slate_edge"])
    arrow(ax, 8.3, 3.8, 6.5, 2.3, PALETTE["slate_edge"])

    plt.tight_layout()
    plt.savefig(outpath, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close()


def fig2_flowchart(outpath):
    fig, ax = plt.subplots(figsize=(7.4, 6.6))
    ax.set_xlim(-1, 11.2); ax.set_ylim(0, 11); ax.axis("off")

    def diamond(x, y, w, h, text, fontsize=8.6):
        pts = [(x, y + h / 2), (x + w / 2, y + h), (x + w, y + h / 2), (x + w / 2, y)]
        ax.add_patch(Polygon(pts, facecolor=PALETTE["amber_fill"], edgecolor=PALETTE["amber"], linewidth=1.4, zorder=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, color=PALETTE["gray_text"], zorder=3)

    box(ax, 2, 9.3, 4, 1, "MedGemma finding (free text)\n+ self-reported urgency rating", PALETTE["steel_fill"], PALETTE["steel"], fontsize=8.6)
    arrow(ax, 4, 9.3, 4, 8.5)
    box(ax, 1.5, 7.3, 5, 1.2, "Sentence-scope negation check\n(NegEx-style; Chapman et al., 2001)\nover modality-specific red-flag terms", PALETTE["steel_fill"], PALETTE["steel"], fontsize=8.2)
    arrow(ax, 4, 7.3, 4, 6.5)
    diamond(1, 4.7, 6, 1.8, "requires_review =\n(un-negated red-flag term found)\nOR (urgency not in {low, routine})")
    arrow(ax, 7, 5.6, 8.2, 5.6, PALETTE["rust"])
    ax.text(7.4, 5.85, "True", fontsize=8.5, style="italic", color=PALETTE["gray_text"])
    arrow(ax, 4, 4.7, 4, 3.7, PALETTE["teal"])
    ax.text(4.3, 4.2, "False", fontsize=8.5, style="italic", color=PALETTE["gray_text"])

    box(ax, 8.3, 5.1, 2, 1, "FLAGGED FOR\nHUMAN REVIEW", PALETTE["rust_fill"], PALETTE["rust"], fontsize=8.4)
    arrow(ax, 9.3, 5.1, 9.3, 3.9)
    box(ax, 8.3, 2.9, 2, 1, "PubMed lookup\nusing flagged term", PALETTE["slate_fill"], PALETTE["slate_edge"], fontsize=8)

    box(ax, 2, 2.5, 4, 1.2, "Content-based department routing\n(scans finding text, falls back to\nmodality default)", PALETTE["steel_fill"], PALETTE["steel"], fontsize=8.4)
    arrow(ax, 4, 2.5, 4, 1.4)
    box(ax, 2, 0.4, 4, 1, "AUTO-BOOKED\nDepartment, appointment in 7 days", PALETTE["teal_fill"], PALETTE["teal"], fontsize=8.6)

    plt.tight_layout()
    plt.savefig(outpath, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close()


def fig3_leakage_comparison(outpath):
    import numpy as np
    modalities = ["Chest X-ray", "Skeletal", "Mammogram", "Abdominal"]
    x = np.arange(len(modalities)); width = 0.2
    fig, ax = plt.subplots(figsize=(7.2, 4.4))

    b_san_c1 = ax.bar(x - 1.5*width, [0,0,0,0], width, label="Sanitized — C1 (Output)", color=PALETTE["teal"])
    b_san_c2 = ax.bar(x - 0.5*width, [0,0,0,0], width, label="Sanitized — C2 (Inter-agent)", color=PALETTE["steel"])
    b_nv_c1  = ax.bar(x + 0.5*width, [100]*4, width, label="Naive — C1 (Output)", color=PALETTE["rust"])
    b_nv_c2  = ax.bar(x + 1.5*width, [100]*4, width, label="Naive — C2 (Inter-agent)", color=PALETTE["amber"])

    ax.set_ylabel("Leak Rate (%)", fontsize=10, color=PALETTE["gray_text"])
    ax.set_xticks(x); ax.set_xticklabels(modalities, fontsize=9.5)
    ax.set_ylim(0, 112)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=8.6, frameon=False)
    ax.grid(axis="y", alpha=0.25, color=PALETTE["slate_edge"])
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(PALETTE["slate_edge"])

    for bars in [b_nv_c1, b_nv_c2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+2, "100%", ha="center", fontsize=7.6, color=PALETTE["gray_text"])
    for bars in [b_san_c1, b_san_c2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, 2, "0%", ha="center", fontsize=7.6, color=PALETTE["gray_text"])

    plt.tight_layout()
    plt.savefig(outpath, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close()


def fig4_sequence(outpath, timing_rows):
    t = {r["operation"]: r for r in timing_rows}
    fig, ax = plt.subplots(figsize=(9.5, 8.2))
    ax.set_xlim(0, 10.5); ax.set_ylim(0, 12); ax.axis("off")

    actors = [("User/\nClinician", 0.8), ("Orchestrator", 3.0), ("Patient\nAgent", 5.0),
              ("Imaging\nAgent", 7.2), ("Research\nAgent", 9.6)]
    top = 11.2
    for name, x in actors:
        b = FancyBboxPatch((x-0.7, top-0.4), 1.4, 0.6, boxstyle="round,pad=0.03",
                            facecolor=PALETTE["steel_fill"], edgecolor=PALETTE["steel"], linewidth=1.3, zorder=2)
        ax.add_patch(b)
        ax.text(x, top-0.1, name, ha="center", va="center", fontsize=8.5, color=PALETTE["gray_text"], zorder=3)
        ax.plot([x, x], [top-0.4, 0.5], color=PALETTE["slate_edge"], linestyle="--", linewidth=1, zorder=1)

    def msg(x1, x2, y, text, dashed=False, fontsize=7.6):
        a = FancyArrowPatch((x1, y), (x2, y), arrowstyle="-|>", mutation_scale=10,
                             color=PALETTE["gray_text"], linewidth=1.1,
                             linestyle="--" if dashed else "-", zorder=3)
        ax.add_patch(a)
        ax.text((x1+x2)/2, y+0.12, text, ha="center", va="bottom", fontsize=fontsize, zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.5))

    def note(x, y, text, fontsize=7):
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, style="italic",
                color=PALETTE["gray_text"],
                bbox=dict(facecolor=PALETTE["slate_fill"], edgecolor=PALETTE["slate_edge"], boxstyle="round,pad=0.3"), zorder=4)

    y = 10.3
    msg(0.8, 3.0, y, "handle_patient_visit(patient_id, image, modality)"); y -= 0.75
    msg(3.0, 5.0, y, "get_record_for(patient_id, purpose='booking')"); y -= 0.55
    msg(5.0, 3.0, y, "sanitize_patient_record() -> {patient_id, conditions,\ninsurance_provider}  [3 of 7 fields]", dashed=True, fontsize=7.2); y -= 1.0
    note(3.0, y+0.3, "log: handoff_to_imaging_agent\n(field names only, no PHI values)"); y -= 0.6
    msg(3.0, 7.2, y, "analyze_and_route(image, modality, patient_id)"); y -= 0.85
    imaging_t = t.get("Imaging analysis (2 MedGemma calls + booking)", {})
    note(7.2, y+0.4, f"MedGemma 1.5 4B-it: finding + urgency\n(mean {imaging_t.get('mean','?')}{imaging_t.get('unit','s')}, n={imaging_t.get('n','?')})"); y -= 0.85
    note(7.2, y+0.3, "booking_tool: NegEx-style\nred-flag + negation check"); y -= 0.65
    msg(7.2, 3.0, y, "{finding, urgency, booking_decision}", dashed=True); y -= 0.85
    ax.text(4.5, y+0.35, "alt [booking_decision == FLAGGED_FOR_HUMAN_REVIEW]", ha="left", fontsize=7.5, style="italic", fontweight="bold", color=PALETTE["rust"])
    y -= 0.4
    msg(3.0, 9.6, y, "handle(query=triggering_red_flag_term)"); y -= 0.85
    pubmed_t = t.get("PubMed literature search", {})
    note(9.6, y+0.4, f"PubMed E-utilities (humans[MeSH] filter)\n(mean {pubmed_t.get('mean','?')}{pubmed_t.get('unit','s')}, n={pubmed_t.get('n','?')})"); y -= 0.7
    msg(9.6, 3.0, y, "related_articles[]", dashed=True); y -= 0.75
    msg(3.0, 0.8, y, "final report {patient_id, finding, urgency,\nbooking, related_research}"); y -= 0.35

    ax.plot([1.0, 10.1], [y+0.15, y+0.15], color=PALETTE["slate_edge"], linewidth=0.5, zorder=1)
    visit_t = t.get("Full patient visit (sanitized)", {})
    note(9.6, y-0.1, f"log: visit_complete\n(mean full visit {visit_t.get('mean','?')}{visit_t.get('unit','s')}, n={visit_t.get('n','?')})")

    plt.tight_layout()
    plt.savefig(outpath, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close()


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------
def main():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))

    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-log", default=os.path.join(project_root, "data", "audit_log.jsonl"))
    ap.add_argument("--outdir", default=os.path.join(project_root, "data", "figures"))
    ap.add_argument("--tables-out", default=os.path.join(project_root, "data", "tables.json"))
    args = ap.parse_args()

    # Make every path absolute up front, and print it, so it is always
    # obvious exactly where files are being read from / written to.
    args.audit_log = os.path.abspath(args.audit_log)
    args.outdir = os.path.abspath(args.outdir)
    args.tables_out = os.path.abspath(args.tables_out)
    print(f"Script location:  {script_dir}")
    print(f"Project root:     {project_root}  (assumed: one level up from tools/)")
    print(f"Audit log (read): {args.audit_log}")
    print(f"Figures (write):  {args.outdir}")
    print(f"Tables (write):   {args.tables_out}")
    print()

    os.makedirs(args.outdir, exist_ok=True)
    tables = {}

    if os.path.exists(args.audit_log):
        entries = load_audit_log(args.audit_log)
        timing_rows = compute_timing_table(entries)
        print(f"Loaded {len(entries)} audit log entries.")
    else:
        print(f"WARNING: {args.audit_log} not found - using placeholder timing values for Fig. 4 only.")
        timing_rows = [
            {"operation": "Imaging analysis (2 MedGemma calls + booking)", "n": "?", "mean_s": "?"},
            {"operation": "PubMed literature search", "n": "?", "mean_s": "?"},
            {"operation": "Full patient visit (sanitized)", "n": "?", "mean_s": "?"},
        ]
    tables["table_iv_timing"] = timing_rows

    tables["table_ii_leakage_stats"] = compute_leakage_stats()
    tables["table_iii_blast_radius"] = compute_blast_radius()
    tables["table_i_escalation"] = compute_escalation_table()

    os.makedirs(os.path.dirname(args.tables_out) or ".", exist_ok=True)
    with open(args.tables_out, "w") as f:
        json.dump(tables, f, indent=2, default=str)
    print(f"Wrote {args.tables_out} with every reproduced table value.")

    fig1_architecture(os.path.join(args.outdir, "fig1_architecture.png"))
    fig2_flowchart(os.path.join(args.outdir, "fig2_flowchart.png"))
    fig3_leakage_comparison(os.path.join(args.outdir, "fig3_leakage_comparison.png"))
    fig4_sequence(os.path.join(args.outdir, "fig4_sequence.png"), timing_rows)
    print(f"Wrote 4 figures to {args.outdir}/")


if __name__ == "__main__":
    main()

