#!/bin/sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
session_dir=$(mktemp -d /tmp/bfc-session.XXXXXX)
trap 'rm -rf -- "$session_dir"' EXIT
trap 'exit 0' HUP INT TERM
ulimit -c 0
cd "$session_dir"
"$app_dir/build/bfc"
