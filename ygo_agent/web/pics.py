"""Card pictures for the panel: EDOPro's own pics folder, else a download from the URL EDOPro itself uses (cached
under ~/.cache/ygo-agent/pics), else a generated placeholder card when offline."""

import html
import json
import os
import threading
import time
import urllib.parse
import urllib.request

from .. import paths

# What EDOPro means by "url": "default" for card pictures (config/configs.json).
EDOPRO_DEFAULT_PICS = "https://pics.projectignis.org:2096/pics/{}.jpg"
RETRY_AFTER = 600  # seconds before a failed download is tried again
MAX_BYTES = 4 << 20  # a card picture is well under 1 MB; anything bigger isn't one
MAGIC = (b"\xff\xd8\xff", b"\x89PNG")


def pic_urls(edopro_dir):
    """The picture URL templates EDOPro is configured with (user_configs.json first, as EDOPro reads them)."""
    urls = []
    for name in ("user_configs.json", "configs.json"):
        try:
            with open(os.path.join(edopro_dir, "config", name), encoding="utf-8") as f:
                entries = json.load(f).get("urls") or []
        except (OSError, ValueError):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("type") == "pic" and e.get("url"):
                url = EDOPRO_DEFAULT_PICS if e["url"] == "default" else e["url"]
                if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
                    continue  # a file:// or ftp:// template from a tampered config isn't a picture site
                if url not in urls:
                    urls.append(url)
    return urls or [EDOPRO_DEFAULT_PICS]


class PicStore:
    def __init__(self, edopro_dir, db=None, cache_dir=None, fetch=True, urls=None, timeout=6):
        self.root = os.path.expanduser(edopro_dir)
        self.db = db
        self.cache_dir = cache_dir or os.path.join(paths.CACHE, "pics")
        self.fetch_enabled = fetch
        self.urls = urls if urls is not None else pic_urls(self.root)
        self.timeout = timeout
        self._failed = {}
        self._locks = {}
        self._lock = threading.Lock()

    def local(self, code):
        for folder in (os.path.join(self.root, "pics"), self.cache_dir):
            for ext in ("jpg", "png"):
                path = os.path.join(folder, f"{code}.{ext}")
                if os.path.isfile(path):
                    return path
        return None

    def get(self, code):
        """(bytes, content type) for a card picture; the placeholder SVG when there is none."""
        path = self.local(code) or self.download(code)
        if path is None and self.db:
            card = self.db.get(code)
            if card and card.alias:  # an alternate artwork: the original's picture is close enough
                path = self.local(card.alias)
        if path:
            with open(path, "rb") as f:
                data = f.read()
            return data, "image/png" if data.startswith(MAGIC[1]) else "image/jpeg"
        return self.placeholder(code).encode("utf-8"), "image/svg+xml"

    def failed_recently(self, code):
        with self._lock:
            return time.time() - self._failed.get(code, 0) < RETRY_AFTER

    def download(self, code):
        if not self.fetch_enabled or not self.urls:
            return None
        with self._lock:
            lock = self._locks.setdefault(code, threading.Lock())
        with lock:  # one download per card, however many browser requests ask for it
            path = self.local(code)
            if path or self.failed_recently(code):
                return path
            for url in self.urls:
                try:
                    req = urllib.request.Request(url.replace("{}", str(code)), headers={"User-Agent": "ygo-agent"})
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        data = resp.read(MAX_BYTES + 1)
                except (OSError, ValueError):
                    continue
                if len(data) <= MAX_BYTES and data.startswith(MAGIC):
                    os.makedirs(self.cache_dir, exist_ok=True)
                    ext = "png" if data.startswith(MAGIC[1]) else "jpg"
                    path = os.path.join(self.cache_dir, f"{code}.{ext}")
                    tmp = f"{path}.{threading.get_ident()}.tmp"
                    with open(tmp, "wb") as f:
                        f.write(data)
                    os.replace(tmp, path)
                    return path
            with self._lock:
                self._failed[code] = time.time()
            return None

    def placeholder(self, code):
        """A card-shaped SVG with the name, type and stats, coloured like the card frame."""
        card = self.db.get(code) if self.db else None
        name = card.name if card else f"#{code}"
        frame, line, stats = "#3a4256", "", ""
        if card:
            line = card.type_line()
            if card.has(0x2):
                frame = "#1d8a6b"
            elif card.has(0x4):
                frame = "#a23a7d"
            elif card.has(0x4000000):
                frame, stats = "#2160a8", f"ATK {card.atk}"
            elif card.has(0x800000):
                frame, stats = "#22252c", f"ATK {card.atk} / DEF {card.defense}"
            elif card.has(0x2000):
                frame, stats = "#c9c9c9", f"ATK {card.atk} / DEF {card.defense}"
            elif card.has(0x40):
                frame, stats = "#7d4aa8", f"ATK {card.atk} / DEF {card.defense}"
            elif card.has(0x80):
                frame, stats = "#4b74c4", f"ATK {card.atk} / DEF {card.defense}"
            elif card.has(0x1):
                frame = "#c5873a" if card.has(0x20) else "#c9a54a"
                stats = f"ATK {card.atk} / DEF {card.defense}"
        words, rows = name.split(), [""]
        for w in words:
            if len(rows[-1]) + len(w) + 1 > 16 and rows[-1]:
                rows.append(w)
            else:
                rows[-1] = f"{rows[-1]} {w}".strip()
        title = "".join(f'<tspan x="88" dy="{0 if i == 0 else 19}">{html.escape(r)}</tspan>'
                        for i, r in enumerate(rows[:4]))
        sub = html.escape(line[:40])
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="177" height="254" viewBox="0 0 177 254">'
                f'<rect width="177" height="254" rx="8" fill="{frame}"/>'
                f'<rect x="9" y="9" width="159" height="236" rx="5" fill="#141822" opacity="0.92"/>'
                f'<text x="88" y="70" text-anchor="middle" font-family="sans-serif" font-size="15" '
                f'font-weight="700" fill="#eef1f7">{title}</text>'
                f'<text x="88" y="178" text-anchor="middle" font-family="sans-serif" font-size="10" '
                f'fill="#9aa3b5">{sub}</text>'
                f'<text x="88" y="222" text-anchor="middle" font-family="monospace" font-size="13" '
                f'font-weight="700" fill="#eef1f7">{html.escape(stats)}</text></svg>')
