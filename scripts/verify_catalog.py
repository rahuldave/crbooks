#!/usr/bin/env python3
"""Verify a built catalog and every local CRBook archive against its checksum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_public_catalog import ALLOWED_COLLECTIONS, EXPECTED_BOOK_COUNT, sha256_file


def verify_catalog(catalog_path: Path, package_root: Path) -> dict[str, int]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    books = catalog.get("books", [])
    errors: list[str] = []
    if len(books) != EXPECTED_BOOK_COUNT:
        errors.append(f"expected {EXPECTED_BOOK_COUNT} books, found {len(books)}")
    if catalog.get("book_count") != len(books):
        errors.append("book_count does not match books")
    if len({book.get("slug") for book in books}) != len(books):
        errors.append("book slugs are not unique")
    if {book.get("collection_slug") for book in books} - ALLOWED_COLLECTIONS:
        errors.append("catalog contains a non-public collection")
    if any(book.get("language") != "en" for book in books):
        errors.append("catalog contains non-English books")

    checked_bytes = 0
    for book in books:
        package = package_root / str(book["collection_slug"]) / str(book["asset_name"])
        if not package.is_file():
            errors.append(f"missing package: {package}")
            continue
        checked_bytes += package.stat().st_size
        if package.stat().st_size != book["bytes"]:
            errors.append(f"size mismatch: {book['slug']}")
        if sha256_file(package) != book["sha256"]:
            errors.append(f"checksum mismatch: {book['slug']}")
        expected_url = (
            f"https://github.com/{catalog['repository']}/releases/download/"
            f"{catalog['release_tag']}/{book['asset_name']}"
        )
        if book["download_url"] != expected_url:
            errors.append(f"download URL mismatch: {book['slug']}")
        if not (catalog_path.parent / book["cover_url"]).is_file():
            errors.append(f"missing cover thumbnail: {book['slug']}")

    if checked_bytes != catalog.get("total_bytes"):
        errors.append("total_bytes does not match local package bytes")
    if errors:
        raise ValueError("\n".join(errors))
    return {"books": len(books), "bytes": checked_bytes, "errors": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("docs/catalog.json"))
    parser.add_argument("--package-root", type=Path, default=Path("dist/packages"))
    args = parser.parse_args()
    summary = verify_catalog(args.catalog.resolve(), args.package_root.resolve())
    print(
        f"Verified {summary['books']} local CRBooks ({summary['bytes']} bytes); "
        f"errors={summary['errors']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
