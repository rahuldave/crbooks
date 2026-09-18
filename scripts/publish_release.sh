#!/usr/bin/env bash
set -euo pipefail

repository="${1:-rahuldave/crbooks}"
release_tag="${2:-crbooks-$(date +%F)}"
package_root="${3:-dist/packages}"
shift "$(( $# < 3 ? $# : 3 ))"
book_slugs=("$@")

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required." >&2
  exit 1
fi

if [[ "${#book_slugs[@]}" -eq 0 ]]; then
  while IFS= read -r slug; do
    book_slugs+=("$slug")
  done < <(tail -n +2 catalogs/catalog.tsv | cut -f4)
fi

assets=()
declare -A seen_slugs=()
for slug in "${book_slugs[@]}"; do
  if [[ -n "${seen_slugs[$slug]:-}" ]]; then
    echo "Refusing to release duplicate book slug: $slug" >&2
    exit 1
  fi
  seen_slugs[$slug]=1
  matches=()
  while IFS= read -r asset; do
    matches+=("$asset")
  done < <(find "$package_root" -mindepth 2 -maxdepth 2 -type f -name "$slug.crbook" -print)
  if [[ "${#matches[@]}" -ne 1 ]]; then
    echo "Refusing to release $slug: expected one package, found ${#matches[@]}." >&2
    exit 1
  fi
  assets+=("${matches[0]}")
done

if [[ "${#assets[@]}" -eq 0 ]]; then
  echo "Refusing to create an empty release." >&2
  exit 1
fi

gh release create "$release_tag" \
  --repo "$repository" \
  --draft \
  --title "Public CRBooks · ${release_tag#crbooks-}" \
  --notes "${#assets[@]} validated English public-domain Project Gutenberg edition(s) in CRBook format. Checksums, source links, and per-book upload dates are published on the catalog site."

gh release upload "$release_tag" "${assets[@]}" --repo "$repository"
gh release edit "$release_tag" --repo "$repository" --draft=false

published_at="$(
  gh release view "$release_tag" \
    --repo "$repository" \
    --json publishedAt \
    --jq .publishedAt
)"

stamp_args=(
  --catalog catalogs/catalog.tsv
  --release-tag "$release_tag"
  --uploaded-at "$published_at"
)
for slug in "${book_slugs[@]}"; do
  stamp_args+=(--book "$slug")
done
uv run python -m scripts.stamp_release "${stamp_args[@]}"

just build
just verify-local
gh release upload "$release_tag" \
  "docs/catalog.json#catalog.json" \
  "docs/catalog.tsv#catalog.tsv" \
  --repo "$repository"

echo "Uploaded ${#assets[@]} CRBook(s) to https://github.com/$repository/releases/tag/$release_tag"
echo "Only the selected catalog rows were stamped; commit catalogs/catalog.tsv and docs/."
