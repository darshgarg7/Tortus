from pathlib import Path

from typer.testing import CliRunner

from tortus import cli
from tortus.cli import app

runner = CliRunner()


def patch_tortus_home(monkeypatch, tmp_path: Path) -> None:
    """Redirect hidden user state into the test temp directory."""
    home = tmp_path / "home" / ".tortus"
    monkeypatch.setattr(cli, "TORTUS_HOME", home)
    monkeypatch.setattr(cli, "TORTUS_PROJECTS_DIR", home / "projects")
    monkeypatch.setattr(cli, "LAST_PROJECT_PATH", home / "last_project.json")


def test_demo_command_runs_from_empty_directory(tmp_path, monkeypatch) -> None:
    patch_tortus_home(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)

    report = tmp_path / "demo-report.md"
    result = runner.invoke(
        app,
        ["demo", "--project", "pytest-demo", "--output", str(report), "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert "Tortus Solve" in result.output
    assert "Recommended Actions" in result.output
    assert "Based on cited evidence" not in result.output
    assert "tortus setup to upgrade" in result.output
    assert (cli.LAST_PROJECT_PATH).exists()
    assert report.exists()
    report_text = report.read_text(encoding="utf-8")
    assert "# Tortus Solve Report" in report_text
    assert "## Recommended Actions" in report_text
    assert "## Citations" in report_text


def test_solve_command_ingests_workspace_sources(tmp_path, monkeypatch) -> None:
    patch_tortus_home(monkeypatch, tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "incident.md").write_text(
        "# Incident\nEU refund traces split after token audience validation failed.",
        encoding="utf-8",
    )
    (docs / "runbook.txt").write_text(
        "Refund retry handlers must preserve traceparent headers after authentication.",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "solve",
            "What should fix EU refund trace fragmentation?",
            str(docs),
            "--project",
            "pytest-workspace",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Sources Loaded" in result.output
    assert "Diagnosis" in result.output
    assert "Recommended Actions" in result.output
    assert "trace" in result.output.lower()
