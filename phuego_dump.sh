#!/usr/bin/env bash
set -euo pipefail

OUT="phuego_web_full_dump.txt"
rm -f "$OUT"

echo "Building dump..."

find . \
  -type d \( \
    -name "__pycache__" -o \
    -name "results" -o \
    -name "databases" -o \
    -name "uploads" -o \
    -name "support_data" -o \
    -name "phuego_standalone" \
  \) -prune \
  -o -type f \( \
    -name "*.py" -o \
    -name "*.js" -o \
    -name "*.html" \
  \) \
  ! -name "._*" \
  ! -name ".DS_Store" \
  -print \
| sort | while read -r file; do
    {
      echo
      echo "############################################################"
      echo "# FILE: $file"
      echo "############################################################"
      echo
      cat "$file"
      echo
    } >> "$OUT"
done

echo "Done → $OUT"
