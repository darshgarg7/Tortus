from pathlib import Path

from tortus.config import get_settings, settings_with_overrides


def test_tortus_toml_sits_below_environment_and_cli_overrides(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    Path("tortus.toml").write_text(
        "\n".join(
            [
                "[tortus]",
                'corpus = "workspace"',
                'data_dir = ".tortus/data"',
                'cache_dir = ".tortus/cache"',
            ]
        ),
        encoding="utf-8",
    )
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.tortus_corpus == "workspace"
    assert settings.tortus_data_dir == Path(".tortus/data")

    monkeypatch.setenv("TORTUS_CORPUS", "engineering")
    get_settings.cache_clear()
    env_settings = get_settings()
    assert env_settings.tortus_corpus == "engineering"

    cli_settings = settings_with_overrides(env_settings, corpus="public-engineering")
    assert cli_settings.tortus_corpus == "public-engineering"
    get_settings.cache_clear()
