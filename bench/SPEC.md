# Benchmark spec v0.1: does a short AI context beat no docs and a code graph?

Step 1 of the product plan. Goal: a public, repeatable benchmark strong enough to put on LinkedIn and in a README.
Status: draft for George's edits. Nothing has run yet.

## What the 22 Nov run showed (and what it can't claim)

eshop-demo, Claude Sonnet, 3 questions × 2 runs, median input tokens:
none 158k · graph 343k · full 78k. Time 54 s vs 30 s. API price $0.24 vs $0.11.

Limits we fix in this benchmark:
1. One repo, 3 questions, 2 runs. Direction is clear, the exact % is not.
2. **No quality score.** HISTORY notes "full" is cheaper partly because Claude digs less (no file:line detail on Q1/Q3).
   Fewer tokens with a worse answer is not a win.
3. Q2: full used more tokens than none (36k vs 29k). We need to know which question types it helps.
4. Graphify ran AST-only, community labels off. A critic will say Graphify wasn't run fully.
5. "full" still contained the Graphify files; only the CLAUDE.md pointer differed. We can't tell if the win is the short
   AI_CONTEXT or the pointer.
6. Engine only understands .NET Aspire repos today (`lib/dev_components.py` reads the AppHost, `SIGNAL_RE` is .NET).

## Arms (what Claude gets in the repo)

| Arm | Contents | Why |
|---|---|---|
| none | code only, our files removed | baseline |
| graphify-ast | Graphify `update` output + 2-line CLAUDE.md pointer | = the 22 Nov "graph" bar |
| graphify-full | Graphify with local-model community labels + pointer | fair to Graphify |
| ours-local | AI_CONTEXT + diagram + ADRs written by local models (9B/27B on the RTX 2070), no graph | the product, local |
| ours-cloud | same generator, cloud model writes the text (Haiku 5.5) | the product, cloud option |
| ours+graph | ours-local + Graphify files | = the 22 Nov "full" bar, to compare with the old numbers |

## Repos (pinned commits, all public)

Start with .NET because that's what the engine reads today:
1. **dotnet/eShop**: medium, Aspire microservices (the original demo, re-run on upstream).
2. **dotnet-architecture/eShopOnWeb**: small monolith (checks we don't only help microservices).
3. **bitwarden/server**: large real product (checks it scales beyond samples).

After step 2 makes the engine language-agnostic, add one TypeScript and one Python repo.

## Questions (10 per repo, written before any run)

Mix of types so we learn where it helps:
- 3 overview: "what are the main parts and how do they talk?"
- 3 trace: "follow X from request to storage, with files"
- 2 change: "to add Y, which files must change?"
- 2 detail: one specific config/value lookup (where docs should NOT help much)

## Answering models

Claude Code headless, read-only tools (Read, Grep, Glob), same as `dev_token_compare.sh`:
Sonnet 5.5 (main), Haiku 5.5 (cheap). 3 runs per question × arm × model, arms interleaved.

## Metrics

- Input tokens (new + cache), output tokens, turns, wall time, API-price cost.
- **Quality, 0–3**, blind: a judge model (Opus 5.5) gets the question, a reference answer, and the answer with the arm hidden.
  Reference answers: written by Opus with full code access, then checked by George for a sample.
- Docs generation cost per arm: GPU minutes (local) or $ (cloud), and regeneration cost per push.
- Headline metric: **tokens per correct answer** (quality ≥ 2), not raw tokens.

## Size and cost estimate

3 repos × 10 questions × 6 arms × 3 runs × 2 models ≈ 1,080 Claude Code runs.
At the 22 Nov average (~$0.03–0.11 per run) ≈ **$40–120 at API price**, or a lot of subscription usage. Option: Sonnet only
first (~540 runs), Haiku later.

## Fairness rules (for credibility)

- Publish this spec + the questions before running (pre-registered).
- Pin repo SHAs, tool versions (Graphify, Ollama models, Claude Code), and the prompt.
- Publish raw JSONL + every answer + judge scores. Report losses too (e.g. Q2-type questions).

## Where it runs

Docs generation for ours-local and graphify-full: geolinux (GPU). Claude answering runs: geolinux too
(Claude Code on George's login, like 22 Nov) or the cloud with an API key. Harness lives in the new product repo.

## Open for George

1. New public repo for the product + benchmark (name?).
2. OK to spend ~$40–120 API price, or start Sonnet-only?
3. Who checks reference answers (George, a sample of ~10)?

## Learning arm (`learn: true`)

Tests the self-improving `LEARNED.md`. `bench learn` runs each fold's questions once, with an extra ask: end the answer
with `LEARNED:` + up to 3 lines `- fact → \`path\`` for what the docs lacked. Lines are checked (path exists in the repo,
no duplicates, no secret-looking text) and pile up in `results/<name>/learned/<repo>/<model>/<arm>/foldN.md`.
`bench run` then measures each question with LEARNED.md built from the OTHER folds only. Learning runs go to
`learn.jsonl`, not `runs.jsonl`, and count in `plan`. Read: does a later question get cheaper because an earlier,
different question already dug the code? Leak risk stays low (separate questions), but related questions can share facts;
that is the point, and it is what happens in real use.
