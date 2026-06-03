import shutil
from pathlib import Path


def clear_directory_contents(directory: Path):
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def create_analysis_dirs(base_dir: Path):

    if base_dir.exists() and base_dir.is_dir():
        clear_directory_contents(base_dir)

    directories = {
        "root": base_dir,
        "data": base_dir / "data",
        "tables": base_dir / "tables",
        "maps": base_dir / "maps",
        "dataviz": base_dir / "dataviz",
        "atlas": base_dir / "atlas",
    }

    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)

    print(f"Répertoires d'analyse créés dans {base_dir} :")

    return directories
