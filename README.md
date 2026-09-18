# Public CRBooks

This repository currently publishes a curated catalog of **61 English public-domain
Project Gutenberg books** in `.crbook` format. Browse by subject, inspect the
source edition, and download any book directly from the catalog website.

**[Browse and download the public CRBook catalog](https://rahuldave.com/crbooks/)**

**[Read the open CRBook format specification](https://rahuldave.com/crbooks/spec/)**

The website is generated into `docs/`; the package archives live outside Git
history as assets on immutable, versioned GitHub Releases. Every Download
button points directly to its matching release asset. `docs/catalog.json`
records each book's release tag and upload timestamp plus its source URL, byte
size, and SHA-256 checksum. The catalog page displays the latest catalog upload
date near the top and repeats the package upload date on every book card. The
per-book fields leave room for a future catalog to retain multiple immutable
package or SQLite-backed versions without treating every book as if it changed
in the same release.

## Open format specification

The website renders the canonical portable-book package contract from
`close_reading/internal_docs/ipad_book_package_spec.md`. The build publishes a
styled page at `docs/spec/index.html` and an exact Markdown copy at
`docs/crbook-spec.md`; neither generated file is a second hand-maintained
source of truth. Public readers can inspect the generated Markdown directly,
and `docs/catalog.json` records its SHA-256 checksum.

Maintainers with the canonical sibling repository checked out can detect any
divergence between the two repositories explicitly:

```bash
just spec-check
```

`just verify-source` runs the normal repository checks and this cross-repository
comparison together. Override `CRBOOK_SPEC_SOURCE` if the sibling checkout is
not at the default `../close_reading` path.

## Why GitHub Releases, not GitHub Packages?

GitHub Packages provides registries for container images and specific package
manager formats such as npm, RubyGems, Maven/Gradle, and NuGet. `.crbook` is a
standalone ZIP-compatible binary, not one of those package formats. GitHub
Releases is GitHub's documented mechanism for attaching binary files to a
versioned release, so Releases holds the downloads and GitHub Pages provides
the browsable catalog.

- [GitHub: Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub: Linking to releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)
- [GitHub: About GitHub Packages](https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages)
- [GitHub: Configuring a Pages publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## What is included

The committed `catalogs/catalog.tsv` is the publication allowlist and the
current-package ledger. It currently contains 61 records in six collections:

- Fiction
- Drama and Poetry
- Politics and Society
- Philosophy and Psychology
- Science, Nature, and Mathematics
- History and Memoir

The four local `Gutenberg_Tiny` starter books are deliberately excluded, as are
all Manning, O'Reilly, Pragmatic Bookshelf, and other private or commercial
books. No source EPUB or extracted book folder is committed here.

## Build the catalog

This site consumes already-audited CRBook packages from the Close Reading
conversion pipeline. Set paths for the package set and corresponding generated
book folders, then build:

```bash
uv sync --all-groups

CRBOOK_PACKAGE_ROOT=/path/to/packages \
CRBOOK_BOOKS_ROOT=/path/to/data/books \
CRBOOK_SPEC_SOURCE=/path/to/close_reading/internal_docs/ipad_book_package_spec.md \
just build

just verify-local
just spec-check
```

`just build` treats every source-catalog row as an explicit public allowlist
entry, checks the exact package set against those rows, creates a compact cover
thumbnail for every book, and writes each Download URL from that book's own
`release_tag`. Each row also carries its normalized `uploaded_at` timestamp.
The page header is computed as the maximum of those per-book timestamps; a site
rebuild never changes an older book's date merely because other books were
uploaded later.

The release workflow obtains GitHub's authoritative timestamp with:

```bash
gh release view crbooks-YYYY-MM-DD \
  --repo rahuldave/crbooks \
  --json publishedAt \
  --jq .publishedAt
```

To create the packages from the sibling Close Reading repository first:

```bash
cd ../close_reading
just gutenberg-package \
  --catalog catalogs/gutenberg_crbooks/catalog.tsv \
  --books-root data/books \
  --output-root ../crbooks_public/dist/packages
```

## Publish a release

Use a new immutable tag whenever any package bytes change. Name only the books
being uploaded; the release script uploads those packages, obtains GitHub's
actual `publishedAt` timestamp, stamps only their source-catalog rows, rebuilds
and verifies the complete site, and uploads the generated catalog manifests.
Existing book rows and download URLs are left untouched.

With `gh` authenticated for the public repository, an upload containing two
books is:

```bash
CRBOOK_RELEASE_TAG=crbooks-YYYY-MM-DD \
just release first_book_slug second_book_slug
git add docs catalogs
git commit -m "release: publish YYYY-MM-DD catalog"
git push
just verify-release
```

Omit book slugs only for an intentional full-catalog release. The final command
downloads every current asset through its per-book immutable release URL and
verifies every byte count and SHA-256 checksum, even when the catalog spans
several releases. GitHub Pages is deployed from the committed `docs/` directory
by the included Actions workflow.

## Add a future public-domain book

1. Add and audit the English Project Gutenberg record in the Close Reading
   Gutenberg catalog. Pin its record URL and illustrated EPUB URL.
2. Convert it, run the source/structure audits, ingest it, and complete the
   all-chapter browser crawl there.
3. Add its row to `catalogs/catalog.tsv`; leave `release_tag` and `uploaded_at`
   empty until the release command stamps the actual GitHub values.
4. Repackage the exact public catalog into a clean package directory.
5. Choose a new release tag and run `just release` with only the new or changed
   book slugs. For two new books, only those two cards receive the new date.
6. Review and commit the stamped ledger and generated site, push it, then run
   `just verify-release`. The header advances to the newest per-book upload.

The current ledger stores one active immutable package per book. A future
version-history table or immutable SQLite catalog can retain older versions;
the per-book release tag, upload timestamp, SHA-256, and URL already provide the
stable identity needed for that extension.

The full EPUB-to-CRBook conversion, validation, and ingestion guide lives in
the Close Reading repository's `docs/crbook-publishing.md`. That reusable
software and skill packaging will be published separately; this repository is
the public book catalog and download surface.

## Rights

These editions were selected as public-domain Project Gutenberg records in the
United States. Project Gutenberg's trademark and redistribution terms still
apply, and copyright status can differ by country. Each catalog record links to
its exact source page so readers can check the applicable notice.

The repository's MIT license applies to the original catalog software and site
code. It does not replace the notices carried inside the book packages.
