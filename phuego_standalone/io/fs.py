from pathlib import Path


def is_hidden_metadata_path(path: Path) -> bool:
    return path.name.startswith("._") or path.name == ".DS_Store"


def iter_visible_children(path: Path):
    for child in path.iterdir():
        if is_hidden_metadata_path(child):
            continue
        yield child


def iter_visible_dirs(path: Path):
    for child in iter_visible_children(path):
        try:
            if child.is_dir():
                yield child
        except PermissionError:
            continue
