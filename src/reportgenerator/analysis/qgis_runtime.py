import os
import shutil
import sys
from pathlib import Path

QGIS_PYTHON_ENV_VARS = ("REPORTGENERATOR_QGIS_PYTHON", "QGIS_PYTHON")
QGIS_PREFIX_ENV_VARS = (
    "REPORTGENERATOR_QGIS_PREFIX",
    "QGIS_PREFIX_PATH",
    "QGIS_PREFIX",
)

WINDOWS_QGIS_DIRS = (
    Path(r"C:\Program Files\QGIS\3_40"),
    Path(r"C:\Program Files\QGIS 3.40"),
    Path(r"C:\Program Files\QGIS 3.40.0"),
    Path(r"C:\OSGeo4W"),
    Path(r"C:\OSGeo4W64"),
)

LINUX_QGIS_PREFIXES = (
    Path("/usr"),
    Path("/usr/local"),
    Path("/opt/qgis"),
)


def _first_existing_path(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def _env_path(names):
    for name in names:
        value = os.getenv(name)
        if value:
            return Path(value)
    return None


def _windows_qgis_dirs():
    qgis_dirs = list(WINDOWS_QGIS_DIRS)
    program_files_dirs = (
        os.getenv("ProgramFiles"),
        os.getenv("ProgramFiles(x86)"),
        os.getenv("ProgramW6432"),
    )

    for program_files_dir in program_files_dirs:
        if not program_files_dir:
            continue

        qgis_dirs.extend(
            path
            for path in sorted(Path(program_files_dir).glob("QGIS*"), reverse=True)
            if path.is_dir()
        )

    return qgis_dirs


def resolve_qgis_python() -> Path:
    """Return the Python executable able to import QGIS bindings."""
    env_path = _env_path(QGIS_PYTHON_ENV_VARS)
    if env_path:
        return env_path

    command = shutil.which("python-qgis-ltr") or shutil.which("python-qgis")
    if command:
        return Path(command)

    if sys.platform.startswith("win"):
        candidates = []
        for qgis_dir in _windows_qgis_dirs():
            candidates.extend(
                (
                    qgis_dir / "bin" / "python-qgis-ltr.bat",
                    qgis_dir / "bin" / "python-qgis.bat",
                    qgis_dir / "bin" / "python.exe",
                )
            )
        found = _first_existing_path(candidates)
        if found:
            return found
    else:
        found = _first_existing_path(
            (
                Path("/usr/bin/python3"),
                Path("/usr/bin/python"),
            )
        )
        if found:
            return found

        for command_name in ("python3", "python"):
            command = shutil.which(command_name)
            if command:
                return Path(command)

    env_names = " or ".join(QGIS_PYTHON_ENV_VARS)
    raise RuntimeError(
        "Impossible de trouver l'interpréteur Python QGIS. "
        f"Définissez {env_names}, par exemple vers "
        r"C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat "
        "ou /usr/bin/python3."
    )


def qgis_subprocess_env() -> dict[str, str]:
    """Build an environment where QGIS Python can import this package."""
    env = os.environ.copy()
    package_root = Path(__file__).resolve().parents[2]
    python_paths = [str(package_root)]

    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    return env


def resolve_qgis_prefix() -> Path:
    """Return the QGIS installation prefix for QgsApplication."""
    env_path = _env_path(QGIS_PREFIX_ENV_VARS)
    if env_path:
        return env_path

    if sys.platform.startswith("win"):
        found = _first_existing_path(_windows_qgis_dirs())
        if found:
            return found
    else:
        found = _first_existing_path(LINUX_QGIS_PREFIXES)
        if found:
            return found

    env_names = " or ".join(QGIS_PREFIX_ENV_VARS)
    raise RuntimeError(
        "Impossible de trouver le préfixe QGIS. "
        f"Définissez {env_names}, par exemple vers "
        r"C:\Program Files\QGIS\3_40 ou /usr."
    )
