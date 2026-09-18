set shell := ["bash", "-euo", "pipefail", "-c"]

repo := env_var_or_default("CRBOOK_REPOSITORY", "rahuldave/crbooks")
tag := env_var_or_default("CRBOOK_RELEASE_TAG", "crbooks-2026-09-16")
source_catalog := env_var_or_default("CRBOOK_SOURCE_CATALOG", "catalogs/catalog.tsv")
package_root := env_var_or_default("CRBOOK_PACKAGE_ROOT", "dist/packages")
books_root := env_var_or_default("CRBOOK_BOOKS_ROOT", "../close_reading/data/books")
spec_source := env_var_or_default("CRBOOK_SPEC_SOURCE", "../close_reading/internal_docs/ipad_book_package_spec.md")

setup:
  uv sync --all-groups

build:
  uv run python -m scripts.build_public_catalog \
    --catalog {{source_catalog}} \
    --package-root {{package_root}} \
    --books-root {{books_root}} \
    --spec-source {{spec_source}} \
    --repository {{repo}} \
    --output-root docs

fmt:
  uv run ruff format scripts tests

lint:
  uv run ruff check scripts tests

test:
  uv run pytest

verify-local:
  uv run python -m scripts.verify_catalog \
    --catalog docs/catalog.json \
    --package-root {{package_root}}

# Fail when the published Markdown copy differs from the canonical contract.
spec-check:
  diff -u "{{spec_source}}" docs/crbook-spec.md

verify-release *extra:
  uv run python -m scripts.verify_release --catalog docs/catalog.json {{extra}}

verify: lint test verify-local

# Maintainer verification when the canonical sibling repository is available.
verify-source: verify spec-check

release *books:
  scripts/publish_release.sh {{repo}} {{tag}} {{package_root}} {{books}}
