"""Shared utility functions for the Rentd scraper."""
import hashlib, re, json
from urllib.parse import urlparse, urlencode, parse_qs

def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()

def content_hash(value: str) -> str:
    return normalize_text(value).lower()[:240]

def fallback_post_key(post: dict) -> str:
    payload = f"{post.get('author','')}|{post.get('content','')}|{post.get('timestamp','')}"
    return hashlib.sha256(payload.encode()).hexdigest()

def parse_post_id(url: str) -> str:
    if not url: return ""
    for pat in [r"story_fbid=(\d+)", r"fbid=(\d+)", r"/posts/(\d+)", r"/permalink/(\d+)", r"multi_permalinks=(\d+)"]:
        m = re.search(pat, url)
        if m: return m.group(1)
    return ""

def normalize_permalink(url: str) -> str:
    if not url: return ""
    try:
        parsed = urlparse(url)
        allowed = {"story_fbid", "id", "multi_permalinks", "fbid"}
        qs = parse_qs(parsed.query)
        clean = {k: v[0] for k, v in qs.items() if k in allowed}
        q = ("?" + urlencode(clean)) if clean else ""
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{q}"
    except Exception:
        return url

def enforce_chronological(url: str) -> str:
    if not url: return url
    try:
        parsed = urlparse(url)
        if "facebook.com" in parsed.hostname and "/groups/" in parsed.path:
            qs = parse_qs(parsed.query)
            qs["sorting_setting"] = ["CHRONOLOGICAL"]
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode({k:v[0] for k,v in qs.items()})}"
    except Exception:
        pass
    return url

def is_likely_human_name(value: str) -> bool:
    t = normalize_text(value)
    if not t or len(t) < 2 or len(t) > 80: return False
    if re.match(r"^(facebook|like|reply|share|comment)$", t, re.I): return False
    if t.lower().startswith("may be an image") or "no photo description" in t.lower(): return False
    if re.match(r"^\+\d+$", t): return False
    return True

def pick_post_key(post: dict) -> str:
    if post.get("postId"): return f"id:{post['postId']}"
    if post.get("permalink"): return f"url:{post['permalink']}"
    return f"txt:{content_hash(post.get('content',''))}|{(post.get('author','') or '').lower()}"

def key_for_post(post: dict) -> str:
    if post.get("postId"): return f"id:{post['postId']}"
    if post.get("permalink"): return f"url:{post['permalink']}"
    return f"fallback:{post.get('author','')}|{post.get('timestamp','')}|{(post.get('content','') or '')[:180]}"

def merge_post(base: dict, incoming: dict) -> dict:
    bc = base.get("content", "") or ""
    ic = incoming.get("content", "") or ""
    return {
        "author": base.get("author") or incoming.get("author", ""),
        "content": bc if len(bc) >= len(ic) else ic,
        "timestamp": base.get("timestamp") or incoming.get("timestamp", ""),
        "permalink": base.get("permalink") or incoming.get("permalink", ""),
        "postId": base.get("postId") or incoming.get("postId", ""),
        "media": merge_media(base.get("media", []), incoming.get("media", []))
    }

def classify_media_url(url: str, path_hint: str = "") -> str:
    v = (url or "").lower()
    h = (path_hint or "").lower()
    if not v.startswith("http"): return ""
    # photo.php and /photos/ links are HTML pages, not direct image assets.
    if re.search(r"facebook\.com/photo(\.php|/)|facebook\.com/.*/photos/|facebook\.com/photos/", v, re.I): return ""
    if re.search(r"emoji\.php|safe_image\.php|/profile(_pic)?/|/rsrc\.php", v, re.I): return ""
    if re.search(r"/groups/\d+/posts/|/permalink/\d+|story_fbid=|multi_permalinks=", v): return ""

    if re.search(r"playable|video|mp4|m3u8|/videos?/", h) or re.search(r"[./](mp4|m3u8)(\?|$)|/videos?/", v):
        if re.search(r"fbcdn\.net", v, re.I) or re.search(r"[./](mp4|m3u8)(\?|$)", v, re.I):
            return "video"
        return ""

    # Accept direct CDN image URLs (or explicit image extensions).
    if re.search(r"fbcdn\.net", v, re.I) or re.search(r"\.(jpe?g|png|webp|gif|bmp)(\?|$)", v, re.I):
        if re.search(r"/scontent|/images?/|/photo", v):
            return "image"
        # For generic CDN URLs with no helpful path marker, trust the extension.
        if re.search(r"\.(jpe?g|png|webp|gif|bmp)(\?|$)", v, re.I):
            return "image"

    if re.search(r"image|photo|thumbnail|preview|cover|sprite", h) and re.search(r"fbcdn\.net", v, re.I):
        return "image"

    return ""

def is_allowed_media_url(url: str) -> bool:
    v = str(url or "")
    if not re.match(r"^https?://", v, re.I): return False
    if re.search(r"emoji\.php|safe_image\.php|/profile(_pic)?/|/rsrc\.php", v, re.I): return False
    if re.search(r"/groups/\d+/posts/|/permalink/\d+|story_fbid=|multi_permalinks=", v): return False
    if re.search(r"facebook\.com/photo(\.php|/)|facebook\.com/.*/photos/|facebook\.com/photos/", v, re.I): return False
    if re.search(r"fbcdn\.net", v, re.I): return True
    if re.search(r"\.(jpe?g|png|webp|gif|bmp|mp4|m3u8)(\?|$)", v, re.I): return True
    return False

def merge_media(base: list, incoming: list) -> list:
    def media_key(url):
        try:
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}{p.path}"
        except Exception:
            return str(url or "").split("?")[0].split("#")[0]

    by_url = {}
    for item in (base or []) + (incoming or []):
        if not item or not item.get("url"): continue
        if not is_allowed_media_url(item["url"]): continue
        k = media_key(item["url"])
        c = {"type": "video" if item.get("type") == "video" else "image", "url": item["url"],
             "width": item.get("width"), "height": item.get("height")}
        w, h = c.get("width") or 0, c.get("height") or 0
        if c["type"] == "image" and w and h and w < 120 and h < 120: continue
        existing = by_url.get(k)
        if not existing:
            by_url[k] = c
        else:
            ea = (existing.get("width") or 0) * (existing.get("height") or 0)
            ca = (w) * (h)
            if ca > ea: by_url[k] = c

    result = sorted(by_url.values(), key=lambda m: (0 if m["type"]=="video" else 1, -((m.get("width") or 0)*(m.get("height") or 0))))
    return result[:12]

def parse_graphql_json_blocks(raw: str) -> list:
    text = re.sub(r"^for\s*\(;;\);\s*", "", raw or "")
    blocks = []
    i = 0
    while i < len(text):
        while i < len(text) and text[i] != "{": i += 1
        if i >= len(text): break
        depth = 0; in_str = False; escaped = False; end = -1
        for j in range(i, len(text)):
            ch = text[j]
            if in_str:
                if escaped: escaped = False
                elif ch == "\\": escaped = True
                elif ch == '"': in_str = False
                continue
            if ch == '"': in_str = True; continue
            if ch == "{": depth += 1
            if ch == "}":
                depth -= 1
                if depth == 0: end = j; break
        if end == -1: break
        chunk = text[i:end+1]
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict) and "data" in parsed:
                blocks.append(parsed)
        except Exception:
            pass
        i = end + 1
    return blocks

def walk_deep(value, visitor):
    if value is None: return
    visitor(value)
    if isinstance(value, list):
        for item in value: walk_deep(item, visitor)
    elif isinstance(value, dict):
        for item in value.values(): walk_deep(item, visitor)

def find_first_deep(value, predicate):
    result = [None]
    def v(node):
        if result[0] is not None: return
        if predicate(node): result[0] = node
    walk_deep(value, v)
    return result[0]

def choose_best_post_url(urls: list, group_id: str) -> str:
    def score(url):
        u = normalize_permalink(url)
        if not u: return (-100, "")
        if re.search(r"/photo/|/photos/|/videos/|/watch/|/reel/", u, re.I): return (-50, u)
        s = 0
        if group_id and f"/groups/{group_id}" in u: s += 4
        if re.search(r"/groups/\d+/posts/\d+", u): s += 8
        if re.search(r"/posts/\d+", u): s += 6
        if re.search(r"/permalink/\d+", u): s += 5
        if re.search(r"story_fbid=\d+", u): s += 4
        if re.search(r"multi_permalinks=\d+", u): s += 3
        return (s, u)
    best = (-100, "")
    for u in urls:
        cur = score(u)
        if cur[0] > best[0]: best = cur
    return best[1]
