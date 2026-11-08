"""Plot Q30 and Q31 weighted response shares and generation gaps by country."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["Gen Z", "Older"]
COLORS = ["#18756f", "#b0bfd1", "#b95732"]
QUESTIONS = [
    ("Q30", "ai_heard", "How much have people heard about AI?",
     {1: "A lot", 2: "A little", 3: "Nothing at all"}),
    ("Q31", "ai_cncexc", "How do people feel about AI in daily life?",
     {1: "More excited", 3: "Equally concerned and excited", 2: "More concerned"}),
]


def shares(data, variable, answers):
    valid = data.dropna(subset=[variable, "generation"])
    if not valid[variable].isin(answers).all() or not valid.generation.isin(GROUPS).all():
        raise ValueError(f"Unexpected answer or generation for {variable}")
    if not (np.isfinite(valid.weight) & valid.weight.gt(0)).all():
        raise ValueError("Invalid survey weight")
    cells = valid.groupby(["cname", "generation", variable]).weight.sum().unstack(fill_value=0)
    cells = cells.reindex(columns=list(answers), fill_value=0)
    expected = pd.MultiIndex.from_product([sorted(data.cname.unique()), GROUPS])
    pct = cells.div(cells.sum(axis=1), axis=0).mul(100).reindex(expected)
    if not np.allclose(pct.sum(axis=1), 100):
        raise ValueError("A country or generation has no valid responses")
    return pct


def plot(pct, question, title, answers, output):
    countries = pct.index.get_level_values(0).unique()
    fig, axes = plt.subplots(1, 2, figsize=(16, 13))
    for ax, block in zip(axes, np.array_split(countries.to_numpy(), 2)):
        ax.set(xlim=(-42, 102), ylim=(len(block)*3.8-0.65, -0.85))
        ax.axis("off")
        for i, country in enumerate(block):
            y = i*3.8
            pair = pct.loc[country].loc[GROUPS].to_numpy()
            ax.text(-41, y, country, weight="bold", fontsize=11)
            # Fixed positions keep small percentages and gaps readable.
            for row, label in enumerate(["Gen Z", "Non-Gen Z"]):
                pos = y + 0.72 + row*0.73
                ax.text(-2, pos, label, ha="right", va="center", fontsize=9)
                left = 0
                for width, color in zip(pair[row], COLORS):
                    ax.barh(pos, width, left=left, height=0.55, color=color)
                    left += width
            # Show both shares even when a segment is too narrow for text.
            for j, (young, older) in enumerate(pair.T):
                x = (j+0.5)*100/3
                ax.text(x, y, f"{young:.1f}% / {older:.1f}%", ha="center",
                        fontsize=9, color="#243447")
                ax.text(x, y+2.37, f"{young-older:+.1f} pp", ha="center", fontsize=9)
            ax.text(-2, y+2.37, "Gap", fontsize=9, ha="right")
            ax.axhline(y+2.9, color="#d9dee2", lw=0.6)
    fig.suptitle(f"{question}   {title}", fontsize=20, y=0.978)
    fig.legend([Patch(color=c) for c in COLORS], answers.values(), loc="upper center",
               bbox_to_anchor=(0.5, 0.949), ncol=3, frameon=False)
    fig.text(0.5, 0.902, "Values above bars: Gen Z / Non-Gen Z, in legend order.    Gap: Gen Z minus Non-Gen Z (percentage points).", ha="center")
    fig.text(0.04, 0.022, "Pew Spring 2025   |   Weighted within each country and age group   |   Gen Z: 18–29; Non-Gen Z: 30+   |   Valid answers only")
    fig.subplots_adjust(left=0.035, right=0.985, top=0.878, bottom=0.05, wspace=0.08)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "Data/Output/clean.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/generation_responses")
    args = parser.parse_args()
    data = pd.read_csv(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for question, variable, title, answers in QUESTIONS:
        pct = shares(data, variable, answers)
        plot(pct, question, title, answers, args.output_dir / f"{question}.png")


if __name__ == "__main__":
    main()
