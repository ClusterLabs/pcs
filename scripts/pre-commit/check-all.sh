#!/bin/sh

# Check definition. Multiline string, every line is for one check.
# Format of line is:
# `Check title ./path/relative/to/this/script/check-script.sh`.
# The last space separates title from script path.
check_list="
RUFF LINT CHECK ./check-lint.sh
RUFF FORMAT CHECK ./check-format.sh
MAKEFILE FILE LISTING CHECK ./check-makefile-file-listing.sh
"

extract_title() {
  echo "$1" | awk '{$NF=""; print $0}'
}

extract_command() {
  realpath "$(dirname "$0")"/"$(echo "$1" | awk '{print $NF}')"
}

err_report=""
while IFS= read -r line; do
  [ -n "$line" ] || continue

  check=$(extract_command "$line")

  if ! output=$("$check" 2>&1); then
    err_report="${err_report}$(extract_title "$line") ($check)\n$output\n\n"
  fi
done << EOF
$check_list
EOF

if [ -z "$err_report" ]; then
  exit 0
fi

echo "Warning: some check failed"
printf "%b" "$err_report"

printf "Checks failed. Continue with commit? (c)Continue (a)Abort: " > /dev/tty
IFS= read -r resolution < /dev/tty

case "$resolution" in
  c | C) exit 0 ;;
  a | A)
    echo "Commit aborted."
    exit 1
    ;;
esac

echo "Unknown resolution '$resolution', aborting commit..."
exit 1
