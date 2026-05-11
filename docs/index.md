---
title: Reddit Reproductive Health Misinformation
---

# Reddit Reproductive Health Misinformation

**NYU DS-GA 1015 (Text as Data), Spring 2026** — Emma Hughes (`eah9921@nyu.edu`)

📄 **[Read the paper (PDF)](paper.pdf)**
💻 **[Source code on GitHub](https://github.com/emmahughes418/reddit-reproductive-health-misinfo)**

## Abstract

As formal sex education in parts of the United States has become more uneven, online peer communities have grown into an important informal source of reproductive-health information. This project measures the accuracy of that peer information by collecting recent posts and top-level comments from three subreddits — `r/birthcontrol`, `r/sex`, and `r/WomensHealth` — and classifying each comment against a medical ground-truth document covering five claim categories: emergency contraception, the fertility window, withdrawal, condoms, and birth-control-pill effectiveness.

A Claude Haiku 4.5 verifier with a cached system prompt classifies 770 human comments; a stratified hand-validation pass on 40 of those classifications shows 87.5% agreement with the model. Within the in-scope categories, roughly 63% of comments classified as factual claims are not strictly accurate — most often by reciting perfect-use effectiveness numbers as if they were attainable in everyday use.

## Headline findings

- 770 human comments classified (after bot/automod removal)
- 89 comments (12%) make verifiable medical claims; 58 are in the five focus categories
- Within in-scope claims: ~33% ACCURATE, ~41% PARTIALLY_ACCURATE, ~22% INACCURATE
- The substantive claim discussion concentrates in r/birthcontrol (91% of claims)
- The dominant error pattern is over-citation of perfect-use effectiveness for the pill
- Hand-validation agreement: 87.5% overall; the INACCURATE stratum is the weakest at 69%

## How to cite

> Hughes, E. (2026). *Reddit Reproductive Health Misinformation in Teen-Focused Communities.* NYU DS-GA 1015 final project. https://github.com/emmahughes418/reddit-reproductive-health-misinfo
