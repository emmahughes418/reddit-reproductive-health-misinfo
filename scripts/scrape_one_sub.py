"""Scrape a single subreddit and APPEND its posts/comments to the existing CSVs.

Usage: python scripts/scrape_one_sub.py <subreddit>

Reuses the helpers in scrape_reddit.py so filter/retry/pacing logic stays consistent.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from scrape_reddit import (
    COMMENT_FIELDS,
    LOOKBACK_DAYS,
    MIN_COMMENTS,
    POST_FIELDS,
    RAW_DIR,
    REPO_ROOT,
    SUBREDDIT_KEYWORDS,
    TARGET_POSTS_PER_SUB,
    fetch_comments_for_post,
    fetch_posts,
    filter_posts,
    project_comment,
    project_post,
)


def append_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    exists = path.exists() and path.stat().st_size > 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def count_rows_per_sub(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sub = row.get("subreddit") or ""
            counts[sub] = counts.get(sub, 0) + 1
    return counts


def main(subreddit: str) -> None:
    posts_path = RAW_DIR / "posts.csv"
    comments_path = RAW_DIR / "comments.csv"

    before_posts = count_rows_per_sub(posts_path)
    before_comments = count_rows_per_sub(comments_path)
    before_post_total = sum(before_posts.values())
    before_comment_total = sum(before_comments.values())

    print(f"=== existing corpus ===")
    for sub, n in sorted(before_posts.items()):
        print(f"  r/{sub}: {n} posts, {before_comments.get(sub, 0)} comments")
    print(f"  TOTAL: {before_post_total} posts, {before_comment_total} comments")

    if subreddit in before_posts:
        print(f"\n!! r/{subreddit} already present in posts.csv with {before_posts[subreddit]} rows. Aborting to avoid duplicates.")
        sys.exit(1)

    start = time.time()
    after_ts = int(start - LOOKBACK_DAYS * 86400)

    print(f"\n=== r/{subreddit} ===")
    print(f"Fetching up to {TARGET_POSTS_PER_SUB} posts from r/{subreddit}...")
    raw = fetch_posts(subreddit, after_ts, TARGET_POSTS_PER_SUB)
    print(f"  pulled {len(raw)} raw posts")

    # filter_posts uses SUBREDDIT_KEYWORDS; r/WomensHealth is broadly on-topic so default empty
    candidates = filter_posts(raw, subreddit)
    keywords = SUBREDDIT_KEYWORDS.get(subreddit, [])
    print(f"  {len(candidates)} candidates after selftext filter ({'no keyword filter' if not keywords else f'keywords: {keywords}'}); fetching comments to apply >={MIN_COMMENTS}-comment engagement filter")

    new_posts: list[dict] = []
    new_comments: list[dict] = []
    for i, post in enumerate(candidates, 1):
        pid = post.get("id")
        print(f"  [{i}/{len(candidates)}] post {pid}...", end=" ", flush=True)
        comments = fetch_comments_for_post(pid)
        if len(comments) < MIN_COMMENTS:
            print(f"only {len(comments)} comments; skipping")
            time.sleep(4.0)
            continue
        print(f"kept ({len(comments)} comments)")
        new_posts.append(project_post(post))
        new_comments.extend(project_comment(c, pid, subreddit) for c in comments)
        time.sleep(4.0)

    append_csv(posts_path, new_posts, POST_FIELDS)
    append_csv(comments_path, new_comments, COMMENT_FIELDS)

    elapsed = time.time() - start

    after_posts = count_rows_per_sub(posts_path)
    after_comments = count_rows_per_sub(comments_path)
    after_post_total = sum(after_posts.values())
    after_comment_total = sum(after_comments.values())

    print(f"\n=== summary ===")
    print(f"  added r/{subreddit}: {len(new_posts)} posts, {len(new_comments)} comments")
    avg = (len(new_comments) / len(new_posts)) if new_posts else 0
    print(f"  avg {avg:.1f} comments/post for new sub")
    print(f"\n  before: {before_post_total} posts, {before_comment_total} comments")
    print(f"   after: {after_post_total} posts, {after_comment_total} comments")
    print(f"\n  per-subreddit totals after append:")
    for sub in sorted(after_posts):
        print(f"    r/{sub}: {after_posts[sub]} posts, {after_comments.get(sub, 0)} comments")
    print(f"\n  runtime: {elapsed/60:.1f} min ({elapsed:.0f}s)")
    print(f"  wrote (append): {posts_path.relative_to(REPO_ROOT)}")
    print(f"  wrote (append): {comments_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/scrape_one_sub.py <subreddit>")
        sys.exit(1)
    main(sys.argv[1])
