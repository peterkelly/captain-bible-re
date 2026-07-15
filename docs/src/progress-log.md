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

Committed Phase 1 as `30b34c8` with subject
`chore: Add FreeDOS game environment`. Verified afterward that the working tree
was clean and every stored commit-message line was at most 72 characters.

### Copy game into the base disk

The user requested that the game be copied into the disk image. First confirmed
that no QEMU process was running, because mtools must not access an image while
the VM is using it. Inspected both 1 GiB images. The persistent play image
already contained `CB.EXE`, `DD1.DAT`, and the sound-driver tree at `C:\CB`, but
the base `build/freedos/freedos.img` did not.

Copied the complete non-hidden host game tree into the base image and performed
a content-level verification:

```sh
mmd -i 'build/freedos/freedos.img@@1048576' ::/CB
mcopy -s -o -i 'build/freedos/freedos.img@@1048576' CB/* ::/CB/
rm -rf build/copy-verification
mkdir -p build/copy-verification
mcopy -s -i 'build/freedos/freedos.img@@1048576' \
  ::/CB build/copy-verification/
find CB -type f ! -name '.DS_Store' -exec shasum -a 256 {} + \
  | awk '{print $1}' | sort > build/copy-verification/host.sha256
find build/copy-verification/CB -type f -exec shasum -a 256 {} + \
  | awk '{print $1}' | sort > build/copy-verification/image.sha256
cmp build/copy-verification/host.sha256 \
  build/copy-verification/image.sha256
```

Both manifests contained 96 files, and `cmp` found no content differences.
Used `mdir` to confirm `C:\CB\CB.EXE`, `C:\CB\DD1.DAT`, and
`C:\CB\DRIVERS\SBLASTER.COM`, then removed the temporary extracted tree and
manifests. The user can run the base image copy with `CD \CB` and `CB`; the
normal `./run.sh` path still starts the already-populated play image
automatically.

The user then reported that after running `run.sh` they could not see the game
on the hard disk. Confirmed QEMU was stopped and inspected the exact play image
selected by `run.sh`. Its root directory contained `CB`, the directory listing
contained all expected top-level game files, and an extracted `CB.EXE` matched
the host executable's SHA-256
`2b7726ae9cf56e0067533e4bd1c5c76685f1d9855a7d90835850388db7b07ee0`.

Identified a likely path-expectation mismatch: the game manual names the normal
installation directory `C:\CBDOME`, while the initial play image used
`C:\CB`. Updated `run.sh` and its auto-start batch file to use the canonical
`C:\CBDOME` path. Also made image preparation tolerate an already-present
directory and print both the host disk path and guest executable path before
QEMU opens. Planned to rebuild the play disk, copy the canonical directory into
the current base disk, remove the old ambiguous `C:\CB` copies, and verify both
images before the user retries.

Confirmed the host `mdeltree` tool was available and no QEMU process was
running. Created `C:\CBDOME` in the base image, copied the game tree into it,
removed the previous `C:\CB` directory, and rebuilt the play image with:

```sh
mmd -i 'build/freedos/freedos.img@@1048576' ::/CBDOME
mcopy -s -o -i 'build/freedos/freedos.img@@1048576' \
  CB/* ::/CBDOME/
mdeltree -i 'build/freedos/freedos.img@@1048576' ::/CB
./run.sh --rebuild --setup-only
```

Extracted `C:\CBDOME` from each stopped image into temporary host directories.
Compared the sorted SHA-256 content hashes from each image with the host `CB/`
tree using `cmp` and process substitution. All three trees contained 96 files,
and both comparisons succeeded with no differences. `mdir` showed `CBDOME` in
the root and `CBDOME\CB.EXE` in both images. Explicit checks confirmed the old
`C:\CB` directory was absent from both. `mtype` confirmed that the play image's
`FDAUTO.BAT` changes to `C:\CBDOME` and invokes `CB`.

Performed a bounded, visible launch check using the required Cocoa display:

```sh
qemu-system-i386 \
  -name 'Captain Bible corrected path check' \
  -machine pc,accel=tcg \
  -cpu pentium \
  -m 16 \
  -boot c \
  -drive file=build/captain-bible/captain-bible.img,format=raw,if=ide,index=0,media=disk \
  -vga std \
  -audiodev coreaudio,id=audio0 \
  -device sb16,audiodev=audio0 \
  -device adlib,audiodev=audio0 \
  -display cocoa,zoom-to-fit=on \
  -monitor stdio
```

The visible QEMU window reached the Captain Bible title screen from the new
canonical path. Captured one screen dump as evidence, then stopped QEMU cleanly
through its monitor with `quit`. Updated the user documentation to say that
`run.sh` prints the host image and `C:\CBDOME\CB.EXE` guest path before opening
QEMU.

### Canonical game-path commit

At the user's request, reviewed the six modified source and documentation files
and confirmed the changes contain the canonical directory fix, reproducible
image behavior, verification evidence, and updated plan and usage guidance.
Prepared to commit these tracked changes while leaving the corrected generated
disk images and launch-check screenshot ignored.

### Static-analysis scope and initial fingerprint

After the user asked for static disassembly, reported that the pass would
fingerprint the executable, identify packing or overlays before trusting an
entry-point disassembly, and keep generated binaries under ignored `build/`.
The user then explicitly asked that QEMU be used for memory dumps and other
debugging facilities. Adopted that request as permission to use runtime state
to recover and verify the executable, while continuing to derive game logic
from static analysis.

Checked repository state, tracked history, current plans and documentation,
and the installed analysis toolchain with commands including:

```sh
git status --short
git log -3 --oneline
find . -maxdepth 3 -type f | sort
command -v cargo
command -v rizin
command -v qemu-system-i386
sed -n '1,260p' PLAN.md
sed -n '1,260p' docs/src/progress-log.md
```

The tree was clean before this pass. The current history showed commits
`833a81d`, `9ade46a`, and `3a1d2ec`. The earlier log's Phase 1 commit ID was a
transient prior ID; no history-changing command was run during this pass.

Inspected the packed file with `stat`, `file`, `shasum`, `xxd`, `strings`,
`rz-bin`, Rizin, and short read-only standard-library Python decoders. Important
results were:

- `CB.EXE` is 64,299 bytes with SHA-256
  `2b7726ae9cf56e0067533e4bd1c5c76685f1d9855a7d90835850388db7b07ee0`.
- Its timestamp is 1996-12-24 23:32 in the host's `+0700` zone.
- The file is a 16-bit MZ executable with a 512-byte header, no outer
  relocations, and entry `0F79:0010` at file offset `0xF9A0`.
- The packed load module has approximately 7.004 bits/byte of entropy.
- Strings include the 1988 Microsoft run-time banner, game resources and UI
  text, `R6000` run-time errors, and `Packed file is corrupt`.

Decoded the 16-byte structure at file offset `0xF990` and disassembled the
following stub. The `RB` signature, reverse `B0` fill/`B2` copy loop, relocation
restoration, and error string identify Microsoft EXEPACK. Recovered:

```text
real_ip       cb5c
real_cs       0000
exepack_size  019b
real_sp       1388
real_ss       1a40
dest_len      1260 paragraphs
signature     4252 ("RB")
```

Parsed the packed relocation table after the 277-byte stub. It occupies the
final 118 file bytes and contains 43 relocations in the standard 16 grouped
segments. The full offset list is preserved in `executable.md`.

Consulted Microsoft's historical DOS documentation, served by PCjs, for the
documented purpose of LINK `/EXEPACK`, and David Fifield's EXEPACK page and
source for a current independent specification and implementation. Also read
the relevant `exepack.rs` and `exe.rs` source in full around header parsing,
backward decompression, relocation decoding, minimum-allocation adjustment,
MZ serialization, and checksum handling.

### Visible QEMU post-unpack capture

Started the prepared game disk with the user-required visible Cocoa display,
plus a monitor and GDB endpoint:

```sh
qemu-system-i386 \
  -name 'Captain Bible memory capture' \
  -machine pc,accel=tcg \
  -cpu pentium \
  -m 16 \
  -boot c \
  -drive file=build/captain-bible/captain-bible.img,format=raw,if=ide,index=0,media=disk \
  -vga std \
  -audiodev coreaudio,id=audio0 \
  -device sb16,audiodev=audio0 \
  -device adlib,audiodev=audio0 \
  -display cocoa,zoom-to-fit=on \
  -gdb tcp:127.0.0.1:1234 \
  -monitor stdio
```

After the title screen appeared, used the QEMU monitor:

```text
stop
info registers
pmemsave 0 0x100000 build/dumps/title-physical-1m.bin
screendump build/dumps/title-screen.ppm
quit
```

The dump SHA-256 is
`aca64f0013d052a2cd8b8ecb5869b1d71df7cd30f704361f57bfebacfa1d67d5`.
The title-screen state had PSP `0617`, `CS=0627`, `IP=C614`, and
`DS=ES=SS=14E1`. Thus the load module begins at physical `0x6270`, its
relative data segment begins at load offset `0xEBA0` / physical `0x14E10`, and
the current instruction was at physical `0x12884`.

Searched the dump for known strings. The Microsoft run-time banner occurs at
physical `0x14E18`, faith/status strings at `0x15068`, `DD1.DAT` at `0x15220`,
the game title at `0x15456`, and the `R6000` strings near `0x18796`. The packed
stub's corruption message is absent from the reconstructed module, as
expected. Stopped QEMU before performing any disk or host-side file work.

Reported to the user that this capture provides a bridge between the packed
DOS file and static analysis and that the rebuilt module would be checked
against the captured process rather than trusting packed-entry disassembly.

### Independent EXEPACK reconstruction

Built an external implementation under ignored `build/tools/` for an initial
independent result:

```sh
mkdir -p build/tools build/analysis
git clone https://www.bamsoftware.com/git/exepack.git \
  build/tools/exepack-src
git -C build/tools/exepack-src rev-parse HEAD
cargo build --release \
  --manifest-path build/tools/exepack-src/Cargo.toml
build/tools/exepack-src/target/release/exepack -d \
  CB/CB.EXE build/analysis/CB_UNPACKED.EXE
```

The source revision was `f715ed19285565d636e78182fc19df62c0fa64b9`.
The output is a 75,776-byte MZ executable with 75,264 load bytes, 43 ordinary
MZ relocations, entry `0000:CB5C`, and SHA-256
`4875f83d6d2ba9c1cc4f058e351e453010c6a5976e1b15976b676689f9747643`.

Applied the relocations with load segment `0x0627` in a read-only Python
comparison and compared all 75,264 bytes with the QEMU dump. The first
`0x905A` bytes are identical. There are 5,612 differing bytes overall, grouped
primarily in initialized state and BSS; inspection showed strings and tables
loaded by startup. Reported the real entry and this verification result to the
user.

Created `tools/analyze_cb_exe.py` using `apply_patch`. It is a dependency-free
MZ/EXEPACK parser, decompressor, relocation decoder, MZ serializer, checksum
writer, and optional QEMU-memory comparator. Created
`tests/test_analyze_cb_exe.py` with size-field, known-output, and memory-dump
regressions.

The first test run exposed a Python 3.14 `dataclasses` import issue because the
dynamically loaded test module had not been registered in `sys.modules`:

```text
AttributeError: 'NoneType' object has no attribute '__dict__'
```

Registered the test module before executing it, then ran:

```sh
chmod +x tools/analyze_cb_exe.py
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  tools/analyze_cb_exe.py tests/test_analyze_cb_exe.py
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED_PY.EXE \
  --memory-dump build/dumps/title-physical-1m.bin \
  --load-segment 0x627
cmp build/analysis/CB_UNPACKED.EXE \
  build/analysis/CB_UNPACKED_PY.EXE
```

All 12 repository tests passed. `cmp` proved that the local Python
implementation emits exactly the same bytes as the independent Rust tool.

### Rizin first pass and segmented-address correction

Ran Rizin recursively over the unpacked file. An initial attempt to set
`asm.bits=16` through an evaluation variable failed with:

```text
ERROR: use -b argument for setting the arch bits
```

Reran with `-b 16`, saved exploratory output under ignored
`build/analysis/`, and searched for DOS, BIOS video, BIOS keyboard, and mouse
interrupt instructions. Rizin reported approximately 340 candidate functions,
79 `int 21h` sites, 12 `int 10h` sites, three `int 16h` sites, and six
`int 33h` sites. Large false function merges remain around tables and unusual
control flow.

The Microsoft startup at `0xCB5C` pushes three values and calls `0x8A82` before
passing the return value to its exit path. The values are `envp`, `argv`, and
`argc` in right-to-left order, identifying `0x8A82` as `main`.

Corrected an important addressing issue during inspection: Rizin displays
ordinary DS immediates as low linear addresses. Startup loads DS with
load-segment plus `0x0EBA`; therefore `DS:08DA` is load offset `0xF47A`, not
code address `0x08DA`. Used this translation when extracting and correlating
strings.

Inspected `main`, its startup callees, the manual's command-line section, the
string run-time functions, DOS file routines, VGA detection, mouse routines,
the event combiner, text export, and save functions. Commands included Rizin
`pdf`, `pd`, `axt`, `afl`, and `/ad` queries, `ndisasm` around instructions
that Rizin initially rendered as invalid, `xxd`, and read-only Python string
and structure decoders.

Confirmed from implementations that `0xE22C`, `0xE26C`, `0xE29E`, `0xE302`,
`0xE31A`, `0xE772`, and `0xE993` are `strcat`, `strcpy`, `strcmp`, `tolower`,
`toupper`, `puts`, and `chdir`; and that `0xD0C2`, `0xD1AE`, and `0xD1D6` are
`fclose`, `fopen`, and `fread`.

Created `analysis/cb.rz` with the high-confidence names. Its first form used
unsupported evaluation-variable names and incorrect address syntax; the
second form collided with Rizin's existing section flags; and another run
revealed that the two tiny mouse cursor wrappers had not been recognized as
functions. Removed the unsupported settings, used `@ address` syntax, stopped
redefining section flags, and explicitly analyzed the two wrappers before
renaming them. Verified the final script with:

```sh
rizin -q -b 16 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~game; afl~save; afl~libc; fl~str_; q' \
  build/analysis/CB_UNPACKED.EXE
```

The final run completed without an error and listed all intended game, save,
library, and string names.

### Static game-system findings

Reported during the pass that the startup analysis had identified these
paths, then documented the evidence in dedicated book chapters:

- `main` directly implements `-t`, `-bX`, `-c`, `-idirectory`, `-sXfilename`,
  `-gXX`, and the non-option per-player save prefix.
- `0x3363` checks VGA, reads `SOUND.5`, conditionally loads `SOUND.1` through
  `SOUND.4`, opens `DD1.DAT`, and initializes hardware/data subsystems.
- `0x5F92` is the ASCII export routine. Its bit tests match the six documented
  `-gXX` categories.
- `0x7BED` merges keyboard, mouse motion, mouse-button, and UI-hit events.
- `0x8E0A` detects the mouse through `int 33h`; `0x8D79` updates buttons and
  clamps coordinates to 320×200.
- `0x7F58` reads a 243-byte `.SV0` index consisting of nine 27-byte labels.
- `0x7FD7` and `0x81AC` write and read a fixed 2,752-byte state in 15 blocks.
  Every supplied `.SV1` through `.SV9` file has that exact size.
- The quick-save path changes the mutable suffix from `0` to `Q`, identifying
  `.SVQ` as the quick-save state file.

Ran `stat`, SHA-256, `xxd`, and a nine-record decoder on the supplied save
files. The supplied `DDGAMES.SV0` is 243 bytes, each state file is 2,752 bytes,
and the index's visible labels begin with `EMPTY`. The missing-index code uses
the initialized string `(EMPTY)` instead.

Updated `PLAN.md`, `README.md`, the mdBook summary and introduction, and added
`executable.md` and `static-analysis.md`. The new chapters preserve the exact
EXEPACK and QEMU evidence, address convention, command parser, export masks,
save block layout, input path, function map, confidence limits, and commands
for reproducing the analysis.

### Static-pass verification

Reported to the user that the repository now contains the reproducible
EXEPACK/QEMU verifier, regression tests, Rizin symbol map, and mdBook findings,
and that a final consistency pass was in progress.

Ran:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  tools/analyze_cb_exe.py tests/test_analyze_cb_exe.py
bash -n run.sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/dumps/title-physical-1m.bin \
  --load-segment 0x627 \
  > build/analysis/analyzer-report.txt
rizin -q -b 16 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~game; afl~save; afl~libc; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/symbol-check.txt
mdbook build docs
test -f build/docs-book/executable.html
test -f build/docs-book/static-analysis.html
git diff --check
git status --short
git diff --stat
```

Results:

- All 12 tests passed.
- Both analysis Python files compiled and `run.sh` still parsed as Bash.
- The analyzer reproduced the expected executable and QEMU comparison report.
- The Rizin script loaded and printed the intended renamed function groups.
- mdBook 0.5.3 built both new chapters successfully.
- The Git whitespace check passed.
- Generated executable, dump, reports, external source, and book output remain
  ignored under `build/`; only analysis source, tests, and documentation are
  pending in the working tree.

After adding the source link and making a formatting-only Python change,
repeated the tests, compiler check, analyzer comparison, Rizin symbol query,
mdBook build, whitespace check, executable-mode check, status, and source line
counts. All checks passed again; `tools/analyze_cb_exe.py` is mode `755`, and
the five new analysis/source files total 805 lines.

### Static-analysis commit preparation

At the user's request, reviewed the complete static-analysis change set
before committing it. Confirmed that the new analyzer, regression tests,
Rizin symbols, executable notes, static-analysis report, and project status
updates belong to this phase of the investigation. The verification results
above establish the commit as a reproducible analysis baseline.
