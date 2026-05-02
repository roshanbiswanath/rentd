"""
Rentd Facebook Group Scraper – Python port of facebook-group-scraper.mjs.
Uses async Playwright for browser automation and intercepts GraphQL API responses.
"""
import asyncio, json, re, sys, argparse, os
from pathlib import Path
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from pymongo import MongoClient

if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport
    def silence_event_loop_closed(func):
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except AttributeError as e:
                if str(e) == "'NoneType' object has no attribute 'close'": pass
                else: raise
        return wrapper
    _ProactorBasePipeTransport.__del__ = silence_event_loop_closed(_ProactorBasePipeTransport.__del__)

import config
from helpers import (
    normalize_text, normalize_permalink, parse_post_id, enforce_chronological,
    fallback_post_key, pick_post_key, key_for_post, merge_post, merge_media,
    content_hash, parse_graphql_json_blocks, is_minimum_image_size, is_allowed_media_url
)
from graphql_extract import (
    collect_story_nodes, is_likely_comment_id, extract_candidate_urls,
    choose_best_post_url, story_belongs_to_group, extract_author,
    extract_message, extract_timestamp, format_timestamp_iso, extract_media
)

# ── MongoDB ──────────────────────────────────────────────────────────────

def init_mongo(uri: str, db_name: str, collection_name: str):
    if not uri or not re.match(r"^mongodb(\+srv)?://", uri, re.I):
        return None
    client = MongoClient(uri)
    coll = client[db_name][collection_name]
    
    # Drop non-sparse postId index if it exists (prevents E11000 errors on empty postId)
    try:
        existing_indexes = {idx['name']: idx for idx in coll.list_indexes()}
        if 'postId_1' in existing_indexes:
            idx = existing_indexes['postId_1']
            # If it exists and is NOT sparse, drop it so we can recreate as sparse
            if not idx.get('sparse', False):
                coll.drop_index('postId_1')
    except Exception:
        pass
    
    # Create indexes (sparse allows multiple empty/null values)
    coll.create_index("postId", unique=True, sparse=True)
    coll.create_index("permalink", unique=True, sparse=True)
    coll.create_index("dedupeKey", unique=True, sparse=True)
    coll.create_index([("updatedAt", -1)])
    return {"client": client, "collection": coll, "db": db_name, "coll_name": collection_name}


def sanitize_media(media_list: list) -> list:
    """Filter out small images (thumbnails/avatars) and keep only meaningful media."""
    if not media_list:
        return []
    
    result = []
    for item in media_list:
        if not isinstance(item, dict):
            continue
        
        media_type = item.get("type", "").lower()
        url = str(item.get("url") or "")

        if not is_allowed_media_url(url):
            continue
        
        # Always keep videos
        if media_type == "video":
            result.append(item)
            continue
        
        # For images, check minimum size and URL patterns (avatars/thumbnails/profile pics)
        if media_type == "image":
            width = item.get("width")
            height = item.get("height")
            lower_url = url.lower()
            looks_like_avatar = any(
                token in lower_url for token in (
                    "/profile_pic/",
                    "/profile/",
                    "safe_image.php",
                    "emoji.php",
                    "/rsrc.php",
                    "thumbnail",
                    "preview",
                    "sprite",
                    "s32x32",
                    "s48x48",
                    "s64x64",
                    "_s32x32",
                    "_s48x48",
                    "_s64x64",
                )
            )
            if not looks_like_avatar and is_minimum_image_size(width, height, min_dimension=150):
                result.append(item)
    
    return result


def upsert_posts(collection, posts: list, context: dict) -> dict:
    if collection is None or not posts:
        return {"matched": 0, "modified": 0, "upserted": 0}
    now = datetime.now(timezone.utc)
    ops = []
    for post in posts:
        np = {
            "author": post.get("author",""), "content": post.get("content",""),
            "timestamp": post.get("timestamp",""), "permalink": post.get("permalink",""),
            "postId": post.get("postId",""), "media": sanitize_media(post.get("media",[])),
        }
        dk = fallback_post_key(np)
        filt = ({"postId": np["postId"]} if np["postId"]
                else {"permalink": np["permalink"]} if np["permalink"]
                else {"dedupeKey": dk})
        ops.append({
            "filter": filt,
            "update": {
                "$set": {**np, "dedupeKey": dk, "groupUrl": context["groupUrl"],
                         "scrapedAt": context["scrapedAt"], "updatedAt": now},
                # New raw posts should be picked up by parser, but existing parsed posts
                # must not be reset back to parsed=False on every scrape cycle.
                "$setOnInsert": {"createdAt": now, "parsed": False, "parseSkipped": False}
            },
            "upsert": True
        })
    from pymongo import UpdateOne
    bulk = [UpdateOne(o["filter"], {"$set": o["update"]["$set"], "$setOnInsert": o["update"]["$setOnInsert"]}, upsert=True) for o in ops]
    result = collection.bulk_write(bulk, ordered=False)
    return {"matched": result.matched_count, "modified": result.modified_count, "upserted": result.upserted_count}


def _known_key_for_doc(post_id: str = "", permalink: str = "", dedupe_key: str = "") -> str:
    if post_id:
        return f"id:{post_id}"
    if permalink:
        return f"url:{permalink}"
    if dedupe_key:
        return f"dk:{dedupe_key}"
    return ""


def load_known_post_keys(collection, group_url: str, limit: int = 10000) -> set[str]:
    """Load known keys from Mongo so scraper can stop once it reaches old posts."""
    if collection is None or not group_url:
        return set()

    keys: set[str] = set()
    cursor = collection.find(
        {"groupUrl": group_url},
        {"postId": 1, "permalink": 1, "dedupeKey": 1},
    ).sort("updatedAt", -1).limit(max(1, int(limit)))

    for doc in cursor:
        post_id = str(doc.get("postId") or "").strip()
        permalink = normalize_permalink(str(doc.get("permalink") or "").strip())
        dedupe_key = str(doc.get("dedupeKey") or "").strip()
        key = _known_key_for_doc(post_id=post_id, permalink=permalink, dedupe_key=dedupe_key)
        if key:
            keys.add(key)

    return keys


def is_known_post(post: dict, known_keys: set[str]) -> bool:
    if not known_keys:
        return False

    post_id = str(post.get("postId") or "").strip()
    permalink = normalize_permalink(str(post.get("permalink") or "").strip())
    dk = fallback_post_key({
        "author": post.get("author", ""),
        "content": post.get("content", ""),
        "timestamp": post.get("timestamp", ""),
    })

    candidates = [
        _known_key_for_doc(post_id=post_id),
        _known_key_for_doc(permalink=permalink),
        _known_key_for_doc(dedupe_key=dk),
    ]
    return any(k and k in known_keys for k in candidates)


def build_merged_results(api_posts: dict, dom_posts: dict, max_posts: int | None = None) -> list:
    """Merge API and DOM post maps into normalized, deduped, sorted results."""
    merged = {}
    for post in api_posts.values():
        merged[key_for_post(post)] = post
    for post in dom_posts.values():
        found_key = ""
        for mk, mp in merged.items():
            if post.get("postId") and mp.get("postId") and post["postId"] == mp["postId"]:
                found_key = mk
                break
            if post.get("permalink") and mp.get("permalink") and post["permalink"] == mp["permalink"]:
                found_key = mk
                break
            sa, sb = post.get("author", "").lower(), mp.get("author", "").lower()
            if sa and sb and sa == sb:
                a, b = content_hash(post.get("content", "")), content_hash(mp.get("content", ""))
                if a and b and (a == b or a.startswith(b) or b.startswith(a)):
                    found_key = mk
                    break
        if found_key:
            merged[found_key] = merge_post(merged[found_key], post)
        else:
            merged[key_for_post(post)] = post

    results = [
        p for p in merged.values()
        if (p.get("postId") or p.get("permalink"))
        and ((p.get("content", "") and len(p["content"]) >= 8) or p.get("permalink"))
    ]
    results.sort(key=lambda p: p.get("timestamp", "") or "", reverse=True)
    if max_posts is None:
        return results
    return results[:max_posts]

# ── DOM extraction (runs inside the browser) ─────────────────────────────

DOM_EXTRACT_JS = """
() => {
    const TIME_RE = /^(?:\\d+\\s?(?:s|m|h|d|w|mo|y)|just now|yesterday|today)$/i;
    const ABS_TIME_RE = /^(?:\\d{1,2}\\s+[A-Za-z]{3,9}(?:\\s+\\d{4})?(?:\\s+at\\s+\\d{1,2}:\\d{2}\\s?(?:AM|PM)?)?|[A-Za-z]{3,9}\\s+\\d{1,2}(?:,\\s*\\d{4})?(?:\\s+at\\s+\\d{1,2}:\\d{2}\\s?(?:AM|PM)?)?|\\d{1,2}:\\d{2}\\s?(?:AM|PM))$/i;
    const clean = v => (v||"").replace(/\\u00a0/g," ").replace(/\\s+\\n/g,"\\n").replace(/\\n{3,}/g,"\\n\\n").trim();
    const txt = n => clean(n?.innerText||n?.textContent||"");
    const noise = t => !t||t.length<2||/^(facebook|most relevant|like|reply|share|comment)$/i.test(t);
    const feed = document.querySelector('div[role="feed"]');
    const arts = Array.from(document.querySelectorAll('div[role="article"]'));
    const cards = feed ? Array.from(feed.querySelectorAll(':scope > div')) : [];
    const cands = Array.from(new Set([...arts,...cards]));
    const results = [];
    for (const root of cands) {
        // Author
        let author = "";
        const links = Array.from(root.querySelectorAll('a[href*="facebook.com"],a[href*="/user/"],a[href*="profile.php"]'))
            .sort((a,b) => {
                const s = h => (/\\/groups\\/\\d+\\/user\\//.test(h)||/profile\\.php/.test(h))?3:(/\\/user\\//.test(h))?2:(/\\/photo\\/|\\/photos\\/|\\/videos\\//.test(h))?-2:0;
                return s(b.href||"")-s(a.href||"");
            });
        for (const l of links) {
            const h=l.href||"",t2=txt(l),ar=clean(l.getAttribute("aria-label")||""),au=t2||ar;
            if(!au||au.length<2||/^\\+\\d+$/.test(au)||/^may be an image/i.test(au)||/no photo description/i.test(au)||/facebook/i.test(au))continue;
            if(/\\/groups\\//.test(h)&&!/\\/user\\//.test(h)&&!/profile\\.php/.test(h))continue;
            if(TIME_RE.test(au.toLowerCase())||/^\\d+[smhdwy]$/i.test(au))continue;
            author=au;break;
        }
        // Content
        let content="",hasExp=false;
        const exp=Array.from(root.querySelectorAll('[data-ad-preview="message"],div[data-ad-comet-preview="message"]')).map(n=>txt(n)).filter(Boolean);
        if(exp.length>0){content=clean(exp.join("\\n\\n")).replace(/\\bSee more\\b/gi,"").trim();hasExp=true;}
        else{const bl=Array.from(root.querySelectorAll('div[dir="auto"],span[dir="auto"]')).map(n=>txt(n)).filter(t=>!noise(t)&&t.length>=8);content=clean(Array.from(new Set(bl)).join("\\n")).replace(/\\bSee more\\b/gi,"").trim();}
        // Permalink + timestamp
        let permalink="",timestamp="";
        const pPat=[/\\/groups\\/\\d+\\/posts\\/\\d+/,/\\/posts\\/\\d+/,/\\/permalink\\/\\d+/,/story_fbid=\\d+/,/multi_permalinks=\\d+/];
        const bPat=[/\\/photo\\//,/\\/photos\\//,/\\/videos\\//,/\\/watch\\//,/\\/reel\\//];
        const vts=v=>{const r=clean(v),l=r.toLowerCase();if(!l||r.length>40||l.startsWith("may be an image")||l.includes("no photo description")||l.includes("\\n"))return false;return TIME_RE.test(l)||ABS_TIME_RE.test(r);};
        for(const l of Array.from(root.querySelectorAll("a[href]"))){
            const h=l.href||"";
            if(!permalink&&pPat.some(p=>p.test(h))&&!bPat.some(p=>p.test(h))){permalink=h;const mt=clean(l.getAttribute("aria-label")||txt(l));if(vts(mt))timestamp=mt;}
            if(!timestamp){const lb=clean(l.getAttribute("aria-label")||""),tx=clean(txt(l));if(vts(tx)||vts(lb)){timestamp=tx||lb;if(!permalink&&!bPat.some(p=>p.test(h)))permalink=h;}}
        }
        if(!timestamp){for(const sp of Array.from(root.querySelectorAll("span[aria-label],span"))){const t2=clean(sp.textContent||""),lb=clean(sp.getAttribute("aria-label")||"");if(vts(t2)||vts(lb)){timestamp=t2||lb;break;}}}
        if(author&&timestamp&&author.toLowerCase()===timestamp.toLowerCase())timestamp="";
        if(permalink&&/\\/groups\\/\\d+\\/user\\//.test(permalink)&&!timestamp)permalink="";
        if(!author&&!content&&!permalink&&!timestamp)continue;
        if(!content&&!permalink)continue;
        if(content&&content.length<8&&!permalink)continue;
        const compact=content.replace(/\\s+/g," ").trim();
        if(!hasExp&&compact.length<120&&/^[^\\n]+\\n[^\\n]{1,80}$/.test(content))continue;
        if(/^sort group feed by/i.test(content))continue;
        // Media
        const media=[];const seen=new Set();
        const pm=(ty,u,w,h)=>{const cu=clean(u);if(!cu||!/^https?:\\/\\//i.test(cu)||seen.has(cu)||/\\/groups\\/\\d+\\/posts\\/|\\/permalink\\/\\d+|story_fbid=/.test(cu))return;seen.add(cu);media.push({type:ty==="video"?"video":"image",url:cu,width:w??null,height:h??null});};
        for(const v of root.querySelectorAll("video[src]"))pm("video",v.src,v.videoWidth||null,v.videoHeight||null);
        for(const s of root.querySelectorAll("video source[src]"))pm("video",s.src);
        for(const im of root.querySelectorAll("img[src]")){const r=im.getBoundingClientRect();const w=Math.max(r.width||0,im.naturalWidth||0),h=Math.max(r.height||0,im.naturalHeight||0);if(w<120||h<120)continue;pm("image",im.src,w,h);}
        for(const a of root.querySelectorAll("a[href]")){const h=a.href||"";if(/\\/videos?\\/|[./]mp4(\\?|$)/i.test(h))pm("video",h);else if(/\\/photo\\/|\\/photos\\//i.test(h))pm("image",h);}
        results.push({author,content,timestamp,permalink,media});
    }
    return results;
}
"""

SEE_MORE_JS = """
() => {
    const isVis = el => {if(!el)return false;const r=el.getBoundingClientRect();const s=window.getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=="hidden"&&s.display!=="none";};
    for (const c of document.querySelectorAll('div[role="button"],button,a[role="button"]')) {
        const l = (c.textContent||"")+" "+(c.getAttribute("aria-label")||"");
        if (/see more/i.test(l) && isVis(c)) c.click();
    }
}
"""

# ── Scrape cycle ─────────────────────────────────────────────────────────

async def scrape_group(
    page,
    group_url: str,
    max_posts: int,
    scroll_delay: int,
    max_empty: int,
    known_keys: set[str] | None = None,
    known_stop_streak: int = 8,
    flush_every: int = 0,
    on_flush=None,
) -> tuple[list, bool]:
    api_posts, dom_posts = {}, {}
    group_id = ""
    m = re.search(r"/groups/([^/?]+)", group_url, re.I)
    if m: group_id = m.group(1)
    combined = 0; empty_scrolls = 0; api_resp_count = 0
    stop_by_known = False
    consecutive_known = 0
    seen_scroll_keys = set()
    emitted_keys = set()

    def should_capture(name, body):
        if re.search(r"GroupsCometFeed|GroupFeed|StoriesPagination|CometFeedRegularStories", name, re.I): return True
        if group_id and group_id in body and re.search(r"graphql", body, re.I): return True
        return False

    async def on_response(response):
        nonlocal api_resp_count
        try:
            if response.status != 200: return
            if not re.search(r"graphql", response.url, re.I): return
            req = response.request
            post_data = req.post_data or ""
            fm = re.search(r"(?:^|&)fb_api_req_friendly_name=([^&]+)", post_data)
            fname = fm.group(1) if fm else ""
            if not should_capture(fname, post_data): return
            raw = await response.text()
            blocks = parse_graphql_json_blocks(raw)
            if not blocks: return
            api_resp_count += 1
            for block in blocks:
                stories = collect_story_nodes(block.get("data"))
                for story in stories:
                    raw_id = str(story.get("post_id") or story.get("id") or "")
                    if is_likely_comment_id(raw_id): continue
                    urls = extract_candidate_urls(story)
                    permalink = choose_best_post_url(urls, group_id)
                    if not story_belongs_to_group(story, group_id, permalink): continue
                    post_id = parse_post_id(permalink)
                    if not post_id and re.match(r"^\d{8,}$", raw_id): post_id = raw_id
                    post = {
                        "author": extract_author(story), "content": extract_message(story),
                        "timestamp": format_timestamp_iso(extract_timestamp(story)),
                        "permalink": normalize_permalink(permalink), "postId": post_id,
                        "media": sanitize_media(merge_media([], extract_media(story)))
                    }
                    if not post["permalink"] and post["postId"] and group_id:
                        post["permalink"] = f"https://www.facebook.com/groups/{group_id}/posts/{post['postId']}/"
                    if not post["content"] and not post["permalink"] and not post["postId"]: continue
                    key = pick_post_key(post)
                    existing = api_posts.get(key)
                    api_posts[key] = merge_post(existing, post) if existing else post
        except Exception:
            pass

    page.on("response", on_response)
    await page.goto(group_url, wait_until="domcontentloaded")

    # Dismiss cookie dialog
    for label in ["Decline optional cookies","Only allow essential cookies","Allow all cookies","Accept all"]:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I)).first
            if await btn.is_visible(timeout=1200):
                await btn.click(timeout=1200); break
        except Exception:
            pass
    await page.wait_for_timeout(1500)

    try:
        await page.wait_for_selector('div[role="feed"]', timeout=30000)
    except Exception:
        raise RuntimeError("Could not find the group feed. Verify URL and login state.")

    while combined < max_posts and empty_scrolls < max_empty:
        await page.evaluate(SEE_MORE_JS)
        await page.wait_for_timeout(450)
        dom_batch = await page.evaluate(DOM_EXTRACT_JS)
        for post in dom_batch:
            post["postId"] = parse_post_id(post.get("permalink",""))
            post["permalink"] = normalize_permalink(post.get("permalink",""))
            post["author"] = normalize_text(post.get("author",""))
            post["content"] = normalize_text(post.get("content",""))
            post["timestamp"] = normalize_text(post.get("timestamp",""))
            post["media"] = sanitize_media(merge_media([], post.get("media",[])))

            scroll_key = key_for_post(post)
            if scroll_key not in seen_scroll_keys:
                seen_scroll_keys.add(scroll_key)
                if known_keys and known_stop_streak > 0 and is_known_post(post, known_keys):
                    consecutive_known += 1
                    if consecutive_known >= known_stop_streak:
                        stop_by_known = True
                        break
                else:
                    consecutive_known = 0

            key = pick_post_key(post)
            existing = dom_posts.get(key)
            dom_posts[key] = merge_post(existing, post) if existing else post

        if stop_by_known:
            print(f"Stopping early after reaching {known_stop_streak} known posts in a row.")
            break

        if on_flush and flush_every > 0:
            snapshot = build_merged_results(api_posts, dom_posts, max_posts=None)
            pending = []
            for p in snapshot:
                k = key_for_post(p)
                if k in emitted_keys:
                    continue
                emitted_keys.add(k)
                pending.append(p)

            if pending:
                for i in range(0, len(pending), flush_every):
                    await on_flush(pending[i:i + flush_every])

        cur = max(len(api_posts), len(dom_posts))
        if cur == combined: empty_scrolls += 1
        else: empty_scrolls = 0
        combined = cur
        await page.mouse.wheel(0, 25000)
        await page.wait_for_timeout(scroll_delay)
        print(f"Collected {min(combined, max_posts)} posts... (api:{len(api_posts)}, dom:{len(dom_posts)}, api_responses:{api_resp_count})")

    page.remove_listener("response", on_response)

    results = build_merged_results(api_posts, dom_posts, max_posts=max_posts)
    return results, stop_by_known

# ── Main ─────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Rentd Facebook Group Scraper")
    parser.add_argument("--group-url", required=False, help="Facebook group URL")
    parser.add_argument("--max-posts", type=int, default=config.DEFAULT_MAX_POSTS)
    parser.add_argument("--output", default="facebook_posts.json")
    parser.add_argument("--state-file", default=config.STATE_FILE)
    parser.add_argument("--scroll-delay-ms", type=int, default=config.DEFAULT_SCROLL_DELAY_MS)
    parser.add_argument("--max-empty-scrolls", type=int, default=config.DEFAULT_MAX_EMPTY_SCROLLS)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=int, default=config.DEFAULT_POLL_INTERVAL)
    parser.add_argument("--mongo-uri", default=config.MONGO_URI)
    parser.add_argument("--mongo-db", default=config.MONGO_DB)
    parser.add_argument("--mongo-collection", default=config.RAW_POSTS_COLLECTION)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--prepare-session", action="store_true")
    parser.add_argument("--known-stop-streak", type=int, default=config.DEFAULT_KNOWN_STOP_STREAK)
    parser.add_argument("--known-keys-limit", type=int, default=config.DEFAULT_KNOWN_KEYS_LIMIT)
    parser.add_argument("--deep-cap-multiplier", type=int, default=config.DEFAULT_DEEP_CAP_MULTIPLIER)
    parser.add_argument("--progress-flush-posts", type=int, default=config.DEFAULT_PROGRESS_FLUSH_POSTS)
    args = parser.parse_args()

    if not args.group_url and not args.prepare_session:
        parser.print_help()
        sys.exit(1)

    group_url = enforce_chronological(args.group_url) if args.group_url else None
    state_file = Path(args.state_file).resolve()
    output_path = Path(args.output).resolve()
    has_state = state_file.exists()

    if args.headless and not has_state and not args.prepare_session:
        print(f"Error: Headless mode requires a session file at {state_file}. Run --prepare-session first.")
        sys.exit(1)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        print(f"Browser launch mode: {'headless' if args.headless else 'headed'}")
        try:
            if has_state:
                context = await browser.new_context(storage_state=str(state_file))
            else:
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
                print("Log in to Facebook in the opened browser window.")
                input("Press Enter here after login is complete...")
                await context.storage_state(path=str(state_file))
                await page.close()
                print(f"Saved login session to: {state_file}")

            # MongoDB
            mongo = init_mongo(args.mongo_uri, args.mongo_db, args.mongo_collection)
            if mongo:
                print(f"Connected to MongoDB: {mongo['db']}.{mongo['coll_name']}")
            else:
                print("MongoDB disabled: no mongo URI found.")

            if args.prepare_session and not group_url:
                print("Session prepared successfully. Exiting.")
                if mongo: mongo["client"].close()
                await context.close()
                return

            cycle = 0
            while True:
                cycle += 1
                scraped_at = datetime.now(timezone.utc).isoformat()
                
                # Adaptive Scraping: If this is a fresh group (0 posts in DB), 
                # boost the first scrape to 500 posts to backfill history.
                current_max = args.max_posts
                if mongo and group_url and cycle == 1:
                    existing = mongo["collection"].count_documents({"groupUrl": group_url})
                    if existing == 0:
                        print(f"✧ Fresh group detected. Boosting backfill to 500 posts...")
                        current_max = max(current_max, 500)

                known_keys = set()
                if mongo and group_url:
                    known_keys = load_known_post_keys(
                        mongo["collection"],
                        group_url,
                        limit=args.known_keys_limit,
                    )

                    # If the group already has data, allow deeper scan than max-posts so we can
                    # pass today's newest posts and stop at the first known boundary.
                    if known_keys and args.deep_cap_multiplier > 1:
                        current_max = max(current_max, args.max_posts * args.deep_cap_multiplier)
                        print(
                            f"Loaded {len(known_keys)} known keys. "
                            f"Deep scan cap for this cycle: {current_max}."
                        )

                page = None
                try:
                    page = await context.new_page()
                    flushed_new_total = 0

                    async def persist_chunk(chunk_posts: list):
                        nonlocal known_keys, flushed_new_total
                        if not mongo or not chunk_posts:
                            return

                        chunk_new = chunk_posts
                        if known_keys:
                            chunk_new = [p for p in chunk_posts if not is_known_post(p, known_keys)]
                        if not chunk_new:
                            return

                        r = upsert_posts(mongo["collection"], chunk_new, {"groupUrl": group_url, "scrapedAt": scraped_at})
                        flushed_new_total += len(chunk_new)
                        print(
                            f"Checkpoint: saved {len(chunk_new)} new posts "
                            f"(upserted={r['upserted']}, modified={r['modified']}, matched={r['matched']})"
                        )

                        for p in chunk_new:
                            pid = str(p.get("postId") or "").strip()
                            permalink = normalize_permalink(str(p.get("permalink") or "").strip())
                            dk = fallback_post_key({
                                "author": p.get("author", ""),
                                "content": p.get("content", ""),
                                "timestamp": p.get("timestamp", ""),
                            })
                            for key in (
                                _known_key_for_doc(post_id=pid),
                                _known_key_for_doc(permalink=permalink),
                                _known_key_for_doc(dedupe_key=dk),
                            ):
                                if key:
                                    known_keys.add(key)

                    posts, stopped_by_known = await scrape_group(
                        page,
                        group_url,
                        current_max,
                        args.scroll_delay_ms,
                        args.max_empty_scrolls,
                        known_keys=known_keys,
                        known_stop_streak=args.known_stop_streak,
                        flush_every=args.progress_flush_posts,
                        on_flush=persist_chunk if mongo and args.progress_flush_posts > 0 else None,
                    )

                    new_posts = posts
                    if known_keys:
                        new_posts = [p for p in posts if not is_known_post(p, known_keys)]

                    payload = {"groupUrl": group_url, "scrapedAt": scraped_at, "postCount": len(posts), "posts": posts}
                    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(
                        f"Cycle {cycle}: saved {len(posts)} posts "
                        f"({len(new_posts)} new, {len(posts) - len(new_posts)} known) to {output_path}"
                    )
                    if flushed_new_total:
                        print(f"Cycle {cycle}: {flushed_new_total} new posts were already checkpointed during scan.")
                    if stopped_by_known:
                        print("Reached known boundary. Next cycle will restart from top for fresh discovery.")
                    if mongo:
                        r = upsert_posts(mongo["collection"], new_posts, {"groupUrl": group_url, "scrapedAt": scraped_at})
                        print(f"Cycle {cycle}: MongoDB upserted={r['upserted']}, modified={r['modified']}, matched={r['matched']}")
                except Exception as e:
                    print(f"Cycle {cycle} failed: {e}")
                    if not args.continuous: raise
                finally:
                    if page:
                        try: await page.close()
                        except: pass

                if not args.continuous: break
                print(f"Waiting {args.poll_interval_seconds}s for next cycle...")
                await asyncio.sleep(args.poll_interval_seconds)

            if mongo: mongo["client"].close()
            await context.close()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
