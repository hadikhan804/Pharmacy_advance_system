from __future__ import annotations

import json

from app.config import I18N_DIR


class Translator:
    def __init__(self) -> None:
        self.lang = "en"
        self._data: dict[str, str] = {}
        self.load("en")

    def load(self, lang: str) -> None:
        path = I18N_DIR / f"{lang}.json"
        if not path.exists():
            path = I18N_DIR / "en.json"
            lang = "en"
        self.lang = lang
        self._data = json.loads(path.read_text(encoding="utf-8"))

    def t(self, key: str, **kwargs) -> str:
        text = self._data.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    @property
    def is_rtl(self) -> bool:
        return self.lang == "ur"


i18n = Translator()


def t(key: str, **kwargs) -> str:
    return i18n.t(key, **kwargs)
