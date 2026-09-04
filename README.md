# Public CRBooks

This repository publishes a curated catalog of **61 English public-domain
Project Gutenberg books** in `.crbook` format. Browse by subject, inspect the
source edition, and download any book directly from the catalog website.

The website is generated into `docs/`; the package archives live outside Git
history as assets on one immutable, versioned GitHub Release. Every Download
button points directly to its matching release asset. `docs/catalog.json`
records the source URL, byte size, and SHA-256 checksum for every archive.

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

The committed `catalogs/catalog.tsv` is the publication allowlist. It contains
exactly 61 records in six collections:

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
CRBOOK_RELEASE_TAG=crbooks-YYYY-MM-DD \
just build

just verify-local
```

`just build` refuses anything other than the exact 61-row English public
catalog, checks every archive against the package manifest, creates a compact
cover thumbnail for every book, and writes release-backed download URLs.

To create the packages from the sibling Close Reading repository first:

```bash
cd ../close_reading
just gutenberg-package \
  --catalog catalogs/gutenberg_crbooks/catalog.tsv \
  --books-root data/books \
  --output-root ../crbooks_public/dist/packages
```

## Publish a release

Use a new immutable tag whenever any package bytes change. With `gh`
authenticated for the public repository:

```bash
CRBOOK_RELEASE_TAG=crbooks-YYYY-MM-DD just release
CRBOOK_RELEASE_TAG=crbooks-YYYY-MM-DD just build
git add docs catalogs
git commit -m "release: publish YYYY-MM-DD catalog"
git push
just verify-release
```

The final command downloads all 61 assets through the exact URLs used by the
site and verifies every byte count and SHA-256 checksum. GitHub Pages is
deployed from the committed `docs/` directory by the included Actions workflow.

## Add a future public-domain book

1. Add and audit the English Project Gutenberg record in the Close Reading
   Gutenberg catalog. Pin its record URL and illustrated EPUB URL.
2. Convert it, run the source/structure audits, ingest it, and complete the
   all-chapter browser crawl there.
3. Copy the revised public allowlist to `catalogs/catalog.tsv` here and update
   `EXPECTED_BOOK_COUNT` in `scripts/build_public_catalog.py`.
4. Repackage the exact public catalog into a clean package directory.
5. Choose a new release tag, rebuild this site, and run `just verify`.
6. Publish the assets, push the generated site, and run `just verify-release`.

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
