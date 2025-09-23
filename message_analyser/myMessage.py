import re
from datetime import datetime


def islink(string):
    # https://stackoverflow.com/a/7160778
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, string) is not None


class MyMessage(dict):
    """Represents a message entity from some messenger.

    Attributes:
        See __init__ args.
    """

    def __init__(self, text, date, author,
                 is_forwarded=False,
                 document_id=None,
                 has_photo=False,
                 has_voice=False,
                 has_audio=False,
                 has_video=False,
                 has_sticker=False,
                 is_link=None,
                 has_video_message=None,
                 has_video_file=None):
        """Inits MyMessage class with all it's attributes values.

        Notes:
            How to check a message for being a file:
                self.has_document = document_id is not None
                self.is_file = text == "" and (self.has_photo or self.has_document)
                # Because sometimes a photo is not considered as a document.

        Args:
            text (str): A raw content of the message.
            date (string ("%Y-%m-%d %H:%M:%S") date or datetime obj): A time when this message was sent.
            author (str): Author's name.
            is_forwarded (bool): True if the message is forwarded from another person.
            document_id (int): Integer id of the document (-1 for vkOpt messages, None for no document).
            has_photo (bool): True if the message has photo.
            has_voice (bool): True if the message has voice-message file attached.
            has_audio (bool): True if the message has audio file attached (NOT voice!).
            has_video (bool): Legacy aggregate flag for any video (will be set to has_video_message or has_video_file).
            has_sticker (bool): True if the message has sticker.
            is_link (bool): True if the whole text of the message is a link.
            has_video_message (bool): True if the message is a round "Video message" (video note).
            has_video_file (bool): True if the message contains a regular video file.
        """
        super().__init__()
        # Derive separate video flags while keeping legacy has_video aggregate for compatibility
        if has_video_message is None:
            has_video_message = False
        if has_video_file is None:
            has_video_file = False
        if has_video and not (has_video_message or has_video_file):
            # Historically "has_video" meant a video message; default to that to avoid overcounting
            has_video_message = True

        attributes = {
            "text": text,
            "date": date,
            "author": author,
            "is_forwarded": is_forwarded,
            "document_id": document_id,
            "has_photo": has_photo,
            "has_voice": has_voice,
            "has_audio": has_audio,
            "has_video_message": has_video_message,
            "has_video_file": has_video_file,
            # keep aggregate for older code paths/serializations
            "has_video": has_video or has_video_message or has_video_file,
            "has_sticker": has_sticker,
            "is_link": is_link,
        }
        if not isinstance(date, datetime):
            attributes["date"] = datetime.strptime(str(date), "%Y-%m-%d %H:%M:%S")
        if is_link is None:
            attributes["is_link"] = islink(text)
        self.update(attributes)

    def __str__(self):
        return (f"Author = {self.author}\n"
                f"Content = [{self.text[:100] + '[...]' if len(self.text) > 100 else self.text}]\n"
                f"Date = {self.date}\n"
                f"Contains document = {self.document_id is not None}\n"
                f"Has photo = {self.has_photo}\n"
                f"Is link = {self.is_link}\n"
                f"Is forwarded = {self.is_forwarded}\n")

    def __repr__(self):
        return str(self)

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, key, value):
        if key in self:
            raise Exception("Can't mutate an Immutable: self.%s = %r" % (key, value))
        self[key] = value

    @staticmethod
    def from_dict(d):
        return MyMessage(**d)
