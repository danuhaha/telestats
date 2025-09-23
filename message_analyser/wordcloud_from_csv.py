import argparse
import csv
from pathlib import Path
from typing import Dict, Optional, Set

import numpy as np
from wordcloud import WordCloud


# A compact Russian stopwords set covering pronouns, prepositions,
# conjunctions, particles, common function words, incl. variants with/without ё
STOPWORDS_RU: Set[str] = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "всё", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы",
    "за", "бы", "по", "только", "её", "ее", "мне", "было", "вот", "от", "меня",
    "еще", "ещё", "нет", "о", "из", "ему", "когда", "даже", "ну",
    "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас",
    "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их",
    "чем", "была", "сам", "чтоб", "лишь", "без", "будто", "чего", "раз", "тоже",
    "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому", "этого", "какой",
    "ним", "здесь", "этом", "один", "почти", "мой", "тем", "чтобы",
    "нее", "неё", "были", "при", "через", "эти", "нас", "про",
    "всего", "них", "какая", "много", "разве", "три", "эту", "моя", "впрочем",
    "хотя", "свой", "эта", "этой", "этом", "этому", "этих", "тех", "теми", "тем", "та",
    "те", "тем самым", "ну-ка", "вон", "ага", "эх", "ой", "ах", "ох", "мм", "ээ", "эээ",
    "я", "меня", "мне", "мною", "мое", "мои", "мой", "моя", "мое", "мои", "мы", "нас", "нам",
    "нами", "наш", "наша", "наше", "наши", "ты", "тебя", "тебе", "тобой", "твой", "твоя",
    "твое", "твои", "он", "его", "ему", "им", "его", "он", "она", "её", "ей", "ею", "она",
    "оно", "его", "ему", "им", "оно", "мы", "нас", "нам", "нами", "наш", "наша", "наше", "наши",
    "вы", "вас", "вам", "вами", "ваш", "ваша", "ваше", "ваши", "они", "их", "им", "ими", "их", "себя",
    "собой", "себе", "себе", "себя", "собой", "в", "на", "за", "под", "перед", "после", "от", "к", "с",
    "о", "у", "среди", "между", "через", "до", "для", "из", "при", "по", "около", "об", "из-за", "за", "над",
    "и", "да", "но", "если", "хотя", "чтобы", "что", "как", "или", "потому что", "либо", "то есть", "не",
    "ли", "бы", "же", "ах", "о", "ой", "ура", "который", "чьи", "чей", "какой", "какая", "какое", "какие",
    "кто", "что", "как", "где", "когда", "куда", "почему", "чем", "который", "что", "этот", "та", "то", "вот",
    "этот", "та", "так",
}


def _read_frequencies(csv_path: Path, column: str = "total") -> Dict[str, int]:
    """Read words and counts from the analyser's words CSV.

    column: one of "total", "you", "target" (case-insensitive)
    Expects headers like: Word, You sent, Target sent, Total. Falls back to
    positional columns if headers differ.
    """
    col = column.strip().lower()

    def pick_from_row_dict(row: dict) -> Optional[tuple[str, int]]:
        w = (row.get("Word") or row.get("word") or "").strip()
        if not w:
            return None
        lookup = {
            "total": row.get("Total") or row.get("total"),
            "you": row.get("You sent") or row.get("you sent") or row.get("you"),
            "target": row.get("Target sent") or row.get("target sent") or row.get("target"),
        }
        val = (lookup.get(col) or "").strip()
        try:
            count = int(val)
        except Exception:
            return None
        return (w, count)

    freq: Dict[str, int] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            for row in reader:
                picked = pick_from_row_dict(row)
                if picked and picked[1] > 0:
                    freq[picked[0]] = picked[1]
            if freq:
                return freq

    # Fallback: simple CSV; assume columns: word, you, target, total (at least word + last as count)
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        first = True
        for row in reader:
            if not row:
                continue
            # skip header row heuristically
            if first and any("word" in str(cell).lower() for cell in row):
                first = False
                continue
            first = False
            w = str(row[0]).strip()
            if not w:
                continue
            try:
                if col == "you" and len(row) >= 2:
                    count = int(str(row[1]).strip())
                elif col == "target" and len(row) >= 3:
                    count = int(str(row[2]).strip())
                else:
                    count = int(str(row[-1]).strip())
            except Exception:
                continue
            if count > 0:
                freq[w] = count
    return freq


def _circle_mask(width: int, height: int) -> np.ndarray:
    """Create a circular mask like the analyser's default."""
    radius = min(width, height) // 2
    cx, cy = width // 2, height // 2
    y, x = np.ogrid[:height, :width]
    mask = (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2
    return 255 * mask.astype(int)


def _build_wc(freq: Dict[str, int], width: int, height: int, background: str, circle: bool, out_path: Path):
    if not freq:
        return False
    mask = None if not circle else _circle_mask(width, height)
    wc = WordCloud(background_color=background, width=width, height=height, mask=mask).generate_from_frequencies(freq)
    wc.to_file(str(out_path))
    return True


def main():
    p = argparse.ArgumentParser(description="Generate word cloud(s) from analyser words CSV")
    p.add_argument("--csv", required=True, help="Path to results/.../words.txt (CSV with counts)")
    p.add_argument("--mode", choices=["all", "total", "you", "target"], default="all", help="Which cloud(s) to generate")
    p.add_argument("--out", help="Output PNG path (single mode) or base directory (all modes; defaults to CSV folder)")
    p.add_argument("--width", type=int, default=1000, help="Image width in pixels (default: 1000)")
    p.add_argument("--height", type=int, default=1000, help="Image height in pixels (default: 1000)")
    p.add_argument("--no-circle", action="store_true", help="Do not use a circular mask")
    p.add_argument("--background", default="white", help="Background color (default: white)")
    p.add_argument("--stopwords-ru", action="store_true", help="Filter common Russian stopwords")
    p.add_argument("--stopwords-file", help="Path to a file with stopwords (one per line)")
    p.add_argument("--min-length", type=int, default=1, help="Drop words shorter than this length after filtering")
    args = p.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    # Determine output(s)
    # Build stopwords set
    stopwords: Set[str] = set()
    if args.stopwords_ru:
        stopwords |= STOPWORDS_RU
    if args.stopwords_file:
        sp = Path(args.stopwords_file)
        if not sp.exists():
            raise SystemExit(f"Stopwords file not found: {sp}")
        for line in sp.read_text(encoding="utf-8-sig").splitlines():
            w = line.strip().lower()
            if w:
                stopwords.add(w)

    def apply_filters(freq: Dict[str, int]) -> Dict[str, int]:
        if not freq:
            return freq
        out: Dict[str, int] = {}
        for w, c in freq.items():
            wl = w.strip().lower()
            if args.min_length > 1 and len(wl) < args.min_length:
                continue
            if wl in stopwords:
                continue
            out[wl] = c
        return out

    if args.mode == "all":
        out_dir = Path(args.out) if args.out else csv_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "total": out_dir / "wordcloud_total.png",
            "you": out_dir / "wordcloud_you.png",
            "target": out_dir / "wordcloud_target.png",
        }
        made_any = False
        for key in ("total", "you", "target"):
            freq = apply_filters(_read_frequencies(csv_path, key))
            if _build_wc(freq, args.width, args.height, args.background, not args.no_circle, paths[key]):
                print(f"Saved: {paths[key]}")
                made_any = True
            else:
                print(f"Skipped {key}: no frequencies found")
        if not made_any:
            raise SystemExit("No clouds generated: empty frequencies for all modes")
        return

    # Single mode: one file
    out_path = Path(args.out) if args.out else csv_path.with_name(f"wordcloud_{args.mode}.png")
    freq = apply_filters(_read_frequencies(csv_path, args.mode))
    ok = _build_wc(freq, args.width, args.height, args.background, not args.no_circle, out_path)
    if not ok:
        raise SystemExit("No frequencies found in CSV (check columns and counts)")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
