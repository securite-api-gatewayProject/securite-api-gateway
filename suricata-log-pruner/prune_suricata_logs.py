import os
import time
from pathlib import Path

LOG_DIR = Path(os.getenv("SURICATA_LOG_DIR", "/var/log/suricata"))
KEEP_FILES = int(os.getenv("KEEP_FILES", "20"))
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "60"))


def list_eve_files():
    patterns = ("eve.json", "eve.json.*", "eve-*.json")
    files = []
    for pattern in patterns:
        files.extend(LOG_DIR.glob(pattern))

    # Remove duplicates and keep only files
    unique = {f.resolve(): f for f in files if f.is_file()}
    return sorted(unique.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def prune_once():
    if not LOG_DIR.exists():
        print(f"[pruner] log dir not found: {LOG_DIR}")
        return

    files = list_eve_files()
    if len(files) <= KEEP_FILES:
        print(f"[pruner] nothing to prune ({len(files)} files, keep={KEEP_FILES})")
        return

    to_delete = files[KEEP_FILES:]
    deleted = 0
    for path in to_delete:
        try:
            path.unlink(missing_ok=True)
            deleted += 1
        except Exception as exc:
            print(f"[pruner] failed to delete {path}: {exc}")

    print(f"[pruner] deleted {deleted} old eve files; remaining={min(len(files), KEEP_FILES)}")


def main():
    print(f"[pruner] started: dir={LOG_DIR}, keep={KEEP_FILES}, interval={INTERVAL_SECONDS}s")
    while True:
        prune_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
