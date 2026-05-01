from pathlib import Path


class RunCancelled(Exception):
    """Raised when a web-submitted run is cancelled by the user."""


def cancel_file(run_dir):
    return Path(run_dir) / "cancel_requested"


def request_cancel(run_dir):
    path = cancel_file(run_dir)
    path.write_text("cancelled\n")
    return path


def clear_cancel(run_dir):
    path = cancel_file(run_dir)
    if path.exists():
        path.unlink()


def cancellation_requested(run_dir):
    return cancel_file(run_dir).exists()


def raise_if_cancelled(run_dir):
    if cancellation_requested(run_dir):
        raise RunCancelled("Analysis cancelled by user")
