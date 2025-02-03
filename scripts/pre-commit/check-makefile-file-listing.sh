#!/bin/sh

makefile_list="\
Makefile.am
pcs/Makefile.am
pcs_test/Makefile.am
pcsd/Makefile.am
data/Makefile.am
"

get_mentioned_files() {
  for makefile in $1; do
    [ -n "$makefile" ] || continue
    "$(dirname "$0")"/extract-extra-dist.sh "$makefile"
  done
}

get_unlisted_files() {
  makefiles=$1
  added_files=$2

  mentioned_files=$(get_mentioned_files "$makefiles")

  for file in $added_files; do
    if ! echo "$mentioned_files" |
      grep --quiet --fixed-strings --line-regexp "$file" 2> /dev/null; then
      echo "$file"
    fi
  done
}

git_added="$(git diff --cached --name-only --diff-filter=A)"

if [ -z "$git_added" ]; then
  exit 0
fi

unlisted_files="$(get_unlisted_files "$makefile_list" "$git_added")"

if [ -z "$unlisted_files" ]; then
  exit 0
fi

echo "Warning: The following files are not listed in any Makefile.am:"
echo "$unlisted_files"
exit 1
