from __future__ import annotations

from pathlib import Path
import re
from typing import List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as du_parser

from message_analyser.myMessage import MyMessage
from message_analyser.misc import log_line

NUMERIC_DMY_RE = re.compile(r"^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")


def _get_html_files(export_path: str) -> List[Path]:
    p = Path(export_path)
    if p.is_file() and p.suffix.lower() == ".html":
        return [p]
    files = sorted(p.glob("*.html"))
    return files


def _select_has(msg, class_name: str) -> bool:
    return msg.select_one(f"div.{class_name}") is not None


def _coerce_author(name: Optional[str], your_name: str, target_name: str, last_author: Optional[str]) -> str:
    if name:
        if name == your_name:
            return your_name
        if name == target_name:
            return target_name
        return name
    return last_author or target_name


def get_mymessages_from_html(export_path: str, your_name: str, target_name: str) -> List[MyMessage]:
    html_files = _get_html_files(export_path)
    if not html_files:
        log_line(f"No HTML files found in {export_path}")
        return []

    msgs: List[MyMessage] = []
    last_author: Optional[str] = None

    for fp in html_files:
        try:
            html = fp.read_text(encoding="utf-8")
        except Exception as exc:
            log_line(f"Failed to read {fp}: {exc}")
            continue

        soup = BeautifulSoup(html, "html.parser")

        for msg in soup.select("div.message"):
            classes = set(msg.get("class", []))
            if "service" in classes:
                continue

            # date
            dt_div = msg.select_one("div.date") or msg.select_one("div.pull_right.date.details")
            if dt_div is None:
                continue
            title = dt_div.get("title") or dt_div.get_text(strip=True)
            try:
                # Many Telegram HTML exports use dd.mm.yyyy; parse as day-first for numeric formats
                if title and NUMERIC_DMY_RE.match(title):
                    dt = du_parser.parse(title, dayfirst=True, fuzzy=True)
                else:
                    dt = du_parser.parse(title, fuzzy=True)
                dt = dt.replace(tzinfo=None)
            except Exception:
                continue

            # author (present in first message from a block; joined messages omit it)
            author_div = msg.select_one("div.from_name")
            raw_author = author_div.get_text(strip=True) if author_div else None
            author = _coerce_author(raw_author, your_name, target_name, last_author)
            last_author = raw_author or last_author or author

            # text
            text_div = msg.select_one("div.text")
            text = text_div.get_text("\n", strip=True) if text_div else ""

            # forwarded
            is_forwarded = msg.select_one("div.forwarded") is not None

            # media flags
            has_voice = _select_has(msg, "media_voice_message")
            has_audio = _select_has(msg, "media_audio_file") or _select_has(msg, "media_audio")
            media_photo_present = _select_has(msg, "media_photo")
            # Video can be rendered via multiple classes; we split into message vs file using class + title
            # Stickers can appear as media_sticker or as media_photo with title "Sticker"
            title_div = (
                msg.select_one("div.media div.title")
                or msg.select_one("div.title.bold")
                or msg.select_one("div.title")
            )
            title_text = title_div.get_text(strip=True).lower() if title_div else ""
            has_sticker = _select_has(msg, "media_sticker") or (media_photo_present and "sticker" in title_text)
            # Distinguish video types
            video_classes_message = _select_has(msg, "media_video_message") or (
                _select_has(msg, "media_video") and "video message" in title_text
            )
            video_classes_file = _select_has(msg, "media_video_file") or (
                _select_has(msg, "media_video") and title_text and "video message" not in title_text and "video" in title_text
            )
            has_video_message = video_classes_message
            has_video_file = video_classes_file
            # Strengthen detection via title text for known media types
            if not has_voice and "voice message" in title_text:
                has_voice = True
            if not has_video_message and "video message" in title_text:
                has_video_message = True
            if not has_audio and ("audio file" in title_text or title_text.startswith("audio")):
                has_audio = True
            # Count photos only when it's a photo and not a sticker
            has_photo = media_photo_present and not has_sticker

            msgs.append(MyMessage(
                text=text,
                date=dt,
                author=author,
                is_forwarded=is_forwarded,
                document_id=None,
                has_photo=has_photo,
                has_voice=has_voice,
                has_audio=has_audio,
                has_video_message=has_video_message,
                has_video_file=has_video_file,
                has_sticker=has_sticker,
            ))

    msgs.sort(key=lambda m: m.date)
    log_line(f"{len(msgs)} messages parsed from Telegram HTML export at {export_path}")
    return msgs
