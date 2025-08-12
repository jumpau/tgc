import os
from dataclasses import dataclass
from pathlib import Path

import toml
from hypy_utils import printc



@dataclass
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    exports: list[dict]
    upload_auth_code: str = None
    upload_url: str
    upload_domain: str
    upload_max_retry: int


def load_config(path: str = "config.toml") -> Config:
    if os.getenv('tgc_config'):
        data = toml.loads(os.getenv('tgc_config'))
    else:
        fp = os.getenv('tgc_config_path')
        if fp is None or not os.path.isfile(fp):
            fp = path
        if fp is None or not os.path.isfile(fp):
            fp = Path.home() / ".config" / "tgc" / "config.toml"
        fp = Path(fp)
        if not fp.is_file():
            printc(f"&cConfig file not found in either {path} or {fp} \nPlease put your configuration in the path")
            exit(3)
        data = toml.loads(fp.read_text())

    upload = data.get("upload", {})
    return Config(
        api_id=data.get("api_id"),
        api_hash=data.get("api_hash"),
        bot_token=data.get("bot_token"),
        exports=data.get("exports", []),
        upload_auth_code=upload.get("auth_code"),
        upload_url=upload.get("upload_url"),
        upload_domain=upload.get("upload_domain"),
        upload_max_retry=int(upload.get("upload_max_retry"))
    )
