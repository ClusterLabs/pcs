#!/bin/sh

if make --dry-run ruff_lint > /dev/null 2>&1; then
  make ruff_lint
else
  echo "No 'make ruff_lint', skipping..."
fi
