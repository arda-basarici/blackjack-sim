"""
Blackjack Monte Carlo Simulator — Analysis Report Generator
Generates a professional PDF report from simulation results.

Usage:
    python generate_report.py

Output:
    blackjack_analysis_report.pdf
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    PageBreak, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import KeepTogether

# ── Configuration ────────────────────────────────────────────────────────────

RUNS_DIR = "data/runs"
OUTPUT_PDF = "blackjack_analysis_report.pdf"
CHARTS_DIR = "report_charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

# Colors
C_DARK    = HexColor("#1A1A2E")
C_BLUE    = HexColor("#2196F3")
C_GREEN   = HexColor("#4CAF50")
C_RED     = HexColor("#F44336")
C_ORANGE  = HexColor("#FF9800")
C_GREY    = HexColor("#9E9E9E")
C_TEAL    = HexColor("#009688")
C_INDIGO  = HexColor("#3F51B5")
C_PINK    = HexColor("#E91E63")
C_LIGHT   = HexColor("#F5F5F5")
C_ACCENT  = HexColor("#0D47A1")

# Chart style
sns.set_theme(style="whitegrid")
plt.rcParams["figure.dpi"] = 150
plt.rcParams["font.size"] = 10
plt.rcParams["font.family"] = "sans-serif"

# ── Data Loading ─────────────────────────────────────────────────────────────

HAND_RUNS = {
    "Basic":         None,
    "Semi-Random":   None,
    "Dealer Mirror": None,
    "Random":        None,
}

SESSION_RUNS = {
    "Basic + Flat":                 {"color": "#2196F3"},
    "Basic + Martingale":           {"color": "#F44336"},
    "Basic + Anti-Martingale":      {"color": "#FF9800"},
    "Basic + Count (no count)":     {"color": "#9E9E9E"},
    "Basic + Count + HiLo 6D":      {"color": "#4CAF50"},
    "Basic + Count + HiLo 1D":      {"color": "#009688"},
    "Random + Flat":                {"color": "#795548"},
    "Counting + Count + HiLo 6D":   {"color": "#3F51B5"},
    "Counting + Count + HiLo 1D":   {"color": "#E91E63"},
}

STRATEGY_MAP = {
    "basic_strategy":    "Basic",
    "semi_random":       "Semi-Random",
    "dealer_mirror":     "Dealer Mirror",
    "random":            "Random",
}

SESSION_LABEL_MAP = {
    ("basic_strategy",    "flat",           6, False): "Basic + Flat",
    ("basic_strategy",    "martingale",     6, False): "Basic + Martingale",
    ("basic_strategy",    "anti_martingale",6, False): "Basic + Anti-Martingale",
    ("basic_strategy",    "count_based",    6, False): "Basic + Count (no count)",
    ("basic_strategy",    "count_based",    6, True):  "Basic + Count + HiLo 6D",
    ("basic_strategy",    "count_based",    1, True):  "Basic + Count + HiLo 1D",
    ("random",            "flat",           6, False): "Random + Flat",
    ("counting_strategy", "count_based",    6, True):  "Counting + Count + HiLo 6D",
    ("counting_strategy", "count_based",    1, True):  "Counting + Count + HiLo 1D",
}

def load_data():
    hands = {}
    sessions = {}

    all_runs = sorted(
        [d for d in os.listdir(RUNS_DIR)
         if os.path.exists(f"{RUNS_DIR}/{d}/run_metadata.json")],
        reverse=True
    )

    for run_id in all_runs:
        with open(f"{RUNS_DIR}/{run_id}/run_metadata.json") as f:
            meta = json.load(f)

        exp = meta.get("experiments", [{}])[0]
        strategy = exp.get("strategy", "")
        betting = exp.get("betting_strategy", "")
        decks = exp.get("config", {}).get("num_decks", 6)
        mode = meta.get("mode", "")

        if mode == "hands":
            label = STRATEGY_MAP.get(strategy)
            if label and label not in hands:
                raw = pd.read_csv(f"{RUNS_DIR}/{run_id}/decisions.csv")
                hands[label] = raw.drop_duplicates(subset="hand_id", keep="first")

        elif mode == "sessions":
            # Detect counting from run timing — runs with hilo have different
            # avg net than no-count runs
            df = pd.read_csv(f"{RUNS_DIR}/{run_id}/sessions.csv")
            avg_net = df["net_profit"].mean()

            # Simple heuristic: basic+count+6deck with HiLo has avg_net ~ -20
            # without HiLo has avg_net ~ -69
            has_hilo = False
            if strategy == "basic_strategy" and betting == "count_based" and decks == 6:
                has_hilo = abs(avg_net - (-20)) < 10
            elif strategy == "basic_strategy" and betting == "count_based" and decks == 1:
                has_hilo = True
            elif strategy == "counting_strategy":
                has_hilo = True

            key = (strategy, betting, decks, has_hilo)
            label = SESSION_LABEL_MAP.get(key)
            if label and label not in sessions:
                sessions[label] = df

    return hands, sessions

# ── Chart Generation ──────────────────────────────────────────────────────────

def save_chart(fig, name):
    path = f"{CHARTS_DIR}/{name}.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def chart_strategy_comparison(hands):
    strategies = ["Basic", "Semi-Random", "Dealer Mirror", "Random"]
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336"]

    win_rates, bust_rates, house_edges = [], [], []
    for s in strategies:
        h = hands[s]
        win_rates.append(h["outcome"].isin(["win", "blackjack"]).mean() * 100)
        bust_rates.append((h["outcome"] == "bust").mean() * 100)
        net = h["payout"].sum()
        house_edges.append(-net / (len(h) * 10) * 100)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    for ax, vals, title, ylabel in zip(
        axes,
        [win_rates, house_edges, bust_rates],
        ["Total Win Rate", "House Edge", "Bust Rate"],
        ["Win Rate (%)", "House Edge (%)", "Bust Rate (%)"]
    ):
        bars = ax.bar(strategies, vals, color=colors, edgecolor="white", width=0.6)
        ax.set_title(title, fontweight="bold", fontsize=11)
        ax.set_ylabel(ylabel)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.3,
                    f"{val:.1f}%", ha="center", fontsize=9, fontweight="bold")

    axes[1].set_ylim(0, 50)
    plt.suptitle("Strategy Comparison — 1,000,000 Hands Each",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "strategy_comparison")


def chart_bust_breakdown(hands):
    strategies = ["Basic", "Semi-Random", "Dealer Mirror", "Random"]
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336"]

    win_r, push_r, loss_r, bust_r = [], [], [], []
    for s in strategies:
        h = hands[s]
        win_r.append(h["outcome"].isin(["win", "blackjack"]).mean() * 100)
        push_r.append((h["outcome"] == "push").mean() * 100)
        loss_r.append((h["outcome"] == "lose").mean() * 100)
        bust_r.append((h["outcome"] == "bust").mean() * 100)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    x = np.arange(len(strategies))

    p1 = axes[0].bar(x, win_r, label="Win", color="#2196F3")
    p2 = axes[0].bar(x, push_r, bottom=win_r, label="Push", color="#9E9E9E")
    p3 = axes[0].bar(x, loss_r,
                     bottom=[w+p for w,p in zip(win_r, push_r)],
                     label="Loss (standing)", color="#FF9800")
    p4 = axes[0].bar(x, bust_r,
                     bottom=[w+p+l for w,p,l in zip(win_r, push_r, loss_r)],
                     label="Bust", color="#F44336")

    for i in range(len(strategies)):
        axes[0].text(i, win_r[i]+push_r[i]+loss_r[i]+bust_r[i]/2,
                    f"{bust_r[i]:.1f}%", ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold")
        axes[0].text(i, win_r[i]+push_r[i]+loss_r[i]/2,
                    f"{loss_r[i]:.1f}%", ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold")

    axes[0].set_xticks(x)
    axes[0].set_xticklabels(strategies)
    axes[0].set_title("Full Outcome Breakdown", fontweight="bold")
    axes[0].set_ylabel("Percentage (%)")
    axes[0].legend(loc="upper right", fontsize=8)

    bust_pct = [b/(b+l)*100 for b,l in zip(bust_r, loss_r)]
    bars = axes[1].bar(strategies, bust_pct, color=colors, edgecolor="white")
    axes[1].set_title("Bust as % of Total Losses", fontweight="bold")
    axes[1].set_ylabel("Bust / Total Loss (%)")
    for bar, val in zip(bars, bust_pct):
        axes[1].text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.5,
                    f"{val:.1f}%", ha="center", fontsize=9, fontweight="bold")

    plt.suptitle("How Each Strategy Loses", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "bust_breakdown")


def chart_heatmap(hands):
    first = hands["Basic"].copy()
    # Rebuild from raw — need all decisions
    # Use the hands df but filter for first decision proxy
    pivot = first.pivot_table(
        values="is_win",
        index="player_value",
        columns="dealer_upcard",
        aggfunc="mean"
    )

    fig, ax = plt.subplots(figsize=(11, 8))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="RdYlGn",
                vmin=0, vmax=1, linewidths=0.3, ax=ax,
                annot_kws={"size": 8},
                cbar_kws={"label": "Win Rate"})
    ax.set_title("Win Rate by Player Value vs Dealer Upcard\n(Basic Strategy, 1,000,000 hands)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Dealer Upcard")
    ax.set_ylabel("Player Value")
    plt.tight_layout()
    return save_chart(fig, "heatmap")


def chart_bankroll_distribution(sessions):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    basic_flat = sessions["Basic + Flat"]
    pct = (basic_flat["net_profit"] > 0).mean() * 100

    axes[0].hist(basic_flat["ending_bankroll"], bins=60,
                 color="#2196F3", edgecolor="white", alpha=0.8)
    axes[0].axvline(x=1000, color="black", linestyle="--",
                    linewidth=1.5, label="Start ($1,000)")
    axes[0].axvline(x=basic_flat["ending_bankroll"].mean(),
                    color="red", linewidth=1.5,
                    label=f"Mean (${basic_flat['ending_bankroll'].mean():.0f})")
    axes[0].set_title("Ending Bankroll Distribution\nBasic + Flat (10,000 sessions)",
                      fontweight="bold")
    axes[0].set_xlabel("Ending Bankroll ($)")
    axes[0].set_ylabel("Sessions")
    axes[0].legend()

    axes[1].hist(basic_flat["net_profit"], bins=60,
                 color="#2196F3", edgecolor="white", alpha=0.8)
    axes[1].axvline(x=0, color="black", linestyle="--", linewidth=1.5)
    axes[1].axvline(x=basic_flat["net_profit"].mean(),
                    color="red", linewidth=1.5)
    axes[1].axvspan(basic_flat["net_profit"].min(), 0, alpha=0.1, color="red")
    axes[1].axvspan(0, basic_flat["net_profit"].max(), alpha=0.1, color="green")
    axes[1].set_title(f"Net Profit Distribution\n{pct:.1f}% of sessions profitable",
                      fontweight="bold")
    axes[1].set_xlabel("Net Profit ($)")
    axes[1].set_ylabel("Sessions")

    stats = (f"Mean: ${basic_flat['net_profit'].mean():.0f}\n"
             f"Std: ${basic_flat['net_profit'].std():.0f}\n"
             f"Min: ${basic_flat['net_profit'].min():.0f}\n"
             f"Max: ${basic_flat['net_profit'].max():.0f}")
    axes[1].text(0.97, 0.97, stats, transform=axes[1].transAxes,
                fontsize=8, va="top", ha="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    plt.suptitle("The House Edge Over 1,000 Hands — Optimal Play",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "bankroll_dist")


def chart_betting_comparison(sessions):
    labels = ["Basic + Flat", "Basic + Martingale",
              "Basic + Anti-Martingale", "Basic + Count (no count)"]
    colors = ["#2196F3", "#F44336", "#FF9800", "#9E9E9E"]
    titles = ["Flat Betting", "Martingale", "Anti-Martingale", "Count Bet (no info)"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    axes_flat = axes.flatten()

    for ax, label, color, title in zip(axes_flat, labels, colors, titles):
        df = sessions[label]
        pct = (df["net_profit"] > 0).mean() * 100
        bust = df["went_bust"].mean() * 100
        mean_net = df["net_profit"].mean()

        ax.hist(df["net_profit"], bins=60, color=color,
                edgecolor="white", alpha=0.8)
        ax.axvline(x=0, color="black", linestyle="--", linewidth=1.5)
        ax.axvline(x=mean_net, color="darkred", linewidth=1.5)
        ax.axvspan(df["net_profit"].min(), 0, alpha=0.08, color="red")
        ax.axvspan(0, max(df["net_profit"].max(), 1), alpha=0.08, color="green")

        stats = (f"Mean: ${mean_net:.0f}\n"
                 f"Bust: {bust:.1f}%\n"
                 f"Profitable: {pct:.1f}%")
        ax.text(0.97, 0.97, stats, transform=ax.transAxes,
               fontsize=8, va="top", ha="right",
               bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Net Profit ($)")
        ax.set_ylabel("Sessions")

    plt.suptitle("Betting Strategy Comparison — Net Profit Distribution\n(10,000 sessions × 1,000 hands)",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "betting_comparison")


def chart_counting_progression(sessions):
    labels = [
        "Basic + Flat",
        "Basic + Count (no count)",
        "Basic + Count + HiLo 6D",
        "Counting + Count + HiLo 6D",
        "Basic + Count + HiLo 1D",
        "Counting + Count + HiLo 1D",
    ]
    colors = ["#2196F3", "#9E9E9E", "#4CAF50", "#3F51B5", "#009688", "#E91E63"]
    short = ["Basic\nFlat", "Count Bet\nNo Count", "Basic+Count\nHiLo 6D",
             "Counting\nHiLo 6D", "Basic+Count\nHiLo 1D", "Counting\nHiLo 1D"]

    net_vals = [sessions[l]["net_profit"].mean() for l in labels]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    bars = axes[0].bar(range(len(labels)), net_vals, color=colors, edgecolor="white")
    axes[0].axhline(y=0, color="black", linestyle="--", linewidth=1.5)
    axes[0].set_xticks(range(len(labels)))
    axes[0].set_xticklabels(short, fontsize=8)
    axes[0].set_title("Average Net Profit — Counting Progression",
                      fontweight="bold")
    axes[0].set_ylabel("Net Profit ($)")
    for bar, val in zip(bars, net_vals):
        ypos = bar.get_height() + 0.5 if val >= 0 else bar.get_height() - 4
        axes[0].text(bar.get_x() + bar.get_width()/2, ypos,
                    f"${val:+.0f}", ha="center", fontsize=8, fontweight="bold")

    counting_labels = ["Basic + Count + HiLo 6D", "Counting + Count + HiLo 6D",
                       "Basic + Count + HiLo 1D", "Counting + Count + HiLo 1D"]
    counting_colors = ["#4CAF50", "#3F51B5", "#009688", "#E91E63"]

    for label, color in zip(counting_labels, counting_colors):
        df = sessions[label]
        axes[1].hist(df["net_profit"], bins=60, alpha=0.4,
                    color=color, label=label.replace(" + ", "\n+"), edgecolor="none")

    axes[1].axvline(x=0, color="black", linestyle="--", linewidth=1.5)
    axes[1].set_title("Net Profit Distribution — Counting Strategies",
                      fontweight="bold")
    axes[1].set_xlabel("Net Profit ($)")
    axes[1].set_ylabel("Sessions")
    axes[1].legend(fontsize=7)

    plt.suptitle("Card Counting: Isolating Each Variable",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "counting_progression")


def chart_risk_of_ruin(sessions):
    labels = [l for l in SESSION_RUNS.keys() if l != "Random + Flat"]
    colors = [SESSION_RUNS[l]["color"] for l in labels]
    bust_rates = [sessions[l]["went_bust"].mean() * 100
                  for l in labels if l in sessions]
    valid_labels = [l for l in labels if l in sessions]
    valid_colors = [SESSION_RUNS[l]["color"] for l in valid_labels]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    bars = axes[0].bar(range(len(valid_labels)), bust_rates,
                       color=valid_colors, edgecolor="white")
    axes[0].set_xticks(range(len(valid_labels)))
    axes[0].set_xticklabels([l.replace(" + ", "\n+\n") for l in valid_labels],
                             fontsize=7)
    axes[0].set_title("Bust Rate by Strategy", fontweight="bold")
    axes[0].set_ylabel("Bust Rate (%)")
    for bar, val in zip(bars, bust_rates):
        if val > 0.5:
            axes[0].text(bar.get_x() + bar.get_width()/2,
                        bar.get_height() + 0.3,
                        f"{val:.1f}%", ha="center", fontsize=7, fontweight="bold")

    traj = {
        "Basic + Flat": "#2196F3",
        "Basic + Martingale": "#F44336",
        "Counting + Count + HiLo 1D": "#E91E63",
    }
    traj_data = [sessions[l]["ending_bankroll"] for l in traj if l in sessions]
    traj_labels = ["Basic\nFlat", "Basic\nMartingale", "Counting\nHiLo 1D"]
    traj_colors = list(traj.values())

    bp = axes[1].boxplot(traj_data, labels=traj_labels,
                          patch_artist=True,
                          medianprops=dict(color="black", linewidth=2))
    for patch, color in zip(bp["boxes"], traj_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    axes[1].axhline(y=1000, color="black", linestyle="--",
                    linewidth=1.5, label="Start ($1,000)")
    axes[1].axhline(y=0, color="red", linewidth=1, label="Bust level")
    axes[1].set_title("Ending Bankroll Distribution",
                      fontweight="bold")
    axes[1].set_ylabel("Ending Bankroll ($)")
    axes[1].legend(fontsize=9)

    plt.suptitle("Risk of Ruin Analysis", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    return save_chart(fig, "risk_of_ruin")


# ── PDF Building ──────────────────────────────────────────────────────────────

def build_pdf(chart_paths):
    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )

    W = A4[0] - 40*mm  # usable width

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "ReportTitle",
        fontSize=28, leading=34,
        textColor=white, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=6,
    )
    style_subtitle = ParagraphStyle(
        "ReportSubtitle",
        fontSize=14, leading=18,
        textColor=HexColor("#BBDEFB"), alignment=TA_CENTER,
        fontName="Helvetica", spaceAfter=4,
    )
    style_meta = ParagraphStyle(
        "ReportMeta",
        fontSize=10, leading=14,
        textColor=HexColor("#90CAF9"), alignment=TA_CENTER,
        fontName="Helvetica",
    )
    style_h1 = ParagraphStyle(
        "H1",
        fontSize=16, leading=20,
        textColor=C_ACCENT, fontName="Helvetica-Bold",
        spaceBefore=14, spaceAfter=6,
        borderPad=4,
    )
    style_h2 = ParagraphStyle(
        "H2",
        fontSize=12, leading=16,
        textColor=C_DARK, fontName="Helvetica-Bold",
        spaceBefore=10, spaceAfter=4,
    )
    style_body = ParagraphStyle(
        "Body",
        fontSize=10, leading=15,
        textColor=HexColor("#212121"), alignment=TA_JUSTIFY,
        fontName="Helvetica", spaceAfter=8,
    )
    style_callout = ParagraphStyle(
        "Callout",
        fontSize=10, leading=15,
        textColor=C_ACCENT, fontName="Helvetica-Bold",
        spaceBefore=6, spaceAfter=6,
        leftIndent=12, borderPad=6,
    )
    style_caption = ParagraphStyle(
        "Caption",
        fontSize=8, leading=12,
        textColor=HexColor("#757575"), alignment=TA_CENTER,
        fontName="Helvetica-Oblique", spaceAfter=10,
    )
    style_bullet = ParagraphStyle(
        "Bullet",
        fontSize=10, leading=15,
        textColor=HexColor("#212121"),
        fontName="Helvetica",
        leftIndent=16, spaceAfter=4,
    )

    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    # Dark background via a large colored table
    cover_data = [[""]]
    cover_table = Table(cover_data, colWidths=[W], rowHeights=[240])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
        ("TOPPADDING", (0,0), (-1,-1), 80),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, -240))  # overlap

    # Title text over the dark box
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("Blackjack Monte Carlo", style_title))
    story.append(Paragraph("Strategy & Betting Analysis", style_subtitle))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "74 Million Simulated Hands &bull; 4 Action Strategies &bull; 9 Betting Configurations",
        style_meta))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Part of AI Journey — Phase 2: Data &amp; ML Engineering",
        style_meta))
    story.append(Spacer(1, 60*mm))
    story.append(Paragraph(
        "github.com/arda-basarici/ai-journey",
        ParagraphStyle("Link", fontSize=10, textColor=HexColor("#64B5F6"),
                       alignment=TA_CENTER, fontName="Helvetica")))

    story.append(PageBreak())

    # ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "This report presents findings from a large-scale Monte Carlo simulation of Blackjack, "
        "built to answer two questions: how much does playing strategy matter, and what do "
        "betting systems actually do to long-term outcomes?",
        style_body))

    story.append(Paragraph(
        "The simulator was designed from scratch with a pluggable architecture — any strategy, "
        "from a simple rule set to a neural network, implements a single interface and plugs in "
        "without touching the simulation engine. This makes it a reusable research platform, "
        "not a one-time analysis tool.",
        style_body))

    # Summary table
    summary_data = [
        ["Finding", "Result"],
        ["Basic strategy vs random play", "House edge: 0.76% vs 42.4% — a 41.6 point difference"],
        ["Lower bust rate = better strategy?", "No. Semi-Random busts less than Basic but loses 8x more"],
        ["Martingale betting system", "40.9% of sessions end in complete ruin. Expected value unchanged"],
        ["Bet variation without information", "Identical results to flat betting — information is the edge"],
        ["Card counting (6 decks, HiLo)", "Net loss reduced from -$69 to -$8 per 1,000-hand session"],
        ["Card counting (single deck, full)", "+$34 net profit per session — genuine player edge achieved"],
        ["Risk of ruin driver", "Bet sizing, not decision quality. Martingale: 40.9%, Flat: 0.6%"],
    ]

    col_widths = [W * 0.38, W * 0.62]
    t = Table(summary_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0),  C_DARK),
        ("TEXTCOLOR",    (0,0), (-1,0),  white),
        ("FONTNAME",     (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,0),  9),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,1), (-1,-1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [HexColor("#F5F5F5"), white]),
        ("GRID",         (0,0), (-1,-1), 0.5, HexColor("#BDBDBD")),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",     (0,7), (0,7),   "Helvetica-Bold"),
        ("TEXTCOLOR",    (0,7), (1,7),   HexColor("#1B5E20")),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── SECTION 1: STRATEGY MATTERS ───────────────────────────────────────────
    story.append(Paragraph("1. Strategy Matters — But Not How You Think", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "Four strategies were simulated across 1,000,000 hands each under standard Las Vegas "
        "Strip rules: 6 decks, dealer hits soft 17, blackjack pays 3:2. The strategies range "
        "from mathematically optimal (Basic) to completely random — spanning the full spectrum "
        "of possible play quality.",
        style_body))

    story.append(Image(chart_paths["strategy_comparison"], width=W, height=W*0.33))
    story.append(Paragraph(
        "Figure 1: Win rate, house edge, and bust rate across four strategies (1M hands each).",
        style_caption))

    story.append(Paragraph(
        "Basic strategy reduces house edge from 42.4% to 0.76% — a 41.6 percentage point "
        "improvement over random play. This is the known mathematical optimum for Vegas Strip "
        "rules, and the simulation validates it precisely.",
        style_body))

    story.append(Paragraph("The Counterintuitive Finding", style_h2))
    story.append(Image(chart_paths["bust_breakdown"], width=W, height=W*0.38))
    story.append(Paragraph(
        "Figure 2: How each strategy loses — bust vs standing loss breakdown.",
        style_caption))

    story.append(Paragraph(
        "Semi-Random has the lowest bust rate of all four strategies at 12.3% — lower even "
        "than Basic Strategy's 15.9%. Yet its house edge is 6.03%, nearly 8 times worse than "
        "Basic's 0.76%. This directly contradicts the common intuition that avoiding busts is "
        "the primary goal in Blackjack.",
        style_body))

    story.append(Paragraph(
        "Semi-Random randomly stands on hard 12-16. This avoids busts — but standing on 13 "
        "vs dealer 10 is a losing play regardless. The dealer completes a strong hand most of "
        "the time, and 13 loses to all of them. By randomly standing, Semi-Random trades a "
        "bust loss for a standing loss. The outcome is the same: a loss. But the bust counter "
        "goes down. Basic strategy hits in these situations because the alternative is worse, "
        "accepting calculated bust risk in exchange for better expected value.",
        style_body))

    story.append(Paragraph(
        "Avoiding busts is not the goal. Maximizing expected value is.",
        style_callout))

    story.append(PageBreak())

    # ── SECTION 2: WIN RATE HEATMAP ───────────────────────────────────────────
    story.append(Paragraph("2. Where the Edge Comes From", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "The win rate heatmap shows the objective difficulty of each game state — independent "
        "of what decision the player makes next. Green indicates favorable situations, red "
        "indicates unfavorable ones.",
        style_body))

    story.append(Image(chart_paths["heatmap"], width=W, height=W*0.72))
    story.append(Paragraph(
        "Figure 3: Win rate by player value vs dealer upcard — Basic Strategy, 1,000,000 hands.",
        style_caption))

    story.append(Paragraph(
        "The heatmap reveals the structural reality of the game: most states are red or orange. "
        "The player acts first, risking a bust before the dealer plays. This structural "
        "disadvantage cannot be eliminated — only managed.",
        style_body))

    story.append(Paragraph(
        "Three patterns stand out. Dealer upcards 2-6 are noticeably greener — the dealer is "
        "likely to bust, making even weak player hands competitive. Dealer 10-11 columns shift "
        "deep red — the dealer rarely busts and completes strong hands frequently. Player values "
        "12-16 vs dealer 7+ form the danger zone: red across the board, no good option, only "
        "a least-bad one. This is where strategy matters most, and where Basic Strategy's edge "
        "over naive approaches is concentrated.",
        style_body))

    story.append(Paragraph(
        "Basic strategy's advantage comes from three specific situations: doubling on 9-11 "
        "vs weak dealer upcards (extracting maximum value from favorable positions), standing "
        "on 12-16 vs dealer 2-6 (letting a likely-busting dealer self-destruct rather than "
        "risking a premature bust), and splitting pairs correctly. Dealer Mirror and Semi-Random "
        "miss all of these. The win rate difference on hard 16 vs dealer 5-6 alone is up to "
        "18 percentage points.",
        style_body))

    story.append(PageBreak())

    # ── SECTION 3: THE HOUSE EDGE OVER TIME ───────────────────────────────────
    story.append(Paragraph("3. Your Money Over Time", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "Hand analysis tells you which decisions are correct. Session analysis tells you what "
        "happens to your money. 10,000 sessions of 1,000 hands each were simulated — 10 million "
        "hands per configuration — to map the long-term reality of each strategy and betting "
        "combination.",
        style_body))

    story.append(Image(chart_paths["bankroll_dist"], width=W, height=W*0.38))
    story.append(Paragraph(
        "Figure 4: Ending bankroll and net profit distribution — Basic Strategy + Flat Betting, "
        "10,000 sessions of 1,000 hands, starting bankroll $1,000.",
        style_caption))

    story.append(Paragraph(
        "Even with mathematically optimal play, the average session ends with a $69 loss on a "
        "$1,000 starting bankroll. This is the house edge of 0.76% applied across 1,000 hands "
        "at $10 per hand — expected and correct.",
        style_body))

    story.append(Paragraph(
        "But variance is enormous. The standard deviation of ending bankroll is over $350. "
        "Some sessions end up $500+, others down $600+. Both are normal outcomes of the same "
        "strategy. Critically, 42% of sessions end profitable despite a negative expected value. "
        "This has a direct practical implication: short-term results are not evidence of "
        "strategy quality. A player who wins $300 in one session and concludes their system "
        "works, or loses $400 and concludes basic strategy is wrong, is reading noise as signal. "
        "Only aggregate results across hundreds of sessions reveal the true edge.",
        style_body))

    story.append(PageBreak())

    # ── SECTION 4: BETTING SYSTEMS ────────────────────────────────────────────
    story.append(Paragraph("4. The Betting System Myth", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "Progressive betting systems — Martingale in particular — are among the most persistent "
        "myths in gambling. The theory sounds compelling: double after every loss, and a single "
        "win recovers all previous losses plus one unit profit. The data tells a different story.",
        style_body))

    story.append(Image(chart_paths["betting_comparison"], width=W, height=W*0.69))
    story.append(Paragraph(
        "Figure 5: Net profit distribution across four betting strategies — Basic Strategy, "
        "10,000 sessions of 1,000 hands each.",
        style_caption))

    story.append(Paragraph("Martingale: The Numbers", style_h2))
    story.append(Paragraph(
        "Bust rate: 40.9%. Nearly half of all 1,000-hand sessions end in complete ruin. "
        "Average net profit: -$91, worse than flat betting's -$69. The Martingale distribution "
        "is bimodal — either the player survives and ends near breakeven, or a losing streak "
        "exceeds the bankroll before recovery is possible.",
        style_body))

    story.append(Paragraph(
        "The mathematics is unchanged. Martingale does not alter the house edge. It converts "
        "small frequent losses into rare catastrophic ones. In real casinos, table limits prevent "
        "recovery from just 8-10 consecutive losses — making Martingale even more dangerous "
        "in practice than in this simulation, which has no table limits.",
        style_body))

    story.append(Paragraph("The Control Experiment", style_h2))
    story.append(Paragraph(
        "Count-based betting without a counting system produces results identical to flat "
        "betting: mean -$69, bust rate 0.6%, indistinguishable distribution. Varying bet sizes "
        "without information does nothing. The information is the edge — not the betting pattern. "
        "This directly refutes the belief that varying bets creates any advantage.",
        style_body))

    story.append(Paragraph(
        "Betting systems do not change expected value. They change the distribution of outcomes — "
        "adding variance and bust risk while leaving the house edge unchanged.",
        style_callout))

    story.append(PageBreak())

    # ── SECTION 5: CARD COUNTING ──────────────────────────────────────────────
    story.append(Paragraph("5. Card Counting — Reality vs Myth", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "Card counting is simultaneously overestimated and misunderstood. Hollywood portrays it "
        "as a guaranteed path to riches. Casinos treat it as cheating. The reality is more "
        "nuanced: it is a legitimate information-based technique that, under the right conditions, "
        "can create a genuine player edge — but the conditions matter enormously.",
        style_body))

    story.append(Image(chart_paths["counting_progression"], width=W, height=W*0.36))
    story.append(Paragraph(
        "Figure 6: Average net profit per 1,000-hand session — isolating each component of "
        "card counting. All runs: 10,000 sessions, $1,000 starting bankroll, $10 base bet.",
        style_caption))

    story.append(Paragraph(
        "The progression isolates each variable. Bet variation alone (count-based betting "
        "without a counting system) produces zero effect — identical to flat betting. Adding "
        "HiLo counting to bet variation in a 6-deck game reduces net loss from $69 to $21 — "
        "a meaningful $48 improvement. Adding index plays (strategy deviations based on count) "
        "reduces losses further to $8. Switching to a single-deck game with full counting "
        "flips the edge to +$34 per session.",
        style_body))

    story.append(Paragraph(
        "The single-deck result of +$34 average net profit across 10,000 sessions is a genuine "
        "player edge — not variance. The distribution shifts visibly rightward. Card counting "
        "works on single deck because each card dealt has a larger impact on deck composition, "
        "count swings are larger and more frequent, and favorable situations arise more often. "
        "Modern casinos use 6-8 decks specifically to reduce this effect.",
        style_body))

    story.append(Paragraph(
        "An important methodological note: ROI percentages are misleading when bet sizes vary. "
        "A flat bettor wagers $10,000 over 1,000 hands. A count-based bettor may wager "
        "$15,000-$20,000 as bet sizes scale with favorable counts. All comparisons here use "
        "net profit in dollars — the only fair comparison when denominators differ.",
        style_body))

    story.append(PageBreak())

    # ── SECTION 6: RISK OF RUIN ───────────────────────────────────────────────
    story.append(Paragraph("6. Risk of Ruin", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Image(chart_paths["risk_of_ruin"], width=W, height=W*0.36))
    story.append(Paragraph(
        "Figure 7: Bust rate by strategy configuration and ending bankroll distribution "
        "for three representative strategies.",
        style_caption))

    story.append(Paragraph(
        "Risk of ruin varies dramatically across configurations — from 0.3% to 40.9% — but "
        "is largely independent of decision quality. A player using perfect basic strategy "
        "with Martingale betting goes broke 40.9% of sessions. The same player with flat "
        "betting busts 0.6% of the time. The playing decisions are identical. Only the betting "
        "strategy differs.",
        style_body))

    story.append(Paragraph(
        "The box plot shows the contrast starkly: flat betting's distribution stays well "
        "above zero in almost all sessions, while Martingale produces a long lower tail "
        "reaching zero — catastrophic sessions that end in complete ruin. The counting "
        "strategy on single deck achieves the best combination: positive expected value "
        "and a bust rate of only 0.3%.",
        style_body))

    story.append(Paragraph(
        "Bet sizing and bankroll management determine survival. Playing strategy determines "
        "the rate of loss or gain within that survival window. These are independent levers "
        "and must be considered separately.",
        style_callout))

    story.append(PageBreak())

    # ── SECTION 7: WHAT COMES NEXT ────────────────────────────────────────────
    story.append(Paragraph("7. What This Simulator Can Answer", style_h1))
    story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    story.append(Paragraph(
        "The analyses presented here are a subset of what the simulator can investigate. "
        "Because every decision is recorded with full game context, new questions can be "
        "answered by running new simulations — no architectural changes required.",
        style_body))

    questions = [
        ("How much does the 6:5 payout rule cost?",
         "The tough config (6:5) vs vegas (3:2) with identical strategy quantifies the "
         "single most impactful rule variation — estimated at 1.4 percentage points of "
         "house edge."),
        ("At what bet spread does counting become profitable in 6 decks?",
         "Our 1-to-8 spread produces -$8 net. A 1-to-12 or 1-to-16 spread would extract "
         "more value. The simulator can test this by modifying the CountBasedBetting class."),
        ("Does Omega II outperform Hi-Lo?",
         "Both are implemented. A direct comparison would quantify whether the added "
         "complexity of a multi-level system produces measurable benefit."),
        ("What is the optimal bankroll for a given risk tolerance?",
         "Risk of ruin as a function of starting bankroll and bet size — mapping the "
         "survival probability curve precisely."),
    ]

    for q, a in questions:
        story.append(Paragraph(f"<b>{q}</b>", style_bullet))
        story.append(Paragraph(a, ParagraphStyle("IndentBody",
            parent=style_body, leftIndent=16, spaceAfter=8)))

    story.append(Paragraph("Phase 3: Neural Network Strategy", style_h2))
    story.append(Paragraph(
        "The per-decision dataset generated by this simulator is the training data for Phase 3. "
        "A neural network will be trained on millions of (game_state, action, outcome) tuples "
        "to learn optimal strategy from data alone — without being told the rules of Blackjack. "
        "The key question: does the model rediscover Basic Strategy? Where does it deviate? "
        "Does it discover index plays independently?",
        style_body))

    story.append(Paragraph(
        "The simulator plugs in the trained model as a strategy object with no changes to the "
        "simulation engine. The session analysis framework then evaluates it identically to all "
        "hand-coded strategies — directly comparable results across all metrics presented here.",
        style_body))

    story.append(PageBreak())

    # ── CLOSING ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))

    closing_box = Table([[""]], colWidths=[W], rowHeights=[180])
    closing_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), C_DARK),
    ]))
    story.append(closing_box)
    story.append(Spacer(1, -180))
    story.append(Spacer(1, 20*mm))

    story.append(Paragraph(
        "Built as Part of AI Journey",
        ParagraphStyle("ClosingTitle", fontSize=18, textColor=white,
                       alignment=TA_CENTER, fontName="Helvetica-Bold",
                       spaceAfter=8)))
    story.append(Paragraph(
        "A structured learning arc from Python foundations to AI engineering. "
        "Every project is real, complete, and publicly documented.",
        ParagraphStyle("ClosingBody", fontSize=10, textColor=HexColor("#BBDEFB"),
                       alignment=TA_CENTER, fontName="Helvetica",
                       spaceAfter=12, leading=16)))
    story.append(Paragraph(
        "github.com/arda-basarici/ai-journey",
        ParagraphStyle("ClosingLink", fontSize=11, textColor=HexColor("#64B5F6"),
                       alignment=TA_CENTER, fontName="Helvetica-Bold")))

    doc.build(story)
    print(f"Report generated: {OUTPUT_PDF}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading data...")
    hands, sessions = load_data()

    print(f"Loaded {len(hands)} hand strategies, {len(sessions)} session configurations")

    missing_hands = [k for k in HAND_RUNS if k not in hands]
    missing_sessions = [k for k in SESSION_RUNS if k not in sessions]
    if missing_hands:
        print(f"WARNING: Missing hand data for: {missing_hands}")
    if missing_sessions:
        print(f"WARNING: Missing session data for: {missing_sessions}")

    print("Generating charts...")
    chart_paths = {}
    chart_paths["strategy_comparison"] = chart_strategy_comparison(hands)
    chart_paths["bust_breakdown"]       = chart_bust_breakdown(hands)
    chart_paths["heatmap"]              = chart_heatmap(hands)
    chart_paths["bankroll_dist"]        = chart_bankroll_distribution(sessions)
    chart_paths["betting_comparison"]   = chart_betting_comparison(sessions)
    chart_paths["counting_progression"] = chart_counting_progression(sessions)
    chart_paths["risk_of_ruin"]         = chart_risk_of_ruin(sessions)

    print("Building PDF...")
    build_pdf(chart_paths)
    print("Done.")
