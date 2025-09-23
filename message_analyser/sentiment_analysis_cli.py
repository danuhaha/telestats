import argparse
import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd
from transformers import pipeline

from message_analyser.retriever.telegram_html import get_mymessages_from_html


def batched(iterable, n=64):
    batch = []
    for x in iterable:
        batch.append(x)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


def run_pipe_avg_scores(pipe, texts: List[str]) -> Dict[str, float]:
    agg: Dict[str, float] = {}
    count = 0
    for batch in batched(texts, 32):
        outs = pipe(batch, truncation=True, max_length=256)
        for res in outs:
            count += 1
            if isinstance(res, list):
                for d in res:
                    agg[d['label']] = agg.get(d['label'], 0.0) + float(d['score'])
            elif isinstance(res, dict):
                agg[res['label']] = agg.get(res['label'], 0.0) + float(res['score'])
    if count == 0:
        return {}
    return {k: v / count for k, v in agg.items()}


def run_pipe_frac_above(pipe, texts: List[str], positive_labels=None, threshold=0.5) -> float:
    if positive_labels is not None:
        positive_labels = set(positive_labels)
    pos = 0
    total = 0
    for batch in batched(texts, 64):
        outs = pipe(batch, truncation=True, max_length=256)
        for res in outs:
            total += 1
            if isinstance(res, list):
                best = max(res, key=lambda d: d['score'])
                lab, score = best['label'], float(best['score'])
            else:
                lab, score = res['label'], float(res['score'])
            if (positive_labels is None and score >= threshold) or (positive_labels and lab in positive_labels and score >= threshold):
                pos += 1
    return (pos / total) if total else 0.0


def normalize_texts(msgs, min_len=5):
    return [m.text.strip() for m in msgs if m.text and len(m.text.strip()) >= min_len]


def sample_texts(texts: List[str], max_n=200):
    if len(texts) <= max_n:
        return texts
    step = len(texts) / max_n
    return [texts[math.floor(i * step)] for i in range(max_n)]


def split_into_conversations(messages, gap_minutes=30):
    if not messages:
        return []
    convos = []
    current = [messages[0]]
    gap = timedelta(minutes=gap_minutes)
    for m in messages[1:]:
        if (m.date - current[-1].date) > gap:
            convos.append(current)
            current = [m]
        else:
            current.append(m)
    convos.append(current)
    return convos


def main():
    ap = argparse.ArgumentParser(description="Conversation-level sentiment/topics from Telegram HTML export")
    ap.add_argument("--export", required=True, help="Path to ChatExport folder or messages.html")
    ap.add_argument("--your-name", required=True)
    ap.add_argument("--target-name", required=True)
    ap.add_argument("--gap-min", type=int, default=30, help="Gap (minutes) to split conversations")
    ap.add_argument("--max-per-convo", type=int, default=200, help="Max texts per conversation for inference")
    ap.add_argument("--max-total", type=int, default=2000, help="Max texts for whole-chat rollup")
    ap.add_argument("--out-dir", help="Output directory (default: <export>/analysis_outputs)")
    ap.add_argument("--device", type=int, default=0, help="Transformers device (0=gpu, -1=cpu)")
    args = ap.parse_args()

    export_path = Path(args.export)
    if not export_path.exists():
        raise SystemExit(f"Export path not found: {export_path}")

    msgs = get_mymessages_from_html(str(export_path), args.your_name, args.target_name)
    conversations = split_into_conversations(msgs, args.gap_min)

    device = args.device
    emo_pipe = pipeline('text-classification', model='Aniemore/rubert-tiny2-russian-emotion-detection', device=device, top_k=None)
    tox_pipe = pipeline('text-classification', model='s-nlp/russian_toxicity_classifier', device=device, top_k=None)
    sens_pipe = pipeline('text-classification', model='apanc/russian-sensitive-topics', device=device, top_k=None)

    rows = []
    for idx, conv in enumerate(conversations):
        texts_all = normalize_texts(conv)
        if not texts_all:
            continue
        texts = sample_texts(texts_all, args.max_per_convo)
        emo_scores = run_pipe_avg_scores(emo_pipe, texts)
        tox_frac = run_pipe_frac_above(tox_pipe, texts, positive_labels={'toxic', 'toxicity', 'TOXIC'})
        sens_scores = run_pipe_avg_scores(sens_pipe, texts)
        start, end = conv[0].date, conv[-1].date
        rows.append({
            'conversation_id': idx,
            'start': start,
            'end': end,
            'duration_min': (end - start).total_seconds() / 60.0,
            'num_messages': len(conv),
            'num_texts_used': len(texts),
            'toxicity_rate': tox_frac,
            **{f'emo_{k}': v for k, v in emo_scores.items()},
            **{f'topic_{k}': v for k, v in sens_scores.items()},
        })

    df = pd.DataFrame(rows).sort_values(['start']).reset_index(drop=True)

    out_dir = Path(args.out_dir) if args.out_dir else export_path / 'analysis_outputs'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / 'sentiment_topics_by_conversation.csv'
    df.to_csv(out_csv, index=False)

    # Whole chat rollup
    texts_all = sample_texts(normalize_texts(msgs), args.max_total)
    emo_all = run_pipe_avg_scores(emo_pipe, texts_all)
    tox_all = run_pipe_frac_above(tox_pipe, texts_all, positive_labels={'toxic', 'toxicity', 'TOXIC'})
    sens_all = run_pipe_avg_scores(sens_pipe, texts_all)
    pd.Series(emo_all).to_csv(out_dir / 'overall_emotions.csv')
    pd.Series(sens_all).to_csv(out_dir / 'overall_topics.csv')
    (out_dir / 'overall_toxicity.txt').write_text(str(tox_all))

    print(f"Saved: {out_csv}")
    print(f"Saved: {out_dir / 'overall_emotions.csv'}")
    print(f"Saved: {out_dir / 'overall_topics.csv'}")
    print(f"Saved: {out_dir / 'overall_toxicity.txt'}")


if __name__ == '__main__':
    main()
