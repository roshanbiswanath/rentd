"""Extract structured post data from Facebook GraphQL API responses."""
import re, base64
from datetime import datetime, timezone
from helpers import (
    walk_deep, find_first_deep, normalize_text, is_likely_human_name,
    classify_media_url, choose_best_post_url, parse_post_id
)

STORY_TYPENAMES = {"Story","FeedStory","GroupFeedStory","GroupPost","UserPost","FeedUnit"}
EXCLUDED_TYPENAMES = {"Comment","Reply","Feedback","Reaction","Notification","AdStory","SponsoredStory"}
TIME_FIELDS = ["creation_time","timestamp","publish_time","created_time","publish_timestamp","created_timestamp"]

def _decode_b64(value: str) -> str:
    try:
        pad = "=" * ((4 - len(value) % 4) % 4)
        return base64.b64decode(value + pad).decode("utf-8")
    except Exception:
        return ""

def is_likely_comment_id(raw_id: str) -> bool:
    if not raw_id or re.match(r"^\d+$", raw_id): return False
    decoded = _decode_b64(str(raw_id)).lower()
    if not decoded: return False
    return any(decoded.startswith(p) for p in ("comment","reply","feedback","notification"))

def collect_story_nodes(root) -> list:
    stories = []
    def visitor(node):
        if not isinstance(node, dict): return
        tn = node.get("__typename","")
        if tn in EXCLUDED_TYPENAMES: return
        has_time = any(
            isinstance(node.get(f), (int,float)) or
            (isinstance(node.get(f), str) and re.match(r"^\d+$", node.get(f,"")))
            for f in TIME_FIELDS
        )
        has_actor = (isinstance(node.get("actors"), list) and len(node.get("actors",[])) > 0) or \
                    isinstance(node.get("actor"), dict) or isinstance(node.get("author"), dict)
        has_id = bool(node.get("post_id") or node.get("id"))
        msg = node.get("message")
        has_msg = (isinstance(msg, dict) and isinstance(msg.get("text"), str) and msg["text"].strip()) or \
                  isinstance((node.get("comet_sections") or {}).get("content",{}).get("story"), dict)
        if tn in STORY_TYPENAMES or (has_time and has_id) or (has_time and has_actor and has_msg):
            stories.append(node)
    walk_deep(root, visitor)
    return stories

def extract_timestamp(story: dict):
    node = find_first_deep(story, lambda n: isinstance(n, dict) and any(
        isinstance(n.get(k), (int,float)) or (isinstance(n.get(k), str) and re.match(r"^\d+$", n.get(k,"")))
        for k in TIME_FIELDS
    ))
    if not node: return None
    for k in TIME_FIELDS:
        v = node.get(k)
        if isinstance(v, (int,float)) and v == v: return int(v)
        if isinstance(v, str) and re.match(r"^\d+$", v): return int(v)
    return None

def format_timestamp_iso(raw_ts) -> str:
    if raw_ts is None: return ""
    ts = raw_ts // 1000 if raw_ts > 10_000_000_000 else raw_ts
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return ""

def extract_author(story: dict) -> str:
    actors = story.get("actors")
    if isinstance(actors, list) and actors:
        name = normalize_text(actors[0].get("name","") if isinstance(actors[0], dict) else "")
        if is_likely_human_name(name): return name
    for key in ("actor","author"):
        obj = story.get(key)
        if isinstance(obj, dict) and is_likely_human_name(obj.get("name","")):
            return normalize_text(obj["name"])
    named = find_first_deep(story, lambda n: isinstance(n, dict) and isinstance(n.get("name"), str) and is_likely_human_name(n["name"]))
    return normalize_text(named["name"]) if named else ""

def extract_message(story: dict) -> str:
    msg = story.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("text"), str) and msg["text"].strip():
        return normalize_text(msg["text"])
    candidates = []
    def visitor(node):
        if not isinstance(node, dict): return
        t = node.get("text")
        if not isinstance(t, str): return
        t = normalize_text(t)
        if len(t) < 8: return
        if re.match(r"^(like|reply|share|comment)$", t, re.I): return
        if t.lower().startswith("may be an image"): return
        candidates.append(t)
    walk_deep(story, visitor)
    candidates.sort(key=len, reverse=True)
    return candidates[0] if candidates else ""

def extract_candidate_urls(story: dict) -> list:
    urls = []
    def visitor(node):
        if isinstance(node, dict) and isinstance(node.get("url"), str) and "facebook.com" in node["url"]:
            urls.append(node["url"])
    walk_deep(story, visitor)
    return urls

def extract_media(story: dict) -> list:
    out, seen = [], set()
    def walk(node, path=None):
        if path is None: path = []
        if node is None: return
        if isinstance(node, list):
            for item in node: walk(item, path)
            return
        if not isinstance(node, dict): return
        cw = node.get("width") if isinstance(node.get("width"), (int,float)) else None
        ch = node.get("height") if isinstance(node.get("height"), (int,float)) else None
        for key, value in node.items():
            np = path + [key]
            if isinstance(value, str) and re.match(r"^https?://", value, re.I):
                mt = classify_media_url(value, ".".join(np))
                if mt and value not in seen:
                    seen.add(value)
                    out.append({"type": mt, "url": value, "width": cw, "height": ch})
            else:
                walk(value, np)
    walk(story)
    return out

def story_belongs_to_group(story: dict, group_id: str, permalink: str) -> bool:
    if not group_id: return True
    if permalink and f"/groups/{group_id}" in permalink: return True
    hit = find_first_deep(story, lambda n: isinstance(n, dict) and (
        (isinstance(n.get("id"), str) and n["id"] == group_id) or
        (isinstance(n.get("url"), str) and f"/groups/{group_id}" in n["url"])
    ))
    return bool(hit)
