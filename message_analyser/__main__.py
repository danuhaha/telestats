import argparse
import asyncio
from pathlib import Path

from message_analyser.analyser import _analyse  # use directly to avoid nested event-loop
from message_analyser import analyser as analyser_mod
from message_analyser import storage


async def run_cli(args):
    if args.from_file:
        path = Path(args.from_file)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        # Load saved messages and analyse without nesting event loops
        msgs = storage.get_msgs(str(path))
        await _analyse(msgs, args.your_name, args.target_name, args.words_file, store_msgs=False)
        return

    if not (args.telegram or args.vkopt_file):
        raise SystemExit("Provide at least one source: --telegram and/or --vkopt-file PATH. Or use --from-file.")
    if not args.your_name or not args.target_name:
        raise SystemExit("--your-name and --target-name are required.")

    session_params = {
        "from_vk": bool(args.vkopt_file),
        "from_telegram": bool(args.telegram),
        "plot_words": bool(args.words_file),
        "vkopt_file": args.vkopt_file or "",
        "words_file": args.words_file or "",
        "your_name": args.your_name,
        "target_name": args.target_name,
    }

    if args.telegram:
        import message_analyser.retriever.telegram as tlg

        api_id = args.api_id or input("Telegram API ID: ").strip()
        api_hash = args.api_hash or input("Telegram API hash: ").strip()
        phone = args.phone or input("Phone number (international format): ").strip()
        code = args.code or input("Login code (leave empty if already authorized): ").strip()
        password = args.password or ""

        res = await tlg.get_sign_in_results(api_id, api_hash, code, phone, password, args.your_name, force_sms=args.force_sms)
        if res != "success":
            raise SystemExit(f"Telegram sign-in failed: {res}")
        storage.store_telegram_secrets(api_id, api_hash, phone, session_name=args.your_name)

        dialog_id = args.dialog_id
        if dialog_id is None:
            dialogs = await tlg.get_str_dialogs()
            print("Available dialogs:")
            for d in dialogs:
                print(" - ", d)
            raw = input("Enter dialog ID to analyse: ").strip()
            try:
                dialog_id = int(raw)
            except ValueError:
                raise SystemExit("Dialog ID must be an integer.")
        session_params["dialogue"] = f"dialog (id={dialog_id})"

    storage.store_session_params(session_params)
    loop = asyncio.get_event_loop()
    await analyser_mod.retrieve_and_analyse(loop)


def build_parser():
    parser = argparse.ArgumentParser(description="Message analyser")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--gui", action="store_true", help="Launch the GUI")
    group.add_argument("--from-file", dest="from_file", metavar="PATH", help="Analyse messages from saved file")
    group.add_argument("--telegram-export", dest="telegram_export", metavar="PATH", help="Analyse from Telegram Desktop/Lite JSON export")

    parser.add_argument("--telegram", action="store_true", help="Use Telegram as a source")
    parser.add_argument("--vkopt-file", metavar="PATH", help="Path to vkOpt .txt export")
    parser.add_argument("--words-file", metavar="PATH", help="Path to words file for word plots")
    parser.add_argument("--your-name", help="Your name")
    parser.add_argument("--target-name", help="Target's name")
    parser.add_argument("--dialog-id", type=int, help="Telegram dialog ID")

    parser.add_argument("--api-id", help="Telegram API ID")
    parser.add_argument("--api-hash", help="Telegram API hash")
    parser.add_argument("--phone", help="Phone number for Telegram login")
    parser.add_argument("--code", help="Telegram login code")
    parser.add_argument("--password", help="Telegram 2FA password", default="")
    parser.add_argument("--force-sms", action="store_true", help="Force SMS delivery of login code")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.gui or not any([args.from_file, args.telegram, args.vkopt_file, args.telegram_export]):
        # Import GUI lazily to avoid requiring tkinter when not needed
        try:
            from message_analyser.GUI import start_gui  # noqa: WPS433
        except Exception as exc:  # noqa: BLE001
            msg = (
                "Tkinter is not available. Install a Python build with Tk support "
                "(on macOS prefer python.org installer) or run CLI with --from-file and/or --telegram/--vkopt-file.\n"
                f"Original error: {exc}"
            )
            raise SystemExit(msg)

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(start_gui(loop))
        finally:
            if not loop.is_closed():
                loop.close()
        return

    # Handle Telegram Desktop/Lite export path directly
    if args.telegram_export:
        if not args.your_name or not args.target_name:
            raise SystemExit("--your-name and --target-name are required with --telegram-export.")

        export_path = Path(args.telegram_export)
        msgs = []
        # Auto-detect JSON vs HTML export
        has_html = export_path.is_file() and export_path.suffix.lower() == ".html"
        has_html = has_html or (export_path.is_dir() and any(export_path.glob("*.html")))
        if has_html:
            from message_analyser.retriever.telegram_html import get_mymessages_from_html
            msgs = get_mymessages_from_html(str(export_path), args.your_name, args.target_name)
        else:
            from message_analyser.retriever.telegram_export import get_mymessages_from_export
            msgs = get_mymessages_from_export(str(export_path), args.your_name, args.target_name)
        # Run analysis directly on the parsed messages
        import asyncio as _asyncio
        _loop = _asyncio.get_event_loop()
        _loop.run_until_complete(analyser_mod._analyse(msgs, args.your_name, args.target_name, args.words_file))
        return

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_cli(args))


if __name__ == "__main__":
    main()
