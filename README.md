# Reddit Reproductive Health Misinformation

**Final project, NYU DS-GA 1015 (Text as Data), Spring 2026.**
Emma Hughes — `eah9921@nyu.edu`

📄 **[Read the paper (PDF)](docs/paper.pdf)**

## Abstract

As formal sex education in parts of the United States has become more uneven, online peer communities have grown into an important informal source of reproductive-health information. This project measures the accuracy of that peer information by collecting recent posts and top-level comments from three subreddits — `r/birthcontrol`, `r/sex`, and `r/WomensHealth` — and classifying each comment against a medical ground-truth document covering five claim categories: emergency contraception, the fertility window, withdrawal, condoms, and birth-control-pill effectiveness. A Claude Haiku 4.5 verifier with a cached system prompt classifies 770 human comments; a stratified hand-validation pass on 40 of those classifications shows 87.5% agreement with the model. Within the in-scope categories, roughly 63% of comments classified as factual claims are not strictly accurate — most often by reciting perfect-use effectiveness numbers as if they were attainable in everyday use.

## Methodology summary

1. **Corpus collection.** Posts pulled from the [PullPush](https://pullpush.io/) archive (`/reddit/search/submission/`); top-level comments fetched from Reddit's anonymous JSON endpoint (`/comments/{post_id}.json`) because PullPush's stored comment archive is incomplete. 12-month window, ≥5-comment engagement filter applied post-hoc on retrieved comments. ([scripts/scrape_reddit.py](scripts/scrape_reddit.py))
2. **Bot/automod removal.** Exact-match exclusion of `AutoModerator`, `[deleted]`, and `*-ModTeam` accounts. ([scripts/filter_comments.py](scripts/filter_comments.py))
3. **LLM claim extraction + verification.** Claude Haiku 4.5 with the full medical ground-truth document in a prompt-cached system block. Each comment receives a structured JSON classification: `comment_type`, `category`, `claim_text`, `classification`, `reasoning`, `hedged`. ([scripts/verify_claims.py](scripts/verify_claims.py))
4. **Hand validation.** Stratified random sample (seed 42), agreement on 40 of 59 rows. Per-stratum agreement: ACCURATE 100%, non_claim 100%, OUTSIDE_GT 100%, PARTIALLY 86%, INACCURATE 69%. ([scripts/build_validation_sample.py](scripts/build_validation_sample.py), [scripts/analyze_validation.py](scripts/analyze_validation.py))
5. **Analysis & figures.** Stdlib-csv stats + matplotlib figures. ([scripts/analyze.py](scripts/analyze.py), [scripts/make_figures.py](scripts/make_figures.py))

Full methods outline: [paper/methods_outline.txt](paper/methods_outline.txt).

## File structure

```
.
├── README.md                  this file
├── PROJECT_PLAN.md            original project plan
├── medical_ground_truth.md    authoritative reference for claim verification
├── requirements.txt           Python dependencies
├── .env.example               template for the Anthropic API key
├── docs/
│   └── paper.pdf              the paper (served via GitHub Pages)
├── data/
│   ├── raw/                   raw scrape (gitignored)
│   ├── processed/             intermediate + classified output (gitignored)
│   └── anonymized/            committable de-identified versions
│       ├── posts.csv
│       ├── comments.csv
│       └── classified_claims.csv
├── scripts/                   pipeline + analysis code
├── outputs/                   results_summary.txt, 5 figures, example claims
├── paper/                     paper drafts and methods outline
└── notebooks/                 (exploratory; empty in replication package)
```

The committed data uses SHA-256 author hashes (first 8 hex chars), consistent across files. Tokens like `[deleted]`, `AutoModerator`, and `*-ModTeam` are passed through.

## Replication

```bash
git clone https://github.com/<your-username>/reddit-reproductive-health-misinfo.git
cd reddit-reproductive-health-misinfo

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your Anthropic API key

# 1. scrape (~75 min for the full corpus; long because of conservative pacing)
python scripts/scrape_reddit.py

# 2. filter bots/automod
python scripts/filter_comments.py

# 3. classify (~25 min; ~$1 in Anthropic API spend)
python scripts/verify_claims.py

# 4. (optional) build a hand-validation sample and run analysis
python scripts/build_validation_sample.py
python scripts/analyze_validation.py
python scripts/analyze.py
python scripts/make_figures.py
```

If you want to skip the scraping/classification steps and reproduce the analysis straight from the de-identified frozen data:

```bash
# Place the anonymized CSVs into the expected paths the analysis reads from:
cp data/anonymized/classified_claims.csv data/processed/classified_claims.csv
python scripts/analyze.py
python scripts/make_figures.py
```

## Ethics

All Reddit data is public, but this project follows community-research norms:

- The paper paraphrases claims rather than quoting them when illustrating misinformation.
- Author usernames in the committed dataset are replaced by SHA-256[:8] hashes; the mapping is not committed.
- "Self-identified teen" is acknowledged as unverified.
- Findings describe public discourse in aggregate rather than profiling individuals.

## License

Code is released under the MIT License. Reddit content (paraphrased in the paper, hashed-author CSVs in this repo) belongs to its original authors and is reproduced under fair-use academic-research norms.
