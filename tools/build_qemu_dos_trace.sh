#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT_DIR/tools/qemu_dos_trace.c"
OUTPUT="${1:-$ROOT_DIR/build/qemu-trace/qemu_dos_trace.so}"
CC_BIN="${CC:-cc}"

if ! command -v "$CC_BIN" >/dev/null 2>&1; then
    printf 'C compiler not found: %s\n' "$CC_BIN" >&2
    exit 1
fi
if ! command -v pkg-config >/dev/null 2>&1; then
    printf 'Required command not found: pkg-config\n' >&2
    exit 1
fi

qemu_include="${QEMU_PLUGIN_INCLUDE:-}"
if [[ -z "$qemu_include" ]]; then
    for candidate in /opt/homebrew/include /usr/local/include /usr/include; do
        if [[ -f "$candidate/qemu-plugin.h" ]]; then
            qemu_include=$candidate
            break
        fi
    done
fi
if [[ -z "$qemu_include" || ! -f "$qemu_include/qemu-plugin.h" ]]; then
    printf '%s\n' \
        'qemu-plugin.h not found; set QEMU_PLUGIN_INCLUDE to its directory.' >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

common_flags=(
    -std=c11
    -O2
    -Wall
    -Wextra
    -Wpedantic
    -fvisibility=hidden
    -I"$qemu_include"
)
read -r -a glib_cflags <<< "$(pkg-config --cflags glib-2.0)"
read -r -a glib_libs <<< "$(pkg-config --libs glib-2.0)"

if [[ "$(uname -s)" == Darwin ]]; then
    link_flags=(-bundle -undefined dynamic_lookup)
else
    common_flags+=(-fPIC)
    link_flags=(-shared)
fi

"$CC_BIN" "${common_flags[@]}" "${glib_cflags[@]}" \
    "${link_flags[@]}" "$SOURCE" "${glib_libs[@]}" -o "$OUTPUT"
printf 'QEMU DOS trace plugin: %s\n' "$OUTPUT"
