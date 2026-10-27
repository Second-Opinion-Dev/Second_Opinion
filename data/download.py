#!/usr/bin/env python3
"""Download the hackathon partner data into this folder (stdlib only).

    python3 data/download.py                 # everything (agv, tai, vle)
    python3 data/download.py agv             # one dataset
    python3 data/download.py agv vle         # several
    python3 data/download.py --list          # show what would be downloaded
    python3 data/download.py tai --force     # re-download even if present

The AGV/TAI API key is read from AISO_API_KEY in the environment or in data/.env
(see data/.env.example). Partner data is for the hackathon only: never commit it or the key.
"""
import argparse
import json
import os
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

BASE = "https://aiso-water-data.vercel.app"
VLE_BASE = "https://sp02.aveiro.vle.global"
VLE_FILES = {  # output name -> endpoint (public, no key; the feed is live)
    "export.csv": "/export",
    "history_all.json": "/api/history?range=all",
    "latest_snapshot.json": "/api/latest",
}
DATASETS = ("agv", "tai", "vle")


def load_env(path):
    """Minimal .env reader: KEY=VALUE lines, existing environment wins."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def fetch(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=120)


def save(url, dest, headers=None, size=None, force=False):
    """Stream url to dest via a .part file. Skip when dest already has the expected size."""
    if not force and dest.is_file() and size is not None and dest.stat().st_size == size:
        print(f"skip  {dest.relative_to(HERE)} (already downloaded)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    print(f"get   {dest.relative_to(HERE)}", end="", flush=True)
    with fetch(url, headers) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    if size is not None and part.stat().st_size != size:
        part.unlink()
        sys.exit(f"\nsize mismatch for {dest.name}: expected {size} bytes")
    part.replace(dest)
    print(f"  ({dest.stat().st_size / 1e6:.1f} MB)")


def extract_tar(tar_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    root = out_dir.resolve()
    with tarfile.open(tar_path) as tar:
        members = tar.getmembers()
        for m in members:
            if not (root / m.name).resolve().is_relative_to(root) or not (m.isfile() or m.isdir()):
                sys.exit(f"refusing to extract unsafe tar entry: {m.name}")
        tar.extractall(out_dir, members=members)
    print(f"extracted {sum(m.isfile() for m in members)} files to {out_dir.relative_to(HERE)}/")


def api_files(key):
    return json.load(fetch(f"{BASE}/files", {"X-API-Key": key}))["files"]


def get_key():
    load_env(HERE / ".env")
    key = os.environ.get("AISO_API_KEY")
    if not key:
        sys.exit("AISO_API_KEY is not set. Copy data/.env.example to data/.env and fill it in.")
    return key


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="*", metavar="dataset", help="agv, tai and/or vle (default: all)")
    ap.add_argument("--list", action="store_true", help="list files without downloading")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--no-extract", action="store_true", help="keep tai_all.tar packed")
    args = ap.parse_args()
    unknown = [d for d in args.datasets if d not in DATASETS]
    if unknown:
        ap.error(f"unknown dataset {unknown}; choose from {', '.join(DATASETS)}")
    wanted = args.datasets or list(DATASETS)

    if "agv" in wanted or "tai" in wanted:
        key = get_key()
        headers = {"X-API-Key": key}
        files = api_files(key)
        for name in [d for d in wanted if d in ("agv", "tai")]:
            # TAI: the single tar holds all 1,082 files, so skip the per-file entries.
            sel = [f for f in files if f["path"].startswith(name + "/")]
            if name == "tai":
                sel = [f for f in sel if f["path"] == "tai/tai_all.tar"]
            if args.list:
                for f in sel:
                    print(f"{f['size_bytes'] / 1e6:9.1f} MB  {f['path']}")
                continue
            for f in sel:
                save(f"{BASE}/files/{f['path']}", HERE / f["path"], headers, f["size_bytes"], args.force)
            if name == "tai" and not args.no_extract:
                extract_tar(HERE / "tai" / "tai_all.tar", HERE / "tai" / "extracted")

    if "vle" in wanted:
        for out, endpoint in VLE_FILES.items():
            if args.list:
                print(f"     live  {VLE_BASE}{endpoint} -> vle/{out}")
            else:  # live feed: always re-fetch so the history is current
                save(VLE_BASE + endpoint, HERE / "vle" / out, force=True)


if __name__ == "__main__":
    main()
