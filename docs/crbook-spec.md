# Spec: Portable Book Package

> **Status (2026-09-04): active package contract.** The iPad-specific Files,
> security-scoped URL, type-registration, and import UI requirements are defined
> in
> [`apps/ipad/internal_docs/ipad_app_implementation_spec.md`](../apps/ipad/internal_docs/ipad_app_implementation_spec.md).
> This document remains the source of truth for the `.crbook` archive payload and
> validation contract.
>
> The macOS Part 9 baseline at `d2cb945` proved that imported packages remain
> portable when `book_imports.package_path` stores only the package filename.
> The iPad Files flow must preserve that rule and must never persist a provider,
> staging, simulator, or app-container absolute path.

## Problem Statement

Close Reading needs a portable, offline-importable book format that is useful
outside the current FastAPI server. The current server app ingests generated
book folders from `data/books/<collection>/<book>/` and derives chapters, cells,
locators, hashes, search rows, annotations, AI interactions, and exports in
SQLite. The portable format should preserve the durable source material only:
Markdown, metadata, and local assets.

## Proposed Solution

Use a ZIP archive whose payload is a single Close Reading book folder. The
folder should be compatible with the existing generated and ingested book
folders first; downstream consumers such as the Apple apps can normalize that
data into a stricter internal model after import.

Do not require a new metadata schema before accepting existing converter output.
A valid v1 package is a folder that could live at
`data/books/<collection>/<book_slug>/` after the current conversion/ingestion
pipeline has produced or normalized it.

The preferred file extension for app association is `.crbook`, with contents
identical to a `.zip`. The importer should also accept `.zip` during early
development.

## Scope

### In Scope

- Single-book ZIP/package structure.
- Required and optional files inside the book folder.
- Metadata normalization for existing generated book folders.
- Markdown parsing expectations for generic books and contracts.
- Import validation rules for app, deploy, and package tooling.

### Out of Scope

- Reader notes, highlights, AI interactions, summaries, tags, and exports.
- Multi-user synchronization.
- iCloud sync or cross-device merge semantics.
- Batch collection import, except for a compatible future layout sketch.
- Re-converting EPUB or PDF sources on device.

## Package Layout

Preferred single-book archive payload:

```text
<book_slug>/
  book.md
  metadata.json
  assets/
    <relative image/media paths>
  book.html
  conversion_manifest.json
  README.md
  original_epub/
  original_pdf/
```

This is the same shape used by deployed folders under
`data/books/<Collection>/<book_slug>/`. Some conversion workflows produce a
staging layout of `<collection>/books/<book_slug>/` with collection-level
`manifest.json` and `manifest.tsv`; a v1 single-book package should contain
only the book folder, not the whole staging collection.

The importer should also accept archives where `book.md` is at the archive root:

```text
book.md
metadata.json
assets/
```

Future collection archives may wrap multiple books:

```text
<collection_slug>/
  manifest.json
  manifest.tsv
  books/
    <book_slug>/
      book.md
      metadata.json
      assets/
```

Single-book import is the v1 book-package requirement. Collection import should
be treated as a separate package-set or app-route feature.

## Required Files

`book.md`

- UTF-8 Markdown.
- The durable reading source.
- Local images must use relative links, usually under `assets/`.
- Chapter boundaries are derived by the importer from headings and tables of
  contents, not stored in the package.

`metadata.json`

- UTF-8 JSON object.
- All current converters and normalized ingested folders write this file.
- Required for v1 app packages unless the app is deliberately accepting an
  old hand-authored folder. In that compatibility case, derive title from the
  first nonblank Markdown line and slug from the folder name.

## Optional Files

`assets/`

- Local book media referenced by `book.md`, `book.html`, or
  `metadata.cover_image.path`.
- Paths are relative to the book folder.
- The importer must reject paths that escape the book folder after
  normalization.
- This directory may be absent only when there are no local media references
  and the importer will synthesize cover art during normalization.

`book.html`

- Optional rich rendered source, currently produced by EPUB/PDF converters.
- The app may prefer Markdown rendering for consistency, or use `book.html`
  when a converter preserves layout that Markdown cannot represent well.
- Any referenced media must still be local to the package.

`conversion_manifest.json`

- Optional converter provenance, warnings, counts, source type, and source path
  hints.
- The importer should store this as metadata but must not require it to render
  or parse the book.
- Historical converter manifests may contain original machine paths as
  provenance, such as `source_pdf`. These are not package asset paths. Importers
  must ignore them for rendering and validation unless a field is explicitly
  defined as a package-relative input, such as `source_epub_path`,
  `output_files`, or `referenced_assets`.

`README.md`

- Optional human-readable conversion note.

`original_epub/` and `original_pdf/`

- Optional provenance only.
- Omit from normal app packages unless the user explicitly wants source-file
  traceability; these files are large and not needed for reading.

## Existing Producers

The package contract should track what these current scripts produce:

| Producer | Folder output | Metadata and cover behavior |
| --- | --- | --- |
| `scripts/convert_ebooks.py` | `book.md`, `book.html`, `metadata.json`, `conversion_manifest.json`, `README.md`, `assets/`, `original_epub/` | Writes nested EPUB metadata, `source_epub`, `rootfile`, `spine_count`, `spine_paths`, `assets_count`, and `cover_image`. Cover selection uses the EPUB manifest cover, a scored asset, a front-matter image, or synthetic `assets/generated-cover.svg`. |
| `scripts/convert_manning_epubs.py` | Same core EPUB folder shape | Writes the same core fields plus Manning nav/title-page diagnostics and optional render features. Writes `cover_image`. |
| `scripts/convert_pragprog_epubs.py` | Same core EPUB folder shape | Writes the same core fields plus PragProg nav/title-page diagnostics. Writes `cover_image`. |
| `scripts/split_epub_collection.py` | Same core EPUB folder shape per split component | Writes component metadata and `referenced_assets`, but the splitter itself does not choose `cover_image`. Current ingested split folders may have `cover_image` because ingestion backfilled a synthetic cover. |
| `scripts/convert_pdfs.py` | `book.md`, `book.html`, `metadata.json`, `conversion_manifest.json`, `README.md`, `assets/`, `original_pdf/` | Writes top-level `title`, `creator`, `source_format: "pdf"`, `source_pdf`, nested PDF metadata, and `cover_image`. The conversion manifest uses PDF-specific stats such as `pages`, `chapters`, `images`, and `warnings`, not the EPUB manifest field names. |
| Contract folders plus `scripts/ingest_contracts.py` | Existing contract folders can contain only `book.md`, `metadata.json`, and `assets/` | Contract ingestion uses the same cover backfill path as generic ingestion and parses Article/Section structure instead of generic book chapters. |

`scripts/ingest_books.py` and `scripts/ingest_contracts.py` are normalizers as
well as database importers. They load existing metadata, derive title and author
from either nested EPUB metadata or top-level fields, create
`assets/generated-cover.svg` when no valid cover exists, update
`metadata.json`, and add a cover image to front matter when needed.

## Metadata Contract

The current server accepts both nested EPUB-style metadata and top-level title
fields. The iPad importer should accept those historical shapes and normalize
them into one internal model.

A typical existing EPUB `metadata.json` looks like this:

```json
{
  "source_epub": "source.epub",
  "rootfile": "OEBPS/content.opf",
  "metadata": {
    "title": "Build a Large Language Model (From Scratch)",
    "creator": "Sebastian Raschka",
    "publisher": "Manning Publications Co.",
    "identifier": "urn:isbn:9781633437166",
    "language": "en-us",
    "date": "2024-09-12"
  },
  "assets_count": 154,
  "cover_image": {
    "path": "assets/Images/cover.jpg",
    "source": "epub_manifest",
    "synthetic": false
  }
}
```

A typical existing PDF `metadata.json` uses top-level display fields:

```json
{
  "title": "Data Engineering Design Patterns",
  "creator": "Bartosz Konieczny",
  "source_format": "pdf",
  "source_pdf": "original_pdf/Data-Engineering-Design-Patterns-121525.pdf",
  "metadata": {
    "title": "Data Engineering Design Patterns",
    "creator": "Bartosz Konieczny",
    "pages": "356"
  },
  "cover_image": {
    "path": "assets/cover.jpg",
    "source": "pdf-cover",
    "synthetic": false
  }
}
```

Normalized importer fields:

- Slug comes from the book folder name unless a future `slug` field is present.
- Collection comes from the surrounding import context or user-selected
  destination collection. Current single-book folders do not reliably encode it.
- Display title is `metadata.title`, then top-level `title`, then the first
  nonblank Markdown line, then the folder name.
- Author is `metadata.creator`, then top-level `creator`.
- Source kind is inferred from `source_format`, `source_pdf`, `source_epub`, or
  `conversion_manifest.json`.
- Package metadata paths used as inputs, such as `metadata.source_pdf`,
  `metadata.source_epub` after resolving under `original_epub/`, and
  `metadata.cover_image.path`, must resolve inside the book folder. Original
  machine paths may appear only in converter-provenance fields that the importer
  does not use as package inputs.
- Parser mode defaults to `generic`; use `contract` only when explicitly chosen
  by the import flow or metadata.
- Existing EPUB/PDF/vendor-specific fields such as `rootfile`, `source_epub`,
  `spine_count`, `spine_paths`, `assets_count`, `component`, `render_features`,
  `chapters`, `pages`, `warnings`, and publisher-specific diagnostics should be
  preserved as opaque metadata.

Do not require existing converters to emit `format`, `collection`, `source`, or
`import` wrapper objects. Those may be added by a future `.crbook` packager, but
they are not part of the historical folder contract.

## Cover And Thumbnail Contract

`metadata.cover_image` is the existing cover contract:

```json
{
  "path": "assets/Images/cover.jpg",
  "source": "epub_manifest",
  "synthetic": false
}
```

- `path` is relative to the book folder and should point under `assets/`.
- Known `source` values include `epub_manifest`, `epub_asset`, `front_matter`,
  `synthetic`, and `pdf-cover`.
- `synthetic: true` means the cover was generated as
  `assets/generated-cover.svg`.
- If `cover_image.path` is present, the importer should verify that the file
  exists and is inside the package.
- If `cover_image.path` is missing or invalid, normalize the copied package by
  creating `assets/generated-cover.svg`, updating stored metadata, and ensuring
  the front matter contains a cover image.

There is no separate historical `thumbnail` field. The current web app renders
book-list thumbnails by using `metadata.cover_image.path` in a fixed-size cover
slot. Some EPUBs include files named `thumb.jpg`, `thumbPPC.jpg`, or similar,
but those are ordinary source assets unless `cover_image.path` points at them.

An app may cache resized thumbnails for performance, but those thumbnails are
derived app state and should live outside the portable book package.

## Collection Creation

Collections are not first-class package contents today. They emerge from two
server-side conventions:

- Converter scripts such as `scripts/convert_ebooks.py` and
  `scripts/split_epub_collection.py` write collection-level `manifest.json` and
  `manifest.tsv` beside a `<collection>/books/` folder.
- Ingestion derives `collection_slug` from the root path: if the root folder is
  named `books`, the collection is the parent folder name; otherwise the root
  folder name is used. `scripts/ingest_books.py --collection-slug` can override
  that derived value.

That side effect is enough for the server filesystem workflow, but it is not
enough for the Apple apps. The app needs an explicit collection import route in
the native bridge:

- `library.importBook`: import one book package into a chosen or newly created
  collection.
- `library.importCollection`: import a package-set manifest or collection
  archive, create/update the collection record, then import each member book.

`scripts/package_books.py` writes package-set `manifest.json` and `manifest.tsv`
files under `dist/book_packages/`. Those generated manifests group archives by
collection and are the initial contract for `library.importCollection`.
Packaging can use `--collection-slug` when a package set needs an explicit
collection identity instead of the slug inferred from the source folder.

## Markdown Rules

The current generic parser should remain the default:

- `#`, `##`, and `###` headings are chapter-boundary candidates.
- A Markdown table of contents with internal links can supply chapter titles.
- Numbered chapter headings and appendix/back-matter titles receive structural
  roles during import.
- Block-level cells are derived by blank-line splitting, with special handling
  for fenced code blocks and loose Markdown tables.

Contract/legal documents are the known parser exception:

- Select `contract` when legal Articles or major Sections should become reader
  chapters.
- The importer should not guess contract parsing solely from Markdown text when
  metadata or the import flow supplies a parser choice.

## Derived State

Do not include these in the book package:

- `close_reading.sqlite` or SQLite sidecar files.
- Search index rows.
- AI traces, AI interactions, chapter summaries, prompt presets, tags, notes,
  highlights, annotations, or exports.

Those are reader state, not book source state. A future export/import format for
reader state should be separate from the book package and keyed by content
hashes plus stable cell locators.

## Import Validation

The iPad importer should:

1. Open `.crbook` or `.zip` with a document picker or share target.
2. Reject archives with no `book.md`, multiple unrelated `book.md` roots, or
   unsafe paths such as absolute paths, `..`, and symlinks. Ignore harmless ZIP
   cruft such as `__MACOSX/` and `.DS_Store`.
3. Decode `book.md` as UTF-8 and parse `metadata.json` when present.
4. Normalize slug, title, author, collection slug, cover path, source kind, and
   parser mode.
5. Verify that every local asset referenced by Markdown, HTML, or
   `metadata.cover_image.path` exists. Remote media references should warn
   because the iPad package is intended to be offline-readable.
6. Ensure a valid cover exists, synthesizing `assets/generated-cover.svg` and
   front-matter cover Markdown when needed.
7. Copy the package into the app sandbox using an internal immutable package
   directory keyed by slug plus content hash.
8. Store only the selected package filename as import provenance. Do not store
   the document-picker URL, security-scoped URL, staging URL, simulator path, or
   application-container path in SQLite.
9. Parse chapters and cells using the same logic as the server app or a tested
   port of that logic.
10. Store derived books, chapters, cells, locators, content hashes, and search
   rows in the local iPad database.
11. On slug conflicts, offer Replace, Keep Both, or Cancel. Replace should warn
   that local reader state may detach if chapter/cell hashes changed.

## Executable Checks

`scripts/lint_books.py` is the general executable linter for book folders. Use
it before ingestion, deployment, package generation, and app bundling:

```bash
just lint-books data/books
```

`scripts/package_books.py` runs the same lint contract before writing archives:

```bash
just package-books data/books dist/book_packages crbook
```

The generated `.crbook` files are ZIP files with a branded extension. The
package target also writes `dist/book_packages/manifest.json` and
`dist/book_packages/manifest.tsv` so a future app route can import a collection
or package set explicitly. The target passes extra script flags through after
the extension, for example:

```bash
just package-books sample_collections/gutenberg_tiny/books dist/gutenberg_seed_packages crbook --collection-slug Gutenberg_Tiny
```

`tests/test_ipad_book_package_spec.py` validates the committed Gutenberg sample
books and opportunistically validates the ignored local `data/books` corpus when
it exists. `tests/test_book_package_tools.py` covers the linter and packager
behavior directly. These checks cover required files, UTF-8/JSON readability,
title compatibility, in-bundle cover paths, Markdown/HTML asset references,
split-EPUB `referenced_assets`, the absence of a separate historical thumbnail
metadata field, and current producer variants when the local corpus is present.

## Acceptance Criteria

- A ZIP of any current normalized `data/books/<collection>/<book_slug>/` folder
  with `book.md`, `metadata.json`, and referenced local assets imports without
  server access.
- A ZIP of raw `scripts/split_epub_collection.py` output imports after the app
  synthesizes missing cover metadata.
- The importer preserves relative asset links and never requires absolute local
  paths.
- Import history contains a portable filename, never a Files-provider,
  security-scoped, staging, simulator, or container absolute path.
- `metadata.cover_image.path` drives the book-list thumbnail. No separate
  package thumbnail is required.
- Contract packages can select contract-aware parsing explicitly through import
  UI or metadata.
- Reader-generated state remains outside the book package.
- A future package generator can emit `.crbook` files without changing the
  current server ingestion folder shape.

## Open Questions

- Should `.crbook` be a renamed `.zip` only, or should it eventually require a
  custom UTI and top-level `close-reading-package.json` manifest?
- Should collection import be supported in the first iPad release, or should the
  app only import one book at a time?
- Should `book.html` remain a first-class display source, or should iPad always
  render Markdown and use HTML only as provenance?
- Should a future `.crbook` packager add optional normalized `format`,
  `collection`, `source`, and `import` objects, or should those remain importer
  database fields only?
- Should reader state export/import be designed before the iPad app ships, or
  deferred until after single-device reading works?

## References

- Existing server docs: `docs/ebook-workflows.md`
- Current generic ingester: `scripts/ingest_books.py`
- Current contract ingester: `scripts/ingest_contracts.py`
- Current EPUB converters: `scripts/convert_ebooks.py`,
  `scripts/convert_manning_epubs.py`, `scripts/convert_pragprog_epubs.py`,
  `scripts/split_epub_collection.py`
- Current PDF converter: `scripts/convert_pdfs.py`
- Current parser: `app/splitter.py`
- Current database schema: `app/db.py`
