#!/bin/sh

if make --dry-run ruff_format_check > /dev/null 2>&1; then
  make ruff_format_check
else
  echo "No 'make ruff_format_check', skipping..."
fi
