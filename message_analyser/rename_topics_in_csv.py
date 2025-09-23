import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


def _coerce_mapping(data: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for k, v in data.items():
        lab = str(v)
        if isinstance(k, int):
            out[k] = lab
            continue
        ks = str(k)
        try:
            out[int(ks)] = lab
            continue
        except Exception:
            pass
        m = re.search(r"(\d+)$", ks)
        if m:
            out[int(m.group(1))] = lab
    return out


def load_id2label(source: str | None, csv_path: Path | None = None) -> Dict[int, str]:
    """Load id2label mapping with sensible defaults.

    Priority:
    1) Explicit --id2label-file path
    2) A file named id2topic.json next to the CSV (csv_dir/id2topic.json)
    3) results/analysis_outputs/id2topic.json relative to repo root
    4) Hugging Face config for 'apanc/russian-sensitive-topics'
    """
    if source and source not in {"hf", "HF"}:
        p = Path(source)
        if not p.exists():
            raise SystemExit(f"id2label file not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        out = _coerce_mapping(data)
        if not out:
            raise SystemExit("id2label file has no usable mappings")
        print(f"Using id2label from: {p}")
        return out

    if csv_path is not None:
        candidate = csv_path.parent / "id2topic.json"
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8-sig"))
            out = _coerce_mapping(data)
            if out:
                print(f"Using id2label from: {candidate}")
                return out

    candidate = Path("results/analysis_outputs/id2topic.json")
    if candidate.exists():
        data = json.loads(candidate.read_text(encoding="utf-8-sig"))
        out = _coerce_mapping(data)
        if out:
            print(f"Using id2label from: {candidate}")
            return out

    try:
        from transformers import AutoConfig  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "transformers is required to fetch id2label from the model config, "
            "or provide --id2label-file or place id2topic.json next to the CSV."
        ) from exc

    cfg = AutoConfig.from_pretrained("apanc/russian-sensitive-topics")
    id2label = getattr(cfg, "id2label", None) or {}
    out = _coerce_mapping(id2label)
    if not out:
        raise SystemExit("Could not obtain id2label mapping from model config")
    print("Using id2label from HF model config")
    return out


def normalize_topic_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+/\s+", "/", s)
    s = s.replace(" ", "_")
    s = s.replace("/", "-")
    return s


def build_renames(columns, id2label: Dict[int, str]) -> Dict[str, str]:
    renames: Dict[str, str] = {}
    for col in columns:
        if not isinstance(col, str):
            continue
        if not col.startswith("topic_"):
            continue
        m = re.match(r"^topic_?label_([0-9]+)$", col, flags=re.IGNORECASE)
        if not m:
            continue
        idx = int(m.group(1))
        label = id2label.get(idx)
        if not label:
            continue
        new_col = f"topic_{normalize_topic_name(label)}"
        renames[col] = new_col
    return renames


def main():
    ap = argparse.ArgumentParser(description="Rename topic_LABEL_* columns in CSV using model id2label mapping")
    ap.add_argument("--csv", required=True, help="Path to sentiment_topics_by_conversation.csv")
    ap.add_argument("--out", help="Output CSV path (default: *_labeled.csv or *_clean.csv next to input)")
    ap.add_argument("--id2label-file", help="Optional JSON file with id->label mapping (use if offline)")
    ap.add_argument("--keep-only", action="store_true", help="Keep only a minimal set of columns")
    ap.add_argument(
        "--keep-cols",
        nargs="*",
        default=[
            "conversation_id",
            "start",
            "end",
            "num_messages",
            "toxicity_rate",
            "top_emotions",
            "top_topics",
        ],
        help="Columns to keep when --keep-only is set",
    )
    args = ap.parse_args()

    in_path = Path(args.csv)
    if not in_path.exists():
        raise SystemExit(f"CSV not found: {in_path}")
    # Decide default output later based on ops
    out_path = Path(args.out) if args.out else None

    id2label = load_id2label(args.id2label_file, in_path)
    if not id2label:
        raise SystemExit("Failed to obtain id2label mapping")

    df = pd.read_csv(in_path)
    renames = build_renames(df.columns, id2label)
    if not renames:
        print("No topic_LABEL_* columns found to rename. Saving a copy anyway.")
    else:
        print("Renaming columns:")
        for k, v in renames.items():
            print(f"  {k} -> {v}")
        df = df.rename(columns=renames)

    # Fix label tokens inside the 'top_topics' string column
    if "top_topics" in df.columns:
        def _sub_row(val: str) -> str:
            if not isinstance(val, str):
                return val
            def _repl(m):
                idx = int(m.group(1))
                label = id2label.get(idx)
                if not label:
                    return m.group(0)
                return "topic_" + normalize_topic_name(label)
            s = re.sub(r"topic_?label_(\d+)", _repl, val, flags=re.IGNORECASE)
            s = re.sub(r"\bLABEL_(\d+)\b", _repl, s, flags=re.IGNORECASE)
            return s
        df["top_topics"] = df["top_topics"].map(_sub_row)

    # Optionally keep only selected columns
    if args.keep_only:
        keep: List[str] = args.keep_cols
        missing = [c for c in keep if c not in df.columns]
        if missing:
            print("Warning: missing columns:", ", ".join(missing))
        df = df[[c for c in keep if c in df.columns]]

    # Choose default output name if not provided
    if out_path is None:
        suffix = "_clean" if args.keep_only else "_labeled"
        out_path = in_path.with_name(in_path.stem + suffix + in_path.suffix)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
