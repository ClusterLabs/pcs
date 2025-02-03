#!/bin/sh

checks=./scripts/pre-commit/check-all.sh

if [ -x "$checks" ]; then
  "$checks"
fi
