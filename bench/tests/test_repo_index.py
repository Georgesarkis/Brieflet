"""All-repos index.html: one button per tested repo with name, open/closed source, size and language."""
import yaml

from bench.presentation.cli import main
from bench.presentation.dashboard.repo_info import info, measure


def _config(tmp, name, files, meta):
    repo = tmp / f"repo-{name}"
    repo.mkdir()
    for fn, text in files.items():
        (repo / fn).write_text(text)
    (tmp / f"{name}.q.yaml").write_text(yaml.safe_dump({"questions": [{"id": "q1", "type": "trace", "text": "where?"}]}))
    art = tmp / "art" / name
    art.mkdir(parents=True)
    (art / "meta.yaml").write_text(yaml.safe_dump(meta))
    p = tmp / f"{name}.yaml"
    p.write_text(yaml.safe_dump({"repeats": 1, "max_usd": 0, "results": f"results/{name}", "artifacts": "art",
                                 "repos": {name: {"path": str(repo), "questions": f"{name}.q.yaml"}},
                                 "arms": {"none": {}}, "models": [{"name": "fake", "runner": "fake", "model": "fake"}]}))
    return p


def test_index_lists_every_repo_with_its_facts(tmp_path):
    a = _config(tmp_path, "shop", {"Basket.cs": "class Basket {}\n\nclass Order {}\n"},
                {"repo": "acme/Shop", "license": "MIT"})
    b = _config(tmp_path, "secret", {"app.py": "x = 1\n", "b.py": "y = 2\n"}, {"repo": "acme/Secret", "source": "closed"})
    assert main(["run", "-c", str(a)]) == 0
    idx = tmp_path / "results" / "index.html"
    html = idx.read_text()
    assert "acme/Shop" in html and "acme/Secret" not in html          # no runs yet for the second repo
    assert main(["run", "-c", str(b)]) == 0
    html = idx.read_text()
    assert html.count('class="chip" aria-pressed') == 2 and 'id="all"' in html
    assert "Open source · MIT" in html and "Closed source" in html
    assert "C# · 1 files · 2 lines" in html and "Python · 2 files · 2 lines" in html
    assert 'href="shop/dashboard.html"' in html and 'href="secret/dashboard.html"' in html
    assert 'id="combined"' in html and 'tr data-i="1"' in html and '"name": "acme/Secret"' in html
    assert "../index.html" in (tmp_path / "results" / "shop" / "dashboard.html").read_text()


def test_meta_fallback_when_checkout_missing(tmp_path):
    r = info("x", {"sha": "4da8212117e8"}, {"repo": "o/r", "language": "C#", "files": 315, "loc": 10893}, tmp_path / "gone")
    assert (r.name, r.sha, r.language, r.size, r.open_source) == ("o/r", "4da8212", "C#", "315 files · 11k lines", True)


def test_measure_skips_build_folders(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "big.js").write_text("a\n" * 999)
    (tmp_path / "main.go").write_text("package main\n")
    assert measure(tmp_path) == ("Go", 1, 1)
