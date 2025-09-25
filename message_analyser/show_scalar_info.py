#!/usr/bin/env python3
"""Render key scalar stats from a CSV file using the cyberpunk theme."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import ft2font
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

import mplcyberpunk

TARGET_KEYS = (
    "Duration:",
    "Most active day:",
    "Average messages per day:",
    "Days without messages:",
    "Longest pause:",
)

TIME_PATTERN = re.compile(r"^(?P<hours>\d+):(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})")

ICON_MAP = {
    "Most active day": "tabler_calendar-bolt.png",
    "On average": "tabler_chart-histogram.png",
    "Days w/out messages": "tabler_hexagon-minus.png",
    "Longest pause": "tabler_clock-pause.png",
}

VALUE_COLOR_MAP = {
    "Most active day": "#4DA8B5",
    "On average": "#7E328C",
    "Days w/out messages": "#B8357E",
    "Longest pause": "#547BC3",
}


def _load_roboto(weight: str = "Regular") -> FontProperties | None:
    base_dir = Path(__file__).resolve().parent.parent / "message_analyser" / "Roboto" / "static"
    font_path = base_dir / f"Roboto-{weight}.ttf"
    if not font_path.exists():
        return None
    try:
        ft2font.FT2Font(str(font_path))
    except Exception:
        return None
    fontManager.addfont(str(font_path))
    return FontProperties(fname=str(font_path))


def _extract_rows(csv_path: Path) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if key in TARGET_KEYS:
                values = [cell.strip().strip(",") for cell in row[1:] if cell.strip()]
                rows[key] = values
            if len(rows) == len(TARGET_KEYS):
                break
    if not rows:
        raise ValueError(
            f"No matching rows found in {csv_path}. Expected keys: {', '.join(TARGET_KEYS)}"
        )
    return rows


def _load_icon_image(icon_path: Path) -> OffsetImage | None:
    if not icon_path.exists():
        return None

    try:
        image = plt.imread(str(icon_path))
    except Exception:
        return None

    return OffsetImage(image, zoom=0.12)


def _format_date(date_str: str) -> str:
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%d %b %Y")
        except ValueError:
            continue
    return date_str.strip()


def _format_most_active(values: list[str]) -> tuple[str, str]:
    if not values:
        return "", ""
    combined = " ".join(values)
    if ":" in combined:
        date_part, message_part = combined.split(":", 1)
        return _format_date(date_part), message_part.strip()
    if len(values) >= 2:
        return _format_date(values[0]), values[1]
    return _format_date(values[0]), ""


def _format_average(values: list[str]) -> str:
    if not values:
        return ""
    number_str = values[0].split()[0]
    try:
        average = round(float(number_str))
        return f"{average} msgs/day"
    except ValueError:
        return " ".join(values)


def _format_days_without(values: list[str]) -> str:
    if not values:
        return "0"
    return values[0]


def _format_longest_pause(raw_value: str) -> tuple[str, str]:
    if not raw_value:
        return "", ""

    time_part, sep, rest = raw_value.partition("From")
    match = TIME_PATTERN.match(time_part.strip())
    if not match:
        return raw_value, ""

    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))

    total_seconds = hours * 3600 + minutes * 60 + seconds
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        if total_seconds > 0:
            parts.append("<1m")
        else:
            parts.append("0m")

    formatted_duration = " ".join(parts)
    date_str = ""
    if sep and rest:
        date_range = rest.strip()
        from_part, _, to_part = date_range.partition("to")
        from_formatted = _format_date(from_part) if from_part else ""
        to_formatted = _format_date(to_part) if to_part else ""
        if from_formatted and to_formatted:
            date_str = f"{from_formatted} - {to_formatted}"
        else:
            date_str = date_range

    return formatted_duration, date_str


def _extract_values(csv_path: Path) -> dict[str, str]:
    rows = _extract_rows(csv_path)

    most_active_date, most_active_msgs = _format_most_active(rows.get("Most active day:", []))
    avg_messages = _format_average(rows.get("Average messages per day:", []))
    days_without = _format_days_without(rows.get("Days without messages:", []))
    duration_row = rows.get("Duration:", [""])
    duration_label = duration_row[0] if duration_row else ""
    duration_days_value = ""
    if duration_label:
        day_token = duration_label.split("days", 1)[0].strip()
        digits = ''.join(ch for ch in day_token if ch.isdigit())
        if digits:
            duration_days_value = digits
    longest_duration, longest_range = _format_longest_pause(" ".join(rows.get("Longest pause:", [])))

    return {
        "Duration label": duration_label,
        "Duration days": duration_days_value,
        "Most active day": most_active_date,
        "Most active day messages": most_active_msgs,
        "Average messages": avg_messages,
        "Days without messages": days_without,
        "Longest pause": longest_duration,
        "Longest pause range": longest_range,
    }


def render_scalar_info(csv_path: Path, save_path: Path | None = None) -> None:
    plt.style.use("cyberpunk")

    roboto_regular = _load_roboto("Regular")
    roboto_semibold = _load_roboto("SemiBold")
    roboto_medium = _load_roboto("Medium")
    roboto_bold = _load_roboto("Bold")
    if roboto_regular:
        matplotlib.rcParams["font.family"] = roboto_regular.get_name()

    values = _extract_values(csv_path)
    duration_label = values.get("Duration label", "")
    duration_days = values.get("Duration days", "")
    longest_pause = values.get("Longest pause", "")
    longest_range = values.get("Longest pause range", "")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axis("off")

    title_font = {"fontproperties": roboto_bold or roboto_regular} if roboto_bold or roboto_regular else {}
    value_primary_font = {"fontproperties": roboto_medium} if roboto_medium else {}
    value_secondary_font = {"fontproperties": roboto_regular} if roboto_regular else {}

    rows = [
        (
            ("Most active day", values.get("Most active day", ""), values.get("Most active day messages", "")),
            ("Longest pause", longest_pause, longest_range),
        ),
        (
            ("On average", values.get("Average messages", ""), ""),
            ("Days w/out messages", values.get("Days without messages", ""), ""),
        ),
    ]

    col_positions = (0.2, 0.74)
    row_start = 0.74
    row_offset = 0.26
    label_offset = 0.0
    value_offset_primary = 0.08
    value_offset_secondary = 0.16

    icon_dir = Path(__file__).resolve().parent
    icon_offset_x = 0.08
    icon_y_adjust = 0.06

    if duration_label:
        ax.text(0.56, 0.96, "Duration", transform=ax.transAxes,
                fontsize=20, va="top", ha="center", **title_font)
        days_display = f"{duration_days} days" if duration_days else duration_label
        ax.text(0.56, 0.88, days_display, transform=ax.transAxes,
                fontsize=18, va="top", ha="center", **value_primary_font)

    for row_idx, columns in enumerate(rows):
        base_y = row_start - row_idx * row_offset
        for col_idx, (label, primary_value, secondary_value) in enumerate(columns):
            x = col_positions[col_idx]
            icon_name = ICON_MAP.get(label)
            if icon_name:
                icon_path = icon_dir / icon_name
                icon_image = _load_icon_image(icon_path)
                if icon_image is not None:
                    ab = AnnotationBbox(icon_image, (x - icon_offset_x, base_y - icon_y_adjust),
                                        xycoords=ax.transAxes, frameon=False, box_alignment=(0.5, 0.5))
                    ax.add_artist(ab)
            ax.text(x, base_y - label_offset, label, transform=ax.transAxes,
                    fontsize=18, va="top", ha="left", **title_font)
            primary_kwargs = value_primary_font.copy()
            color = VALUE_COLOR_MAP.get(label)
            if color:
                primary_kwargs["color"] = color
            ax.text(x, base_y - value_offset_primary, primary_value, transform=ax.transAxes,
                    fontsize=16, va="top", ha="left", **primary_kwargs)
            if secondary_value:
                ax.text(x, base_y - value_offset_secondary, secondary_value, transform=ax.transAxes,
                        fontsize=13, va="top", ha="left", **value_secondary_font)

    fig.tight_layout(rect=(0, 0, 1, 0.95))

    if save_path:
        fig.savefig(save_path, dpi=500)
    else:
        plt.show()

    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to scalar_info.csv")
    parser.add_argument("--output", "-o", type=Path, help="Optional path to save the rendered figure")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = args.csv.expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    save_path = args.output.expanduser().resolve() if args.output else None
    if save_path and save_path.is_dir():
        save_path = save_path / "scalar_info.png"

    render_scalar_info(csv_path, save_path)


if __name__ == "__main__":
    main()
