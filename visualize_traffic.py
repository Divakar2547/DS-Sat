from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


BASE = Path(__file__).parent
SOURCE = BASE / "output" / "cleaned_network_flows.csv"
OUTPUT = BASE / "NetShield_Visualization.png"


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Cleaned traffic data not found: {SOURCE}")

    df = pd.read_csv(SOURCE)
    df["label"] = df["label"].astype(str).str.strip().str.lower()
    df["unusual"] = df["label"].ne("normal")
    overall = df["unusual"].mean()

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), facecolor="#f5f7fb")
    fig.subplots_adjust(top=0.86, hspace=0.46, wspace=0.32)
    fig.suptitle(
        "NetShield | Network Traffic Insights",
        fontsize=23,
        fontweight="bold",
        color="#14213d",
        y=0.97,
    )
    fig.text(
        0.5,
        0.915,
        f"{len(df):,} flows analyzed  |  {df['unusual'].sum():,} unusual  |  "
        f"{overall:.1%} overall unusual rate",
        ha="center",
        fontsize=12,
        color="#52627a",
    )
    colors = [
        "#2a9d8f",
        "#e76f51",
        "#e9c46a",
        "#457b9d",
        "#8e6cbb",
        "#f4a261",
        "#52b788",
    ]

    ax = axes[0, 0]
    protocol_rates = (
        df.groupby("protocol")["unusual"]
        .agg(["mean", "count"])
        .sort_values("mean", ascending=False)
        .head(8)
        .sort_values("mean")
    )
    bars = ax.barh(
        protocol_rates.index.astype(str),
        protocol_rates["mean"] * 100,
        color="#e76f51",
    )
    ax.axvline(
        overall * 100,
        color="#14213d",
        linestyle="--",
        linewidth=1.5,
        label=f"Overall {overall:.1%}",
    )
    ax.set_title("Unusual rate by protocol", loc="left", fontweight="bold", color="#14213d")
    ax.set_xlabel("Unusual flows (%)")
    ax.legend(frameon=False, fontsize=9)
    for bar, value in zip(bars, protocol_rates["mean"] * 100):
        ax.text(
            value + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%",
            va="center",
            fontsize=9,
        )

    ax = axes[0, 1]
    hourly_rates = (
        df.groupby("hour")["unusual"].mean().reindex(range(24)).fillna(0)
    )
    ax.plot(
        hourly_rates.index,
        hourly_rates * 100,
        color="#e76f51",
        marker="o",
        linewidth=2,
        markersize=4,
        label="Unusual rate",
    )
    ax.axhline(
        overall * 100,
        color="#14213d",
        linestyle="--",
        linewidth=1.3,
        label=f"Overall {overall:.1%}",
    )
    ax.set_title("Unusual rate by hour", loc="left", fontweight="bold", color="#14213d")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Unusual flows (%)")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1, 0]
    host_rates = (
        df.groupby("host_group")["unusual"]
        .agg(["mean", "count"])
        .sort_values("mean", ascending=False)
        .head(8)
        .sort_values("mean")
    )
    bars = ax.barh(
        host_rates.index.astype(str),
        host_rates["mean"] * 100,
        color="#457b9d",
    )
    ax.axvline(overall * 100, color="#14213d", linestyle="--", linewidth=1.5)
    ax.set_title("Unusual rate by host group", loc="left", fontweight="bold", color="#14213d")
    ax.set_xlabel("Unusual flows (%)")
    for bar, value in zip(bars, host_rates["mean"] * 100):
        ax.text(
            value + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}%",
            va="center",
            fontsize=9,
        )

    ax = axes[1, 1]
    all_counts = df["label"].value_counts()
    label_counts = all_counts.head(7).copy()
    if len(all_counts) > 7:
        label_counts.loc["other"] = all_counts.iloc[7:].sum()
    wedges, _, _ = ax.pie(
        label_counts.values,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 4 else "",
        startangle=90,
        colors=colors[: len(label_counts)],
        wedgeprops={"width": 0.43, "edgecolor": "white"},
        textprops={"fontsize": 9},
    )
    ax.text(
        0,
        0,
        f"{len(df):,}\nflows",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="#14213d",
    )
    ax.set_title("Traffic labels", loc="left", fontweight="bold", color="#14213d")
    ax.legend(
        wedges,
        [f"{label} ({count:,})" for label, count in label_counts.items()],
        loc="center left",
        bbox_to_anchor=(0.92, 0.5),
        frameon=False,
        fontsize=8,
    )

    for ax in axes.flat:
        ax.set_facecolor("#ffffff")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.22)

    fig.text(
        0.01,
        0.015,
        "Descriptive analysis of cleaned network flows. Rates are grouped averages; "
        "small groups may vary.",
        fontsize=8,
        color="#6b7280",
    )
    fig.savefig(OUTPUT, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved visualization to: {OUTPUT}")


if __name__ == "__main__":
    main()
