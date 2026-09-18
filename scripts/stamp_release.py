#!/usr/bin/env python3
"""Stamp selected catalog books with their immutable GitHub release metadata."""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

from scripts.build_public_catalog import CATALOG_FIELDS, normalize_release_published_at


def stamp_release(
    catalog_path: Path,
    *,
    book_slugs: set[str],
    release_tag: str,
    uploaded_at: str,
) -> int:
    if not release_tag.strip():
        raise ValueError("release tag is empty")
    if not book_slugs:
        raise ValueError("at least one book slug is required")
    normalized_uploaded_at = normalize_release_published_at(uploaded_at)

    with catalog_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        if set(fieldnames) != CATALOG_FIELDS:
            raise ValueError("catalog fields do not include per-book release metadata")
        rows = list(reader)

    known_slugs = {row["slug"] for row in rows}
    unknown = book_slugs - known_slugs
    if unknown:
        raise ValueError(f"unknown book slug(s): {sorted(unknown)}")
    for row in rows:
        if row["slug"] in book_slugs:
            row["release_tag"] = release_tag
            row["uploaded_at"] = normalized_uploaded_at

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=catalog_path.parent,
            prefix=f".{catalog_path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        os.chmod(temporary_path, catalog_path.stat().st_mode)
        os.replace(temporary_path, catalog_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return len(book_slugs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalogs/catalog.tsv"))
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--uploaded-at", required=True)
    parser.add_argument("--book", action="append", required=True)
    args = parser.parse_args()
    count = stamp_release(
        args.catalog.resolve(),
        book_slugs=set(args.book),
        release_tag=args.release_tag,
        uploaded_at=args.uploaded_at,
    )
    print(f"Stamped {count} book(s) for {args.release_tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
