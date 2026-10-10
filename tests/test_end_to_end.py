import pytest

from ownerlens.cli import main
from ownerlens.evaluate import evaluate
from ownerlens.generate import generate
from ownerlens.rules import analyze


@pytest.fixture(scope="module")
def default_run():
    registry, truth = generate()
    return analyze(registry), truth


def test_every_planted_company_gets_its_expected_flag(default_run):
    analysis, truth = default_run
    for pattern in truth["patterns"]:
        for company_id in pattern["companies"]:
            finding = analysis.finding(company_id)
            assert finding and pattern["rule"] in finding.rules, (pattern["pattern"], company_id)


def test_harmless_lookalikes_stay_below_medium(default_run):
    analysis, truth = default_run
    medium_plus = {f.company_id for f in analysis.at_least("medium")}
    for name, companies in truth["benign"].items():
        assert not (set(companies) & medium_plus), name


def test_nothing_unplanted_reaches_medium(default_run):
    analysis, truth = default_run
    planted = {c for p in truth["patterns"] for c in p["companies"]}
    assert {f.company_id for f in analysis.at_least("medium")} <= planted


def test_the_shell_factory_is_high_risk(default_run):
    analysis, truth = default_run
    shells = next(p for p in truth["patterns"] if p["pattern"] == "shell_factory_nominee")["companies"]
    assert all(analysis.finding(c).level == "high" for c in shells)


def test_no_false_positives_across_several_backgrounds():
    results = evaluate(list(range(7, 17)))
    assert sum(r.other_medium_plus for r in results) == 0
    assert sum(r.benign_medium_plus for r in results) == 0
    for result in results:
        assert all(found == planted for found, planted in result.recall.values()), result.seed


def test_command_line_end_to_end(tmp_path, capsys):
    data, reports, truth = tmp_path / "registry", tmp_path / "reports", tmp_path / "truth.json"
    assert main(["generate", "--out", str(data), "--truth", str(truth)]) == 0
    assert main(["analyze", "--data", str(data), "--out", str(reports)]) == 0
    for name in ("findings.md", "findings.csv", "ownership_network.png"):
        assert (reports / name).stat().st_size > 0
    capsys.readouterr()

    company = (reports / "findings.csv").read_text().splitlines()[1].split(",")[0]
    assert main(["owners", company, "--data", str(data)]) == 0
    assert company in capsys.readouterr().out


def test_command_line_reports_a_broken_registry(tmp_path, capsys):
    assert main(["analyze", "--data", str(tmp_path / "nothing"), "--out", str(tmp_path / "out")]) == 1
    assert "missing file" in capsys.readouterr().err
