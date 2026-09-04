#!/usr/bin/env bash
set -euo pipefail

repository="${1:-rahuldave/crbooks}"
release_tag="${2:-crbooks-2026-09-04}"
package_root="${3:-dist/packages}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required." >&2
  exit 1
fi

assets=()
while IFS= read -r asset; do
  assets+=("$asset")
done < <(find "$package_root" -mindepth 2 -maxdepth 2 -type f -name '*.crbook' -print | sort)
if [[ "${#assets[@]}" -ne 61 ]]; then
  echo "Refusing to release: expected 61 .crbook files, found ${#assets[@]}." >&2
  exit 1
fi

for required in docs/catalog.json docs/catalog.tsv; do
  if [[ ! -f "$required" ]]; then
    echo "Refusing to release: missing $required." >&2
    exit 1
  fi
done

gh release create "$release_tag" \
  --repo "$repository" \
  --draft \
  --title "Public CRBooks · ${release_tag#crbooks-}" \
  --notes "61 validated English public-domain Project Gutenberg editions in CRBook format. Checksums and source links are published on the catalog site."

gh release upload "$release_tag" "${assets[@]}" \
  "docs/catalog.json#catalog.json" \
  "docs/catalog.tsv#catalog.tsv" \
  --repo "$repository"

gh release edit "$release_tag" --repo "$repository" --draft=false

echo "Uploaded ${#assets[@]} CRBooks to https://github.com/$repository/releases/tag/$release_tag"
