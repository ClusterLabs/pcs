#!/bin/sh

makefile="$1"
inside_extra_dist=0
files=""

while IFS= read -r line; do
  case "$line" in
    *EXTRA_DIST[[:space:]]*=*)
      inside_extra_dist=1
      files="${line#*=}"
      files="${files%\\}"
      ;;
    *\\)
      [ $inside_extra_dist -eq 1 ] && files="$files ${line%\\}"
      ;;
    *) # the last line in EXTRA_DIST
      [ $inside_extra_dist -eq 1 ] && files="$files $line" && break
      ;;
  esac
done < "$makefile"

# no globing
set -f
# split to arguments
# shellcheck disable=2086
set -- $files
for file in "$@"; do
  printf "%s\n" "${makefile%Makefile.am}$file"
done
