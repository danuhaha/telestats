import argparse
from collections import Counter
from pathlib import Path

import pandas as pd


def _first_name_from_top(cell: str, prefix_to_strip: str = "") -> str | None:
    if not isinstance(cell, str):
        return None
    s = cell.strip()
    if not s:
        return None
    # Expect format like "name:0.42, name2:0.21, name3:0.10"
    first = s.split(",", 1)[0].strip()
    if ":" in first:
        name = first.split(":", 1)[0].strip()
    else:
        name = first
    if prefix_to_strip and name.lower().startswith(prefix_to_strip.lower()):
        name = name[len(prefix_to_strip):]
        # strip any leftover underscore if prefix is like 'emo_'
        if name.startswith("_"):
            name = name[1:]
    return name or None


def main():
    ap = argparse.ArgumentParser(description="Summarize conversation-level CSV: avg toxicity, first top emotion/topic counts")
    ap.add_argument(
        "--csv",
        default=str(Path("results/analysis_outputs/sentiment_topics_by_conversation_labeled_clean.csv")),
        help="Path to labeled & cleaned conversations CSV",
    )
    ap.add_argument(
        "--out-dir",
        help="Directory to write summaries (default: alongside CSV)",
    )
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # 1) Average toxicity rate
    if "toxicity_rate" not in df.columns:
        raise SystemExit("Column 'toxicity_rate' not found in CSV")
    avg_tox = float(pd.to_numeric(df["toxicity_rate"], errors="coerce").dropna().mean()) if len(df) else 0.0

    # 2) First top emotion counts (strip optional 'emo_' prefix)
    if "top_emotions" not in df.columns:
        raise SystemExit("Column 'top_emotions' not found in CSV")
    emo_counts = Counter()
    for v in df["top_emotions"].tolist():
        name = _first_name_from_top(v, prefix_to_strip="emo_")
        if name:
            emo_counts[name] += 1

    # 3) First top topic counts (strip optional 'topic_' prefix)
    if "top_topics" not in df.columns:
        raise SystemExit("Column 'top_topics' not found in CSV")
    topic_counts = Counter()
    for v in df["top_topics"].tolist():
        name = _first_name_from_top(v, prefix_to_strip="topic_")
        if name:
            topic_counts[name] += 1

    out_dir = Path(args.out_dir) if args.out_dir else csv_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write outputs
    (out_dir / "toxicity_average.txt").write_text(f"{avg_tox}\n", encoding="utf-8")
    pd.Series(emo_counts).sort_values(ascending=False).to_csv(out_dir / "first_top_emotions_counts.csv", header=["count"])
    pd.Series(topic_counts).sort_values(ascending=False).to_csv(out_dir / "first_top_topics_counts.csv", header=["count"])

    # Also print to stdout for convenience
    print(f"Average toxicity_rate: {avg_tox:.6f}")
    print("Top-1 emotion counts:")
    for k, v in emo_counts.most_common():
        print(f"  {k}: {v}")
    print("Top-1 topic counts:")
    for k, v in topic_counts.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

