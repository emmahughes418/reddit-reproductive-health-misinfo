"""Scrape posts and comments from r/birthcontrol, r/sex, r/teenagers via PullPush.

Saves to data/raw/posts.csv and data/raw/comments.csv.
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import requests

SUBMISSION_URL = "https://api.pullpush.io/reddit/search/submission/"
COMMENT_URL = "https://api.pullpush.io/reddit/search/comment/"
REDDIT_COMMENTS_URL = "https://www.reddit.com/comments/{post_id}.json"
REDDIT_USER_AGENT = "ReproHealthMisinfoResearch/0.1 (NYU DS-GA 1015 final project)"

SUBREDDITS = ["birthcontrol", "sex", "WomensHealth"]
TARGET_POSTS_PER_SUB = 400
PAGE_SIZE = 100
MIN_COMMENTS = 5
COMMENTS_PER_POST = 25
LOOKBACK_DAYS = 365

# Map of subreddit -> required keyword list. Subreddits absent from this dict
# (or with an empty list) are treated as fully on-topic and skip keyword filtering.
# r/teenagers needed this when included; the current three subs are all on-topic.
SUBREDDIT_KEYWORDS: dict[str, list[str]] = {}

DEAD_BODIES = {"[deleted]", "[removed]", ""}

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"

POST_FIELDS = ["id", "subreddit", "title", "selftext", "author", "score", "num_comments", "created_utc"]
COMMENT_FIELDS = ["id", "post_id", "subreddit", "body", "author", "score", "created_utc", "parent_id"]


def get_with_retry(url: str, params: dict | None = None, headers: dict | None = None, max_attempts: int = 5):
    """GET with exponential backoff. Honors Retry-After on 429. Returns parsed JSON or None."""
    backoffs_429 = [15, 30, 60, 120]
    backoffs_other = [2, 4, 8, 16]
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=45)
            if r.status_code == 429:
                if attempt == max_attempts:
                    print(f"    ! 429 after {max_attempts} attempts; skipping")
                    return None
                retry_after = r.headers.get("Retry-After")
                wait = int(retry_after) if (retry_after and retry_after.isdigit()) else backoffs_429[attempt - 1]
                print(f"    ! 429 (attempt {attempt}); sleeping {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == max_attempts:
                print(f"    ! request failed after {max_attempts} attempts ({e}); skipping")
                return None
            wait = backoffs_other[attempt - 1]
            print(f"    ! attempt {attempt} failed ({e}); sleeping {wait}s")
            time.sleep(wait)
    return None


def matches_keywords(post: dict, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{post.get('title') or ''} {post.get('selftext') or ''}".lower()
    return any(kw.lower() in text for kw in keywords)


def fetch_posts(subreddit: str, after_ts: int, target: int) -> list[dict]:
    """Page backwards in time using `before` until we hit `target` raw posts or run out."""
    collected: list[dict] = []
    before: int | None = None
    while len(collected) < target:
        params = {
            "subreddit": subreddit,
            "size": PAGE_SIZE,
            "sort": "desc",
            "sort_type": "created_utc",
            "after": after_ts,
        }
        if before is not None:
            params["before"] = before
        data = get_with_retry(SUBMISSION_URL, params)
        if not data:
            break
        batch = data.get("data", [])
        if not batch:
            break
        collected.extend(batch)
        oldest = min(p.get("created_utc", 0) for p in batch)
        if oldest <= after_ts or len(batch) < PAGE_SIZE:
            break
        before = oldest - 1
        time.sleep(1.5)
    return collected[:target]


def filter_posts(posts: list[dict], subreddit: str) -> list[dict]:
    """Pre-filter on selftext + keywords only. The num_comments filter is applied
    post-hoc using comments actually returned from PullPush, since PullPush snapshots
    num_comments at ingest time and the field is unreliable."""
    keywords = SUBREDDIT_KEYWORDS.get(subreddit, [])
    kept = []
    for p in posts:
        body = (p.get("selftext") or "").strip()
        if body in DEAD_BODIES:
            continue
        if not matches_keywords(p, keywords):
            continue
        kept.append(p)
    return kept


def fetch_comments_for_post(post_id: str) -> list[dict]:
    """Fetch top-level comments via Reddit's anonymous JSON endpoint.

    Reddit returns a 2-element listing: [post, comments]. We pull `data.children`
    from the comments listing, ignore "more" placeholders, and keep only top-level
    items (those whose parent_id starts with t3_, i.e., parent is the post itself).
    """
    headers = {"User-Agent": REDDIT_USER_AGENT}
    data = get_with_retry(
        REDDIT_COMMENTS_URL.format(post_id=post_id),
        params={"limit": COMMENTS_PER_POST, "sort": "top", "raw_json": 1},
        headers=headers,
    )
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    children = data[1].get("data", {}).get("children", [])
    out = []
    for child in children:
        if child.get("kind") != "t1":
            continue
        c = child.get("data", {})
        body = (c.get("body") or "").strip()
        if body in DEAD_BODIES:
            continue
        parent_id = c.get("parent_id") or ""
        if not parent_id.startswith("t3_"):
            continue
        out.append(c)
    return out[:COMMENTS_PER_POST]


def project_post(p: dict) -> dict:
    return {k: p.get(k) for k in POST_FIELDS}


def project_comment(c: dict, post_id: str, subreddit: str) -> dict:
    return {
        "id": c.get("id"),
        "post_id": post_id,
        "subreddit": subreddit,
        "body": c.get("body"),
        "author": c.get("author"),
        "score": c.get("score"),
        "created_utc": c.get("created_utc"),
        "parent_id": c.get("parent_id"),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    start = time.time()
    after_ts = int(start - LOOKBACK_DAYS * 86400)

    all_posts: list[dict] = []
    all_comments: list[dict] = []
    per_sub_posts: dict[str, int] = {}
    per_sub_comments: dict[str, int] = {}

    for sub in SUBREDDITS:
        print(f"\n=== r/{sub} ===")
        print(f"Fetching up to {TARGET_POSTS_PER_SUB} posts from r/{sub}...")
        raw = fetch_posts(sub, after_ts, TARGET_POSTS_PER_SUB)
        print(f"  pulled {len(raw)} raw posts")
        candidates = filter_posts(raw, sub)
        print(f"  {len(candidates)} candidates after selftext/keyword filter; fetching comments to apply >={MIN_COMMENTS}-comment engagement filter")

        sub_kept_posts = 0
        sub_comment_count = 0
        for i, post in enumerate(candidates, 1):
            pid = post.get("id")
            print(f"  [{i}/{len(candidates)}] post {pid}...", end=" ", flush=True)
            comments = fetch_comments_for_post(pid)
            if len(comments) < MIN_COMMENTS:
                print(f"only {len(comments)} comments; skipping")
                time.sleep(4.0)
                continue
            print(f"kept ({len(comments)} comments)")
            all_posts.append(project_post(post))
            all_comments.extend(project_comment(c, pid, sub) for c in comments)
            sub_kept_posts += 1
            sub_comment_count += len(comments)
            time.sleep(4.0)

        per_sub_posts[sub] = sub_kept_posts
        per_sub_comments[sub] = sub_comment_count
        print(f"  -> r/{sub}: kept {sub_kept_posts} posts with {sub_comment_count} comments")

    posts_path = RAW_DIR / "posts.csv"
    comments_path = RAW_DIR / "comments.csv"
    write_csv(posts_path, all_posts, POST_FIELDS)
    write_csv(comments_path, all_comments, COMMENT_FIELDS)

    elapsed = time.time() - start
    total_posts = len(all_posts)
    total_comments = len(all_comments)

    print("\n=== summary ===")
    for sub in SUBREDDITS:
        n_posts = per_sub_posts.get(sub, 0)
        n_comments = per_sub_comments.get(sub, 0)
        avg = (n_comments / n_posts) if n_posts else 0
        print(f"  r/{sub}: {n_posts} posts, {n_comments} comments (avg {avg:.1f}/post)")
    overall_avg = (total_comments / total_posts) if total_posts else 0
    print(f"  TOTAL: {total_posts} posts, {total_comments} comments (avg {overall_avg:.1f}/post)")
    print(f"  wrote: {posts_path.relative_to(REPO_ROOT)}")
    print(f"  wrote: {comments_path.relative_to(REPO_ROOT)}")
    print(f"  runtime: {elapsed/60:.1f} min ({elapsed:.0f}s)")


if __name__ == "__main__":
    main()
