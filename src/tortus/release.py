"""Installed-package diagnostics and release validation helpers."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .api import PACKAGE_DIR
from .config import Settings


@dataclass(frozen=True)
class DoctorCheck:
    """One install diagnostic check."""

    name: str
    ok: bool
    detail: str


def run_doctor(settings: Settings) -> list[DoctorCheck]:
    """Return package, asset, optional dependency, and data-path diagnostics."""
    checks: list[DoctorCheck] = []
    try:
        version = importlib.metadata.version("tortus-rag")
        checks.append(DoctorCheck("distribution", True, f"tortus-rag {version}"))
    except importlib.metadata.PackageNotFoundError:
        checks.append(DoctorCheck("distribution", False, "tortus-rag distribution not installed"))

    for label, path in {
        "template asset": PACKAGE_DIR / "templates" / "index.html",
        "static asset": PACKAGE_DIR / "static" / "app.js",
        "typed marker": PACKAGE_DIR / "py.typed",
    }.items():
        checks.append(DoctorCheck(label, path.exists(), str(path)))

    for package in ("pypdf", "trafilatura", "bs4", "faiss", "graphrag", "llama_index", "lightrag"):
        checks.append(
            DoctorCheck(
                f"optional dependency {package}",
                importlib.util.find_spec(package) is not None,
                "available" if importlib.util.find_spec(package) is not None else "not installed",
            )
        )

    try:
        settings.tortus_data_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.tortus_data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(DoctorCheck("data path", True, str(settings.tortus_data_dir)))
    except OSError as exc:
        checks.append(DoctorCheck("data path", False, str(exc)))
    return checks


def run_release_check(project_root: Path) -> list[str]:
    """Build, inspect, install, and smoke-test the distribution artifacts."""
    project_root = project_root.resolve()
    if not (project_root / "pyproject.toml").exists():
        raise FileNotFoundError("release-check must be run from a project with pyproject.toml")

    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    messages: list[str] = []
    run([sys.executable, "-m", "build"], cwd=project_root)
    messages.append("built wheel and sdist")
    run([sys.executable, "-m", "twine", "check", "dist/*"], cwd=project_root, shell=True)
    messages.append("twine check passed")

    wheels = sorted(dist_dir.glob("tortus_rag-*.whl"))
    if not wheels:
        raise FileNotFoundError("no tortus-rag wheel was produced")

    with tempfile.TemporaryDirectory(prefix="tortus-release-") as tmp:
        temp_root = Path(tmp)
        venv = temp_root / "venv"
        run([sys.executable, "-m", "venv", str(venv)], cwd=project_root)
        python = venv_python(venv)
        env = os.environ.copy()
        env["TORTUS_DATA_DIR"] = str(temp_root / "data")
        env["TORTUS_CACHE_DIR"] = str(temp_root / "cache")
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=project_root)
        run([str(python), "-m", "pip", "install", str(wheels[-1])], cwd=project_root)
        run([str(python), "-c", "import tortus; print(tortus.__version__)"], cwd=project_root)
        tortus = venv_bin(venv, "tortus")
        run([str(tortus), "--help"], cwd=project_root, env=env)
        run([str(tortus), "ingest", "--corpus", "engineering"], cwd=project_root, env=env)
        run([str(tortus), "index", "--corpus", "engineering"], cwd=project_root, env=env)
        run(
            [
                str(tortus),
                "query",
                "How did token migration connect authentication and tracing?",
            ],
            cwd=project_root,
            env=env,
        )
        run([str(tortus), "serve", "--dry-run"], cwd=project_root, env=env)
    messages.append("installed wheel and smoke-tested tortus CLI")
    return messages


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> None:
    """Run a release-check subprocess with useful errors."""
    completed = subprocess.run(
        command if not shell else " ".join(command),
        cwd=cwd,
        env=env,
        shell=shell,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def venv_python(venv: Path) -> Path:
    """Return the Python executable inside a venv."""
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def venv_bin(venv: Path, name: str) -> Path:
    """Return a console script path inside a venv."""
    if sys.platform == "win32":
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name
