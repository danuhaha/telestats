import os
from pathlib import Path
import re
import json
import configparser
from message_analyser.myMessage import MyMessage
from message_analyser.misc import log_line


def _get_config_file_name():
    return str(Path(__file__).resolve().parents[1] / "config.ini")


def store_session_params(params):
    config_file_name = _get_config_file_name()
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file_name, encoding="utf-8-sig")
    assert params["from_vk"] or params["from_telegram"]
    config_parser.set("session_params", "dialog_id",
                      re.compile("\(id=[0-9]+\)$").search(params["dialogue"]).group()[4:-1] if params["from_telegram"]
                      else "")
    config_parser.set("session_params", "vkopt_file", params["vkopt_file"] if params["from_vk"] else "")
    config_parser.set("session_params", "words_file", params["words_file"] if params["plot_words"] else "")

    assert params["your_name"] and params["target_name"]
    config_parser.set("session_params", "your_name", params["your_name"])
    config_parser.set("session_params", "target_name", params["target_name"])
    with open(config_file_name, "w+", encoding="utf-8") as config_file:
        config_parser.write(config_file)
    log_line(f"Session parameters were stored in {config_file_name} file.")


def get_session_params():
    config_file_name = _get_config_file_name()
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file_name, encoding="utf-8-sig")
    dialog_id = config_parser.get("session_params", "dialog_id", fallback="")
    dialog_id = int(dialog_id) if dialog_id else -1
    vkopt_file = config_parser.get("session_params", "vkopt_file", fallback="")
    words_file = config_parser.get("session_params", "words_file", fallback="")
    your_name = config_parser.get("session_params", "your_name", fallback="")
    target_name = config_parser.get("session_params", "target_name", fallback="")
    log_line(f"Session parameters were received from {config_file_name} file.")
    return dialog_id, vkopt_file, words_file, your_name, target_name


def store_telegram_secrets(api_id, api_hash, phone_number, session_name="Message retriever"):
    config_file_name = _get_config_file_name()
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file_name, encoding="utf-8-sig")
    config_parser.set("telegram_secrets", "api_id", api_id)
    config_parser.set("telegram_secrets", "api_hash", api_hash)
    config_parser.set("telegram_secrets", "session_name", session_name)
    config_parser.set("telegram_secrets", "phone_number", phone_number)
    with open(config_file_name, "w+", encoding="utf-8") as config_file:
        config_parser.write(config_file)
    log_line(f"Telegram secrets were stored in {config_file_name} file.")


def get_telegram_secrets():
    config_file_name = _get_config_file_name()
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file_name, encoding="utf-8-sig")
    api_id = config_parser.get("telegram_secrets", "api_id", fallback="")
    api_hash = config_parser.get("telegram_secrets", "api_hash", fallback="")
    phone_number = config_parser.get("telegram_secrets", "phone_number", fallback="")
    session_name = config_parser.get("telegram_secrets", "session_name", fallback="")
    log_line(f"Telegram secrets were received from {config_file_name} file.")
    return api_id, api_hash, phone_number, session_name


def store_msgs(file_path, msgs):
    with open(file_path, 'w') as fp:
        json.dump(msgs, fp, default=str)
    log_line(f"{len(msgs)} messages were stored in {file_path} file.")


def store_top_words_count(words, your_words_cnt, target_words_cnt, file_path):
    with open(file_path, 'w', encoding="utf-8") as fp:
        fp.write("Word, You sent, Target sent, Total\n")
        for word in words:
            fp.write(f"{word}, {your_words_cnt[word]}, {target_words_cnt[word]}, "
                     f"{your_words_cnt[word]+target_words_cnt[word]}\n")

def get_msgs(file_path):
    with open(file_path, 'r') as f:
        msgs = [MyMessage.from_dict(msg) for msg in json.loads(f.read())]
    log_line(f"{len(msgs)} messages were received from {file_path} file.")
    return msgs


def get_words(file_path):
    with open(file_path, 'r', encoding="utf-8-sig") as f:
        words = [word.strip() for word in f.readlines()
                 if all([ch.isalpha() or ch == '\'' or ch == '`' for ch in word.strip()])]
    log_line(f"{len(words)} words were received from {file_path} file.")
    return words
