
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.feature_selection import mutual_info_classif
from sklearn.preprocessing import LabelEncoder

# 1. Project setup
BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
PLOTS = OUT / "plots"

PLOTS.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid")

files = [
    "flows.csv",
    "hosts.csv",
    "sessions.csv",
    "labels.csv",
    "calendar.csv"
]

data = {}

# 2. Load datasets and inspect data
for filename in files:
    path = BASE / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Missing {filename}. Place it in {BASE}"
        )

    name = filename.replace(".csv", "")
    frame = pd.read_csv(path)

    frame.columns = (
        frame.columns.str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )

    data[name] = frame

    print(f"\n{name.upper()}: {frame.shape}")
    print(frame.head())
    print("\nData types:\n", frame.dtypes)
    print("\nMissing values:\n", frame.isnull().sum())
    print("Duplicate rows:", frame.duplicated().sum())

# 3. Remove duplicates and clean data
for name in data:
    data[name] = data[name].drop_duplicates().copy()

flows = data["flows"].copy()
hosts = data["hosts"].copy()
sessions = data["sessions"].copy()
labels = data["labels"].copy()
calendar = data["calendar"].copy()

if "flow_id" in flows.columns:
    print(
        "Duplicate flow IDs:",
        flows["flow_id"].duplicated().sum()
    )
    flows = flows.drop_duplicates(
        subset="flow_id", keep="first"
    )

if "protocol" in flows.columns:
    flows["protocol"] = (
        flows["protocol"]
        .astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
        .fillna("UNKNOWN")
    )

for col in ["duration", "bytes", "packets"]:
    if col in flows.columns:
        flows[col] = pd.to_numeric(
            flows[col], errors="coerce"
        )
        flows.loc[flows[col] < 0, col] = np.nan

        median = flows[col].median()
        flows[col] = flows[col].fillna(
            0 if pd.isna(median) else median
        )

if "timestamp" in flows.columns:
    flows["timestamp"] = pd.to_datetime(
        flows["timestamp"], errors="coerce"
    )

if "timestamp" in calendar.columns:
    calendar["timestamp"] = pd.to_datetime(
        calendar["timestamp"], errors="coerce"
    )

for col in ["label", "category", "event_category"]:
    if col in labels.columns:
        labels[col] = (
            labels[col].astype("string")
            .str.strip().str.lower()
        )
        labels[col] = labels[col].replace({
            "event: scan": "scan"
        })

for frame in [hosts, sessions]:
    for col in frame.select_dtypes(
        include=["object", "string"]
    ).columns:
        frame[col] = frame[col].astype("string").str.strip()

# 4. Merge datasets
df = flows.copy()

if "flow_id" in df.columns and "flow_id" in labels.columns:
    labels = labels.drop_duplicates("flow_id")
    df = df.merge(
        labels, on="flow_id", how="left",
        suffixes=("", "_label"),
        validate="one_to_one"
    )

host_keys = [
    key for key in ["host_id", "host_group_id", "host_group"]
    if key in df.columns and key in hosts.columns
]

if host_keys:
    key = host_keys[0]
    hosts = hosts.drop_duplicates(key)
    df = df.merge(
        hosts, on=key, how="left",
        suffixes=("", "_host"),
        validate="many_to_one"
    )
else:
    print("No common host key found.")

session_keys = [
    key for key in ["session_id", "flow_id"]
    if key in df.columns and key in sessions.columns
]

if session_keys:
    key = session_keys[0]
    sessions = sessions.drop_duplicates(key)
    df = df.merge(
        sessions, on=key, how="left",
        suffixes=("", "_session"),
        validate="many_to_one"
    )
else:
    print("No common session key found.")

if (
    "timestamp" in df.columns
    and "timestamp" in calendar.columns
):
    calendar = calendar.dropna(subset=["timestamp"])
    calendar = calendar.drop_duplicates("timestamp")

    calendar_cols = [
        col for col in calendar.columns
        if col not in df.columns or col == "timestamp"
    ]

    df = df.merge(
        calendar[calendar_cols],
        on="timestamp",
        how="left",
        suffixes=("", "_calendar"),
        validate="many_to_one"
    )

print("\nCombined dataset:", df.shape)

# 5. Feature engineering
if {"bytes", "duration"}.issubset(df.columns):
    df["bytes_per_second"] = (
        df["bytes"] / df["duration"].replace(0, np.nan)
    )

if {"packets", "duration"}.issubset(df.columns):
    df["packets_per_second"] = (
        df["packets"] / df["duration"].replace(0, np.nan)
    )

if {"bytes", "packets"}.issubset(df.columns):
    df["bytes_per_packet"] = (
        df["bytes"] / df["packets"].replace(0, np.nan)
    )

if "timestamp" in df.columns:
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["is_off_hours"] = (
        (df["hour"] < 6) | (df["hour"] >= 22)
    ).astype(int)

if "bytes" in df.columns:
    q1 = df["bytes"].quantile(0.25)
    q3 = df["bytes"].quantile(0.75)
    upper = q3 + 1.5 * (q3 - q1)

    df["extreme_bytes_flag"] = (
        df["bytes"] > upper
    ).astype(int)

    df["log_bytes"] = np.log1p(
        df["bytes"].clip(lower=0)
    )

# 6. Descriptive statistics
numeric_cols = df.select_dtypes(
    include=np.number
).columns.tolist()

if numeric_cols:
    df[numeric_cols].describe().T.to_csv(
        OUT / "descriptive_statistics.csv"
    )

# 7. EDA visualizations

# Protocol distribution
if "protocol" in df.columns:
    plt.figure(figsize=(8, 5))
    df["protocol"].value_counts().plot(kind="bar")
    plt.title("Network Flows by Protocol")
    plt.xlabel("Protocol")
    plt.ylabel("Number of Flows")
    plt.tight_layout()
    plt.savefig(PLOTS / "protocol_distribution.png", dpi=150)
    plt.close()

# Byte distribution
if "bytes" in df.columns:
    plt.figure(figsize=(8, 5))
    sns.histplot(data=df, x="bytes", bins=40)
    plt.title("Network Traffic Byte Distribution")
    plt.xlabel("Bytes")
    plt.tight_layout()
    plt.savefig(PLOTS / "bytes_distribution.png", dpi=150)
    plt.close()

# Correlation heatmap
numeric = [
    col for col in [
        "duration", "bytes", "packets",
        "bytes_per_second", "packets_per_second",
        "bytes_per_packet"
    ] if col in df.columns
]

if len(numeric) >= 2:
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        df[numeric].corr(),
        annot=True, cmap="coolwarm", fmt=".2f"
    )
    plt.title("Network Feature Correlation")
    plt.tight_layout()
    plt.savefig(PLOTS / "correlation_heatmap.png", dpi=150)
    plt.close()

# Traffic by hour
if "hour" in df.columns:
    hourly = df.groupby("hour").size().reindex(
        range(24), fill_value=0
    )

    plt.figure(figsize=(9, 5))
    hourly.plot(kind="line", marker="o")
    plt.title("Network Flow Volume by Hour")
    plt.xlabel("Hour")
    plt.ylabel("Number of Flows")
    plt.xticks(range(24))
    plt.tight_layout()
    plt.savefig(PLOTS / "hourly_traffic.png", dpi=150)
    plt.close()

# Event category comparisons
target = next(
    (col for col in ["label", "category", "event_category"]
     if col in df.columns),
    None
)

if target:
    for col in ["bytes", "duration", "packets"]:
        if col in df.columns:
            plt.figure(figsize=(9, 5))
            sns.boxplot(data=df, x=target, y=col)
            plt.title(f"{col.title()} by Event Category")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(
                PLOTS / f"{col}_by_category.png",
                dpi=150
            )
            plt.close()

# Port distribution
if "port_category" in df.columns:
    plt.figure(figsize=(9, 5))
    df["port_category"].value_counts().plot(kind="bar")
    plt.title("Network Flows by Port Category")
    plt.xlabel("Port Category")
    plt.ylabel("Number of Flows")
    plt.tight_layout()
    plt.savefig(PLOTS / "port_distribution.png", dpi=150)
    plt.close()

# 8. Encode categorical variables
categorical = [
    col for col in [
        "protocol", "source_zone", "destination_zone",
        "port_category", "host_group", "network_zone"
    ] if col in df.columns
]

encoded = pd.get_dummies(
    df, columns=categorical, dummy_na=True, dtype=int
)

# 9. Feature selection
if target and target in df.columns:
    candidates = [
        col for col in [
            "duration", "bytes", "packets",
            "bytes_per_second", "packets_per_second",
            "bytes_per_packet", "hour", "weekday",
            "is_weekend", "is_off_hours",
            "extreme_bytes_flag", "log_bytes"
        ] if col in df.columns
    ]

    work = df[candidates + [target]].copy()
    work = work.replace([np.inf, -np.inf], np.nan)
    work = work.dropna(subset=[target])

    if candidates and len(work) > 1:
        X = work[candidates].fillna(
            work[candidates].median()
        ).fillna(0)

        y = LabelEncoder().fit_transform(
            work[target].astype(str)
        )

        if len(np.unique(y)) > 1:
            scores = mutual_info_classif(
                X, y, random_state=42
            )

            importance = pd.Series(
                scores, index=candidates,
                name="mutual_information"
            ).sort_values(ascending=False)

            importance.to_csv(
                OUT / "feature_importance.csv"
            )

            selected = importance[importance > 0].index.tolist()

            pd.DataFrame({
                "selected_feature": selected
            }).to_csv(
                OUT / "selected_features.csv",
                index=False
            )

            plt.figure(figsize=(9, 5))
            importance.sort_values().plot(kind="barh")
            plt.title("Feature Importance")
            plt.xlabel("Mutual Information")
            plt.tight_layout()
            plt.savefig(
                PLOTS / "feature_importance.png", dpi=150
            )
            plt.close()

            print("\nFeature importance:\n", importance)
        else:
            print("Feature selection skipped: only one label class.")
    else:
        print("Feature selection skipped: insufficient data.")
else:
    print("Feature selection skipped: no target label found.")

# 10. Save final datasets and quality report
df.to_csv(OUT / "cleaned_network_flows.csv", index=False)
encoded.to_csv(OUT / "encoded_network_flows.csv", index=False)

pd.DataFrame({
    "column": df.columns,
    "missing_values": [df[col].isna().sum() for col in df.columns],
    "data_type": [str(df[col].dtype) for col in df.columns]
}).to_csv(OUT / "data_quality_summary.csv", index=False)

print("\n" + "=" * 50)
print("PROCESS COMPLETED SUCCESSFULLY")
print("=" * 50)
print("Cleaned dataset:", OUT / "cleaned_network_flows.csv")
print("Encoded dataset:", OUT / "encoded_network_flows.csv")
print("Plots directory:", PLOTS)

for path in sorted(OUT.rglob("*")):
    if path.is_file():
        print(path.relative_to(BASE))
