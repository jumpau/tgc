#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.
import asyncio
import shutil
from pathlib import Path
import requests
import toml
from dataclasses import dataclass
from pathlib import Path

from tempfile import TemporaryDirectory
from typing import Callable, Any

from hypy_utils import ensure_dir, md5
from hypy_utils.file_utils import escape_filename
from pyrogram import types, Client
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId, FileType, PHOTO_TYPES
from pyrogram.types import Message


@dataclass
class UploadConfig:
    auth_code: str = None

def load_upload_config(path: str = "config.toml") -> UploadConfig:
    fp = Path(path)
    if not fp.is_file():
        fp = Path(__file__).parent.parent.parent / "config.toml"
    if not fp.is_file():
        raise FileNotFoundError(f"Config file not found: {fp}")
    data = toml.loads(fp.read_text())
    upload = data.get("upload", {})
    return UploadConfig(auth_code=upload.get("auth_code"))
import time

UPLOAD_URL = "https://all.openjpg.qzz.io/login/upload"
DOMAIN = "https://all.openjpg.qzz.io"
MAX_RETRY = 3

try:
    GLOBAL_AUTH_CODE = load_upload_config().auth_code
except Exception:
    GLOBAL_AUTH_CODE = None

def upload_file(file_path, auth_code=None, upload_channel="telegram", server_compress=True, auto_retry=True, upload_name_type="default", return_format="default", upload_folder=None):
    params = {
        "authCode": auth_code,
        "serverCompress": str(server_compress).lower(),
        "uploadChannel": upload_channel,
        "autoRetry": str(auto_retry).lower(),
        "uploadNameType": upload_name_type,
        "returnFormat": return_format,
    }
    if upload_folder:
        params["uploadFolder"] = upload_folder

    files = {"file": open(file_path, "rb")}
    for attempt in range(MAX_RETRY):
        try:
            response = requests.post(UPLOAD_URL, params=params, files=files)
            data = response.json()
            if data and isinstance(data, list) and data[0].get("src"):
                src = data[0]["src"]
                return DOMAIN + src
        except Exception as e:
            time.sleep(2)
    return None
def guess_ext(client: Client, file_type: int, mime_type: str | None) -> str:
    guessed_extension = client.guess_extension(mime_type) if mime_type else None

    if file_type in PHOTO_TYPES:
        return ".jpg"
    elif file_type == FileType.VOICE:
        return guessed_extension or ".ogg"
    elif file_type in (FileType.VIDEO, FileType.ANIMATION, FileType.VIDEO_NOTE):
        return guessed_extension or ".mp4"
    elif file_type == FileType.DOCUMENT:
        return guessed_extension or ".zip"
    elif file_type == FileType.STICKER:
        return guessed_extension or ".webp"
    elif file_type == FileType.AUDIO:
        return guessed_extension or ".mp3"
    else:
        return ".unknown"


def has_media(message: Message) -> Any | None:
    available_media = ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note",
                       "new_chat_photo")

    if isinstance(message, types.Message):
        for kind in available_media:
            media = getattr(message, kind, None)

            if media is not None:
                break
        else:
            return None
    else:
        media = message

    return media


def get_file_name(client: Client, message: Message) -> tuple[str, FileId]:
    """
    Guess a file name of a message media

    :param client: Client
    :param message: Message or media
    :return: File name, file id object
    """
    media = has_media(message)

    if isinstance(media, str):
        file_id_str = media
    else:
        file_id_str = media.file_id

    file_id_obj = FileId.decode(file_id_str)
    file_type = file_id_obj.file_type

    mime_type = getattr(media, "mime_type", "")
    date = getattr(media, "date", None)

    file_name = getattr(media, "file_name", None)

    if not file_name:
        file_name = f"{FileType(file_type).name.lower()}"
        if date:
            file_name += f"_{date.strftime('%Y-%m-%d_%H-%M-%S')}"
        file_name += guess_ext(client, file_type, mime_type)
    file_name = escape_filename(file_name)

    # Sometimes, if the file name is too long, the file extension is stripped by telegram api
    # We need to add it back
    if '.' not in file_name:
        file_name += guess_ext(client, file_type, mime_type)

    return file_name, file_id_obj


async def download_media(
        client: Client,
        message: types.Message,
        directory: str | Path = "media",
        fname: str | None = None,
        progress: Callable = None,
        progress_args: tuple = (),
        max_file_size: int = 0
) -> Path | Path:
    directory: Path = ensure_dir(directory)

    media = has_media(message)

    # Check filesize
    fsize = getattr(media, 'file_size', 0)
    if max_file_size and fsize > max_file_size:
        print(f"Skipped {fname} because of file size limit ({fsize} > {max_file_size})")
        return None

    file_name, file_id_obj = get_file_name(client, message)
    file_name = fname or file_name

    p = directory / file_name
    if p.exists():
        return p

    print(f"Downloading {p.name}...")

    while True:
        try:
            local_path = Path(await client.handle_download(
                (file_id_obj, directory, file_name, False, fsize, progress, progress_args)
            ))
            # 下载完成后上传
            external_link = upload_file(
                str(local_path),
                auth_code=GLOBAL_AUTH_CODE
            )
            if external_link:
                print(f"Uploaded to cloud: {external_link}")
                return external_link
            else:
                print("Upload failed, retrying...")
                time.sleep(2)
        except FloodWait as e:
            print(f"Sleeping for {e.value} seconds...")
            await asyncio.sleep(e.value)


async def download_media_urlsafe(
        client: Client,
        message: types.Message,
        directory: str | Path = "media",
        fname: str | None = None,
        progress: Callable = None,
        progress_args: tuple = (),
        max_file_size: int = 0
) -> tuple[Path, str]:
    """
    Download media into a renamed file

    :return: Renamed file path, original file name
    """
    file_name, file_id_obj = get_file_name(client, message)
    renamed = str(message.id) + Path(file_name).suffix
    return await download_media(client, message, directory, renamed, progress, progress_args, max_file_size), file_name
