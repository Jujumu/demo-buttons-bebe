#!/usr/bin/env bash
# Enforce the first-party production Python file-size limit.
#
# Usage: bash tools/check_python_file_sizes.sh [scan-root ...]
#
# Each supplied root is scanned recursively. The default is the repository's
# processor, webhook, and kb roots, which makes the guard directly testable
# against one or more isolated fixtures as well.
set -euo pipefail

readonly LIMIT=1000

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
default_root="$(cd "$script_dir/.." && pwd -P)"

if (( $# == 0 )); then
  scan_roots=(
    "$default_root/processor"
    "$default_root/webhook"
    "$default_root/kb"
  )
else
  scan_roots=("$@")
fi

resolved_roots=()
for scan_root in "${scan_roots[@]}"; do
  if [[ ! -d "$scan_root" ]]; then
    echo "python file-size guard failed: required root is missing: $scan_root" >&2
    exit 1
  fi
  if ! resolved_root="$(cd "$scan_root" && pwd -P)"; then
    echo "python file-size guard failed: cannot resolve required root: $scan_root" >&2
    exit 1
  fi
  resolved_roots+=("$resolved_root")
done
scan_roots=("${resolved_roots[@]}")

if ! file_list="$(mktemp "${TMPDIR:-/tmp}/buttons-bebe-python-files.XXXXXXXXXX")"; then
  echo "python file-size guard failed: could not create a temporary file list" >&2
  exit 1
fi
trap 'rm -f "$file_list"' EXIT

# Keep traversal NUL-delimited so spaces, tabs, and newlines in filenames do
# not split a path. Dependency and test trees use conventional basenames;
# generated roots are handled below only at each supplied scan root so a
# production package merely named data/index/cache cannot bypass the guard.
if ! find "${scan_roots[@]}" \
  \( -type d \( \
    -name '.git' -o \
    -name '.venv' -o \
    -name 'venv' -o \
    -name '.env' -o \
    -name 'env' -o \
    -name 'site-packages' -o \
    -name 'node_modules' -o \
    -name '__pycache__' -o \
    -name 'build' -o \
    -name 'dist' -o \
    -name 'tests' -o \
    -name 'test' -o \
    -name '__tests__' \
  \) -prune \) -o \
  \( -type f -name '*.py' \
    ! -name 'test_*.py' \
    ! -name '*_test.py' \
    -print0 \
  \) > "$file_list"; then
  echo "python file-size guard failed: traversal failed" >&2
  exit 1
fi

scanned=0
read_errors=()
offender_paths=()
offender_counts=()

while IFS= read -r -d '' file_path; do
  generated_root=0
  for scan_root in "${scan_roots[@]}"; do
    case "$file_path" in
      "$scan_root"/generated/*|"$scan_root"/index/*|"$scan_root"/cache/*|\
      "$scan_root"/.cache/*|"$scan_root"/lancedb/*|"$scan_root"/.lancedb/*|\
      "$scan_root"/artifacts/*|"$scan_root"/coverage/*|"$scan_root"/htmlcov/*)
        generated_root=1
        break
        ;;
    esac
  done
  if (( generated_root )); then
    continue
  fi

  scanned=$((scanned + 1))
  if ! line_count="$(wc -l < "$file_path")"; then
    read_errors+=("$file_path")
    continue
  fi
  if [[ ! "$line_count" =~ ^[[:space:]]*([0-9]+)[[:space:]]*$ ]]; then
    read_errors+=("$file_path")
    continue
  fi
  line_count="${BASH_REMATCH[1]}"

  if (( line_count > LIMIT )); then
    offender_paths+=("$file_path")
    offender_counts+=("$line_count")
  fi
done < "$file_list"

if (( scanned == 0 )); then
  echo "python file-size guard failed: scanned zero production Python files" >&2
  exit 1
fi

if (( ${#offender_paths[@]} > 0 )); then
  for index in "${!offender_paths[@]}"; do
    printf 'FAIL: %s is %s lines (>%s)\n' \
      "${offender_paths[$index]}" "${offender_counts[$index]}" "$LIMIT" >&2
  done
fi

if (( ${#read_errors[@]} > 0 )); then
  for file_path in "${read_errors[@]}"; do
    printf 'FAIL: could not count lines in %s\n' "$file_path" >&2
  done
fi

if (( ${#offender_paths[@]} > 0 || ${#read_errors[@]} > 0 )); then
  echo "python file-size guard failed: scanned $scanned production Python files" >&2
  exit 1
fi

echo "python file-size guard passed: scanned $scanned production Python files (limit $LIMIT)"
