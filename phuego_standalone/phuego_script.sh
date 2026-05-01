#!/usr/bin/env bash

OUTFILE="phuego_full_dump.txt"

rm -f "$OUTFILE"

echo "================ DIRECTORY TREE ================" >> "$OUTFILE"
tree -a -I ".*" >> "$OUTFILE"
echo -e "\n\n" >> "$OUTFILE"

echo "================ FULL PYTHON CODE ==============" >> "$OUTFILE"

# append python files (excluding hidden dirs/files)
find . -type f -name "*.py" ! -path "phuego/.*" | sort | while read file; do
    echo -e "\n\n==================================================================" >> "$OUTFILE"
    echo "FILE: $file" >> "$OUTFILE"
    echo "==================================================================" >> "$OUTFILE"
    echo "" >> "$OUTFILE"
    cat "$file" >> "$OUTFILE"
    echo "" >> "$OUTFILE"
done

echo "Done. Output -> $OUTFILE"
