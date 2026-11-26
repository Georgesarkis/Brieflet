# Contributing to Brieflet

Issues and pull requests are welcome.

## Before you start

- For a bigger change, open an issue first so we can agree on the approach.
- Keep pull requests small and focused on one thing.
- The benchmark must stay fair and honest: no claims that `bench report` can't show. See [`bench/SPEC.md`](bench/SPEC.md).

## Develop

```
python -m pytest tests bench/tests     # offline, no API keys, no cost
```

Tests use fake models. Don't add tests that call paid APIs.

## Contributor License Agreement

Before your first pull request is merged you sign the [Contributor License Agreement](CLA.md). It takes one
comment in the pull request, and the CLA bot tells you what to write.

Why: Brieflet is Apache 2.0, and the CLA lets the maintainer also offer it under other terms later (for example
a commercial edition or a move to a company) without asking every past contributor. You keep your copyright,
and everything released under Apache 2.0 stays available under it.

## License

By contributing, you agree your contribution is licensed under the [Apache License 2.0](LICENSE) and the
[CLA](CLA.md).
