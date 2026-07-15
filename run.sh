#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="$ROOT_DIR/build/freedos/freedos.img"
PLAY_DIR="$ROOT_DIR/build/captain-bible"
PLAY_IMAGE="$PLAY_DIR/captain-bible.img"
GAME_DIR="$ROOT_DIR/CB"
GAME_DOS_DIR="CBDOME"
AUTOEXEC="$ROOT_DIR/tools/captain-bible-autoexec.bat"
PARTITION_OFFSET=1048576

rebuild=false
setup_only=false
trace_dos=false

usage() {
    printf '%s\n' \
        'Usage: ./run.sh [--rebuild] [--setup-only] [--trace-dos]' \
        '' \
        '  --rebuild     Recreate the play image from the current CB directory.' \
        '  --setup-only  Prepare images without starting QEMU.' \
        '  --trace-dos   Trace game DOS calls and enable a monitor socket.'
}

while (($#)); do
    case "$1" in
        --rebuild)
            rebuild=true
            ;;
        --setup-only)
            setup_only=true
            ;;
        --trace-dos)
            trace_dos=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        exit 1
    fi
}

clone_sparse() {
    local source=$1
    local destination=$2

    if [[ "$(uname -s)" == Darwin ]]; then
        cp -c "$source" "$destination"
    elif cp --reflink=auto --sparse=always "$source" "$destination" 2>/dev/null; then
        :
    else
        cp "$source" "$destination"
    fi
}

if [[ ! -f "$GAME_DIR/CB.EXE" ]]; then
    printf 'Game executable not found: %s\n' "$GAME_DIR/CB.EXE" >&2
    exit 1
fi

if [[ ! -f "$BASE_IMAGE" ]]; then
    require_command python3
    "$ROOT_DIR/tools/setup_freedos_image.py"
fi

if [[ ! -f "$PLAY_IMAGE" || "$rebuild" == true ]]; then
    for command in mcopy mdir mmd unzip; do
        require_command "$command"
    done

    mkdir -p "$PLAY_DIR"
    temporary_image="$PLAY_IMAGE.tmp"
    package_dir="$PLAY_DIR/package.tmp"
    rm -f "$temporary_image"
    rm -rf "$package_dir"
    trap 'rm -f "$temporary_image"; rm -rf "$package_dir"' EXIT

    printf 'Preparing persistent Captain Bible play image...\n'
    clone_sparse "$BASE_IMAGE" "$temporary_image"
    image_spec="$temporary_image@@$PARTITION_OFFSET"

    if ! mdir -i "$image_spec" "::/$GAME_DOS_DIR" >/dev/null 2>&1; then
        mmd -i "$image_spec" "::/$GAME_DOS_DIR"
    fi
    mcopy -s -o -i "$image_spec" "$GAME_DIR"/* "::/$GAME_DOS_DIR/"

    mkdir -p "$package_dir"
    mcopy -i "$image_spec" ::/packages/base/ctmouse.zip "$package_dir/ctmouse.zip"
    unzip -jo "$package_dir/ctmouse.zip" BIN/CTMOUSE.EXE -d "$package_dir" >/dev/null
    mcopy -o -i "$image_spec" "$package_dir/CTMOUSE.EXE" ::/FREEDOS/BIN/CTMOUSE.EXE

    mcopy -o -t -i "$image_spec" "$AUTOEXEC" ::/AUTOEXEC.BAT
    mcopy -o -t -i "$image_spec" "$AUTOEXEC" ::/FDAUTO.BAT

    mv -f "$temporary_image" "$PLAY_IMAGE"
    rm -rf "$package_dir"
    trap - EXIT
    printf 'Play image ready: %s\n' "$PLAY_IMAGE"
fi

if [[ "$setup_only" == true ]]; then
    exit 0
fi

require_command qemu-system-i386

printf 'QEMU disk: %s\n' "$PLAY_IMAGE"
printf 'Game inside FreeDOS: C:\\%s\\CB.EXE\n' "$GAME_DOS_DIR"

tcg_options=tcg
if [[ "$trace_dos" == true ]]; then
    tcg_options=tcg,one-insn-per-tb=on
fi

qemu_args=(
    -name "Captain Bible"
    -machine pc
    -accel "$tcg_options"
    -cpu pentium
    -m 16
    -boot c
    -drive "file=$PLAY_IMAGE,format=raw,if=ide,index=0,media=disk"
    -vga std
)

if [[ "$trace_dos" == true ]]; then
    trace_dir="$ROOT_DIR/build/qemu-trace"
    trace_plugin="$trace_dir/qemu_dos_trace.so"
    trace_log="$trace_dir/dos-calls.log"
    trace_monitor="$trace_dir/monitor.sock"

    "$ROOT_DIR/tools/build_qemu_dos_trace.sh" "$trace_plugin"
    rm -f "$trace_monitor"
    qemu_args+=(
        -plugin "$trace_plugin,log=$trace_log,cs=0x627,start=0xCB5C"
        -monitor "unix:$trace_monitor,server=on,wait=off"
    )
    printf 'DOS trace: %s\n' "$trace_log"
    printf 'QEMU monitor: %s\n' "$trace_monitor"
fi

if [[ "$(uname -s)" == Darwin ]]; then
    qemu_args+=(
        -audiodev none,id=audio0
        -device sb16,audiodev=audio0
        -device adlib,audiodev=audio0
        -display cocoa,zoom-to-fit=on
    )
else
    qemu_args+=(
        -audiodev none,id=audio0
        -device sb16,audiodev=audio0
        -device adlib,audiodev=audio0
    )
fi

exec qemu-system-i386 "${qemu_args[@]}"
