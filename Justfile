set shell := ["bash", "-euo", "pipefail", "-c"]

repo := env_var_or_default("CRBOOK_REPOSITORY", "rahuldave/crbooks")
tag := env_var_or_default("CRBOOK_RELEASE_TAG", "crbooks-2026-09-04")
source_catalog := env_var_or_default("CRBOOK_SOURCE_CATALOG", "catalogs/catalog.tsv")
package_root := env_var_or_default("CRBOOK_PACKAGE_ROOT", "dist/packages")
books_root := env_var_or_default("CRBOOK_BOOKS_ROOT", "../close_reading/data/books")

setup:
  uv sync --all-groups

build:
  uv run python -m scripts.build_public_catalog \
    --catalog {{source_catalog}} \
    --package-root {{package_root}} \
    --books-root {{books_root}} \
    --repository {{repo}} \
    --release-tag {{tag}} \
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

verify-release *extra:
  uv run python -m scripts.verify_release --catalog docs/catalog.json {{extra}}

verify: lint test verify-local

release:
  scripts/publish_release.sh {{repo}} {{tag}} {{package_root}}
