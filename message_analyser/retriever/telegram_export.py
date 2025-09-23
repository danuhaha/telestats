import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from message_analyser.myMessage import MyMessage
from message_analyser.misc import log_line


def _coerce_text(text_field) -> str:
    if isinstance(text_field, str):
        return text_field
    if isinstance(text_field, list):
        parts = []
        for item in text_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _parse_msg_author(msg_from: Optional[str], your_name: str, target_name: str) -> str:
    if msg_from == your_name:
        return your_name
    if msg_from == target_name:
        return target_name
    return msg_from or target_name


def _has_audio(msg: dict) -> bool:
    if "audio_file" in msg:
        return True
    f = msg.get("file") or ""
    audio_exts = (".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav")
    return isinstance(f, str) and f.lower().endswith(audio_exts)


def _has_video_file(msg: dict) -> bool:
    if "video_file" in msg:
        return True
    f = msg.get("file") or ""
    video_exts = (".mp4", ".mov", ".mkv", ".webm", ".avi")
    return isinstance(f, str) and f.lower().endswith(video_exts)


def _to_mymessage(msg: dict, your_name: str, target_name: str) -> Optional[MyMessage]:
    if msg.get("type") != "message":
        return None
    text = _coerce_text(msg.get("text", ""))
    date_str = msg.get("date")
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

    author = _parse_msg_author(msg.get("from"), your_name, target_name)

    has_photo = "photo" in msg
    has_voice = "voice_message" in msg
    has_video_message = "video_message" in msg
    has_video_file = _has_video_file(msg)
    has_sticker = ("sticker_emoji" in msg) or (isinstance(msg.get("file"), str) and msg.get("file", "").lower().endswith(".webp"))
    has_audio = _has_audio(msg)

    is_forwarded = "forwarded_from" in msg or "forwarded_from_id" in msg

    return MyMessage(
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
    )


def get_mymessages_from_export(export_path: str, your_name: str, target_name: str) -> List[MyMessage]:
    path = Path(export_path)
    if path.is_file():
        json_files = [path]
    else:
        candidates = [path / "result.json", path / "messages.json"]
        candidates.extend(sorted(path.glob("messages*.json")))
        json_files = [p for p in candidates if p.exists() and p.is_file()]
    if not json_files:
        log_line(f"No Telegram JSON export found in {export_path} (expected result.json or messages*.json)")
        return []

    msgs: List[MyMessage] = []
    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            log_line(f"Failed to read {jf}: {exc}")
            continue
        records = data.get("messages") if isinstance(data, dict) else data
        if not isinstance(records, list):
            continue
        for rec in records:
            mm = _to_mymessage(rec, your_name, target_name)
            if mm is not None:
                msgs.append(mm)

    msgs.sort(key=lambda m: m.date)
    log_line(f"{len(msgs)} messages parsed from Telegram export at {export_path}")
    return msgs
