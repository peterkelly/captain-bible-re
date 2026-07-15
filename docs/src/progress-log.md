# Progress Log

This is an append-only narrative of project actions. Commands are shown as
run from `/Users/peter/ai/captain-bible-re` unless another directory is
specified. Routine documentation edits are described by filename rather than
reproducing the patch payload.

## 2026-07-15

### Initial inventory

Reported to the user that the first pass would be limited to a reproducible
FreeDOS/QEMU setup, a playable `run.sh`, documentation scaffolding, and a boot
and launch check before pausing for their test.

Ran:

```sh
pwd
rg --files -g 'AGENTS.md' -g '!CB/**' -g '!docs/**' | sort
find CB -maxdepth 2 -type f -print | sort | sed -n '1,240p'
command -v qemu-system-i386
qemu-system-i386 --version
command -v qemu-img
qemu-img --version
command -v rizin
rizin -v
command -v mdbook
mdbook --version
```

Results:

- Confirmed the workspace path and the repository-level `AGENTS.md`.
- Found `CB.EXE`, `CB.PIF`, `CB.ICO`, `DD1.DAT`, eight extensionless `DDL*`
  files, ten initial `DDGAMES.SV*` save files, `SOUND.1` through `SOUND.5`,
  `SETSOUND.BAT`, `MANUAL.TXT`, and a large collection of sound drivers.
- Found QEMU 11.0.2, Rizin 0.9.1, and mdBook 0.5.3.

Ran:

```sh
git status --short --branch
du -ah CB | sort -h | tail -40
file CB/CB.EXE CB/CB.PIF CB/CB.ICO CB/DD1.DAT CB/DDLA CB/SOUND.1
sed -n '1,240p' CB/MANUAL.TXT
sed -n '1,160p' CB/SETSOUND.BAT
```

Results:

- The working tree was initially clean on `main`.
- `CB/` occupies approximately 2.7 MB. `DD1.DAT` is approximately 1.8 MB,
  the sound-driver directory is approximately 672 KB, and `CB.EXE` is
  approximately 64 KB.
- The host `file` utility recognizes `CB.EXE` as an MS-DOS executable and
  `CB.PIF` as a Windows Program Information File.
- The manual says the normal DOS launch is `CB` from the installed directory
  and claims a conventional-memory requirement of approximately 500 KiB.
- `SETSOUND.BAT` runs separate digital-audio and MIDI configuration programs,
  then copies the selected driver artifacts to `SOUND.1` through `SOUND.4`.

### FreeDOS source selection

Looked up the official FreeDOS download and installation documentation. The
official site identifies FreeDOS 1.4 as the stable release and recommends the
LiveCD when installing in a virtual machine. It publishes a 20 MB minimum
disk requirement. The official download page links to:

```text
https://download.freedos.org/1.4/FD14-LiveCD.zip
```

The first session was interrupted after this read-only research. No VM or
repository files had been created at that point.

After the user requested that work continue, reported that the completed
actions would be recorded before creating and driving the VM installation.

Ran:

```sh
ls -la
curl -fsSL https://www.freedos.org/download/ \
  | rg -o 'href="[^"]*(FD14|LiveCD|live|verify)[^"]*"' \
  | sed -n '1,120p'
```

Results:

- Confirmed the repository initially tracks `.gitignore`, `AGENTS.md`, and
  `url.txt`; the ignored `CB/` directory contains the supplied game.
- Extracted the official FreeDOS 1.4 LiveCD ZIP URL shown above.

Ran:

```sh
sed -n '1,120p' .gitignore
sed -n '1,120p' url.txt
git log -5 --oneline --decorate
git ls-files
```

Results:

- `.gitignore` already excludes `/CB/` and `/build/`, which is suitable for
  keeping original game files, downloaded media, VM disks, and book output
  out of version control.
- `url.txt` points to an archived copy of the game.
- The repository contains one initial commit on `main`.

### Documentation scaffolding

Created `PLAN.md`, `README.md`, `docs/book.toml`, and the initial sources under
`docs/src/`. The plan separates environment setup, static analysis, dynamic
analysis, game-system research, and final consolidation. Configured mdBook to
write generated HTML to the ignored `build/docs-book/` directory.

### Superseded installer attempt

Downloaded the official FreeDOS 1.4 LiveCD ZIP to
`build/downloads/FD14-LiveCD.zip` and verified it against the official SHA-256
value:

```text
2020ff6bb681967fd6eff8f51ad2e5cd5ab4421165948cef4246e4f7fcaf6339
```

Extracted `FD14LIVE.iso` and observed its SHA-256 as
`c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e6ef2deb0477f81fb`.
Created a sparse 512 MiB QCOW2 disk with:

```sh
mkdir -p build/downloads build/vm build/screenshots
curl -fL --progress-bar \
  https://download.freedos.org/1.4/FD14-LiveCD.zip \
  -o build/downloads/FD14-LiveCD.zip
printf '%s  %s\n' \
  '2020ff6bb681967fd6eff8f51ad2e5cd5ab4421165948cef4246e4f7fcaf6339' \
  'build/downloads/FD14-LiveCD.zip' | shasum -a 256 -c -
unzip -l build/downloads/FD14-LiveCD.zip
unzip -jo build/downloads/FD14-LiveCD.zip FD14LIVE.iso \
  -d build/downloads
shasum -a 256 build/downloads/FD14LIVE.iso
qemu-img create -f qcow2 build/vm/freedos.qcow2 512M
qemu-img info build/vm/freedos.qcow2
```

Started QEMU headlessly with its monitor on standard input, captured screen
dumps, and injected keys through the monitor. Selected the hard-disk installer,
English, partitioned the disk, rebooted, selected the installer again,
formatted the new FAT16 partition, chose a US keyboard and the plain DOS
package set, and began installation. This approach was not completed.

The user then supplied `FREEDOS_SETUP_INSTRUCTIONS.md`, which explicitly
requires a simpler, noninteractive construction method and prohibits driving
the installer. Read that file in full, then read all 321 lines of its reference
implementation at:

```text
/Users/peter/ai/agi/reverse/tools/setup_freedos_image.py
```

Confirmed that `mformat`, `mcopy`, `mmd`, `mdir`, and `mtype` are installed.
Stopped the installer VM through its QEMU monitor with `quit`. Removed only the
superseded generated VM artifacts and installer download:

```sh
rm -rf build/vm build/screenshots
rm -f build/downloads/FD14-LiveCD.zip build/downloads/FD14LIVE.iso
```

### Noninteractive image builder

Created `tools/setup_freedos_image.py`, adapted from the supplied reference
while removing its project-specific imports, game-copy functionality, and
custom VGA BIOS support. The builder:

- accepts every required command-line option;
- downloads through a `.download` path and publishes only a verified archive;
- extracts the largest source image and validates its MBR and boot sector;
- preserves the source MBR boot code while defining the requested partition;
- creates and formats the target atomically through a temporary image;
- copies the complete source filesystem; and
- replaces both boot scripts with the required direct-to-prompt commands.

Created `tests/test_setup_freedos_image.py` with focused checks for the MBR
signature, preserved boot code, active/type/start/count partition fields, CHS
encoding and saturation, and invalid-MBR rejection.

Ran the test and static validation commands:

```sh
chmod +x tools/setup_freedos_image.py
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  tools/setup_freedos_image.py tests/test_setup_freedos_image.py
tools/setup_freedos_image.py --help
git diff --check
```

All nine unit tests passed. The script compiled, exposed all required CLI
options, and the Git whitespace check passed.

### Build and verify the base image

Ran:

```sh
tools/setup_freedos_image.py --print-mtools-image
```

The builder downloaded the prescribed archive, selected `FD14LITE.img`, and
created `build/freedos/freedos.img`. It printed the partition-aware path
`build/freedos/freedos.img@@1048576`.

Ran:

```sh
shasum -a 256 build/downloads/FD14-LiteUSB.zip
stat -f 'logical_size=%z bytes' build/freedos/freedos.img
du -h build/freedos/freedos.img
tools/setup_freedos_image.py --print-mtools-image
mdir -i 'build/freedos/freedos.img@@1048576' ::/
mtype -i 'build/freedos/freedos.img@@1048576' ::/AUTOEXEC.BAT
mtype -i 'build/freedos/freedos.img@@1048576' ::/FDAUTO.BAT
```

Results:

- The archive SHA-256 was exactly
  `857dcd2ebf9d3d094320154db5fb5b830acba6fb98f981a95a0ca7ab3350338b`.
- The raw image's logical size is 1,073,741,824 bytes and its initial physical
  allocation was approximately 37 MiB.
- The root directory contains `KERNEL.SYS`, `COMMAND.COM`, both boot scripts,
  `FDCONFIG.SYS`, and the FreeDOS and package trees.
- Both boot scripts contain the required five lines with DOS CRLF endings.

Used a short standard-library Python inspection to decode the first partition
entry. It found MBR signature `55aa`, active status `80`, type `0e`, first LBA
2048, and 2,095,104 sectors.

### Screenshot-free QEMU boot smoke test

Made a temporary copy-on-write clone of the base disk and replaced both boot
scripts on that clone with the required script plus:

```bat
ECHO FREEDOS_READY>C:\BOOT.OK
```

Confirmed `BOOT.OK` did not exist before boot. Started the clone with:

```sh
qemu-system-i386 \
  -name 'FreeDOS smoke test' \
  -machine pc,accel=tcg \
  -cpu pentium \
  -m 16 \
  -boot c \
  -drive file=build/freedos/freedos-smoke.img,format=raw,if=ide,index=0,media=disk \
  -display none \
  -monitor stdio
```

Allowed five seconds for boot, stopped QEMU through its monitor with `quit`,
then ran:

```sh
mdir -i 'build/freedos/freedos-smoke.img@@1048576' ::/BOOT.OK
mtype -i 'build/freedos/freedos-smoke.img@@1048576' ::/BOOT.OK
```

The marker existed and contained `FREEDOS_READY`. Removed the smoke-test clone
and temporary script afterward. The deliverable base image was never mounted
with mtools while QEMU was running.

### Play-image and QEMU configuration

Inspected QEMU's available display, audio, Sound Blaster 16, AdLib, and machine
options. The Homebrew build supports Cocoa display and CoreAudio, plus ISA
Sound Blaster 16 and AdLib devices. Inspected the manual's controls section;
the game supports mouse input as well as cursor keys, Space, Enter, function
keys, and letter shortcuts.

Inspected the base FreeDOS filesystem and found that CuteMouse was not
installed, but `PACKAGES/BASE/CTMOUSE.ZIP` was present. Copied that archive to
a temporary host directory, listed its members, confirmed
`BIN/CTMOUSE.EXE`, and removed the inspection copy. Ran `strings` against the
supplied sound files and found that `SOUND.1` is configured for Sound Blaster
16 and `SOUND.2` for Sound Blaster Pro FM sound.

Created `tools/captain-bible-autoexec.bat` and `run.sh`. The run script keeps
the verified base disk unchanged and atomically prepares a persistent derived
disk at `build/captain-bible/captain-bible.img`. It copies the game, extracts
and installs CuteMouse, patches both boot paths to run the game, and starts
QEMU with suitable emulated hardware. Added `--setup-only`, `--rebuild`, and
`--help` options.

Ran:

```sh
chmod +x run.sh
bash -n run.sh
./run.sh --help
./run.sh --rebuild --setup-only
```

The first setup attempt failed safely while copying CuteMouse because the
actual LiteUSB system directory is `C:\FREEDOS`, not `C:\FDOS`. The temporary
image cleanup trap ran, so no partial play image was published. Corrected the
derived disk's destination and `PATH` to `C:\FREEDOS`, leaving the base image's
required boot-script text unchanged, then reran the setup successfully.

Verified the resulting play disk with `stat`, `du`, `mdir`, and `mtype`.
`CB.EXE`, `CTMOUSE.EXE`, `AUTOEXEC.BAT`, and `FDAUTO.BAT` were all present;
the clone remained sparse at approximately 42 MiB physical allocation.

### Game launch check

Booted the play image for a bounded launch check with:

```sh
qemu-system-i386 \
  -name 'Captain Bible launch check' \
  -machine pc,accel=tcg \
  -cpu pentium \
  -m 16 \
  -boot c \
  -drive file=build/captain-bible/captain-bible.img,format=raw,if=ide,index=0,media=disk \
  -vga std \
  -audiodev coreaudio,id=audio0 \
  -device sb16,audiodev=audio0 \
  -device adlib,audiodev=audio0 \
  -display none \
  -monitor stdio
```

No device conflicts or QEMU errors occurred. After five seconds, captured one
screen dump solely as visual launch evidence, stopped QEMU with `quit`, and
converted the dump to PNG. It showed the Captain Bible title screen rendered
at 640×400. This visual check was not used to automate FreeDOS setup; the base
boot proof remained the marker-file test described above.

The user then requested that game runs always be visible with
`-display cocoa,zoom-to-fit=on`. Updated `run.sh` to use that exact display
option for macOS game launches and recorded the behavior in the user and book
documentation. Headless QEMU remains limited to the automated base-image boot
smoke test, which does not run the game.

### Final Phase 1 validation

Added Python bytecode/cache patterns to `.gitignore`, because running the unit
tests and compiler creates `__pycache__` directories that are not research
artifacts.

Ran:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  tools/setup_freedos_image.py tests/test_setup_freedos_image.py
bash -n run.sh
./run.sh --setup-only
tools/setup_freedos_image.py --print-mtools-image
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck run.sh
else
  echo 'shellcheck: not installed (skipped)'
fi
mdbook build docs
test -f build/docs-book/index.html
git diff --check
git status --short --branch
git diff --stat
stat -f '%Sp %N' run.sh tools/setup_freedos_image.py
```

Results:

- All nine unit tests passed again.
- Both Python files compiled.
- Bash parsed `run.sh`, and setup-only mode found the prepared images.
- The builder reported the expected partition-aware image path.
- `shellcheck` is not installed, so that optional check was skipped.
- mdBook generated `build/docs-book/index.html` successfully.
- The Git whitespace check passed.
- Both executable scripts have mode `755`.
- The working tree contains the intended new research/setup files and the
  user-provided, untouched `FREEDOS_SETUP_INSTRUCTIONS.md`; no commit was made.

### Handoff

Reported that Phase 1 is ready for the user's interactive test. The handoff
directs them to run `./run.sh`, notes the visible Cocoa zoom-to-fit display and
persistent play image, summarizes the successful base boot marker and title
screen checks, and identifies interactive input, audio, and clean exit as the
remaining user confirmations. Reverse-engineering analysis is paused until the
user says to proceed.

### Phase 1 commit

At the user's request, reviewed the final working-tree status, the ignore-file
change, every new project file, and the complete user-provided
`FREEDOS_SETUP_INSTRUCTIONS.md`. Prepared to stage the full Phase 1 source and
documentation set while leaving all ignored downloads, raw disks, screenshots,
book output, game files, and Python caches out of version control. The commit
uses the repository's required imperative subject and a detailed, wrapped body
that explains the reproducibility and documentation rationale.
