# Project Plan: Reproductive Health Misinformation in Teen-Focused Reddit Communities

## Project context

This is a final project for NYU's *Text as Data* course (DS-GA 1015, Spring 2026), due **May 12th**. The student has limited prior experience with web scraping, APIs, and Python beyond coursework. AI coding assistance is encouraged by the course; the instructor (Elliott Ash) is an empirical economist who values rigor, clean methodology, and findings grounded in social-science questions.

## Research question

**How does sex education and reproductive health misinformation spread in online peer communities frequented by teens, and what does it look like?**

The motivation: as formal sex education has become more uneven and restricted in parts of the U.S., online peer communities have become an increasingly important informal source of reproductive health information for teens. This project measures the accuracy of that peer information across five specific medical claim categories. The findings are intended to be descriptive ("here's what we measured") rather than advocacy.

## Methodology overview

1. **Corpus collection.** Pull posts and top-level comments from three subreddits: `r/teenagers`, `r/birthcontrol`, and `r/sex`. For r/teenagers, filter posts using reproductive-health keywords. For r/birthcontrol and r/sex, filter to posts where the original poster self-identifies as a teen (under 20) using LLM-based or regex-based age extraction from the post text (formats like "16F", "I'm 17", "as a 15-year-old"). Target ~500–1500 total comments after filtering.

2. **Claim extraction.** Use an LLM (Gemini 2.5 Flash or Flash-Lite via the paid API — budget ~$5) to read each comment and identify whether it makes a claim in one of five categories defined in `medical_ground_truth.md`.

3. **Claim verification.** Use the same LLM, with the medical ground truth document included in the prompt, to classify each extracted claim as ACCURATE / INACCURATE / PARTIALLY ACCURATE / NOT APPLICABLE / OUTSIDE GROUND TRUTH.

4. **Validation.** Hand-label a stratified sample of ~50–100 LLM classifications to compute verifier accuracy. Report this accuracy in the methods section as a defense of the pipeline.

5. **Analysis.** Report aggregate misinformation rates by category, examples of common false claims (paraphrased, not quoted, for ethics), correction dynamics (do incorrect comments get downvoted? get corrected by replies?), and any patterns in how upvotes correlate with accuracy.

## Five claim categories (defined in detail in `medical_ground_truth.md`)

1. **Emergency contraception (Plan B / Ella / copper IUD)** — timing windows, effectiveness percentages, mechanism of action, conflation with abortion pill
2. **Fertility window and ovulation timing** — sperm survival, egg viability, "you can't get pregnant on your period," day-14 myth
3. **Withdrawal method** — typical vs. perfect use, pre-ejaculate, "if he's careful" misconception
4. **Condom effectiveness and use** — typical vs. perfect use, lambskin, double-bagging, oil-based lubricants
5. **Birth control pill missed-dose rules** — combination vs. progestin-only differences, current CDC US SPR guidance

The ground truth document includes a generalized "perfect-use principle" rule: claims citing perfect-use effectiveness numbers as if they're attainable in real life should be classified as MISLEADING across all categories.

## Subreddit selection rationale

- **r/teenagers** — large teen-only sub (community-bounded age); captures peer-to-peer discussion. Filter for reproductive health keywords.
- **r/birthcontrol** — most contraception-dense sub on Reddit; used in prior peer-reviewed research. Filter for self-identified teen authors.
- **r/sex** — broader sexual health discussion; filter for self-identified teens.

Methodology of "filter to self-identified AYAs" follows precedent in published Reddit reproductive health research (e.g., Pleasants et al. 2023 on r/birthcontrol; 2026 study in J. Pediatric Adolescent Gynecology using 8 subreddits with self-identified <26 filter).

## Technical pipeline

### Phase 1: Setup
- Project folder structure: `data/` (raw + processed), `scripts/` (pipeline code), `notebooks/` (exploratory analysis), `docs/` (the ground truth, paper drafts), `outputs/` (figures, tables)
- Anthropic API key stored in `.env` file (NEVER committed to git; add to `.gitignore`)
- Python environment with: `requests`, `anthropic`, `pandas`, `python-dotenv`, optionally `scikit-learn` for any clustering
- **No Reddit API credentials needed** — using PullPush instead (see Phase 2)

### Phase 2: Data collection (~3 hours of work)
- Write `scrape_reddit.py` using the **PullPush API** (https://pullpush.io/) — a third-party Reddit archive used in academic Reddit research. No Reddit account, app registration, or credentials needed; just HTTP requests via the `requests` library.
- Endpoints to use: `https://api.pullpush.io/reddit/search/submission/` for posts and `https://api.pullpush.io/reddit/search/comment/` for comments. Both accept query parameters like `subreddit`, `q` (keyword), `after`, `before`, `size`, `sort`.
- Pull from r/teenagers (with keyword filter), r/birthcontrol, r/sex (last 6–12 months)
- For each post: capture id, subreddit, title, body (selftext), author, score, num_comments, created_utc
- Pull comments by querying with `link_id` parameter set to the post id, capture comment id, body, score, parent_id
- Save raw to `data/raw/posts.csv` and `data/raw/comments.csv`
- For r/birthcontrol and r/sex, run age-extraction step to filter to self-identified teens
- **Note on PullPush limitations:** Very recent posts (last 24–48 hours) may lag; not a concern for this project since we're analyzing historical posts. Service occasionally has hiccups; build in retry logic with exponential backoff.

### Phase 3: Claim extraction + verification (~2 hours of work + LLM time)
- Write `verify_claims.py` that:
  - Reads each comment
  - Sends to Claude Haiku via the Anthropic API with a prompt that includes `medical_ground_truth.md` as reference
  - Gets back structured JSON: `{category, claim_text, classification, reasoning}`
  - Saves to `data/processed/classified_claims.csv`
- Cost target: under $10 for full corpus
- Use Claude Haiku 4.5 (claude-haiku-4-5) — comparable quality to Gemini Flash for structured extraction at ~$1/M input, $5/M output

### Phase 4: Validation (~1 hour)
- Random sample of 50–100 classified claims
- Hand-label them for accuracy
- Compute simple agreement rate; report in methods

### Phase 5: Analysis + paper (~3–4 hours)
- Misinformation rate by category (bar chart)
- Examples of common false claims, paraphrased
- Upvote-vs-accuracy correlation (scatter or boxplot)
- Correction dynamics (do replies to wrong comments correct them?)
- Write 6–10 page paper structured as: motivation, data, methods, results, discussion, limitations

## Important constraints and decisions

- **Time budget:** ~10–12 hours of work between today (May 7) and May 12. Scope must stay tight. No fine-tuning. No multi-source corpus expansion. No state-policy correlation. No web app.
- **Cost budget:** ~$5–10 in Anthropic API credits. Use Claude Haiku, not Opus or Sonnet.
- **Output format:** A research paper (PDF) hosted on GitHub Pages with a public URL, plus replication package (code, data, ground truth doc, README).
- **Ethics:** All Reddit data is public, but the paper should:
  - Paraphrase rather than quote when illustrating misinformation
  - Anonymize fully (no usernames, no identifying details)
  - Frame as analyzing public discourse, not analyzing individuals
  - Acknowledge in limitations that "self-identified teen" is unverified
  - Acknowledge that Reddit users are not representative of teens generally

## Deliverables checklist

- [ ] Public GitHub repo with all code
- [ ] GitHub Pages site with link to PDF paper
- [ ] Final paper PDF (6–10 pages)
- [ ] `medical_ground_truth.md` (already drafted)
- [ ] Raw data CSV (or filtered/anonymized version if size is an issue)
- [ ] Classified claims CSV
- [ ] Validation results
- [ ] README with replication instructions
- [ ] `.gitignore` excluding credentials

## Out of scope (intentionally cut for time)

- Multi-community comparison (paper treats the three subs as a pooled sample)
- State-level policy correlation
- Geolocation of users
- Fine-tuning a custom classifier
- A web app or interactive dashboard
- Comparing to non-Reddit sources (Yahoo Answers archive, TikTok, etc.)

These belong in the "future work" section of the paper.

## Files in this project

- `medical_ground_truth.md` — the authoritative reference document for claim verification (already drafted)
- `PROJECT_PLAN.md` — this file
- `scripts/scrape_reddit.py` — to be written
- `scripts/extract_age.py` — to be written (age filter for r/birthcontrol and r/sex)
- `scripts/verify_claims.py` — to be written
- `scripts/analyze.py` — to be written (or done as Jupyter notebook)
- `notebooks/exploratory.ipynb` — for messing around with data before writing final analysis
- `paper/paper.md` — the eventual paper draft
