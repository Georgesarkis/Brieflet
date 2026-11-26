# Brieflet

Short, local-written AI context for code repositories. A local model writes a brief (`AI_CONTEXT.md`, a component
diagram, decision records) so a big model like Claude reads fewer tokens and answers faster.

First measurement (22 Nov 2026, eShop, Claude Sonnet, 3 questions × 2 runs): **78k input tokens with the brief vs
158k with no docs and 343k with a raw Graphify code graph**, 30 s vs 54 s. Small sample: the benchmark in
[`bench/`](bench/) exists to test this properly, including answer quality.

## Benchmark

```
pip install pyyaml anthropic openai
cp bench/bench.example.yaml bench/bench.yaml     # edit repos, arms, models
python -m bench plan -c bench/bench.yaml         # matrix + cost estimate, spends nothing
python -m bench run  -c bench/bench.yaml         # free runners only; paid ones need --yes and estimate ≤ max_usd
python -m bench report -c bench/bench.yaml
python -m pytest bench/tests                     # offline tests, no keys
```

Runners: `claude_code` (Claude Code on your Claude login: no extra money, uses your plan's limit),
`anthropic` (Sonnet / Opus / Haiku via API key), `openai` (API key, set the model + price in `bench/prices.yaml`),
`fake` (offline). The API runners share the same three read-only tools and system prompt. Compare arms within one
model; different runners are different harnesses.

Spec and fairness rules: [`bench/SPEC.md`](bench/SPEC.md).

## License

Open source core; license to be decided.
