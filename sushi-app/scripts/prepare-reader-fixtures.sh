#!/bin/sh
# Test fixtures: version-pinned public arXiv papers, not redistributed in git.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
dir=${1:-"$root/tests/fixtures"}
mkdir -p "$dir"
fetch() {
  name=$1 url=$2 expected=$3
  tmp=$(mktemp "$dir/.reader-fixture.XXXXXXXX")
  trap 'rm -f "$tmp"' EXIT HUP INT TERM
  curl -fsSL --max-time 120 "$url" -o "$tmp"
  actual=$(shasum -a 256 "$tmp" | cut -d ' ' -f 1)
  if [ "$actual" != "$expected" ]; then
    printf 'SHA-256 mismatch: %s\n' "$name" >&2
    exit 1
  fi
  mv "$tmp" "$dir/$name"
  trap - EXIT HUP INT TERM
  printf 'Verified %s\n' "$name"
}
fetch reader-attention.pdf https://arxiv.org/pdf/1706.03762v7 bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697
fetch reader-bert.pdf https://arxiv.org/pdf/1810.04805v2 5692a5514787a8c6727b4ff3b726a3385798bc68e12138d1d4af83947e2acf6e
