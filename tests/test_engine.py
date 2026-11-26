"""brieflet init with a fake model on a tiny Aspire repo: no network, no cost."""
import json
import subprocess
from pathlib import Path

from brieflet.engine import AI_CONTEXT, COMPONENTS, DECISIONS, Init
from brieflet.llm import LLM

APPHOST = '''var builder = DistributedApplication.CreateBuilder(args);
var redis = builder.AddRedis("redis");
var bus = builder.AddRabbitMQ("eventbus");
var basket = builder.AddProject<Projects.Basket_API>("basket-api").WithReference(redis).WithReference(bus);
var web = builder.AddProject<Projects.WebApp>("webapp").WithReference(basket);
builder.Build().Run();
'''


class FakeLLM(LLM):
    def ask_json(self, role, system, prompt, max_out):
        self.calls.append({"role": role})
        if "name boxes" in system:
            return {"labels": {"webapp": "Online store UI", "basket_api": "Shopping basket"}}, ""
        if "AI_CONTEXT" in system:
            return {"overview": "A tiny shop.", "how_they_talk": ["webapp calls basket-api"],
                    "where": [{"topic": "basket", "paths": ["src/Basket.API"]}, {"topic": "ghost", "paths": ["src/Nope"]}]}, ""
        return {"title": "Use Redis for the basket", "context": "c", "decision": "d", "consequences": "e", "confidence": "medium"}, ""


def repo(tmp: Path) -> Path:
    r = tmp / "r"
    for path, txt in {"src/AppHost/AppHost.csproj": '<Project Sdk="Aspire.AppHost.Sdk"></Project>',
                      "src/AppHost/AppHost.cs": APPHOST,
                      "src/Basket.API/Basket.API.csproj": "<Project></Project>",
                      "src/Basket.API/Program.cs": 'builder.AddRedisClient("redis");',
                      "src/WebApp/WebApp.csproj": "<Project></Project>",
                      "src/WebApp/Program.cs": 'builder.Services.AddGrpcClient<B>(o => o.Address = new("http://basket-api"));'}.items():
        p = r / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
        subprocess.run(["git", "-C", str(r), *c], check=True)
    return r


def test_init_writes_files(tmp_path):
    r = repo(tmp_path)
    out = tmp_path / "out"
    job = Init(r, FakeLLM("ollama"), out, log=lambda *a: None)
    plan = job.plan()
    assert {n["name"] for n in plan["comp"]["nodes"]} == {"redis", "eventbus", "basket-api", "webapp"}
    res = job.run(plan)
    ctx = (out / AI_CONTEXT).read_text()
    assert "Online store UI" in ctx and "`src/Basket.API`" in ctx and "src/Nope" not in ctx
    assert any("ghost" in n for n in res["notes"])
    assert "gRPC" in (out / COMPONENTS).read_text()
    assert (out / DECISIONS).exists() and (out / "CLAUDE.md").exists()
    assert not (r / AI_CONTEXT).exists()  # --out never touches the repo


def test_cloud_needs_yes(tmp_path, capsys):
    from brieflet.__main__ import main
    r = repo(tmp_path)
    assert main(["init", str(r), "--llm", "anthropic"]) == 2
    assert "Refused" in capsys.readouterr().out


def test_learned_kept_and_pruned(tmp_path):
    r = repo(tmp_path)
    (r / "LEARNED.md").write_text("# Learned\n\n- Basket uses Redis → `src/Basket.API/Program.cs` · 2026-11-20\n"
                                  "- Old thing → `src/Removed/Old.cs`\n")
    out = tmp_path / "out"
    res = Init(r, FakeLLM("ollama"), out, log=lambda *a: None).run(Init(r, FakeLLM("ollama"), out).plan())
    txt = (out / "LEARNED.md").read_text()
    assert "Basket uses Redis" in txt and "Old thing" not in txt
    assert any("src/Removed/Old.cs" in n for n in res["notes"])
    claude = (out / "CLAUDE.md").read_text()
    assert "LEARNED.md" in claude and "had to search the code" in claude


def test_footer_on_by_default_and_can_be_turned_off(tmp_path, monkeypatch):
    from brieflet.engine import FOOTER
    r = repo(tmp_path)
    out = tmp_path / "on"
    Init(r, FakeLLM("ollama"), out, log=lambda *a: None).run(Init(r, FakeLLM("ollama"), out).plan())
    for f in (AI_CONTEXT, COMPONENTS, DECISIONS):
        assert (out / f).read_text().rstrip().endswith(FOOTER)
    assert FOOTER not in (out / "CLAUDE.md").read_text() and FOOTER not in (out / "LEARNED.md").read_text()
    off = tmp_path / "off"
    Init(r, FakeLLM("ollama"), off, log=lambda *a: None, footer=False).run(Init(r, FakeLLM("ollama"), off).plan())
    assert FOOTER not in (off / AI_CONTEXT).read_text()
    monkeypatch.setenv("BRIEFLET_FOOTER", "0")
    env = tmp_path / "env"
    Init(r, FakeLLM("ollama"), env, log=lambda *a: None).run(Init(r, FakeLLM("ollama"), env).plan())
    assert FOOTER not in (env / COMPONENTS).read_text()
