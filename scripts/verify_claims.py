"""Classify each Reddit comment against medical_ground_truth.md using Claude Haiku 4.5.

Usage:
  python scripts/verify_claims.py --test     # run on first 10 comments, print results
  python scripts/verify_claims.py            # run on full corpus, save to CSV

Output: data/processed/classified_claims.csv with all original comment columns
plus contains_claim, category, claim_text, classification, reasoning, hedged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
GROUND_TRUTH_PATH = REPO_ROOT / "medical_ground_truth.md"
COMMENTS_PATH = REPO_ROOT / "data" / "processed" / "comments_filtered.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "processed" / "classified_claims.csv"

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 400

# Haiku 4.5 pricing per https://www.anthropic.com/pricing (USD per 1M tokens)
PRICE_INPUT = 1.00
PRICE_OUTPUT = 5.00
PRICE_CACHE_WRITE = 1.25
PRICE_CACHE_READ = 0.10

NEW_FIELDS = ["comment_type", "contains_claim", "category", "claim_text", "classification", "reasoning", "hedged"]

SYSTEM_INSTRUCTIONS = """You are a medical-claim verifier. You read short Reddit comments and decide (1) what kind of comment it is, and (2) if it makes a verifiable medical claim falling into one of five categories defined in the GROUND TRUTH document below, you classify the claim against the ground truth.

COMMENT TYPE (use these exact codes):
- "claim_fact"            → the comment makes a verifiable medical claim or asserts a fact about contraception / reproductive health. This must align with contains_claim=true.
- "personal_experience"   → the comment shares a personal anecdote or experience WITHOUT making a generalizable claim ("My IUD insertion hurt", "I had irregular periods on the pill").
- "social_encouragement"  → supportive remarks, agreement, emotional reactions, encouragement, affirmation, sympathy ("Good luck!", "I'm sorry you're going through this", "Same here").
- "other"                 → questions, off-topic, unclear, jokes, or anything that doesn't fit the above.

PRIORITY RULE — CRITICAL: if a comment contains BOTH a personal anecdote AND a generalizable medical claim, classify as "claim_fact". The presence of a generalizable claim takes priority over the anecdotal framing.
  Example: "I took Plan B at 50 hours and it worked, so it still works through 72 hours" → claim_fact (the second clause is a generalizable claim).
  Example: "My IUD insertion hurt for hours afterward" → personal_experience (no generalizable claim).

ADVICE-FRAMING CLARIFICATION: When a comment contains a factual assertion about how contraception or reproductive biology works — such as "the pill increases appetite," "IUDs cause cramping," "condoms don't work with oil lube" — classify as claim_fact even if the comment's overall purpose is practical advice. The verifiability of the underlying assertion takes priority over the comment's conversational function. Phrases like "X causes Y," "X does Z," "X is W" embedded in advice or recommendations still count as generalizable claims.
  Example: "The pill increases your appetite, so watching your portions helps" → claim_fact (asserts pill→appetite causation; advice framing is irrelevant).
  Example: "Plan B can mess with your cycle for a couple months, just be patient" → claim_fact (asserts EC→cycle effect).
  Example: "Talk to your doctor about switching pills" → social_encouragement / other (no factual assertion about how anything works).

SCOPING NOTE FOR CATEGORY 5 (Birth Control Pill): This category covers BOTH (a) missed-dose rules AND (b) general claims about pill effectiveness, including claims about pregnancy risk while on the pill. Claims like "she's on the pill so pregnancy is very unlikely," "the pill is 99% effective," "BC almost guarantees you won't get pregnant," or "pregnancy is non-existent on BC" should be classified as Category 5 / "pill" claims (likely PARTIALLY_ACCURATE or INACCURATE per the perfect-use principle), NOT as OUTSIDE_GROUND_TRUTH.

CATEGORIES (use these exact codes):
- "EC"          → emergency contraception (Plan B / Ella / copper IUD as EC)
- "fertility"   → fertility window, ovulation timing, sperm/egg survival
- "withdrawal"  → withdrawal / pull-out method, pre-ejaculate
- "condoms"     → condom effectiveness, materials, lubricants, double-bagging
- "pill"        → birth control pill missed-dose rules (combination vs progestin-only)
- "outside"     → comment makes a verifiable medical claim, but on a topic OUTSIDE the five categories above
- null          → comment does NOT contain a verifiable medical claim (e.g., personal anecdote without factual claim, off-topic, joke, pure opinion)

CLASSIFICATION (use these exact strings):
- "ACCURATE"            → claim aligns with the ground truth
- "INACCURATE"          → claim conflicts with the ground truth
- "PARTIALLY_ACCURATE"  → claim is partly right, partly wrong, or misleading (e.g., quotes perfect-use stats as if real-world)
- "NOT_APPLICABLE"      → contains_claim is false, OR comment is in scope but the ground truth has no specific position
- "OUTSIDE_GROUND_TRUTH"→ category is "outside" (verifiable medical claim outside the five focus categories)

OTHER FIELDS:
- claim_text: a short factual paraphrase (NOT a quote) of the claim being made. null if contains_claim=false.
- reasoning: 1-2 sentences citing what the claim says vs what the ground truth says.
- hedged: true if the commenter signals uncertainty ("I think", "I heard", "not sure", "maybe", "afaik"). False if asserted confidently.

OUTPUT FORMAT — return ONLY a single JSON object, no markdown, no surrounding text:
{"comment_type": <string>, "contains_claim": <bool>, "category": <string|null>, "claim_text": <string|null>, "classification": <string|null>, "reasoning": <string>, "hedged": <bool>}

GROUND TRUTH:

"""


def load_ground_truth() -> str:
    return GROUND_TRUTH_PATH.read_text(encoding="utf-8")


def build_system_blocks(ground_truth: str) -> list[dict]:
    """System content with prompt caching on the (large, static) ground truth block."""
    return [
        {
            "type": "text",
            "text": SYSTEM_INSTRUCTIONS + ground_truth,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def call_with_retry(client: anthropic.Anthropic, system_blocks: list[dict], comment_body: str, max_attempts: int = 3):
    """Returns (parsed_json_dict, usage_dict, raw_text). Raises on persistent failure."""
    user_prompt = (
        "Classify the following Reddit comment. Return only the JSON object specified in the system prompt.\n\n"
        f"COMMENT:\n{comment_body}"
    )
    backoffs = [2, 5, 15, 30]
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = resp.content[0].text.strip()
            # tolerate models occasionally wrapping in fences
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            usage = {
                "input_tokens": getattr(resp.usage, "input_tokens", 0),
                "output_tokens": getattr(resp.usage, "output_tokens", 0),
                "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
                "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            }
            return parsed, usage, text
        except (anthropic.APIError, json.JSONDecodeError) as e:
            if attempt == max_attempts:
                raise
            wait = backoffs[attempt - 1]
            print(f"    ! attempt {attempt} failed ({type(e).__name__}: {e}); sleeping {wait}s")
            time.sleep(wait)


def empty_classification(error_msg: str | None = None) -> dict:
    return {
        "comment_type": None,
        "contains_claim": None,
        "category": None,
        "claim_text": None,
        "classification": None,
        "reasoning": f"ERROR: {error_msg}" if error_msg else None,
        "hedged": None,
    }


def normalize(parsed: dict) -> dict:
    """Coerce parsed JSON to our canonical fields, tolerating slight schema drift."""
    return {
        "comment_type": parsed.get("comment_type"),
        "contains_claim": parsed.get("contains_claim"),
        "category": parsed.get("category"),
        "claim_text": parsed.get("claim_text"),
        "classification": parsed.get("classification"),
        "reasoning": parsed.get("reasoning"),
        "hedged": parsed.get("hedged"),
    }


def cost_for_usage(totals: dict) -> float:
    return (
        totals["input_tokens"] * PRICE_INPUT
        + totals["output_tokens"] * PRICE_OUTPUT
        + totals["cache_creation_input_tokens"] * PRICE_CACHE_WRITE
        + totals["cache_read_input_tokens"] * PRICE_CACHE_READ
    ) / 1_000_000


def aggregate_usage(running: dict, u: dict) -> None:
    for k in u:
        running[k] = running.get(k, 0) + (u[k] or 0)


def main(test_mode: bool) -> None:
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    ground_truth = load_ground_truth()
    system_blocks = build_system_blocks(ground_truth)
    client = anthropic.Anthropic()

    df = pd.read_csv(COMMENTS_PATH)
    if test_mode:
        df = df.head(10).copy()
        print(f"=== TEST MODE: classifying {len(df)} comments ===\n")
    else:
        print(f"=== FULL RUN: classifying {len(df)} comments ===\n")

    results: list[dict] = []
    totals: dict = {}
    start = time.time()

    for i, row in enumerate(df.itertuples(index=False), 1):
        body = (row.body or "") if isinstance(row.body, str) else ""
        if not body.strip():
            results.append(empty_classification("empty body"))
            continue
        try:
            parsed, usage, raw = call_with_retry(client, system_blocks, body)
            aggregate_usage(totals, usage)
            normalized = normalize(parsed)
            results.append(normalized)
            if test_mode:
                print(f"--- comment {i} (id={row.id}, sub=r/{row.subreddit}, score={row.score}) ---")
                print(f"BODY: {body[:400]}{'...' if len(body) > 400 else ''}")
                print(f"RAW JSON: {raw}")
                print(f"PARSED:   {json.dumps(normalized, indent=2)}\n")
        except Exception as e:
            print(f"  ! comment {i} (id={row.id}) failed permanently: {e}")
            results.append(empty_classification(str(e)))

        if not test_mode and i % 50 == 0:
            elapsed = time.time() - start
            running_cost = cost_for_usage(totals)
            print(f"  [{i}/{len(df)}] elapsed {elapsed/60:.1f} min, running cost ${running_cost:.4f}")

    out_df = df.reset_index(drop=True).copy()
    res_df = pd.DataFrame(results)
    for col in NEW_FIELDS:
        out_df[col] = res_df[col].values

    if not test_mode:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(OUTPUT_PATH, index=False)
        print(f"\nwrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(out_df)} rows)")

    elapsed = time.time() - start

    if not test_mode:
        n_total = len(out_df)
        n_failed = int(out_df["reasoning"].fillna("").str.startswith("ERROR:").sum())
        print("\n=== distributions ===")
        print(f"  total processed: {n_total} ({n_failed} permanent failures)")
        for col in ["comment_type", "contains_claim", "category", "classification"]:
            print(f"\n  {col}:")
            counts = out_df[col].fillna("(null)").astype(str).value_counts()
            for v, n in counts.items():
                print(f"    {v}: {n}")

    print("\n=== usage ===")
    for k, v in totals.items():
        print(f"  {k}: {v:,}")
    print(f"  estimated cost: ${cost_for_usage(totals):.4f}")
    print(f"  runtime: {elapsed/60:.1f} min ({elapsed:.0f}s)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true", help="run on first 10 comments, print results")
    args = p.parse_args()
    main(args.test)
