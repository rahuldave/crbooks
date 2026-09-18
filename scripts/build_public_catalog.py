#!/usr/bin/env python3
"""Build a static, release-backed catalog for the public Gutenberg CRBooks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from PIL import Image, ImageOps

ALLOWED_COLLECTIONS = {
    "Gutenberg_Fiction",
    "Gutenberg_Drama_and_Poetry",
    "Gutenberg_Politics_and_Society",
    "Gutenberg_Philosophy_and_Psychology",
    "Gutenberg_Science_and_Nature",
    "Gutenberg_History_and_Memoir",
}
CATALOG_FIELDS = {
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
}


class PublicSpecLinkTreeprocessor(Treeprocessor):
    """Prevent private relative references from becoming broken public links."""

    def run(self, root: Any) -> Any:
        for element in root.iter("a"):
            value = element.get("href")
            if value and not value.startswith(("#", "//")) and not urlparse(value).scheme:
                element.tag = "span"
                element.attrib = {"class": "source-reference"}
        for element in root.iter("img"):
            value = element.get("src")
            if value and not urlparse(value).scheme and not value.startswith("//"):
                raise ValueError(
                    "CRBook spec contains a relative image that is not public-site content"
                )
        return root


class PublicSpecLinkExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        md.treeprocessors.register(
            PublicSpecLinkTreeprocessor(md),
            "public_spec_links",
            0,
        )


@dataclass(frozen=True)
class Book:
    collection_slug: str
    category: str
    gutenberg_id: int
    slug: str
    title: str
    author: str
    language: str
    page_url: str
    epub_url: str
    selection_note: str
    release_tag: str
    uploaded_at: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_catalog(path: Path) -> list[Book]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        if fields != CATALOG_FIELDS:
            raise ValueError(
                f"catalog fields differ: expected={sorted(CATALOG_FIELDS)} actual={sorted(fields)}"
            )
        books = [
            Book(
                collection_slug=row["collection_slug"],
                category=row["category"],
                gutenberg_id=int(row["gutenberg_id"]),
                slug=row["slug"],
                title=row["title"],
                author=row["author"],
                language=row["language"],
                page_url=row["page_url"],
                epub_url=row["epub_url"],
                selection_note=row["selection_note"],
                release_tag=row["release_tag"].strip(),
                uploaded_at=normalize_release_published_at(row["uploaded_at"]),
            )
            for row in reader
        ]

    if not books:
        raise ValueError("catalog does not contain any books")
    if len({book.slug for book in books}) != len(books):
        raise ValueError("catalog has duplicate slugs")
    if len({book.gutenberg_id for book in books}) != len(books):
        raise ValueError("catalog has duplicate Project Gutenberg record IDs")
    invalid_collections = sorted({book.collection_slug for book in books} - ALLOWED_COLLECTIONS)
    if invalid_collections:
        raise ValueError(f"catalog contains non-public collections: {invalid_collections}")
    non_english = [book.slug for book in books if book.language != "en"]
    if non_english:
        raise ValueError(f"catalog contains non-English books: {non_english}")
    for book in books:
        if not book.release_tag:
            raise ValueError(f"catalog release tag is empty for {book.slug}")
        expected_page = f"https://www.gutenberg.org/ebooks/{book.gutenberg_id}"
        if book.page_url != expected_page:
            raise ValueError(f"unexpected Project Gutenberg page URL for {book.slug}")
        if not book.epub_url.startswith(f"{expected_page}."):
            raise ValueError(f"unexpected Project Gutenberg EPUB URL for {book.slug}")
    return books


def load_packages(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise ValueError("package manifest does not contain a packages list")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for package in packages:
        key = (str(package["collection_slug"]), str(package["book_slug"]))
        if key in result:
            raise ValueError(f"duplicate package manifest entry: {key}")
        result[key] = package
    return result


def release_asset_url(repository: str, release_tag: str, asset_name: str) -> str:
    return (
        f"https://github.com/{repository}/releases/download/"
        f"{quote(release_tag, safe='')}/{quote(asset_name, safe='._-')}"
    )


def normalize_release_published_at(value: str) -> str:
    """Validate an ISO-8601 release timestamp and normalize it to UTC seconds."""

    candidate = value.strip()
    if not candidate:
        raise ValueError("release published timestamp is empty")
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        published_at = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise ValueError("release published timestamp must be ISO-8601") from error
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("release published timestamp must include a timezone")
    published_at = published_at.astimezone(UTC).replace(microsecond=0)
    return published_at.isoformat(timespec="seconds").replace("+00:00", "Z")


def format_release_date(value: str) -> str:
    """Return a readable UTC calendar date for a release timestamp."""

    normalized = normalize_release_published_at(value)
    published_at = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return f"{published_at:%B} {published_at.day}, {published_at.year}"


def latest_release(books: list[Book]) -> tuple[str, str]:
    """Return the tag and timestamp for the newest per-book package upload."""

    if not books:
        raise ValueError("catalog does not contain any books")
    latest_uploaded_at = max(book.uploaded_at for book in books)
    latest_release_tags = {
        book.release_tag for book in books if book.uploaded_at == latest_uploaded_at
    }
    if len(latest_release_tags) != 1:
        raise ValueError(
            "books at the latest upload timestamp must share one release tag: "
            f"{sorted(latest_release_tags)}"
        )
    return next(iter(latest_release_tags)), latest_uploaded_at


def copy_cover(book: Book, books_root: Path, covers_root: Path) -> str:
    book_root = books_root / book.collection_slug / book.slug
    metadata_path = book_root / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    cover = metadata.get("cover_image")
    if not isinstance(cover, dict) or not cover.get("path"):
        raise ValueError(f"{book.slug}: metadata does not declare a cover image")
    source = book_root / str(cover["path"])
    if not source.is_file():
        raise ValueError(f"{book.slug}: cover image is missing: {source}")

    covers_root.mkdir(parents=True, exist_ok=True)
    output = covers_root / f"{book.slug}.webp"
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA")
        image.thumbnail((480, 640), Image.Resampling.LANCZOS)
        if image.mode == "RGBA":
            flattened = Image.new("RGB", image.size, "#f2eadb")
            flattened.paste(image, mask=image.getchannel("A"))
            image = flattened
        else:
            image = image.convert("RGB")
        image.save(output, "WEBP", quality=84, method=6)
    return f"covers/{output.name}"


def format_bytes(byte_count: int) -> str:
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    raise AssertionError("unreachable")


def render_card(book: dict[str, Any], index: int) -> str:
    search_text = " ".join(
        [book["title"], book["author"], book["category"], str(book["gutenberg_id"])]
    ).lower()
    loading = "eager" if index < 8 else "lazy"
    uploaded_at = normalize_release_published_at(str(book["uploaded_at"]))
    upload_date = format_release_date(uploaded_at)
    return f"""
      <article class="book-card" data-category="{html.escape(book["collection_slug"])}" data-search="{html.escape(search_text, quote=True)}">
        <div class="cover-wrap">
          <img class="cover" src="{html.escape(book["cover_url"])}" alt="Cover of {html.escape(book["title"])}" loading="{loading}" width="360" height="500">
        </div>
        <div class="book-copy">
          <p class="category-label">{html.escape(book["category"])}</p>
          <h3>{html.escape(book["title"])}</h3>
          <p class="author">{html.escape(book["author"])}</p>
          <p class="upload-date"><span>Uploaded</span> <time datetime="{html.escape(uploaded_at)}">{html.escape(upload_date)}</time></p>
          <div class="card-actions">
            <a class="download" href="{html.escape(book["download_url"])}">Download <span>{html.escape(book["size"])}</span></a>
            <a class="source" href="{html.escape(book["source_url"])}">Project Gutenberg</a>
          </div>
        </div>
      </article>"""


def extract_markdown_title(markdown_text: str) -> tuple[str, str]:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            if not title:
                break
            body = "\n".join([*lines[:index], *lines[index + 1 :]]).lstrip()
            return title, body
    raise ValueError("CRBook spec must contain a level-one Markdown title")


def render_spec(markdown_text: str, *, source_sha256: str) -> str:
    title, markdown_body = extract_markdown_title(markdown_text)
    display_title = title.removeprefix("Spec:").strip()
    converter = Markdown(
        extensions=[
            "extra",
            "sane_lists",
            "toc",
            PublicSpecLinkExtension(),
        ],
        extension_configs={
            "toc": {
                "permalink": "¶",
                "permalink_title": "Permanent link",
            }
        },
    )
    rendered_body = converter.convert(markdown_body)
    toc = converter.toc
    escaped_digest = html.escape(source_sha256)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="The open specification for portable CRBook reading packages.">
  <title>{html.escape(display_title)} · CRBooks</title>
  <link rel="stylesheet" href="../styles.css">
</head>
<body class="spec-page">
  <header class="spec-hero">
    <nav class="topbar" aria-label="Primary">
      <a class="wordmark" href="../">CRBooks</a>
      <div>
        <a href="./" aria-current="page">Format spec</a>
        <a href="../catalog.json">Catalog JSON</a>
        <a href="https://github.com/rahuldave/crbooks">GitHub</a>
      </div>
    </nav>
    <div class="spec-hero-copy">
      <p class="eyebrow">Open format specification</p>
      <h1>{html.escape(display_title)}</h1>
      <p class="spec-lede">The portable, offline package contract used by the Close Reading reader. This page is generated directly from the canonical Markdown in the <code>close_reading</code> repository.</p>
      <div class="spec-actions">
        <a class="spec-action-primary" href="../crbook-spec.md">View source Markdown</a>
        <a href="../">Browse the catalog</a>
      </div>
    </div>
  </header>

  <main class="spec-main">
    <div class="spec-layout">
      <aside class="spec-sidebar">
        <nav class="spec-toc" aria-label="Specification contents">
          <p>On this page</p>
          {toc}
        </nav>
      </aside>
      <article class="spec-content">
        {rendered_body}
      </article>
    </div>
  </main>

  <footer>
    <p>This rendered page and its <a href="../crbook-spec.md">Markdown copy</a> come from the canonical package contract maintained in <code>close_reading</code>.</p>
    <p><a href="../">Browse CRBooks</a> · Source SHA-256 <code>{escaped_digest[:12]}</code></p>
  </footer>
</body>
</html>
"""


def publish_spec(*, source_path: Path, output_root: Path) -> dict[str, str]:
    source_bytes = source_path.read_bytes()
    markdown_text = source_bytes.decode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    markdown_path = output_root / "crbook-spec.md"
    markdown_path.write_bytes(source_bytes)
    spec_root = output_root / "spec"
    spec_root.mkdir(parents=True)
    (spec_root / "index.html").write_text(
        render_spec(
            markdown_text,
            source_sha256=source_sha256,
        ),
        encoding="utf-8",
    )
    return {
        "format": "crbook-package-spec",
        "url": "spec/",
        "markdown_url": "crbook-spec.md",
        "sha256": source_sha256,
    }


def render_index(manifest: dict[str, Any]) -> str:
    books = manifest["books"]
    categories = manifest["categories"]
    release_published_at = normalize_release_published_at(str(manifest["release_published_at"]))
    release_date = format_release_date(release_published_at)
    category_buttons = "\n".join(
        f'<button type="button" data-filter="{html.escape(category["collection_slug"])}">'
        f"{html.escape(category['name'])} <span>{category['book_count']}</span></button>"
        for category in categories
    )
    cards = "\n".join(render_card(book, index) for index, book in enumerate(books))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Download {manifest["book_count"]} validated public-domain books in CRBook format.">
  <title>CRBooks · A public close-reading library</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="hero">
    <nav class="topbar" aria-label="Primary">
      <a class="wordmark" href="./">CRBooks</a>
      <div>
        <a href="spec/">Format spec</a>
        <a href="catalog.json">Catalog JSON</a>
        <a href="https://github.com/{html.escape(manifest["repository"])}">GitHub</a>
      </div>
    </nav>
    <div class="hero-copy">
      <p class="eyebrow">Public-domain editions · Built for close reading</p>
      <h1>Books worth<br><em>reading slowly.</em></h1>
      <p class="lede">A curated library of {manifest["book_count"]} English Project Gutenberg works, packaged for the Close Reading reader. Every download is verified and traceable to its source edition.</p>
      <p class="release-note"><span>Latest package upload</span><time datetime="{html.escape(release_published_at)}">{html.escape(release_date)}</time></p>
    </div>
    <dl class="stats">
      <div><dt>{manifest["book_count"]}</dt><dd>books</dd></div>
      <div><dt>{len(categories)}</dt><dd>collections</dd></div>
      <div><dt>{html.escape(manifest["total_size"])}</dt><dd>total download size</dd></div>
    </dl>
  </header>

  <main>
    <section class="catalog-heading" aria-labelledby="catalog-title">
      <div>
        <p class="eyebrow">The catalog</p>
        <h2 id="catalog-title">Choose a book</h2>
      </div>
      <label class="search">
        <span class="sr-only">Search by title, author, collection, or Gutenberg ID</span>
        <input id="search" type="search" placeholder="Search title or author…" autocomplete="off">
      </label>
    </section>
    <div class="filters" aria-label="Filter by collection">
      <button type="button" class="active" data-filter="all">All <span>{manifest["book_count"]}</span></button>
      {category_buttons}
    </div>
    <p id="result-count" class="result-count" aria-live="polite">Showing all {manifest["book_count"]} books</p>
    <section id="books" class="book-grid" aria-label="Books">
      {cards}
    </section>
    <p id="empty-state" class="empty-state" hidden>No books match that search.</p>
  </main>

  <footer>
    <p>CRBook packages are ZIP-compatible reading bundles described by the open <a href="spec/">format specification</a>. The books are public-domain Project Gutenberg editions; availability and rights may differ outside the United States.</p>
    <p>Release <a href="https://github.com/{html.escape(manifest["repository"])}/releases/tag/{html.escape(manifest["release_tag"])}">{html.escape(manifest["release_tag"])}</a> · Uploaded <time datetime="{html.escape(release_published_at)}">{html.escape(release_date)}</time> · <a href="catalog.json">checksums and metadata</a></p>
  </footer>
  <script src="app.js" defer></script>
</body>
</html>
"""


def build_catalog(
    *,
    catalog_path: Path,
    package_root: Path,
    books_root: Path,
    repository: str,
    output_root: Path,
    site_root: Path,
    spec_source_path: Path,
) -> dict[str, Any]:
    books = load_catalog(catalog_path)
    latest_release_tag, latest_uploaded_at = latest_release(books)
    package_manifest_path = package_root / "manifest.json"
    packages = load_packages(package_manifest_path)
    expected = {(book.collection_slug, book.slug) for book in books}
    actual = set(packages)
    if expected != actual:
        raise ValueError(
            f"package set differs from catalog: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    spec = publish_spec(
        source_path=spec_source_path,
        output_root=output_root,
    )
    covers_root = output_root / "covers"
    public_books: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    total_bytes = 0

    for book in books:
        package = packages[(book.collection_slug, book.slug)]
        package_path = package_root / str(package["path"])
        if not package_path.is_file():
            raise ValueError(f"package is missing: {package_path}")
        byte_count = package_path.stat().st_size
        digest = sha256_file(package_path)
        if byte_count != int(package["bytes"]) or digest != package["sha256"]:
            raise ValueError(f"package manifest does not match archive: {book.slug}")
        asset_name = f"{book.slug}.crbook"
        if asset_name in seen_assets:
            raise ValueError(f"release asset name is not unique: {asset_name}")
        seen_assets.add(asset_name)
        cover_url = copy_cover(book, books_root, covers_root)
        total_bytes += byte_count
        public_books.append(
            {
                "collection_slug": book.collection_slug,
                "category": book.category,
                "gutenberg_id": book.gutenberg_id,
                "slug": book.slug,
                "title": book.title,
                "author": book.author,
                "language": book.language,
                "source_url": book.page_url,
                "source_epub_url": book.epub_url,
                "selection_note": book.selection_note,
                "asset_name": asset_name,
                "release_tag": book.release_tag,
                "uploaded_at": book.uploaded_at,
                "download_url": release_asset_url(repository, book.release_tag, asset_name),
                "bytes": byte_count,
                "size": format_bytes(byte_count),
                "sha256": digest,
                "cover_url": cover_url,
            }
        )

    category_names = {book.collection_slug: book.category for book in books}
    categories = [
        {
            "collection_slug": slug,
            "name": category_names[slug],
            "book_count": sum(book.collection_slug == slug for book in books),
        }
        for slug in category_names
    ]
    manifest = {
        "format": "public-crbook-catalog",
        "version": 2,
        "repository": repository,
        "release_tag": latest_release_tag,
        "release_published_at": latest_uploaded_at,
        "book_count": len(public_books),
        "total_bytes": total_bytes,
        "total_size": format_bytes(total_bytes),
        "spec": spec,
        "categories": categories,
        "books": public_books,
    }
    (output_root / "catalog.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_root / "catalog.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "collection_slug",
                "category",
                "gutenberg_id",
                "slug",
                "title",
                "author",
                "language",
                "source_url",
                "release_tag",
                "uploaded_at",
                "download_url",
                "bytes",
                "sha256",
            ]
        )
        for book in public_books:
            writer.writerow([book[field] for field in writer_fields()])
    (output_root / "index.html").write_text(render_index(manifest), encoding="utf-8")
    shutil.copy2(site_root / "styles.css", output_root / "styles.css")
    shutil.copy2(site_root / "app.js", output_root / "app.js")
    (output_root / ".nojekyll").write_text("", encoding="utf-8")
    return manifest


def writer_fields() -> tuple[str, ...]:
    return (
        "collection_slug",
        "category",
        "gutenberg_id",
        "slug",
        "title",
        "author",
        "language",
        "source_url",
        "release_tag",
        "uploaded_at",
        "download_url",
        "bytes",
        "sha256",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalogs/catalog.tsv"))
    parser.add_argument("--package-root", type=Path, default=Path("dist/packages"))
    parser.add_argument("--books-root", type=Path, required=True)
    parser.add_argument("--repository", default="rahuldave/crbooks")
    parser.add_argument("--output-root", type=Path, default=Path("docs"))
    parser.add_argument("--site-root", type=Path, default=Path("site"))
    parser.add_argument(
        "--spec-source",
        type=Path,
        default=Path("../close_reading/internal_docs/ipad_book_package_spec.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_catalog(
        catalog_path=args.catalog.resolve(),
        package_root=args.package_root.resolve(),
        books_root=args.books_root.resolve(),
        repository=args.repository,
        output_root=args.output_root.resolve(),
        site_root=args.site_root.resolve(),
        spec_source_path=args.spec_source.resolve(),
    )
    print(
        f"Built {manifest['book_count']} books in {len(manifest['categories'])} collections "
        f"({manifest['total_size']}) for {manifest['release_tag']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
