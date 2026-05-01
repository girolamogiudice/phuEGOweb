import json
from datetime import datetime
from pathlib import Path
from typing import Any


def update_progress(run_dir: Path, **kwargs: Any) -> None:
    """
    Write/update a progress.json file.
    Safe to call many times.
    """

    progress_file = run_dir / "progress.json"

    # -------------------------
    # load previous state (merge!)
    # -------------------------
    if progress_file.exists():
        try:
            existing = json.loads(progress_file.read_text())
        except Exception:
            existing = {}
    else:
        existing = {}

    # -------------------------
    # merge new data
    # -------------------------
    data = {
        **existing,
        **kwargs,
        "updated_at": datetime.utcnow().isoformat(),
    }

    # -------------------------
    # auto-compute percent
    # -------------------------
    progress = data.get("progress")
    if isinstance(progress, dict):
        cur = progress.get("current")
        tot = progress.get("total")
        if isinstance(cur, (int, float)) and isinstance(tot, (int, float)) and tot > 0:
            progress["percent"] = round(100.0 * cur / tot, 1)

    progress_file.write_text(json.dumps(data, indent=2))
