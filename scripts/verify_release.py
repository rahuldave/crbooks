#!/usr/bin/env python3
"""Verify every GitHub Release download in the public catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def verify_download(url: str, expected_bytes: int, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    byte_count = 0
    request = urllib.request.Request(url, headers={"User-Agent": "crbooks-release-verifier/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}: {url}")
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    if byte_count != expected_bytes:
        raise ValueError(f"byte-size mismatch ({byte_count} != {expected_bytes}): {url}")
    if digest.hexdigest() != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: {url}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("docs/catalog.json"))
    parser.add_argument("--book", action="append", help="Verify only this slug (repeatable).")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    selected = set(args.book or [])
    books = [book for book in catalog["books"] if not selected or book["slug"] in selected]
    if selected - {book["slug"] for book in books}:
        raise ValueError(
            f"unknown book slug(s): {sorted(selected - {book['slug'] for book in books})}"
        )
    for index, book in enumerate(books, start=1):
        print(f"[{index}/{len(books)}] {book['slug']}", flush=True)
        verify_download(book["download_url"], book["bytes"], book["sha256"])
    print(f"Verified {len(books)} GitHub Release downloads with exact SHA-256 checksums.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
