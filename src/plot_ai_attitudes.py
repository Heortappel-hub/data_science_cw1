"""Plot weighted Q31 response distributions within predictor groups in each country."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ANSWERS = {1: "More excited", 3: "Equally concerned and excited", 2: "More concerned"}
COLORS = ["#197873", "#d3d9dd", "#ad5135"]


def distributions(data, group, levels):
    frame = data.assign(group=group).dropna(subset=["group", "ai_cncexc", "weight"])
    if not frame.ai_cncexc.isin(ANSWERS).all() or not (frame.weight > 0).all():
        raise ValueError("Unexpected Q31 response or nonpositive survey weight")
    keys = ["cname", "group"]
    cells = frame.groupby(keys + ["ai_cncexc"], observed=True).weight.sum().unstack(fill_value=0)
    cells = cells.reindex(columns=list(ANSWERS), fill_value=0)
    pct = cells.div(cells.sum(axis=1), axis=0).mul(100).rename(columns=ANSWERS)
    pct["n"] = frame.groupby(keys, observed=True).size()
    countries = sorted(data.cname.unique())
    return pct.reindex(pd.MultiIndex.from_product([countries, levels], names=keys))


def plot(table, title, note, output):
    countries = table.index.get_level_values("cname").unique()
    cols = min(4, len(countries))
    rows = (len(countries) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.8 * cols, 3.4 * rows + 1.8), squeeze=False)
    for ax, country in zip(axes.flat, countries):
        block = table.loc[country]
        y = np.arange(len(block))
        left = np.zeros(len(block))
        # Use a separate label line for the entire bar if any segment is too narrow.
        narrow = block[list(ANSWERS.values())].min(axis=1).lt(16).to_numpy()
        for index, (answer, color) in enumerate(zip(ANSWERS.values(), COLORS)):
            widths = block[answer].fillna(0).to_numpy()
            ax.barh(y, widths, left=left, color=color, height=0.49)
            for pos in y[block.n.notna()]:
                if narrow[pos]:
                    x = (index + 0.5) * 100 / 3
                    dy = 0.40
                    ink = ["#125e5a", "#444c50", "#913f28"][index]
                else:
                    x = left[pos] + widths[pos] / 2
                    dy = 0
                    ink = "#233136" if index == 1 else "white"
                ax.text(x, pos + dy, f"{widths[pos]:.1f}%", ha="center",
                        va="center", fontsize=8, color=ink)
            left += widths
        ax.set_yticks(y, block.index)
        ax.set_ylim(len(block) - 0.30, -0.5)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 50, 100], ["0%", "50%", "100%"])
        for pos in y[block.n.isna()]:
            ax.text(2, pos, "No valid responses", va="center", fontsize=8, color="#666666")
        ax.set_title(country, loc="left", fontsize=11, fontweight="bold")
        ax.tick_params(labelsize=8, length=0)
        ax.spines[["top", "right", "left"]].set_visible(False)
    for ax in list(axes.flat)[len(countries):]:
        ax.set_visible(False)
    fig.suptitle(title, fontsize=17, y=0.985)
    fig.legend([Patch(color=c) for c in COLORS], list(ANSWERS.values()),
               loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=3, frameon=False)
    fig.text(0.02, 0.017, "Each bar = 100% of valid Q31 responses in the group, using Pew survey weights. " + note, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92), h_pad=1.8)
    fig.savefig(output, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "Data/Output/clean.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/ai_attitude_distributions")
    args = parser.parse_args()
    data = pd.read_csv(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ages = ["18–29", "30–49", "50–64", "65+"]
    age = pd.cut(data.age_assigned, [18, 30, 50, 65, np.inf], right=False, labels=ages)
    internet = {1: "Almost constantly", 2: "Several times/day", 3: "About once/day",
                4: "Several times/week", 5: "Less often", 6: "Never"}
    education = {1: "Low (0–2)", 2: "Middle (3–4)", 3: "High (5–8)"}
    for key, title, group, levels, note in [
        ("age", "AI attitudes by age group", age, ages, "Age bands match Australia's published groups."),
        ("politics", "AI attitudes by political self-placement", data.ideology, list(range(7)),
         "0–6: left to right; in Japan and South Korea: progressive to conservative."),
        ("internet", "AI attitudes by internet use (Q105)", data.internetfreq.map(internet), list(internet.values()),
         "Australia has no public Q105 data."),
        ("education", "AI attitudes by harmonised education", data.educ_harmonised.map(education),
         list(education.values()), "Education groups use mapped ISCED levels.")]:
        table = distributions(data, group, levels)
        table.to_csv(args.output_dir / f"{key}.csv", encoding="utf-8-sig")
        plot(table, title, note, args.output_dir / f"{key}.png")


if __name__ == "__main__":
    main()
