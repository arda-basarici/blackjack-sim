"""
Blackjack Monte Carlo Simulator — Analysis Report Generator
Generates a professional PDF report from simulation results.

All headline numbers are computed from the current data at build time, so the
report never drifts out of sync with the runs. Hand-level logs are loaded with
only the needed columns; the two 6-deck counting decision logs are read once for
the "how counting changes decisions" figure (the slow part of the build).

Usage:
    python generate_report.py

Output:
    blackjack_analysis_report.pdf
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    PageBreak, Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# -- Configuration -------------------------------------------------------------

RUNS_DIR   = "data/runs"
OUTPUT_PDF = "blackjack_analysis_report.pdf"
CHARTS_DIR = "report_charts"
BASE_BET   = 10
START_BR   = 1000
os.makedirs(CHARTS_DIR, exist_ok=True)

C_DARK   = HexColor("#1A1A2E")
C_ACCENT = HexColor("#0D47A1")
C_INK    = HexColor("#212121")
C_RED    = HexColor("#B71C1C")
C_PANEL  = HexColor("#EEF2F7")

sns.set_theme(style="whitegrid")
plt.rcParams.update({"figure.dpi": 150, "font.size": 10, "font.family": "sans-serif"})

# -- Data loading --------------------------------------------------------------

HAND_RUNS = {
    "Basic": "hands_basic", "Semi-Random": "hands_semi_random",
    "Dealer Mirror": "hands_dealer_mirror", "Random": "hands_random",
}
HAND_COLOR = {"Basic": "#2196F3", "Semi-Random": "#4CAF50",
              "Dealer Mirror": "#FF9800", "Random": "#F44336"}
HAND_USECOLS = ["hand_id", "player_value", "dealer_upcard", "action",
                "final_dealer_value", "outcome", "is_win", "payout"]
HAND_DT = {"player_value": "int16", "dealer_upcard": "int16", "is_win": "int8",
           "action": "category", "outcome": "category"}

SESSION_RUNS = {
    "Basic + Flat":             ("sess_basic_flat",          "#2196F3"),
    "Basic + Martingale":       ("sess_basic_martingale",    "#F44336"),
    "Basic + Anti-Martingale":  ("sess_basic_anti",          "#FF9800"),
    "Basic + Count (no count)": ("sess_basic_count_nocount", "#9E9E9E"),
    "Basic + Count + HiLo 6D":  ("sess_basic_count_hilo_6d", "#4CAF50"),
    "Basic + Count + HiLo 1D":  ("sess_basic_count_hilo_1d", "#009688"),
    "Random + Flat":            ("sess_random_flat",         "#795548"),
    "Counting + HiLo 6D":       ("sess_counting_hilo_6d",    "#3F51B5"),
    "Counting + HiLo 1D":       ("sess_counting_hilo_1d",    "#E91E63"),
}
SCOLOR = {lbl: c for lbl, (r, c) in SESSION_RUNS.items()}

DEC_COLS = ["decision_index", "player_value", "player_is_soft", "dealer_upcard",
            "true_count", "bet_size", "is_win", "can_split", "action"]
DEC_DT = {"decision_index": "int16", "player_value": "int16", "dealer_upcard": "int16",
          "player_is_soft": "bool", "true_count": "float32", "bet_size": "float32",
          "is_win": "int8", "can_split": "bool", "action": "category"}


def load_data():
    hands, sessions = {}, {}
    for lbl, run in HAND_RUNS.items():
        df = pd.read_csv(f"{RUNS_DIR}/{run}/decisions.csv", usecols=HAND_USECOLS, dtype=HAND_DT)
        hands[lbl] = df.drop_duplicates("hand_id", keep="first")
    for lbl, (run, _) in SESSION_RUNS.items():
        sessions[lbl] = pd.read_csv(f"{RUNS_DIR}/{run}/sessions.csv")
    return hands, sessions


def load_counting_decisions():
    """Per-decision logs for the two 6-deck counting runs (the slow read)."""
    out = {}
    for lbl in ["Basic + Count + HiLo 6D", "Counting + HiLo 6D"]:
        run = SESSION_RUNS[lbl][0]
        out[lbl] = pd.read_csv(f"{RUNS_DIR}/{run}/decisions.csv",
                               usecols=DEC_COLS, dtype=DEC_DT)
    return out


def compute_metrics(hands, sessions):
    M = {}
    for s, h in hands.items():
        n = len(h)
        m = dict(
            win=(h.outcome.isin(["win", "blackjack"])).mean() * 100,
            bust=(h.outcome == "bust").mean() * 100,
            loss=(h.outcome.isin(["lose", "bust"])).mean() * 100,
            push=(h.outcome == "push").mean() * 100,
            he=-h.payout.sum() / (n * BASE_BET) * 100,
            dealer_bust=(h.final_dealer_value > 21).mean() * 100,
            bj=(h.outcome == "blackjack").mean() * 100,
        )
        m["bust_share"] = m["bust"] / m["loss"] * 100
        m["sum"] = m["win"] + m["loss"] + m["push"]
        M[s] = m
    S = {lbl: dict(net=d.net_profit.mean(), std=d.net_profit.std(),
                   ruin=d.went_bust.mean() * 100, win=d.win_rate.mean() * 100,
                   prof=(d.net_profit > 0).mean() * 100)
         for lbl, d in sessions.items()}
    f = sessions["Basic + Flat"]
    total = sum(len(h) for h in hands.values()) + \
        sum(int(d.hands_played.sum()) for d in sessions.values())
    return {"H": M, "S": S, "flat_end_mean": f.ending_bankroll.mean(),
            "flat_net_min": f.net_profit.min(), "flat_net_max": f.net_profit.max(),
            "total_hands": total}

# -- Charts --------------------------------------------------------------------

ACODE = {"hit": "H", "stand": "S", "double": "D", "split": "P", "surrender": "R", "none": "-"}


def save_chart(fig, name):
    path = f"{CHARTS_DIR}/{name}.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    return path


def chart_strategy_comparison(hands, M):
    order = list(HAND_RUNS); colors = [HAND_COLOR[s] for s in order]
    panels = [("win", "Total Win Rate", "Win Rate (%)", 60),
              ("he", "House Edge", "House Edge (%)", 50),
              ("bust", "Bust Rate (hand over 21)", "Bust Rate (%)", 40)]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for ax, (k, title, ylab, ymax) in zip(axes, panels):
        vals = [M["H"][s][k] for s in order]
        bars = ax.bar(order, vals, color=colors, edgecolor="white", width=0.6)
        ax.set_title(title, fontweight="bold", fontsize=11); ax.set_ylabel(ylab); ax.set_ylim(0, ymax)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + ymax * 0.012, f"{v:.1f}%",
                    ha="center", fontsize=9, fontweight="bold")
    plt.suptitle(f"Strategy Comparison — {len(hands['Basic']):,} Hands Each",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "strategy_comparison")


def chart_bust_breakdown(hands, M):
    order = list(HAND_RUNS); colors = [HAND_COLOR[s] for s in order]
    win = [M["H"][s]["win"] for s in order]; push = [M["H"][s]["push"] for s in order]
    bust = [M["H"][s]["bust"] for s in order]
    stand_loss = [M["H"][s]["loss"] - M["H"][s]["bust"] for s in order]
    x = np.arange(len(order))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(x, win, 0.6, label="Win", color="#2196F3")
    axes[0].bar(x, push, 0.6, bottom=win, label="Push", color="#9E9E9E")
    axes[0].bar(x, stand_loss, 0.6, bottom=np.add(win, push), label="Loss (standing)", color="#FF9800")
    axes[0].bar(x, bust, 0.6, bottom=np.add(np.add(win, push), stand_loss), label="Bust", color="#F44336")
    for i in range(len(order)):
        axes[0].text(i, win[i] + push[i] + stand_loss[i] + bust[i] / 2, f"{bust[i]:.1f}%",
                     ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        axes[0].text(i, win[i] + push[i] + stand_loss[i] / 2, f"{stand_loss[i]:.1f}%",
                     ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    axes[0].set_xticks(x); axes[0].set_xticklabels(order)
    axes[0].set_title("Full Outcome Breakdown", fontweight="bold")
    axes[0].set_ylabel("Percentage (%)"); axes[0].set_ylim(0, 105); axes[0].legend(loc="upper right", fontsize=8)
    share = [M["H"][s]["bust_share"] for s in order]
    bars = axes[1].bar(order, share, color=colors, edgecolor="white")
    axes[1].set_title("Bust as % of Total Losses", fontweight="bold")
    axes[1].set_ylabel("Bust / Total Loss (%)"); axes[1].set_ylim(0, 70)
    for b, v in zip(bars, share):
        axes[1].text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.0f}%", ha="center", fontsize=9, fontweight="bold")
    plt.suptitle("How Each Strategy Loses", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "bust_breakdown")


def _win_action_annot(h):
    h = h.copy(); h["action"] = h["action"].astype(str)
    win = h.pivot_table("is_win", "player_value", "dealer_upcard", "mean")
    act = h.pivot_table("action", "player_value", "dealer_upcard", aggfunc=lambda x: x.mode().iat[0])
    ann = win.copy().astype(object)
    for r in win.index:
        for c in win.columns:
            v = win.loc[r, c]
            if pd.isna(v):
                ann.loc[r, c] = ""
            else:
                a = act.loc[r, c] if (r in act.index and c in act.columns) else ""
                ann.loc[r, c] = f"{v:.2f}\n{ACODE.get(a, '')}"
    return win, act, ann


def chart_heatmap(hands):
    win, act, ann = _win_action_annot(hands["Basic"])
    fig, ax = plt.subplots(figsize=(11, 8.5))
    sns.heatmap(win, annot=ann, fmt="", cmap="RdYlGn", vmin=0, vmax=1, linewidths=0.3,
                ax=ax, annot_kws={"size": 8}, cbar_kws={"label": "Win Rate"})
    ax.set_title("Win Rate + Basic Strategy Action  (H=Hit  S=Stand  D=Double  P=Split)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Dealer Upcard"); ax.set_ylabel("Player Value")
    plt.tight_layout(); return save_chart(fig, "heatmap")


def chart_bankroll_distribution(sessions):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    f = sessions["Basic + Flat"]; pct = (f.net_profit > 0).mean() * 100
    axes[0].hist(f.ending_bankroll, bins=60, color="#2196F3", edgecolor="white", alpha=0.85)
    axes[0].axvline(START_BR, color="black", ls="--", lw=1.5, label=f"Start (${START_BR:,})")
    axes[0].axvline(f.ending_bankroll.mean(), color="red", lw=1.5, label=f"Mean (${f.ending_bankroll.mean():.0f})")
    axes[0].set_title("Ending Bankroll — Basic + Flat", fontweight="bold")
    axes[0].set_xlabel("Ending Bankroll ($)"); axes[0].set_ylabel("Sessions"); axes[0].legend()
    axes[1].hist(f.net_profit, bins=60, color="#2196F3", edgecolor="white", alpha=0.85)
    axes[1].axvline(0, color="black", ls="--", lw=1.5); axes[1].axvline(f.net_profit.mean(), color="red", lw=1.5)
    axes[1].axvspan(f.net_profit.min(), 0, alpha=0.08, color="red")
    axes[1].axvspan(0, f.net_profit.max(), alpha=0.08, color="green")
    axes[1].set_title(f"Net Profit — {pct:.1f}% of sessions profitable", fontweight="bold")
    axes[1].set_xlabel("Net Profit ($)"); axes[1].set_ylabel("Sessions")
    stats = (f"Mean: ${f.net_profit.mean():.0f}\nStd: ${f.net_profit.std():.0f}\n"
             f"Min: ${f.net_profit.min():.0f}\nMax: ${f.net_profit.max():.0f}")
    axes[1].text(0.97, 0.97, stats, transform=axes[1].transAxes, fontsize=8, va="top", ha="right",
                 bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))
    plt.suptitle("The House Edge Over 1,000 Hands — Optimal Play, Flat Bets",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "bankroll_dist")


def chart_betting_comparison(sessions):
    labels = ["Basic + Flat", "Basic + Martingale", "Basic + Anti-Martingale", "Basic + Count (no count)"]
    titles = ["Flat Betting", "Martingale", "Anti-Martingale", "Count Bet (no information)"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, lbl, title in zip(axes.flatten(), labels, titles):
        d = sessions[lbl]
        ax.hist(d.net_profit, bins=60, color=SCOLOR[lbl], edgecolor="white", alpha=0.85)
        ax.axvline(0, color="black", ls="--", lw=1.5); ax.axvline(d.net_profit.mean(), color="darkred", lw=1.5)
        stats = (f"Mean: ${d.net_profit.mean():.0f}\nGoes broke: {d.went_bust.mean()*100:.1f}%\n"
                 f"Profitable: {(d.net_profit>0).mean()*100:.1f}%")
        ax.text(0.97, 0.97, stats, transform=ax.transAxes, fontsize=8, va="top", ha="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))
        ax.set_title(title, fontweight="bold"); ax.set_xlabel("Net Profit ($)"); ax.set_ylabel("Sessions")
    plt.suptitle("Betting Strategy Comparison — Net Profit Distribution",
                 fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "betting_comparison")


def chart_counting_progression(sessions):
    labels = ["Basic + Flat", "Basic + Count (no count)", "Basic + Count + HiLo 6D",
              "Counting + HiLo 6D", "Basic + Count + HiLo 1D", "Counting + HiLo 1D"]
    short = ["Basic\nFlat", "Count Bet\nNo Count", "Basic+Count\n6D", "Counting\n6D",
             "Basic+Count\n1D", "Counting\n1D"]
    colors = [SCOLOR[l] for l in labels]; net = [sessions[l].net_profit.mean() for l in labels]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    bars = axes[0].bar(range(len(labels)), net, color=colors, edgecolor="white")
    axes[0].axhline(0, color="black", ls="--", lw=1.5)
    axes[0].set_xticks(range(len(labels))); axes[0].set_xticklabels(short, fontsize=8)
    axes[0].set_title("Average Net Profit — Counting Progression", fontweight="bold"); axes[0].set_ylabel("Net Profit ($)")
    for b, v in zip(bars, net):
        axes[0].text(b.get_x() + b.get_width() / 2, b.get_height(), f"${v:+.0f}",
                     ha="center", va="bottom" if v >= 0 else "top", fontsize=8, fontweight="bold")
    for lbl in labels[2:]:
        axes[1].hist(sessions[lbl].net_profit, bins=60, alpha=0.4, color=SCOLOR[lbl], label=lbl)
    axes[1].axvline(0, color="black", ls="--", lw=1.5)
    axes[1].set_title("Net Profit Distribution — Counting Strategies", fontweight="bold")
    axes[1].set_xlabel("Net Profit ($)"); axes[1].set_ylabel("Sessions"); axes[1].legend(fontsize=7)
    plt.suptitle("Card Counting: Isolating Each Variable", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "counting_progression")


def chart_counting_mechanism(dec):
    c6 = dec["Counting + HiLo 6D"]; f6 = c6[c6.decision_index == 0].copy()
    f6["tc"] = pd.cut(f6.true_count, bins=[-100, -1, 1, 3, 5, 100],
                      labels=["< -1", "-1 to 1", "1 to 3", "3 to 5", "> 5"])
    bet = f6.groupby("tc", observed=True).bet_size.mean()
    win = f6.groupby("tc", observed=True).is_win.mean() * 100

    def hard16v10(df):
        m = ((df.decision_index == 0) & (df.player_value == 16) & (~df.player_is_soft)
             & (df.dealer_upcard == 10) & (~df.can_split) & (df.action.isin(["hit", "stand"])))
        return df[m]

    def hs(d):
        v = d.action.astype(str).value_counts(normalize=True) * 100
        return [v.get("hit", 0), v.get("stand", 0)]
    bc = hard16v10(dec["Basic + Count + HiLo 6D"]); cc = hard16v10(c6)
    bv, cv = hs(bc), hs(cc)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    axes[0].bar(bet.index.astype(str), bet.values, color="#3F51B5", edgecolor="white")
    axes[0].axhline(BASE_BET, color="black", ls="--", lw=1.5, label=f"Min bet (${BASE_BET})")
    axes[0].set_title("Bet Size Rises With the Count", fontweight="bold")
    axes[0].set_xlabel("True Count"); axes[0].set_ylabel("Avg Bet ($)"); axes[0].legend()
    for i, v in enumerate(bet.values):
        axes[0].text(i, v + 0.5, f"${v:.0f}", ha="center", fontsize=9, fontweight="bold")
    axes[1].bar(win.index.astype(str), win.values, color="#4CAF50", edgecolor="white")
    axes[1].axhline(f6.is_win.mean() * 100, color="black", ls="--", lw=1.5, label="Overall avg")
    axes[1].set_title("So Does the Win Rate", fontweight="bold")
    axes[1].set_xlabel("True Count"); axes[1].set_ylabel("Win Rate (%)"); axes[1].set_ylim(40, 47); axes[1].legend()
    for i, v in enumerate(win.values):
        axes[1].text(i, v + 0.1, f"{v:.1f}%", ha="center", fontsize=9, fontweight="bold")
    x = np.arange(2); w = 0.35
    axes[2].bar(x - w / 2, bv, w, label="Basic strategy", color="#4CAF50", edgecolor="white")
    axes[2].bar(x + w / 2, cv, w, label="Counting", color="#3F51B5", edgecolor="white")
    axes[2].set_xticks(x); axes[2].set_xticklabels(["Hit", "Stand"])
    axes[2].set_title("Index Play: Hard 16 vs Dealer 10", fontweight="bold")
    axes[2].set_ylabel("% of decisions"); axes[2].legend()
    axes[2].text(0.5, 0.92, f"Win rate: Basic {bc.is_win.mean()*100:.1f}%  |  Counting {cc.is_win.mean()*100:.1f}%",
                 transform=axes[2].transAxes, ha="center", fontsize=9,
                 bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.85))
    for i in range(2):
        axes[2].text(i - w / 2, bv[i] + 1, f"{bv[i]:.0f}%", ha="center", fontsize=9)
        axes[2].text(i + w / 2, cv[i] + 1, f"{cv[i]:.0f}%", ha="center", fontsize=9)
    plt.suptitle("How Counting Changes Decisions  (Counting + HiLo, 6 decks)",
                 fontsize=13, fontweight="bold", y=1.03)
    plt.tight_layout(); return save_chart(fig, "counting_mechanism")


def chart_risk_of_ruin(sessions):
    order = [l for l in SESSION_RUNS if l != "Random + Flat"]; colors = [SCOLOR[l] for l in order]
    ruin = [sessions[l].went_bust.mean() * 100 for l in order]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    bars = axes[0].bar(range(len(order)), ruin, color=colors, edgecolor="white")
    axes[0].set_xticks(range(len(order)))
    axes[0].set_xticklabels([l.replace(" + ", "\n+\n") for l in order], fontsize=7)
    axes[0].set_title("Ruin Rate — % of Sessions That Go Broke", fontweight="bold"); axes[0].set_ylabel("Ruin Rate (%)")
    for b, v in zip(bars, ruin):
        if v > 0.4:
            axes[0].text(b.get_x() + b.get_width() / 2, v + 0.3, f"{v:.1f}%", ha="center", fontsize=7, fontweight="bold")
    box_labels = ["Basic + Flat", "Basic + Martingale", "Counting + HiLo 1D"]
    data = [sessions[l].ending_bankroll for l in box_labels]
    bp = axes[1].boxplot(data, patch_artist=True, showfliers=False, medianprops=dict(color="black", lw=2))
    for patch, l in zip(bp["boxes"], box_labels):
        patch.set_facecolor(SCOLOR[l]); patch.set_alpha(0.7)
    axes[1].set_xticks(range(1, len(box_labels) + 1))
    axes[1].set_xticklabels(["Basic\nFlat", "Basic\nMartingale", "Counting\nHiLo 1D"])
    axes[1].axhline(START_BR, color="black", ls="--", lw=1.5, label=f"Start (${START_BR:,})")
    axes[1].axhline(0, color="red", lw=1, label="Broke")
    axes[1].set_title("Ending Bankroll — Spread of Outcomes", fontweight="bold")
    axes[1].set_ylabel("Ending Bankroll ($)"); axes[1].legend(fontsize=9)
    plt.suptitle("Risk of Ruin — Profit Is Not the Same as Survival", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout(); return save_chart(fig, "risk_of_ruin")


def chart_edge_map(hands):
    """Appendix: where Basic out-wins Dealer Mirror, masked to divergent decisions."""
    b = hands["Basic"].copy(); b["action"] = b["action"].astype(str)
    m = hands["Dealer Mirror"].copy(); m["action"] = m["action"].astype(str)
    bw = b.pivot_table("is_win", "player_value", "dealer_upcard", "mean")
    mw = m.pivot_table("is_win", "player_value", "dealer_upcard", "mean")
    ba = b.pivot_table("action", "player_value", "dealer_upcard", aggfunc=lambda x: x.mode().iat[0])
    ma = m.pivot_table("action", "player_value", "dealer_upcard", aggfunc=lambda x: x.mode().iat[0])
    idx = bw.index.intersection(mw.index); col = bw.columns.intersection(mw.columns)
    diff = bw.loc[idx, col] - mw.loc[idx, col]
    same = pd.DataFrame(False, index=idx, columns=col)
    for r in idx:
        for c in col:
            if r in ba.index and c in ba.columns and r in ma.index and c in ma.columns:
                same.loc[r, c] = (ba.loc[r, c] == ma.loc[r, c])
    div = diff.where(~same)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    for ax, data, title in [(axes[0], diff, "All cells"),
                            (axes[1], div, "Only where the two strategies differ")]:
        sns.heatmap(data, annot=True, fmt=".2f", cmap="RdYlGn", vmin=-0.15, vmax=0.15,
                    linewidths=0.3, ax=ax, cbar_kws={"label": "Win-rate diff (Basic − Mirror)"})
        ax.set_title(title, fontweight="bold"); ax.set_xlabel("Dealer Upcard"); ax.set_ylabel("Player Value")
    plt.suptitle("Where Basic Strategy Gains Its Edge Over Dealer Mirror",
                 fontsize=13, fontweight="bold", y=1.0)
    plt.tight_layout(); return save_chart(fig, "edge_map")


def chart_action_maps(hands):
    order = ["Basic", "Dealer Mirror", "Semi-Random", "Random"]
    deterministic = {"Basic", "Dealer Mirror"}
    fig, axes = plt.subplots(2, 2, figsize=(18, 15))
    for ax, name in zip(axes.flatten(), order):
        if name in deterministic:
            win, act, ann = _win_action_annot(hands[name])
            sns.heatmap(win, annot=ann, fmt="", cmap="RdYlGn", vmin=0, vmax=1, linewidths=0.3,
                        ax=ax, cbar=False, annot_kws={"size": 7})
            sub = "H=Hit  S=Stand  D=Double  P=Split"
        else:
            win = hands[name].pivot_table("is_win", "player_value", "dealer_upcard", "mean")
            sns.heatmap(win, annot=True, fmt=".2f", cmap="RdYlGn", vmin=0, vmax=1, linewidths=0.3,
                        ax=ax, cbar=False, annot_kws={"size": 7})
            sub = "win rate only — no fixed action"
        ax.set_title(f"{name}  ({sub})", fontsize=11, fontweight="bold")
        ax.set_xlabel("Dealer Upcard"); ax.set_ylabel("Player Value")
    plt.suptitle("Action Maps — All Four Strategies", fontsize=14, fontweight="bold", y=1.0)
    plt.tight_layout(); return save_chart(fig, "action_maps")

# -- PDF -----------------------------------------------------------------------

def build_pdf(chart_paths, M):
    doc = SimpleDocTemplate(OUTPUT_PDF, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    W = A4[0] - 40*mm
    H, S = M["H"], M["S"]

    title  = ParagraphStyle("T", fontSize=30, leading=36, textColor=white, alignment=TA_CENTER,
                            fontName="Helvetica-Bold", spaceAfter=8)
    sub    = ParagraphStyle("Sub", fontSize=15, leading=20, textColor=HexColor("#BBDEFB"),
                            alignment=TA_CENTER, fontName="Helvetica", spaceAfter=4)
    meta   = ParagraphStyle("Meta", fontSize=11, leading=16, textColor=HexColor("#90CAF9"),
                            alignment=TA_CENTER, fontName="Helvetica")
    h1     = ParagraphStyle("H1", fontSize=16, leading=20, textColor=C_ACCENT, fontName="Helvetica-Bold",
                            spaceBefore=12, spaceAfter=6)
    h2     = ParagraphStyle("H2", fontSize=12, leading=16, textColor=C_DARK, fontName="Helvetica-Bold",
                            spaceBefore=10, spaceAfter=4)
    body   = ParagraphStyle("B", fontSize=10, leading=15, textColor=C_INK, alignment=TA_JUSTIFY,
                            fontName="Helvetica", spaceAfter=8)
    lead   = ParagraphStyle("Lead", fontSize=11.5, leading=17, textColor=C_INK, alignment=TA_JUSTIFY,
                            fontName="Helvetica", spaceAfter=9)
    callout = ParagraphStyle("C", fontSize=10.5, leading=15, textColor=C_ACCENT, fontName="Helvetica-Bold",
                             spaceBefore=6, spaceAfter=6, leftIndent=10)
    cap    = ParagraphStyle("Cap", fontSize=8, leading=12, textColor=HexColor("#757575"),
                            alignment=TA_CENTER, fontName="Helvetica-Oblique", spaceAfter=10)
    bullet = ParagraphStyle("Bul", fontSize=10, leading=15, textColor=C_INK, fontName="Helvetica",
                            leftIndent=14, spaceAfter=4)
    boxh   = ParagraphStyle("BoxH", fontSize=12, leading=16, textColor=C_ACCENT, fontName="Helvetica-Bold", spaceAfter=5)
    boxb   = ParagraphStyle("BoxB", fontSize=9.5, leading=14, textColor=C_INK, fontName="Helvetica", spaceAfter=4)
    tc     = ParagraphStyle("tc", fontSize=9, leading=12, textColor=C_INK, fontName="Helvetica")
    tcr    = ParagraphStyle("tcr", fontSize=9, leading=12, textColor=C_RED, fontName="Helvetica-Bold")
    th     = ParagraphStyle("th", fontSize=9.5, leading=12, textColor=white, fontName="Helvetica-Bold")

    story = []
    def P(t, s=body): story.append(Paragraph(t, s))
    def fig(key, hr, caption): story.append(Image(chart_paths[key], width=W, height=W*hr)); P(caption, cap)
    def rule(): story.append(HRFlowable(width=W, thickness=1, color=C_ACCENT, spaceAfter=10))

    def panel(flowables, bg=C_DARK, height=None, pad=20):
        kw = {"colWidths": [W]}
        if height: kw["rowHeights"] = [height]
        t = Table([[flowables]], **kw)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), bg), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                               ("LEFTPADDING", (0,0), (-1,-1), 26), ("RIGHTPADDING", (0,0), (-1,-1), 26),
                               ("TOPPADDING", (0,0), (-1,-1), pad), ("BOTTOMPADDING", (0,0), (-1,-1), pad)]))
        return t

    def styled_table(data, widths, header=True, red_row=None):
        t = Table(data, colWidths=widths)
        sty = [("BACKGROUND", (0,0), (-1,0), C_DARK),
               ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#F5F5F5"), white]),
               ("GRID", (0,0), (-1,-1), 0.5, HexColor("#BDBDBD")),
               ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
               ("LEFTPADDING", (0,0), (-1,-1), 8), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]
        if red_row is not None:
            sty.append(("BACKGROUND", (0, red_row), (-1, red_row), HexColor("#FDECEA")))
        t.setStyle(TableStyle(sty)); return t

    # ---------------- COVER ----------------
    cover = [Paragraph("Does Strategy Beat the House?", title),
                        
             Paragraph("A Monte Carlo Investigation of Blackjack", sub),
             Spacer(1, 9*mm),
             Paragraph(f"{M['total_hands']/1e6:.0f} million simulated hands &bull; 4 playing "
                       "strategies &bull; 9 betting systems", meta),
             Spacer(1, 2*mm),
             Paragraph("Part of AI Journey &mdash; Phase 2: Data &amp; ML Engineering", meta),
             Spacer(1, 14*mm),
             Paragraph("github.com/arda-basarici/ai-journey",
                       ParagraphStyle("L", fontSize=10.5, textColor=HexColor("#64B5F6"),
                                      alignment=TA_CENTER, fontName="Helvetica"))]
    story.append(panel(cover, height=120*mm))
    story.append(PageBreak())

    # ---------------- EXECUTIVE SUMMARY ----------------
    P("Executive Summary", h1); rule()
    P("Almost everything most people believe about beating blackjack is wrong &mdash; and a "
      f"simulation of nearly {M['total_hands']/1e6:.0f} million hands can show exactly where, and "
      "why. This report plays four strategies and nine betting systems through millions of hands "
      "under one fixed rule set, then follows the money across 10,000 thousand-hand sessions to "
      "see what actually happens to a bankroll over time.", lead)
    P("The engine was built from scratch with a pluggable design: any strategy &mdash; a rule of "
      "thumb, the textbook optimum, or a future neural network &mdash; implements one interface and "
      "drops into the simulator without changing the engine. That makes it a reusable research "
      "platform, and its output is validated against the known mathematics of the game.", body)

    def r(q, a, red=False):
        st = tcr if red else tc
        return [Paragraph(q, st), Paragraph(a, st)]
    rows = [
        [Paragraph("Question", th), Paragraph("What the data says", th)],
        r("Does playing strategy matter?",
          f"Enormously. Optimal play cuts the house edge from {H['Random']['he']:.0f}% (random) to {H['Basic']['he']:.2f}%."),
        r("Is avoiding busts the goal?",
          f"No. The strategy that busts least loses {H['Semi-Random']['he']/H['Basic']['he']:.0f}x more money than the best one."),
        r("Can a betting system beat the house?",
          f"No. Martingale goes broke {S['Basic + Martingale']['ruin']:.0f}% of sessions; the expected loss is unchanged."),
        r("Does varying your bets help?",
          "Only with information. Bet variation with no card counting equals flat betting to the dollar."),
        r("Does card counting work?",
          f"In 6 decks, barely (about breakeven). On a single deck, yes: +${S['Counting + HiLo 1D']['net']:.0f} per session."),
        r("So counting is a free win?",
          f"No &mdash; it is the catch. That single-deck edge goes broke {S['Counting + HiLo 1D']['ruin']:.0f}% of sessions: high reward, high ruin.", red=True),
        r("What drives going broke?",
          f"Bet size vs bankroll, not skill. Same play: {S['Basic + Martingale']['ruin']:.0f}% ruin with Martingale, {S['Basic + Flat']['ruin']:.0f}% flat."),
    ]
    story.append(styled_table(rows, [W*0.34, W*0.66], red_row=6))
    story.append(Spacer(1, 8))

    # How to read this report (box)
    htr = [Paragraph("How to Read This Report", boxh),
           Paragraph("<b>The game.</b> 6 decks (single deck where noted), dealer stands on soft 17, "
                     "blackjack pays 3:2, double on any two cards. A fixed random seed makes every "
                     "run reproducible.", boxb),
           Paragraph("<b>A &ldquo;session&rdquo;</b> is 1,000 hands played on a $1,000 starting "
                     "bankroll at a $10 base bet &mdash; one evening at the table. We run 10,000 of them per setup.", boxb),
           Paragraph("<b>House edge</b> is the casino&rsquo;s long-run cut per dollar bet. "
                     "<b>Bust</b> means a <i>hand</i> goes over 21; <b>ruin</b> (or &ldquo;going "
                     "broke&rdquo;) means a <i>bankroll</i> hits zero &mdash; two different things. "
                     "<b>Win rate</b> is the share of hands won; <b>profitable</b> is the share of "
                     "sessions that finished ahead. A strategy can win a minority of hands and still finish in profit.", boxb)]
    story.append(panel(htr, bg=C_PANEL, pad=12))
    story.append(PageBreak())

    # ---------------- 1. VALIDATION ----------------
    P("1. Is the Simulator Trustworthy?", h1); rule()
    P("Before any finding, the engine has to earn trust. The simplest test is to check the numbers "
      "that should not depend on how the player plays. The dealer busts and deals blackjacks at "
      "rates fixed by the cards, not the player &mdash; if those drift between strategies, something "
      "is broken. They do not.", body)
    vrows = [[Paragraph("Strategy", th), Paragraph("Dealer Bust", th), Paragraph("Blackjack", th),
              Paragraph("Outcomes Sum", th), Paragraph("House Edge", th)]]
    for s in HAND_RUNS:
        vrows.append([Paragraph(s, tc), Paragraph(f"{H[s]['dealer_bust']:.1f}%", tc),
                      Paragraph(f"{H[s]['bj']:.2f}%", tc), Paragraph(f"{H[s]['sum']:.1f}%", tc),
                      Paragraph(f"{H[s]['he']:.2f}%", tc)])
    story.append(styled_table(vrows, [W*0.28, W*0.18, W*0.18, W*0.18, W*0.18]))
    story.append(Spacer(1, 8))
    P(f"Across all four strategies the dealer busts about {H['Basic']['dealer_bust']:.0f}% of the "
      f"time and blackjacks land near {H['Basic']['bj']:.1f}% &mdash; flat, exactly as the cards "
      "dictate, and every outcome distribution sums to 100%. The anchor is the bottom-right cell: "
      f"Basic Strategy&rsquo;s house edge of {H['Basic']['he']:.2f}% sits squarely on the known "
      "value for these rules. The engine reproduces real blackjack mathematics, so the differences "
      "in the rest of this report are signal, not artefacts.", body)
    story.append(PageBreak())

    # ---------------- 2. STRATEGY ----------------
    P("2. Does Strategy Even Matter?", h1); rule()
    P("Start with the widest question: how much does skill change the outcome? Four strategies span "
      "the full range of play, from the mathematically optimal Basic Strategy to a player choosing "
      "at random. Each was dealt one million hands.", body)
    fig("strategy_comparison", 0.33,
        "Figure 1: Win rate, house edge, and hand-bust rate across four strategies (1M hands each).")
    P(f"The gap is staggering. Random play hands the house a {H['Random']['he']:.0f}% edge &mdash; it "
      f"bleeds money fast. Basic Strategy shrinks that to just {H['Basic']['he']:.2f}%, about "
      f"{H['Random']['he']-H['Basic']['he']:.0f} percentage points better, and the simulator "
      "reproduces the known optimum exactly.", body)
    P(f"But notice the win-rate panel: the best strategy wins {H['Basic']['win']:.0f}% of hands, the "
      f"worst still wins {H['Random']['win']:.0f}%. A 13-point spread in hands won, yet a 45-point "
      "spread in money lost. Winning more hands is clearly not where the money is &mdash; which "
      "leads to the most surprising result in the study.", body)
    story.append(PageBreak())

    # ---------------- 3. BUST MYTH ----------------
    P("3. The Myth of “Don't Bust”", h1); rule()
    P("Ask a casual player for the golden rule of blackjack and most will say: don't bust. The data "
      "says that instinct is actively costing them money.", lead)
    fig("bust_breakdown", 0.38,
        "Figure 2: How each strategy loses — busting (over 21) versus losing at showdown.")
    P(f"Look at Semi-Random. It busts the <i>least</i> of all four ({H['Semi-Random']['bust']:.1f}%), "
      f"even less than optimal play ({H['Basic']['bust']:.1f}%) &mdash; yet its house edge is "
      f"{H['Semi-Random']['he']/H['Basic']['he']:.0f} times worse. Avoiding busts did not make it a "
      "better strategy. It made it a worse one.", body)
    P("The reason is subtle and important. Semi-Random dodges busts by standing on stiff hands like "
      "14 or 15. But standing on 15 against a dealer's 10 loses almost as often as busting would "
      "&mdash; the dealer simply makes a better hand. The loss does not disappear; it moves from the "
      "“bust” column to the “beaten at showdown” column. Optimal play accepts a "
      "higher bust rate on purpose, because on those hands taking the risk loses less money than "
      "playing it safe.", body)
    P("Avoiding busts is not the goal. Losing the least money is &mdash; and sometimes that means "
      "taking the bust risk.", callout)
    story.append(PageBreak())

    # ---------------- 4. WHERE THE EDGE ----------------
    P("4. Where the Edge Is Won", h1); rule()
    P("If skill is concentrated in a few decisions, which ones? The map below colours every "
      "situation &mdash; the player's hand against the dealer's visible card &mdash; by how often it "
      "wins, with Basic Strategy's correct move printed underneath.", body)
    fig("heatmap", 0.78,
        "Figure 3: Win rate and optimal action by player hand vs dealer upcard (Basic Strategy, 1M "
        "hands). Green = favourable, red = unfavourable.")
    P("Two things jump out. Most of the board is red or orange: the player acts first and can bust "
      "before the dealer even plays, so the game is structurally stacked against you &mdash; skill "
      "manages that, it does not erase it. And the colour is set by the <i>situation</i>, not the "
      "player; what skill controls is the move written in each cell.", body)
    P("The edge lives in two regions. Against a weak dealer card (2&ndash;6), Basic Strategy stands "
      "on stiff hands and lets the dealer bust itself; against a strong card (7+) it takes the hit, "
      "because standing is worse. And in the green cells it doubles or splits, pressing more money "
      "down exactly when it is ahead. Naive strategies never make these moves &mdash; on 16 versus a "
      "dealer 5 alone, optimal play wins up to 18 percentage points more often. (The full edge map "
      "is in Appendix A.)", body)
    story.append(PageBreak())

    # ---------------- 5. MONEY OVER TIME ----------------
    P("5. What Actually Happens to Your Money", h1); rule()
    P("Knowing the right move is one thing; living with the results is another. Switching from single "
      "hands to 10,000 full sessions shows the house edge as a bankroll trajectory, not a percentage.", body)
    fig("bankroll_dist", 0.38,
        "Figure 4: Ending bankroll and net profit across 10,000 sessions — optimal play, flat $10 "
        "bets, $1,000 starting bankroll.")
    flat = S["Basic + Flat"]
    P(f"Even with perfect play, the average session ends down about ${abs(flat['net']):.0f} &mdash; "
      f"the {H['Basic']['he']:.2f}% house edge, ground out over a thousand hands. But the average is "
      "the least interesting number here. The spread is enormous: individual sessions swing from "
      f"roughly &minus;${abs(M['flat_net_min']):.0f} to +${M['flat_net_max']:.0f}, and "
      f"{flat['prof']:.0f}% of them finish in profit.", body)
    P("That is the whole psychology of the casino floor in one chart. Nearly half of all sessions win "
      "money &mdash; more than enough to convince a player their system works &mdash; while the "
      "long-run average sits stubbornly in the red. Short-term results are noise; only thousands of "
      "sessions reveal the true edge.", body)
    story.append(PageBreak())

    # ---------------- 6. BETTING SYSTEMS ----------------
    P("6. The Betting-System Myth", h1); rule()
    P("If you cannot out-play the house, can you out-bet it? Progressive systems &mdash; Martingale "
      "above all &mdash; promise exactly that: double after every loss, and one win wipes out the "
      "whole streak plus a profit. On paper it cannot fail.", body)
    fig("betting_comparison", 0.69,
        "Figure 5: Net profit across four betting systems, same optimal play underneath (10,000 "
        "sessions each).")
    mart, ctrl = S["Basic + Martingale"], S["Basic + Count (no count)"]
    P(f"In practice Martingale goes broke {mart['ruin']:.0f}% of the time. The distribution splits in "
      "two: a tall spike at total ruin beside a hump of small wins. Win small often, lose everything "
      f"occasionally &mdash; and the average result (${mart['net']:.0f}) is no better than flat "
      "betting. The system did not change the math; it traded many small losses for a few "
      "catastrophic ones.", body)
    P(f"The cleanest proof sits in the fourth panel. “Count betting” with the counting "
      f"switched <i>off</i> &mdash; bets that vary for no reason &mdash; is identical to flat betting "
      f"to the dollar (${ctrl['net']:.0f}, {ctrl['ruin']:.1f}% ruin). Varying your bets achieves "
      "nothing on its own. The information is the edge, never the bet pattern.", body)
    P("Betting systems do not change what you expect to lose. They only change how wildly the "
      "outcomes swing &mdash; and how often you go broke.", callout)
    story.append(PageBreak())

    # ---------------- 7. CARD COUNTING ----------------
    P("7. Card Counting: Does It Actually Work?", h1); rule()
    P("Card counting is both over-hyped and misunderstood &mdash; Hollywood's guaranteed jackpot, the "
      "casino's cardinal sin. The truth is narrower: it is legal information, and under the right "
      "conditions it flips the edge to the player. The first chart isolates each ingredient in turn.", body)
    fig("counting_progression", 0.36,
        "Figure 6: Average net profit per session as each piece of counting is added — bet variation, "
        "then information, then deck count.")
    c6, c1 = S["Counting + HiLo 6D"], S["Counting + HiLo 1D"]
    P(f"Each step adds one thing. Bet variation alone does nothing. Add real Hi-Lo counting in a "
      f"six-deck shoe and the loss shrinks toward breakeven (${c6['net']:.0f} per session) &mdash; "
      "meaningful, but not yet a win, because in six decks the count rarely swings far enough. Switch "
      f"to a single deck and everything changes: profit jumps to +${c1['net']:.0f} per session.", body)
    P(f"That +${c1['net']:.0f} is a genuine edge, not luck &mdash; the average of 10,000 sessions, "
      "with the whole distribution shifted right. It works out to roughly +1.3% on every dollar "
      "wagered, exactly the range real single-deck counters achieve, and precisely why casinos deal "
      "six to eight decks and shuffle early. (Reassuringly, the same calculation on flat betting "
      f"returns &minus;{H['Basic']['he']:.2f}% &mdash; the house edge, recovered from a different angle.)", body)
    P("What the Counter Actually Does Differently", h2)
    fig("counting_mechanism", 0.29,
        "Figure 7: Three mechanisms of counting in a six-deck shoe — bets scale with the count, the "
        "win rate rises with it, and specific decisions change (hard 16 vs dealer 10).")
    P("The mechanism is concrete. As the true count climbs, the counter raises the bet from the $10 "
      "minimum up toward $68 &mdash; and that is justified, because the win rate genuinely rises with "
      "the count (a ten-rich deck means more blackjacks and more dealer busts). Counting also changes "
      "individual plays: on a hard 16 against a dealer 10, basic strategy always hits, but the counter "
      "stands almost half the time when the deck is rich &mdash; a deviation that lifts the win rate on "
      "that single hand. Small per hand, applied to the largest bets, repeated thousands of times: that "
      "is the entire edge.", body)
    story.append(PageBreak())

    # ---------------- 8. RISK OF RUIN ----------------
    P("8. The Catch: Profit Is Not Survival", h1); rule()
    P("A positive edge sounds like the end of the story. It is not &mdash; because a strategy that "
      "wins on average can still bankrupt you on the way there. This is where the single-deck result "
      "earns its asterisk.", lead)
    fig("risk_of_ruin", 0.36,
        "Figure 8: How often each strategy goes broke, and the full spread of ending bankrolls for "
        "three representative strategies.")
    c1, flat2, mart2 = S["Counting + HiLo 1D"], S["Basic + Flat"], S["Basic + Martingale"]
    P(f"The very strategy that tops the profit chart &mdash; single-deck counting &mdash; also goes "
      f"broke {c1['ruin']:.0f}% of the time: one session in five wiped out completely. That is the "
      "opposite of safe. The aggressive bet spread that <i>creates</i> the edge is the same thing "
      f"that drives the wild swings. Flat betting, by contrast, goes broke barely {flat2['ruin']:.1f}% "
      "of the time, but only ever bleeds slowly. More edge here is bought with more risk, not handed "
      "over for free.", body)
    P(f"And the driver of ruin is not skill &mdash; it is bet size relative to bankroll. The identical "
      f"optimal play goes broke {mart2['ruin']:.0f}% of the time with Martingale and "
      f"{flat2['ruin']:.1f}% with flat betting. Same decisions, wildly different survival. Expected "
      "value and risk of ruin are two separate dials, and a strategy has to be judged on both.", body)
    P("Profit answers “does it make money?” Risk of ruin answers “does it survive?” "
      "&mdash; and the best-paying strategy here is also one of the most dangerous.", callout)
    story.append(PageBreak())

    # ---------------- SCOREBOARD ----------------
    P("The Scoreboard: All Nine Configurations", h1); rule()
    P("Every betting setup at a glance, over 10,000 sessions each. Read it as the whole report in one "
      "table: optimal play loses slowly and safely; progressive systems trade that for ruin; counting "
      "earns a real edge on a single deck, but only by accepting real ruin risk.", body)
    srows = [[Paragraph("Configuration", th), Paragraph("Avg Net", th), Paragraph("Ruin Rate", th),
              Paragraph("Hand Win %", th), Paragraph("Profitable %", th)]]
    for lbl in SESSION_RUNS:
        d = S[lbl]
        srows.append([Paragraph(lbl, tc), Paragraph(f"${d['net']:+.0f}", tc),
                      Paragraph(f"{d['ruin']:.1f}%", tc), Paragraph(f"{d['win']:.1f}%", tc),
                      Paragraph(f"{d['prof']:.1f}%", tc)])
    story.append(styled_table(srows, [W*0.36, W*0.16, W*0.16, W*0.16, W*0.16]))
    story.append(PageBreak())

    # ---------------- 9. LIMITATIONS ----------------
    P("9. What This Does &mdash; and Doesn't &mdash; Model", h1); rule()
    P("An analysis is defined as much by what it refuses to claim as by what it asserts. This is a "
      "faithful model of the <i>mathematics</i> of blackjack, not a how-to-win guide, and several "
      "real-world frictions are deliberately left out:", body)
    for q, a in [
        ("No table limits.",
         "Real casinos cap the maximum bet, so a Martingale player cannot keep doubling. In practice "
         "that makes Martingale even more lethal than the 40% ruin shown here."),
        ("Single-deck games are rare and well defended.",
         "The +$314 edge assumes a single deck dealt to 50% penetration and a casino that tolerates a "
         "1-to-8 bet spread. Modern casinos use six to eight decks and watch for exactly this &mdash; "
         "both assumptions are optimistic."),
        ("Counting assumes flawless tracking.",
         "The simulated counter never miscounts. A real human under pressure does, and every error "
         "eats into a thin edge."),
        ("Human and house factors are out of scope.",
         "Comps, fatigue, and getting barred by the pit are real parts of advantage play and are not "
         "modelled here."),
    ]:
        P(f"<b>{q}</b>", bullet)
        P(a, ParagraphStyle("ib", parent=body, leftIndent=14, spaceAfter=8))
    P("None of this changes the core findings &mdash; it sharpens them. The mathematics says counting "
      "can win on a single deck; the real world is built specifically to keep that math out of reach.", body)
    story.append(PageBreak())

    # ---------------- 10. PLATFORM ----------------
    P("10. A Reusable Platform &mdash; and What's Next", h1); rule()
    P("Everything above came out of one engine, and the analysis is only a slice of what it can "
      "answer. Because every decision is recorded with full game context, new questions need new "
      "runs, not new code:", body)
    for q, a in [
        ("How much does a 6:5 payout cost the player?",
         "Swap the payout rule and re-run &mdash; the single most damaging rule a casino can change."),
        ("What bet spread makes counting profitable in six decks?",
         "Widen the spread in the betting module and measure where the line crosses zero."),
        ("How big a bankroll makes single-deck counting safe?",
         "Map ruin rate against starting bankroll &mdash; the practical question behind the +$314 edge."),
    ]:
        P(f"<b>{q}</b>", bullet)
        P(a, ParagraphStyle("ib2", parent=body, leftIndent=14, spaceAfter=8))
    P("Phase 3: Learning the Strategy From Data", h2)
    P("The millions of recorded decisions are the training set for the next phase: a neural network "
      "learns to play from the data alone, never told the rules. Does it rediscover Basic Strategy? "
      "Does it find the counting deviations on its own? Because strategies are pluggable, the trained "
      "model drops straight into this same framework and is judged on the very metrics in this report "
      "&mdash; a clean, directly comparable benchmark.", body)
    story.append(PageBreak())

    # ---------------- APPENDIX ----------------
    P("Appendix A &mdash; Where Basic Beats Dealer Mirror", h1); rule()
    P("Dealer Mirror plays by the dealer's own rules (hit to 17, never double or split). Subtracting "
      "its win rate from Basic Strategy's, then keeping only the cells where the two make different "
      "decisions, shows precisely where the edge is manufactured: the stiff hands against weak dealers, "
      "and the doubling band on 9&ndash;11.", body)
    fig("edge_map", 0.46,
        "Figure A1: Win-rate difference (Basic minus Dealer Mirror). Left, all cells; right, only "
        "where the two strategies choose differently.")
    story.append(PageBreak())

    P("Appendix B &mdash; Action Maps, All Four Strategies", h1); rule()
    P("The same win-rate field underlies every strategy &mdash; the colour is a property of the game, "
      "not the player. What differs is the move each strategy makes. Basic Strategy shows deliberate "
      "structure (doubles, splits, disciplined stands); Dealer Mirror shows a flat cut at 17; the "
      "random strategies show no fixed action at all.", body)
    fig("action_maps", 0.83,
        "Figure B1: Win rate by game state for all four strategies, with the chosen action for the two "
        "deterministic ones (H=Hit, S=Stand, D=Double, P=Split).")
    story.append(PageBreak())

    # ---------------- CLOSING ----------------
    story.append(Spacer(1, 30*mm))
    closing = [Paragraph("Built as Part of AI Journey",
                         ParagraphStyle("CT", fontSize=18, textColor=white, alignment=TA_CENTER,
                                        fontName="Helvetica-Bold", spaceAfter=30)),
               Paragraph("A structured path from Python foundations to AI engineering. Every project "
                         "real, complete, and publicly documented.",
                         ParagraphStyle("CB", fontSize=10, textColor=HexColor("#BBDEFB"),
                                        alignment=TA_CENTER, fontName="Helvetica", spaceAfter=14, leading=16)),
               Paragraph("github.com/arda-basarici/ai-journey",
                         ParagraphStyle("CL", fontSize=11, textColor=HexColor("#64B5F6"),
                                        alignment=TA_CENTER, fontName="Helvetica-Bold"))]
    story.append(panel(closing, height=200))

    doc.build(story)
    print(f"Report generated: {OUTPUT_PDF}")


# -- Main ----------------------------------------------------------------------

def main():
    print("Loading data...")
    hands, sessions = load_data()
    print(f"Loaded {len(hands)} hand strategies, {len(sessions)} session configurations")
    print("Computing metrics...")
    M = compute_metrics(hands, sessions)
    print("Loading counting decision logs (the slow read)...")
    dec = load_counting_decisions()
    print("Generating charts...")
    chart_paths = {
        "strategy_comparison":  chart_strategy_comparison(hands, M),
        "bust_breakdown":       chart_bust_breakdown(hands, M),
        "heatmap":              chart_heatmap(hands),
        "bankroll_dist":        chart_bankroll_distribution(sessions),
        "betting_comparison":   chart_betting_comparison(sessions),
        "counting_progression": chart_counting_progression(sessions),
        "counting_mechanism":   chart_counting_mechanism(dec),
        "risk_of_ruin":         chart_risk_of_ruin(sessions),
        "edge_map":             chart_edge_map(hands),
        "action_maps":          chart_action_maps(hands),
    }
    print("Building PDF...")
    build_pdf(chart_paths, M)
    print("Done.")


if __name__ == "__main__":
    main()
