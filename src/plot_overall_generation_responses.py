"""Country-level weighted dumbbell charts with an equal-country summary row."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from plot_generation_responses import ROOT, QUESTIONS, shares
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

YOUNG, OLD = "#205ba9", "#86b7ed"


def results(data, variable, answers):
    frame = data
    pct = shares(frame, variable, answers)[1].unstack()
    valid = frame.dropna(subset=[variable, "generation"])
    groups = valid.groupby(["cname", "generation"]).weight
    effective_n = groups.sum().pow(2) / groups.apply(lambda w: w.pow(2).sum())
    variance = (pct * (100 - pct) / effective_n.unstack()).sum(axis=1)
    table = pct.rename(columns={"Gen Z": "young_pct", "Older": "older_pct"})
    table["gap_pp"] = table.young_pct - table.older_pct
    table["se_pp"] = variance.pow(0.5)
    table = table.sort_values("gap_pp", ascending=False)
    average = table.mean()
    average["se_pp"] = np.sqrt(variance.sum()) / len(table)
    table.loc["Country mean"] = average
    table["significant"] = table.gap_pp.abs() > 1.96 * table.se_pp
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "Data/Output/clean.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/overall_generation")
    args = parser.parse_args()
    data = pd.read_csv(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(15, 10))
    tables = {}
    titles = ["Heard a lot about AI", "More excited than concerned"]
    for ax, (q, variable, _, answers), title in zip(axes, QUESTIONS, titles):
        table = results(data, variable, answers)
        tables[q] = table
        for i, row in enumerate(table.itertuples()):
            ax.hlines(i, row.older_pct, row.young_pct, color="#bdbbbb", lw=3)
            ax.scatter(row.older_pct, i, color=OLD, s=52, zorder=3)
            ax.scatter(row.young_pct, i, edgecolor=YOUNG,
                       facecolor=YOUNG if row.significant else "white", lw=1.8, s=52, zorder=4)
            ax.text(max(row.older_pct, row.young_pct)+1.6, i, f"{row.gap_pp:+.1f}",
                    va="center", fontsize=9)
        ax.axhline(len(table)-1.5, color="#999999", lw=0.8)
        ax.set_yticks(range(len(table)), table.index)
        ax.invert_yaxis()
        ax.set_xlim(0, 100 if q=="Q30" else max(65, table[["older_pct","young_pct"]].max().max()+12))
        ax.grid(axis="x", color="#e2e2e2")
        ax.set_axisbelow(True)
        ax.set_title(f"{q}   {title}", loc="left", weight="bold", fontsize=14)
        ax.set_xlabel("Weighted share of valid responses (%)")
        ax.spines[["top","left","right"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    labels = ["Non-Gen Z (30+)", "Gen Z (18–29)", "Gen Z, gap not significant"]
    handles = [Line2D([], [], marker="o", linestyle="", color=c, markerfacecolor=f, markersize=8)
               for c, f in [(OLD, OLD), (YOUNG, YOUNG), (YOUNG, "white")]]
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.text(0.03, 0.025, "Labels: Gen Z minus Non-Gen Z in percentage points. Hollow: approximate 5% test using Kish effective sample sizes.\n"
             "Country mean gives each country equal weight. DK/refused excluded. Source: Pew Spring 2025.")
    fig.subplots_adjust(left=0.11, right=0.985, top=0.92, bottom=0.11, wspace=0.38)
    prefix = args.output_dir / "generation_gaps"
    fig.savefig(prefix.with_suffix(".png"), dpi=180)
    plt.close(fig)
    pd.concat(tables, names=["question","country"]).to_csv(prefix.with_suffix(".csv"))


if __name__ == "__main__":
    main()

