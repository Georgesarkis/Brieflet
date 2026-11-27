# Architecture

Brieflet uses **Clean Architecture** (also called Onion or Ports & Adapters), with **MVC in the presentation layer**.
Both apps in this repo, the engine (`brieflet/`) and the benchmark (`bench/`), follow the same four layers.

```
presentation ──┐                      CLI = controller, presenters, Markdown/HTML views
               ├──> application ──> domain
infrastructure ┘                      git, disk, Ollama, plugin loading, JSONL files
```

**The one rule:** dependencies point inward. `domain` imports nothing from the other layers and does no IO.
`application` imports only `domain` and talks to the outside through interfaces (`ports.py`). `infrastructure`
implements those interfaces. `presentation` turns use-case results into text. Only the composition root
(`bootstrap.py`) knows the concrete classes. [`tests/test_architecture.py`](tests/test_architecture.py) checks this
rule on every test run, the same way NetArchTest does it in .NET.

## If you know C#

| Here | .NET equivalent |
|---|---|
| `domain/` (dataclasses + pure functions) | `Domain` project: entities, value objects, domain rules |
| `application/ports.py` (`typing.Protocol`) | interfaces in the `Application` project (`IRepoSnapshot`, `ILanguageModel`) |
| `application/*.py` use cases (`GenerateBrief`, `RunBenchmark`) | application services / MediatR handlers |
| `infrastructure/` | `Infrastructure` project: EF Core, HTTP clients, SDK wrappers |
| `presentation/cli.py` | an API controller (parse input, call one use case, return the view) |
| `presentation/views/`, `presentation/dashboard/` | Razor views |
| `presentation/brief_presenter.py` | a mapper from result to view model |
| `bootstrap.py` | `Program.cs` with the DI registrations |
| `typing.Protocol` | an interface: a class satisfies it by having the methods, with no `: IFoo` needed |

## Engine: `brieflet/`

```
brieflet/
  domain/            components.py (Component, Link, ComponentGraph) · decisions.py (DecisionCandidate,
                     DecisionRecord) · learned.py (LearnedFact + pruning rules) · model_text.py (secret filter, plain text)
  application/       ports.py · generate_brief.py (the use case) · prompts.py · model_answers.py (checks model JSON)
  infrastructure/    git_snapshot.py · folder.py · llm/ (gateway, backends, json_reply) · scanners.py (chains) ·
                     dotnet/ (aspire_scanner.py, apphost_statements.py, decision_scanner.py) ·
                     generic/ (any language: manifests.py, compose.py, tech.py, workspace_scanner.py,
                     grouping.py, decision_scanner.py)
  presentation/      cli.py · brief_controller.py · brief_presenter.py ·
                     views/ (ai_context_md, components_md, decisions_md, learned_md, claude_md, footer)
  bootstrap.py       composition root
```

`brieflet init` from start to end:

1. `cli.py` parses the arguments and asks `bootstrap.py` for a `BriefController`.
2. `GenerateBrief.plan()` asks the `ComponentScanner` for the component graph and the `DecisionScanner` for
   decision candidates. No model is called, so `--plan` can show the cost first. The scanner is a chain
   (`FirstFound`): the .NET Aspire scanner first, then the any-language `WorkspaceScanner`. Decision scanners all
   add candidates (`AllDecisions`); the generic one stays out of Aspire repos so their output does not change.
3. `GenerateBrief.run()` calls the `LanguageModel` for labels, the AI_CONTEXT prose and one record per decision.
   `model_answers.py` drops anything it can't verify (paths not in the repo, secret-looking text) and adds a note.
4. The use case returns a `Brief` (data only). `brief_presenter.py` renders it with the views, the controller writes
   the files through the `Folder` port.

## Benchmark: `bench/`

```
bench/
  domain/            pricing.py (cost + money rules) · scoring.py (0-3 quality rule) · folds.py · results.py (ArmStats)
  application/       ports.py · config.py (BenchConfig) · plan_benchmark.py · run_benchmark.py · learning_pass.py ·
                     judge_answers.py · outcome.py (exit codes)
  infrastructure/    config_loader.py · results_store.py (JSONL) · workspaces.py (arm copies) · judge_clients.py ·
                     notifier.py · runners/ (fake + plugin registry)
  presentation/      cli.py · plan_table.py · report_table.py · dashboard/ (page, results_html, setup_html, markdown_html)
  bootstrap.py       composition root (BenchApp)
```

The money gate (`--yes`, `max_usd`, the live budget stop) lives in the use cases, so no runner can skip it.
Tests swap the real runners and judge for fakes through `main(argv, runner_for=..., judge=...)`, which is
constructor injection with no DI container.

The benchmark uses the engine as a library: `brieflet.domain.learned` (fact rules), the LEARNED.md view and the
`LEARNED_ASK` prompt.

## Where new things go

| You want to… | Add… |
|---|---|
| support a new manifest type or language | a reader in `infrastructure/generic/manifests.py` (`READERS`) |
| teach it a new database / queue / image | `infrastructure/generic/tech.py` (data only) |
| a repo type with its own model of the system (like Aspire) | a `ComponentScanner` + `DecisionScanner` in `infrastructure/<name>/`, put in the chain in `bootstrap.py` |
| add a model backend | a plugin package: a class with `complete()`, `default_models`, `prices`, `paid`, registered under the `brieflet.llm_backends` entry point group (see `infrastructure/llm/backends.py`) |
| add a benchmark reader / judge | a plugin package: `run()` under `brieflet.bench_runners`, `ask()` under `brieflet.bench_judges`, prices under `brieflet.bench_prices` |
| change what a generated doc looks like | its view in `presentation/views/` (only there) |
| change a rule (scoring, pruning, cost) | `domain/`, with a unit test, no mocks needed |

Only local models ship in this repo. Anything else (cloud models, hosted runners) is a separate package that
plugs into these entry points, so the core never imports a cloud SDK.

## Conventions

- Names say what a thing is (`AspireScanner`, `JsonlResults`), no `utils` or `helpers` modules.
- Errors are typed (`ModelError`, `RepoUnreadable`, `NoComponentsFound`, `SetupError`), and the CLI turns them into
  a message and exit code 2. A bad model *answer* is not an error: it's dropped with a note in the output.
- Files stay under ~200 lines and functions under ~50.
