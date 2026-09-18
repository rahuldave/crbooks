from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from scripts.build_public_catalog import (
    Book,
    format_release_date,
    latest_release,
    load_catalog,
    normalize_release_published_at,
    publish_spec,
    release_asset_url,
    render_index,
    sha256_file,
)
from scripts.stamp_release import stamp_release
from scripts.verify_catalog import verify_catalog


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "collection_slug",
        "category",
        "gutenberg_id",
        "slug",
        "title",
        "author",
        "language",
        "page_url",
        "epub_url",
        "selection_note",
        "release_tag",
        "uploaded_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_release_asset_url_is_versioned_and_direct() -> None:
    assert release_asset_url("rahuldave/crbooks", "crbooks-2026-09-04", "43_jekyll.crbook") == (
        "https://github.com/rahuldave/crbooks/releases/download/crbooks-2026-09-04/43_jekyll.crbook"
    )


def test_release_published_at_is_timezone_aware_and_normalized() -> None:
    assert normalize_release_published_at("2026-09-16T16:45:41-04:00") == "2026-09-16T20:45:41Z"
    assert format_release_date("2026-09-16T20:45:41Z") == "September 16, 2026"
    with pytest.raises(ValueError, match="timezone"):
        normalize_release_published_at("2026-09-16T20:45:41")


def test_catalog_rejects_tiny_and_private_collections(tmp_path: Path) -> None:
    path = tmp_path / "catalog.tsv"
    base = {
        "category": "Fiction",
        "gutenberg_id": "43",
        "slug": "43_jekyll",
        "title": "Jekyll and Hyde",
        "author": "Robert Louis Stevenson",
        "language": "en",
        "page_url": "https://www.gutenberg.org/ebooks/43",
        "epub_url": "https://www.gutenberg.org/ebooks/43.epub3.images",
        "selection_note": "test",
        "release_tag": "crbooks-2026-09-16",
        "uploaded_at": "2026-09-16T20:45:41Z",
    }
    rows = []
    for index in range(61):
        row = dict(base)
        row["gutenberg_id"] = str(1000 + index)
        row["slug"] = f"{1000 + index}_book"
        row["page_url"] = f"https://www.gutenberg.org/ebooks/{1000 + index}"
        row["epub_url"] = f"{row['page_url']}.epub3.images"
        row["collection_slug"] = "Gutenberg_Fiction"
        rows.append(row)
    rows[0]["collection_slug"] = "Gutenberg_Tiny"
    write_catalog(path, rows)

    with pytest.raises(ValueError, match="non-public collections"):
        load_catalog(path)


def test_local_verifier_checks_archive_and_cover(tmp_path: Path) -> None:
    package_root = tmp_path / "packages"
    docs = tmp_path / "docs"
    books = []
    total_bytes = 0
    for index in range(61):
        slug = f"{1000 + index}_book"
        collection = "Gutenberg_Fiction"
        package_dir = package_root / collection
        package_dir.mkdir(parents=True, exist_ok=True)
        package_path = package_dir / f"{slug}.crbook"
        with zipfile.ZipFile(package_path, "w") as archive:
            archive.writestr(f"{slug}/book.md", f"# Book {index}\n")
        cover_path = docs / "covers" / f"{slug}.webp"
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), "red").save(cover_path, "WEBP")
        byte_count = package_path.stat().st_size
        total_bytes += byte_count
        books.append(
            {
                "collection_slug": collection,
                "slug": slug,
                "language": "en",
                "asset_name": package_path.name,
                "bytes": byte_count,
                "sha256": sha256_file(package_path),
                "release_tag": "v1",
                "uploaded_at": "2026-09-16T20:45:41Z",
                "cover_url": f"covers/{slug}.webp",
                "download_url": f"https://github.com/example/crbooks/releases/download/v1/{slug}.crbook",
            }
        )
    docs.mkdir(exist_ok=True)
    spec_markdown = docs / "crbook-spec.md"
    spec_markdown.write_text("# Portable Book Package\n", encoding="utf-8")
    spec_html = docs / "spec" / "index.html"
    spec_html.parent.mkdir()
    spec_html.write_text("<!doctype html><title>Portable Book Package</title>", encoding="utf-8")
    catalog_path = docs / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "repository": "example/crbooks",
                "release_tag": "v1",
                "release_published_at": "2026-09-16T20:45:41Z",
                "book_count": 61,
                "total_bytes": total_bytes,
                "spec": {
                    "url": "spec/",
                    "markdown_url": "crbook-spec.md",
                    "sha256": sha256_file(spec_markdown),
                },
                "books": books,
            }
        ),
        encoding="utf-8",
    )

    assert verify_catalog(catalog_path, package_root) == {
        "books": 61,
        "bytes": total_bytes,
        "errors": 0,
    }

    stale_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    stale_catalog["books"][0]["uploaded_at"] = "2026-10-01T12:00:00Z"
    catalog_path.write_text(json.dumps(stale_catalog), encoding="utf-8")
    with pytest.raises(ValueError, match="not the latest per-book upload"):
        verify_catalog(catalog_path, package_root)


def test_book_model_keeps_source_provenance() -> None:
    book = Book(
        collection_slug="Gutenberg_Science_and_Nature",
        category="Science, Nature, and Mathematics",
        gutenberg_id=33283,
        slug="33283_calculus_made_easy",
        title="Calculus Made Easy",
        author="Silvanus P. Thompson",
        language="en",
        page_url="https://www.gutenberg.org/ebooks/33283",
        epub_url="https://www.gutenberg.org/ebooks/33283.epub3.images",
        selection_note="Accessible classic introduction.",
        release_tag="crbooks-2026-09-16",
        uploaded_at="2026-09-16T20:45:41Z",
    )
    assert book.gutenberg_id == 33283
    assert book.page_url.endswith("/33283")


def test_latest_release_uses_newest_per_book_upload_only() -> None:
    shared = {
        "collection_slug": "Gutenberg_Fiction",
        "category": "Fiction",
        "author": "Author",
        "language": "en",
        "page_url": "https://www.gutenberg.org/ebooks/1",
        "epub_url": "https://www.gutenberg.org/ebooks/1.epub3.images",
        "selection_note": "test",
    }
    older = Book(
        **shared,
        gutenberg_id=1,
        slug="older",
        title="Older",
        release_tag="crbooks-2026-09-16",
        uploaded_at="2026-09-16T20:45:41Z",
    )
    newer = Book(
        **shared,
        gutenberg_id=2,
        slug="newer",
        title="Newer",
        release_tag="crbooks-2026-10-01",
        uploaded_at="2026-10-01T12:00:00Z",
    )

    assert latest_release([older, newer]) == (
        "crbooks-2026-10-01",
        "2026-10-01T12:00:00Z",
    )


def test_stamp_release_updates_only_selected_books(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.tsv"
    base = {
        "collection_slug": "Gutenberg_Fiction",
        "category": "Fiction",
        "author": "Author",
        "language": "en",
        "selection_note": "test",
        "release_tag": "crbooks-2026-09-16",
        "uploaded_at": "2026-09-16T20:45:41Z",
    }
    rows = []
    for gutenberg_id, slug in ((1, "unchanged"), (2, "updated")):
        rows.append(
            {
                **base,
                "gutenberg_id": str(gutenberg_id),
                "slug": slug,
                "title": slug.title(),
                "page_url": f"https://www.gutenberg.org/ebooks/{gutenberg_id}",
                "epub_url": f"https://www.gutenberg.org/ebooks/{gutenberg_id}.epub3.images",
            }
        )
    write_catalog(catalog_path, rows)
    catalog_path.chmod(0o644)
    original_mode = catalog_path.stat().st_mode

    assert (
        stamp_release(
            catalog_path,
            book_slugs={"updated"},
            release_tag="crbooks-2026-10-01",
            uploaded_at="2026-10-01T08:00:00-04:00",
        )
        == 1
    )
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        stamped = {row["slug"]: row for row in csv.DictReader(handle, delimiter="\t")}

    assert stamped["unchanged"]["release_tag"] == "crbooks-2026-09-16"
    assert stamped["unchanged"]["uploaded_at"] == "2026-09-16T20:45:41Z"
    assert stamped["updated"]["release_tag"] == "crbooks-2026-10-01"
    assert stamped["updated"]["uploaded_at"] == "2026-10-01T12:00:00Z"
    assert catalog_path.stat().st_mode == original_mode
    assert b"\r\n" not in catalog_path.read_bytes()


def test_publish_spec_renders_canonical_markdown_without_private_links(tmp_path: Path) -> None:
    source = tmp_path / "package-spec.md"
    source.write_text(
        "# Spec: Portable Book Package\n\n"
        "> Active contract.\n\n"
        "## Layout\n\n"
        "See the [app requirements](../apps/ipad/spec.md).\n\n"
        "The public [project page](https://example.com/crbooks) remains linked.\n\n"
        "| File | Required |\n| --- | --- |\n| `book.md` | yes |\n",
        encoding="utf-8",
    )
    output = tmp_path / "docs"
    output.mkdir()

    metadata = publish_spec(source_path=source, output_root=output)

    rendered = (output / "spec" / "index.html").read_text(encoding="utf-8")
    assert '<a href="./" aria-current="page">Format spec</a>' in rendered
    assert "<h1>Portable Book Package</h1>" in rendered
    assert "<blockquote>" in rendered
    assert "<table>" in rendered
    assert '<span class="source-reference">app requirements</span>' in rendered
    assert 'href="https://example.com/crbooks"' in rendered
    assert (output / "crbook-spec.md").read_bytes() == source.read_bytes()
    assert metadata["sha256"] == sha256_file(source)


def test_publish_spec_rejects_unpublished_relative_images(tmp_path: Path) -> None:
    source = tmp_path / "package-spec.md"
    source.write_text(
        "# Spec: Portable Book Package\n\n![Private diagram](../internal/layout.png)\n",
        encoding="utf-8",
    )
    output = tmp_path / "docs"
    output.mkdir()

    with pytest.raises(ValueError, match="relative image"):
        publish_spec(source_path=source, output_root=output)


def test_catalog_navigation_links_to_format_spec() -> None:
    rendered = render_index(
        {
            "books": [
                {
                    "collection_slug": "Gutenberg_Fiction",
                    "category": "Fiction",
                    "gutenberg_id": 43,
                    "title": "Jekyll and Hyde",
                    "author": "Robert Louis Stevenson",
                    "cover_url": "covers/43_jekyll.webp",
                    "download_url": "https://example.com/43_jekyll.crbook",
                    "source_url": "https://www.gutenberg.org/ebooks/43",
                    "release_tag": "v1",
                    "uploaded_at": "2026-09-16T20:45:41Z",
                    "size": "1.0 MB",
                }
            ],
            "categories": [],
            "book_count": 0,
            "total_size": "0 B",
            "repository": "example/crbooks",
            "release_tag": "v1",
            "release_published_at": "2026-09-16T20:45:41Z",
        }
    )

    assert '<a href="spec/">Format spec</a>' in rendered
    assert '<a href="spec/">format specification</a>' in rendered
    assert (
        '<p class="release-note"><span>Latest package upload</span>'
        '<time datetime="2026-09-16T20:45:41Z">September 16, 2026</time></p>'
    ) in rendered
    assert (
        rendered.count(
            '<p class="upload-date"><span>Uploaded</span> '
            '<time datetime="2026-09-16T20:45:41Z">September 16, 2026</time></p>'
        )
        == 1
    )
