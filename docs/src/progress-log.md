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

## 2026-07-15: Dynamic DOS-call tracing

The user asked to continue after commit `86bb979`. Reported that the next
step would build on the verified EXEPACK/QEMU baseline by capturing a more
useful runtime snapshot and correlating it with the static function map.

Inspected `AGENTS.md`, `PLAN.md`, `README.md`, `run.sh`, the executable and
static-analysis chapters, and the existing files under `build/analysis/` and
`build/dumps/`. Confirmed that the worktree was clean, the current play path
still uses the required visible `-display cocoa,zoom-to-fit=on`, and the title
snapshot is present.

Checked the installed dynamic-analysis interfaces with:

```sh
command -v qemu-system-i386 rizin rz-bin gdb lldb nc socat \
  mtools mcopy mdir
qemu-system-i386 --version
qemu-system-i386 -plugin help
find /opt/homebrew /usr/local -path '*qemu-plugin.h' \
  -o -path '*libexeclog*'
qemu-system-i386 -d help
rg -n 'read_register|read_memory|vcpu_insn_exec' \
  /opt/homebrew/include/qemu-plugin.h
sed -n '1,1260p' /opt/homebrew/include/qemu-plugin.h
```

QEMU 11.0.2 includes plugin API version 6, an installed
`qemu-plugin.h`, instruction callbacks, register access, and physical-memory
reads. The host has LLDB but not GDB. Chose a TCG plugin as the next tracing
method because it can observe each `int 21h` at its exact game address, read
the DOS call registers and pathname from guest memory, and leave `CB.EXE`
unchanged. Added the plugin and trace-capture steps to `PLAN.md`.

The user asked that QEMU remain visible but stop playing audio. Changed the
macOS QEMU audio backend in `run.sh` from `coreaudio` to `none`, while retaining
the emulated Sound Blaster 16 and AdLib devices. This keeps the guest hardware
paths available for analysis without producing host sound. Documented the
behavior in `README.md`; it applies to normal and traced launches.

### Building the TCG tracer

Added `tools/qemu_dos_trace.c`, `tools/build_qemu_dos_trace.sh`, and the
`--trace-dos` option to `run.sh`. The plugin recognizes executed `CD 21`
instructions, reads the i386 register descriptors and guest physical memory,
escapes DOS pathname strings, pairs calls with their returns, and writes an
ignored log under `build/qemu-trace/`. Trace mode also creates a QEMU monitor
socket so screen, memory, and register evidence can be captured while the
Cocoa window remains visible.

Ran:

```sh
chmod +x tools/build_qemu_dos_trace.sh
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/build_qemu_dos_trace.sh
file build/qemu-trace/qemu_dos_trace.so
git diff --check
```

The plugin compiled without warnings as a native arm64 Mach-O bundle. Both
shell scripts parsed successfully and the Git whitespace check passed.

Launched the first visible trace with `./run.sh --trace-dos`. After allowing
FreeDOS and the game to start, inspected `dos-calls.log`, connected to the
monitor socket with `nc -U`, stopped the guest, recorded `info registers`,
used `screendump`, saved the first MiB with `pmemsave`, and quit QEMU. The
first screen capture showed the opening Captain Bible conversation. QEMU had
captured hundreds of paired interrupt sites, but every apparent AH value was
zero.

Compared those sites with Rizin disassembly. For example, load offset
`0x9908` is an `int 21h` immediately after `mov ah,49h`, proving that the
initial zero was a tracing artifact rather than the executed function. Normal
instruction callbacks exposed register state from the translation-block
entry. Added `-accel tcg,one-insn-per-tb=on` for traced runs and moved register
sampling to translation-block entry callbacks. Normal `./run.sh` execution
remains unrestricted.

The one-instruction mode fixed PC and the other argument registers, but QEMU
11.0.2's plugin accessor continued to report only EAX as zero. Tested both
the synchronous-exception callback and retaining the register-descriptor
array for the entire VM lifetime; neither changed EAX. Removed the misleading
AX values from output. The final implementation reads up to 48 preceding code
bytes and derives the DOS function from the nearest `MOV AH,imm8` or
`MOV AX,imm16`. It preserves the directly observed BX, CX, DX, SI, DI, DS,
ES, and returned carry flag, and states the AX limitation in the trace header
and dynamic-analysis chapter.

An early trace also contained calls from a FreeDOS program that temporarily
used segment `0627` before `CB.EXE` loaded. Added the `start=0xCB5C` plugin
option and configured `run.sh` to keep tracing dormant until physical address
`0627:CB5C` executes. The log now begins with the game's real startup calls:
DOS version `30h`, memory resize `4Ah`, interrupt-vector setup, and handle
IOCTL calls.

### Startup trace and memory capture

Repeated the visible, silent QEMU run after each timing/filter correction.
For the final run, polled the log until call 195, then issued these monitor
operations:

```text
stop
info registers
screendump build/qemu-trace/startup-screen.ppm
pmemsave 0 1048576 build/qemu-trace/startup-physical-1m.bin
quit
```

Converted the PPM to PNG with `sips` and visually inspected it. The screen is
the first story narration, beginning “There once was a city far from us in
place and time.” The stopped registers were `CS:IP=0627:C668`,
`DS=ES=SS=14E1`, `FS=0617`, and `GS=04C7`. These segment values reproduce the
earlier title-screen capture.

The final trace has exactly 195 `CALL`/`RET` pairs, no unresolved `fn=FF`
records, and no `CF=1` returns. Function counts include 78 reads, 27 seeks,
16 allocations, 15 IOCTL calls, 11 opens, 10 attribute queries, nine closes,
six resizes, and six frees. Its SHA-256 is
`f8013fb529444c409a6309a5bbc57336d674382f4e20dcde9185a4d67658e3c9`.
The memory dump SHA-256 is
`7fee3fdda30db225711d0db84d1f292efb9b087c4a91deb2e035025cd31bf71e`;
the PNG SHA-256 is
`85a46bbf6345d5cd88393596706ded3daadbbe0ecb9853cdd0bcecf610077c79`.

Ran the existing EXEPACK analyzer against the new memory dump:

```sh
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/qemu-trace/startup-physical-1m.bin \
  --load-segment 0x627 \
  > build/qemu-trace/memory-comparison.txt
```

It again found a `0x905A`-byte identical prefix and 5,612 differing runtime
bytes across the full 75,264-byte load module. This exactly matches the first
title-screen comparison and independently validates the new capture's process
location.

### Runtime file findings

Extracted the path timeline with `rg '^CALL.*arg='`. The trace changes to
`C:\CBDOME`, reads `SOUND.5`, loads `SOUND.1` through `SOUND.4`, probes and
reopens `DD1.DAT`, reads `DDGAMES.SV0`, loads `DDLC` twice, and reads the save
index again before the story introduction. Every recorded path operation has
carry clear.

Correlated the sound calls with `stat`, `xxd`, `file`, `strings`,
`SETSOUND.BAT`, `MANUAL.TXT`, and the disassembly of
`initialize_hardware_and_data`. `SOUND.1` is the configured DIGPAK Sound
Blaster 16 `soundrv.com`; `SOUND.2` is Miles Design `midpak.adv`; `SOUND.3`
is `tmidpak.com`; and `SOUND.4` is `midpak.ad` timbre data. The trace shows
that the generic loader at `0xACDA` measures each file, requests its size
rounded up to a DOS paragraph, reads it, and closes it. The observed
allocations are `012Eh`, `03F9h`, `0340h`, and `00E3h`, exactly matching the
four rounded file sizes.

Disassembly shows that four-byte `SOUND.5` is the installation-lock record,
not a driver selector. Its word at offset 0 controls the Bible translation;
byte 2 forces no-mature mode unless it is `DBh`; byte 3 is ORed into the
no-combat flag. The supplied `01 00 00 00` selects translation value 1,
forces no-mature mode, and leaves combat unrestricted. This behavior also
explains how the installation locks combine with `-b`, `-t`, and `-c`.

The trace opens `DD1.DAT` as persistent DOS handle 5, then seeks and reads
resources through that handle. It never opens the static `RUN.ART` name as a
DOS path, establishing that names used by `load_art_resource` are members of
the `DD1.DAT` container. `DDLC` is different: it is opened directly twice.

### Inventory and documentation

Ran `stat`, `shasum -a 256`, and `file` over every supplied file except host
`.DS_Store`. All distributed files share timestamp
`1996-12-24 23:32:00 +0700`. Recorded every size and SHA-256 in the new file
inventory chapter. Noted that `file`'s “Arhangel archive” guess for `DDLE` is
only a heuristic and that `DDGAMES.SV6` and `DDGAMES.SV8` are byte-identical.

Added `dynamic-analysis.md` and `file-inventory.md`, updated the mdBook
summary and introduction, expanded the static-analysis sound findings,
documented `--trace-dos` in `README.md`, and marked the inventory and startup
trace tasks complete in `PLAN.md`. Added high-confidence Rizin names for the
far-memory file loader and Microsoft C low-level open, read, write, seek, and
close routines.

### Dynamic-pass verification

Ran:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  tools/analyze_cb_exe.py tests/test_analyze_cb_exe.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/build_qemu_dos_trace.sh
./run.sh --help
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~lowio; afl~far_memory; q' \
  build/analysis/CB_UNPACKED.EXE
mdbook build docs
test -f build/docs-book/dynamic-analysis.html
test -f build/docs-book/file-inventory.html
git diff --check
git status --short
git diff --stat
```

All 12 Python tests passed, both Python analysis files compiled, both shell
scripts parsed, and the C plugin rebuilt without compiler warnings. The
launcher help exposes `--trace-dos`; Rizin loaded all five low-level I/O names
and `load_file_into_far_memory`; mdBook 0.5.3 built both new chapters; and the
Git whitespace check passed. Generated plugins, traces, screenshots, memory
dumps, reports, and book output remain ignored under `build/`.

## 2026-07-15: `DD1.DAT` resource format

After verifying the dynamic pass, reported that work would continue into the
main resource container rather than stop at the trace. Chose `DD1.DAT` because
QEMU established it as the persistent handle used for named resource seeks,
while static analysis identified `load_art_resource` and the member name
`RUN.ART`. Added explicit directory-recovery and extractor tasks to `PLAN.md`.

### Directory reconstruction

Inspected the beginning and end of the archive, searched its strings, compared
QEMU's handle-5 seeks with archive offsets, and disassembled the code around
the resource loader. The investigation used `xxd`, `strings`, `rg`, Rizin, and
small read-only Python parsers. Representative commands were:

```sh
stat -f 'size=%z bytes' CB/DD1.DAT
shasum -a 256 CB/DD1.DAT
xxd -g 1 -l 512 CB/DD1.DAT
xxd -g 1 -s -256 CB/DD1.DAT
strings -a -t x CB/DD1.DAT | head
rg 'RUN\.ART|LOGO\.BIN' build/qemu-trace/dos-calls.log
rizin -q -b 16 -a x86 -e scr.color=false \
  build/analysis/CB_UNPACKED.EXE
```

The first word is `0x0171`, or 369. Parsing the following bytes as 24-byte
records produced printable names, markers 0 or 1, monotonic offsets, expanded
sizes, and stored sizes. The implied directory length,
`2 + 369 * 24 = 0x229A`, is exactly the first payload offset. A Python
invariant pass confirmed that every payload begins at the preceding payload's
end and that the last ends at file size `0x1C7954`. All 369 payloads begin
with `GC`.

Correlated individual records with runtime and static evidence. Directory
index 1 is `LOGO.BIN`, offset `0x24DA`, stored size 431, and expanded size
640. Those are the same seek and size values in the QEMU startup trace.
Index 82 is `RUN.ART`, offset `0x6F69C`, stored size 16,138, and expanded size
53,213. This establishes the static `RUN.ART` string as a container member,
consistent with the absence of a DOS pathname open.

Counted 38 marker-0 records and 331 marker-1 records. Marker 0 always has
`stored_size = expanded_size + 2`, identifying it as an uncompressed body
after `GC`. The extension counts are 143 `ART`, 62 `BIN`, 41 `ABT`, 37 `PAL`,
33 without extensions, 32 `XMI`, and 21 `MAP`. The three duplicate names are
`GANTRY.PAL`, `HOLEA.ART`, and `NG`.

### Loader and compression disassembly

Followed calls from the art loader and saved a focused disassembly with:

```sh
rizin -q -b 16 -a x86 -e scr.color=false -e asm.bytes=false \
  -i analysis/cb.rz \
  -c 's 0x97d0; pdf; s 0x99ab; pdf; s 0x9bef; pdf; \
s 0x9ca4; pdf; s 0x9d98; pdf; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/dd1-functions.txt
```

The routine at `0x99AB` mutates the requested name to uppercase, splits it at
the dot, scans the memory-resident directory in `0x18`-byte increments, seeks
to the record's 32-bit offset, reads two bytes, and compares them with little-
endian word `0x4347` (`GC`). The caller at `0x97D0` branches on the record
marker: `0x9BEF` copies raw data and `0x9CA4` expands compressed data.
`0x9C5F` refills the input buffer, while `0x9D98` recursively walks the
decoder's prefix table and writes suffix bytes.

Reconstructed the compressed code stream in a temporary Python decoder. The
format uses literal roots 0 through 255 and grows through code `0x1000`. For
each group of eight codes, it puts one to four bytes containing the high-bit
planes before the eight low bytes. Each plane byte is consumed least-
significant bit first across the group. When the counter reaches `0x1001`,
the decoder begins a new dictionary pass with a literal; there is no clear
code in the stream.

The first temporary implementation expanded all 331 compressed members to
their declared lengths and consumed every stored byte. That established the
bit-plane boundaries but was not yet sufficient evidence that every output
byte matched the executable's prefix/suffix update order.

### Reproducible extractor

Added executable `tools/extract_dd1.py` and
`tests/test_extract_dd1.py`. The tool validates the complete directory and
payload layout, lists members, extracts by unique name or numeric index, and
extracts every member with an index prefix so duplicates cannot overwrite one
another. It checks compressed stream bounds and exact consumption in addition
to expanded size.

The first tool check ran:

```sh
git status --short
chmod +x tools/extract_dd1.py
python3 -m py_compile tools/extract_dd1.py tests/test_extract_dd1.py
python3 -m unittest -v tests.test_extract_dd1
```

Three structural tests and the all-members length test passed. The initial
`RUN.ART` checksum fixture failed because it had not been independently tied
to the newly written decoder. Extracted `RUN.ART` and `LOGO.BIN`, inspected
their first 64 bytes, then exercised the all-members mode and computed archive
statistics:

```sh
mkdir -p build/dd1
tools/extract_dd1.py --extract RUN.ART \
  --output build/dd1/RUN.ART CB/DD1.DAT
tools/extract_dd1.py --extract LOGO.BIN \
  --output build/dd1/LOGO.BIN CB/DD1.DAT
shasum -a 256 build/dd1/RUN.ART build/dd1/LOGO.BIN
wc -c build/dd1/RUN.ART build/dd1/LOGO.BIN
xxd -l 64 build/dd1/RUN.ART
xxd -l 64 build/dd1/LOGO.BIN
rm -rf build/dd1/all
tools/extract_dd1.py --extract-all build/dd1/all CB/DD1.DAT
find build/dd1/all -type f | wc -l
du -sh build/dd1/all
```

All 369 files were present. Raw entries contain 203,303 expanded bytes and
203,379 stored bytes; compressed entries contain 5,340,520 expanded bytes and
1,653,831 stored bytes. Total expanded content is 5,543,823 bytes. A separate
checksum and `cmp` pass established that both instances of each of the three
duplicate names have identical content.

Re-read the decoder instructions one by one before accepting those bytes. At
`0x9CF8`, the first literal becomes prefix entry `0x100`. Before each later
expansion, `0x9D87` saves the current code at prefix index `BP`, while the leaf
case at `0x9DDE` writes the phrase's first byte at suffix index `BP - 1`.
This offset is essential to the usual LZW case where a code refers to the
entry currently being completed. The temporary/tool implementation had put
that suffix at `BP`; output lengths and stream consumption could not reveal
the error.

Reported this correction immediately, wrote a second inline decoder matching
the assembly order, and compared it byte-for-byte with the first output. The
first difference was byte 10 of `LOGO.BIN` and byte 24 of `RUN.ART`. The exact
decoder still expanded all 369 records to the declared sizes and consumed all
stored input. Corrected `decode_gc_dictionary`, added fixed checksums for both
resources, and reran:

```sh
python3 -m py_compile tools/extract_dd1.py tests/test_extract_dd1.py
python3 -m unittest -v tests.test_extract_dd1
rm -rf build/dd1/all
tools/extract_dd1.py --extract-all build/dd1/all CB/DD1.DAT
tools/extract_dd1.py --extract RUN.ART \
  --output build/dd1/RUN.ART CB/DD1.DAT
tools/extract_dd1.py --extract LOGO.BIN \
  --output build/dd1/LOGO.BIN CB/DD1.DAT
shasum -a 256 build/dd1/RUN.ART build/dd1/LOGO.BIN
wc -c build/dd1/RUN.ART build/dd1/LOGO.BIN
xxd -l 64 build/dd1/RUN.ART
xxd -l 64 build/dd1/LOGO.BIN
find build/dd1/all -type f | wc -l
```

All five focused tests passed. The final `RUN.ART` output is 53,213 bytes with
SHA-256
`c4b00d2e31e9dec81cc419dc577086b143a546a4a0b618dbe5600df4e5fd4ac0`;
`LOGO.BIN` is 640 bytes with SHA-256
`8580d3ff93c6e775aa71334c50762ffde2b1f42a320ee362f5608bd8cbc51424`.

Added the dedicated `DD1.DAT` book chapter, extractor usage to `README.md`,
the six archive functions to `analysis/cb.rz` and the static function map, and
marked directory recovery and extractor implementation complete in
`PLAN.md`. Reported that the extractor had passed the full container and that
the recovered format was being made reproducible in the documentation.

### DD1 and dynamic-pass verification

Ran the complete repository checks after the extractor and documentation
changes:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/build_qemu_dos_trace.sh
./run.sh --help
tools/extract_dd1.py --list CB/DD1.DAT > build/dd1/list.txt
test "$(wc -l < build/dd1/list.txt | tr -d ' ')" = 370
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/qemu-trace/startup-physical-1m.bin \
  --load-segment 0x627 \
  > build/dd1/analyzer-check.txt
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~archive_; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/dd1/symbol-check.txt
mdbook build docs
test -f build/docs-book/dd1-container.html
git diff --check
git status --short
git diff --stat
```

All 17 tests passed, all Python sources compiled, both shell scripts parsed,
and the QEMU plugin rebuilt without warnings. The list has one heading plus
369 records. The EXEPACK analyzer again reported the verified load module,
`0x905A`-byte identical memory prefix, and 5,612 dynamic differences. Rizin
loaded all six archive names at their intended offsets. mdBook generated the
new chapter, and the Git whitespace check passed. All generated extraction,
analysis, trace, and book artifacts remain under ignored `build/`; no commit
was requested or made.

After adding that verification record, rebuilt the book once more, checked
tracked and untracked source files for whitespace errors, and confirmed that
`run.sh`, `tools/build_qemu_dos_trace.sh`, and `tools/extract_dd1.py` all retain
executable mode. The final checks passed.

## 2026-07-15: Dynamic-analysis commit preparation

The user requested a commit. Reviewed the complete tracked and untracked
change set to ensure it contains only the visible/silent QEMU launcher, DOS
tracer, startup evidence and inventory, `DD1.DAT` extractor and tests, symbol
map additions, book chapters, and associated plan, README, and progress-log
updates. Generated traces, dumps, extracted resources, plugin binaries, and
rendered documentation remain ignored under `build/`.

Repeated the pre-commit verification with:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/build_qemu_dos_trace.sh
./run.sh --help
rm -rf build/dd1/commit-check
tools/extract_dd1.py --extract-all build/dd1/commit-check CB/DD1.DAT
test "$(find build/dd1/commit-check -type f | wc -l | tr -d ' ')" = 369
tools/analyze_cb_exe.py CB/CB.EXE \
  --output build/analysis/CB_UNPACKED.EXE \
  --memory-dump build/qemu-trace/startup-physical-1m.bin \
  --load-segment 0x627 \
  > build/dd1/commit-analyzer-check.txt
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~archive_; afl~lowio_; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/dd1/commit-symbol-check.txt
mdbook build docs
test -f build/docs-book/dynamic-analysis.html
test -f build/docs-book/file-inventory.html
test -f build/docs-book/dd1-container.html
git diff --check
```

All 17 unit tests passed, all Python files compiled, both shell scripts parsed,
the QEMU plugin rebuilt without warnings, and the launcher exposed trace mode.
The extractor produced exactly 369 outputs. The analyzer reproduced the
verified executable and memory comparison, Rizin loaded all archive and
low-level I/O names, mdBook rendered the three new chapters, and the Git
whitespace check passed. Prepared one commit with an imperative subject and a
detailed, 72-column-wrapped explanation of the tracing and extraction work.

## 2026-07-15: Palette and artwork format analysis

After commit `7354291`, the user asked to continue. Reported that the next
Phase 4 milestone would recover the palette and artwork formats, correlate
their extracted bytes with rendering code and the captured QEMU screen, and
add a reproducible decoder when supported by the evidence. Added explicit
palette/artwork recovery and rendering-tool tasks to `PLAN.md`.

Confirmed the worktree was clean, reviewed the current plan and latest log,
and verified that the ignored `build/dd1/all/` extraction still contains all
369 members. No source files were changed before the two new plan tasks and
this log entry.

### Resource population and descriptor inference

Used a read-only Python inventory over the extracted resources to group files
by extension, count sizes, print leading bytes, and interpret initial words.
All 37 `PAL` members are exactly 768 bytes. All their values are at most 63,
which is the six-bit VGA DAC component range. `ART` sizes range from 201 to
64,041 bytes and their leading words form plausible positions and dimensions.

The first `ART` hypothesis came from `BOSS2.ART`: its first six values are X
180, Y 44, width 31, height 4, and 32-bit offset 60. The next pixel offset is
184, exactly `60 + 31 * 4`. `LOGO.ART` begins with offset 72, indicating six
12-byte records. Wrote a temporary parser treating each record as signed X/Y,
unsigned width/height, and a 32-bit offset, then checked all 143 members:

```sh
python3 - <<'PY'
# Parse every *_*.ART as repeated struct '<hhHHI'.
# Require first_offset % 12 == 0, contiguous width*height pixel bodies,
# and final offset == file size.
PY
```

Every resource passed with no exceptions. The population contains 1,178
frames and 4,850,699 pixel bytes. Frame counts range from one to 63; the
63-frame file is `MAP.ART`. Eleven files contain a full `(0, 0, 320, 200)`
frame. Negative signed origins occur frequently, including `RUN.ART` frame 0
at `(-28, -5)` with dimensions 46×61, showing that they are relative sprite
anchors rather than always screen coordinates.

Counted content identities with SHA-256. The 37 palettes represent 35 unique
payloads: the two `GANTRY.PAL` entries match, and `RICH.PAL` matches `1.PAL`.
The 143 artwork members represent 142 unique payloads because the two
`HOLEA.ART` entries match.

Inspected `LOGO.BIN`, `INTRO.BIN`, `TITLE.BIN`, `MENU.BIN`, and `DOME.BIN`
with `strings -a -t x` to see how scripts refer to artwork and other assets.
The first guessed numeric paths for `MENU.BIN` and `DOME.BIN` did not exist;
used `find` to obtain their actual indices 326 and 330, then repeated the
inspection. Strings such as `MTITLE` are command plus music names, not an
embedded palette declaration, so palette pairing required program and runtime
evidence.

### Graphics disassembly

Saved focused Rizin listings for the art loader, descriptor users, low-level
blitters, palette functions, and palette-effect loop:

```sh
rizin -q -b 16 -a x86 -e scr.color=false -e asm.bytes=false \
  -i analysis/cb.rz \
  -c 's 0xb818; pdf; axt; s 0xb7ea; pdf; \
s 0xb8f0; pd 260; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/art-functions.txt

rizin -q -b 16 -a x86 -e scr.color=false -e asm.bytes=false \
  -i analysis/cb.rz \
  -c 's 0xa0c9; pdf; s 0xb99c; af; pdf; /ad/ out; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/graphics-functions.txt

rizin -q -b 16 -a x86 -e scr.color=false -e asm.bytes=false \
  -i analysis/cb.rz \
  -c 's 0x9f80; pd 240; q' \
  build/analysis/CB_UNPACKED.EXE

rizin -q -b 16 -a x86 -e scr.color=false -e asm.bytes=false \
  -i analysis/cb.rz \
  -c 's 0xc000; pdf; s 0xbf88; pdf; s 0xb620; pdf; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/art-rendering.txt
```

At `0xB99C`, the requested frame index is multiplied by 12. The routine reads
width from descriptor offset 4, height from 6, and the 32-bit pixel offset
from 8 before copying rows to VGA memory. `0xA0C9` uses destination stride 320
and segment `A000h`. `0xA106` explicitly skips source byte 0, while `0xA136`
copies every pixel, proving that transparency is a draw-call choice rather
than a descriptor bit.

Palette code provides a similarly direct match. `0xA017` invokes BIOS video
function `1012h` for all 256 entries. `0xA032` synchronizes through status port
`03DAh`, writes the starting index to `03C8h`, and sends raw RGB triplets to
`03C9h`. `0xB620` computes bounded component changes and submits a palette
range, accounting for fades and palette cycling.

### Prototype rendering and captured-screen checks

Confirmed Pillow 12.3.0 is installed. Wrote an ignored, inline prototype to
parse the descriptors, expand six-bit components, and render `LOGO`, `INTRO`,
`TITLE`, `DOME`, `BOSS`, and `MENU` under `build/graphics/`. The first version
created a mask with `P`-mode `Image.point`; Pillow remapped palette indices
while producing that mask, so its colors were visibly wrong. Checked source
and saved pixels, found that source index 33 had become index 21, and replaced
the mask with an explicit `L` image containing byte 255 for nonzero pixels.
The corrected renders show the Bridgestone logo, opening story, title screen,
dome landscape, boss screen, and menu artwork with the expected geometry and
colors.

Used the QEMU startup screenshot and `INTRO.ART` pixels to derive the dominant
runtime RGB value for each of the 39 indices used on that screen. Static
entries match `TITLE.PAL` closely; indices 243 through 254 differ because the
text range is being color-cycled. This also explained why a base-palette
preview need not match the exact text shade at the capture instant.

Performed a stronger comparison that does not depend on RGB conversion:

```sh
python3 - <<'PY'
# Compare INTRO.ART's 64,000-byte frame with dump[0xA0000:0xAFA00].
PY
xxd -l 64 -s 0xa0000 build/qemu-trace/startup-physical-1m.bin
xxd -l 64 -s 12 build/dd1/all/006_INTRO.ART
```

The frame and live VGA memory share 63,648 of 64,000 bytes. All 352
differences are explained by two visible runtime overlays: 333 pixels in the
floppy/save icon bounding box X 297–316, Y 1–17, and 19 pixels in the centered
mouse cursor bounding box X 154–166, Y 94–106. Outside those rectangles the
resource and framebuffer are byte-for-byte identical. The extracted frame
pixel SHA-256 is
`9f0926921d2a5ca01586a1f644d1eee24e734b4f6cbc3b0399e9883f97d2a014`.

Also checked the older and current one-MiB dumps. They are different overall,
but their VGA ranges contain the same opening scene; the older filename refers
to the executable-analysis milestone rather than a distinct title-frame VGA
capture. Did not use it as independent title-art evidence.

### Reproducible artwork tool

Added executable `tools/render_art.py` and `tests/test_render_art.py`. The tool
validates descriptor alignment, positive dimensions, contiguous pixel blocks,
exact resource length, 768-byte palette size, and six-bit palette components.
It can list descriptors, render a single transparent frame, render every frame
with index-preserving filenames, or composite signed origins on a configurable
canvas. It implements clipping itself so index values remain stable and uses
nearest-neighbor integer scaling.

The first focused run was:

```sh
chmod +x tools/render_art.py
python3 -m py_compile tools/render_art.py tests/test_render_art.py
python3 -m unittest -v tests.test_render_art
```

Seven structural tests passed; one guessed LOGO canvas checksum failed. As
reported to the user, computed a second composite independently with a simple
pixel loop. It exactly matched the tool output and established SHA-256
`e3234c620a873a2f91bb68e8e631d0a645b7958a24b3b07e5890f9bc7b5d62bc`.
Corrected the stale fixture and all eight focused tests passed.

Changed the tests to extract their ART/PAL inputs directly from `CB/DD1.DAT`
through `DD1Archive`, rather than depend on ignored pre-extracted files. This
makes the test suite reproducible from the supplied game directory alone. A
fresh `--extract-all` run separately produced all 369 files.

Exercised each command-line rendering path with:

```sh
tools/render_art.py build/dd1/all/003_LOGO.ART --list \
  > build/graphics/tool-check/logo-frames.txt
tools/render_art.py build/dd1/all/003_LOGO.ART \
  --palette build/dd1/all/002_LOGO.PAL \
  --canvas --scale 2 \
  --output build/graphics/tool-check/logo.png
tools/render_art.py build/dd1/all/006_INTRO.ART \
  --palette build/dd1/all/025_TITLE.PAL \
  --canvas --scale 2 \
  --output build/graphics/tool-check/intro.png
tools/render_art.py build/dd1/all/082_RUN.ART \
  --palette build/dd1/all/025_TITLE.PAL \
  --all-frames build/graphics/tool-check/run-frames \
  --scale 2
```

The list reports all six LOGO descriptors, the two composites are valid
640×400 indexed PNGs, and all 21 RUN frames were written. Visually inspected
the final logo, opening scene, and first running frame; their pixels,
transparency, orientation, and palette are correct.

Added the palette/artwork book chapter, renderer instructions and Pillow
requirement to `README.md`, format findings to the static-analysis chapter,
and eight high-confidence graphics names to `analysis/cb.rz`. Marked the two
graphics tasks complete in `PLAN.md`.

### Graphics-pass verification

Ran:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/render_art.py --help > build/graphics/tool-check/help.txt
tools/render_art.py build/dd1/all/003_LOGO.ART \
  --palette build/dd1/all/002_LOGO.PAL \
  --canvas --scale 2 \
  --output build/graphics/tool-check/final-logo.png
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~vga_; afl~blit_; afl~palette_effect; afl~draw_art; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/graphics/tool-check/symbols.txt
mdbook build docs
test -f build/docs-book/graphics-formats.html
git diff --check
git status --short
git diff --stat
```

All 25 tests passed, every Python source compiled, both existing shell scripts
still parsed, and the renderer reproduced its checked 640×400 logo PNG. Rizin
loaded all eight graphics names at their intended offsets. mdBook rendered the
new graphics chapter, and the tracked-source whitespace check passed. Source
changes remain uncommitted pending the next requested checkpoint.

### Beginning scene-command analysis

Continued directly into the `BIN` resources because they contain artwork,
music, text, timing, and effect references that connect the recovered graphics
to startup behavior. Added explicit `BIN` command-stream recovery to
`PLAN.md`.

Correlated the archive seeks in the existing QEMU DOS-call trace with the
decoded `DD1.DAT` directory. The startup path reads these resources in order:

```text
LOGO.BIN -> LOGO.PAL -> LOGO.ART -> D003.ABT
TITLE.BIN -> TITLE.PAL -> TITLE.ART -> TITLE2.ART -> MUS001.XMI
INTRO.BIN -> INTRO.ART
```

The trace's archive offsets, entry numbers, stored sizes, and expanded sizes
all agree with the extractor: `LOGO.BIN` is entry 1 at `0x24da`, `TITLE.BIN`
is entry 332 at `0x1b8665`, and `INTRO.BIN` is entry 5 at `0xaad0`. The later
scene reuses `TITLE.PAL`; no second palette read occurs before `INTRO.ART`.
The destination segments in the DOS reads also show a reusable resource
buffer: both `TITLE.BIN` and `INTRO.BIN` occupy segment `4c13` at their
respective points in startup.

### Live BIN resource and interpreter state

Reported that work would continue by finishing the BIN bytecode chapter and
guides, recording both the evidence trail and corrections, and running the
complete verification suite.

Searched the startup physical-memory dump for the fully expanded
`INTRO.BIN`, its far pointer, and nearby interpreter state. Repeated the check
in a self-contained form with:

```sh
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from extract_dd1 import DD1Archive

archive = DD1Archive.from_path(Path('CB/DD1.DAT'))
intro = archive.extract(archive.matching('INTRO.BIN')[0])
dump = Path('build/qemu-trace/startup-physical-1m.bin').read_bytes()
pointer = bytes.fromhex('00 00 13 4c')
print([hex(i) for i in range(len(dump)) if dump.startswith(intro, i)])
print([hex(i) for i in range(0x14000, 0x16000)
       if dump.startswith(pointer, i)])
print(dump[0x14f06:0x14f0e].hex(' '))
print(hex(intro[0x4b]))
PY
```

Results:

- The only complete live copy of the 184-byte `INTRO.BIN` begins at physical
  address `0x4C130`, the linear address of `4C13:0000`.
- The base pointer bytes `00 00 13 4C` occur at physical `0x14F0A`, which is
  the data-segment state at `DS:00FA`.
- Bytes at `DS:00F6..00FD` are `4B 00 13 4C 00 00 13 4C`. They encode current
  cursor `4C13:004B` and resource base `4C13:0000`.
- `INTRO.BIN[0x4B]` is opcode `0x42`, at a valid command boundary immediately
  after the `return_minus_one` command ending at file offset `0x4B`.

This established that the interpreter stores a file-relative cursor in
`DS:00F6`, its segment in `DS:00F8`, and the resource-base far pointer in
`DS:00FA..00FD`. It also tied a statically decoded command boundary to QEMU
runtime state rather than relying only on whole-file plausibility.

### Interpreter and operand readers

Followed references to `DS:00FA` and inspected the parser region and its
callers in Rizin. Saved the focused output as ignored research artifacts:

```text
build/analysis/bin-parser-region.txt
build/analysis/bin-core-functions.txt
build/analysis/bin-callers.txt
```

The static pass identified:

- `0x3A1E`, which reads a byte from the far cursor and increments its offset.
- `0x3A30`, which reads two bytes and constructs a little-endian word.
- `0x3A64`, which normally advances through a NUL-terminated string and
  returns its resource-base-relative starting offset. An initial `0xFF`
  instead introduces an explicit 16-bit offset.
- `0x451B`, the main interpreter. It installs `base + argument` as the cursor,
  reads an opcode, subtracts one, checks the range through `0x91`, and uses a
  145-entry near-pointer table at `0x59AB`.
- `0x6631`, which appends `.BIN`, loads a scene resource, installs the base and
  cursor, initializes thread/object state, and executes file offset zero.
- `0x7997`, which resumes active scene threads by passing their saved offsets
  to `0x451B`.

Out-of-range bytes are consumed by the game's fallback path. The host decoder
rejects them instead because treating arbitrary embedded data as executable
commands would conceal region boundaries.

Recovered the operand layout of each handler by following calls to the three
readers and direct cursor adjustments. The compact schema is:

```text
B  unsigned byte
H  little-endian 16-bit word
z  NUL-terminated CP437 string
9  opaque nine-byte animation record
s  optional extra word when the preceding H is signed-negative
```

During the iterative decoder work, corrected several prototype mistakes:

- An early schema string used uppercase `Z`, which the prototype did not
  recognize as a string marker. Standardized strings on lowercase `z`.
- The conditional instruction layout was temporarily written as `Bhs`; the
  lowercase `h` was not a valid word marker. Corrected opcodes `0x11`, `0x12`,
  and `0x17` through `0x1A` to `BHs`.
- The initial resource count was reported internally as 60 because a quick
  scan omitted two members. The archive-backed test enumerated 62, and all
  documentation and totals now use that value.
- The first `ROOM3.BIN` region test assumed its second code block continued to
  EOF. It stopped at another invalid zero block at `0x1754`; inspection found
  a 20-byte reserved region followed by a third command entry point at
  `0x1768`.

Reported the resulting structural milestone: all 145 dispatched opcodes have
operand layouts, and 62 archived BIN resources cross-check against them, with
two deliberate mixed code/data cases exposed explicitly.

### Opcode meanings and corrected resource interpretation

Cross-referenced handler callees, suffix-building functions, and script
control flow. High-confidence meanings include art and palette loading,
music selection, scene changes, timing, variable assignment/increment/
decrement, jumps, calls, returns, state snapshots, and art unloading.

The most important correction concerned strings such as `MTITLE` seen during
the earlier graphics pass. They were initially described as a command plus a
music name. Static analysis of `0x4001` showed it appends the suffix at
`DS:0434`, which is `.PAL`, while `0x4091` separately constructs `MUS###` or
`IBM###` XMI names. Checked the suffixes directly in the QEMU memory dump:

```text
DS:0434  .PAL
DS:0490  .ART
DS:0721  .BIN
```

Thus bytes `4D 54 49 54 4C 45 00` are opcode `0x4D` followed by string
`TITLE`, not an embedded `MTITLE` music identifier. Both opcodes `0x4D` and
`0x6D` invoke palette loading; opcode `0x52` selects music by numeric index.

Decoded the startup streams completely. Their sizes and command counts are:

```text
LOGO.BIN    640 bytes    114 commands
TITLE.BIN   436 bytes     80 commands
INTRO.BIN   184 bytes     39 commands
MENU.BIN  2,004 bytes     99 commands
```

`INTRO.BIN` begins with opcodes `6B 43`, `4C 0F`, palette command `4D
"TITLE"`, and art command `01 "INTRO"`. It later issues music command `52
01` and, at file offset `0x009A`, scene-change command `0D "dome" "seg"`.

### Reproducible BIN inspection tool

Added executable `tools/inspect_bin.py`. It contains the recovered schema for
every opcode `0x01..0x91`, typed command/operand records, bounds checks,
CP437-string decoding, conditional signed-word handling, and a command-line
listing with file offsets. Known operations receive semantic names; other
handlers deliberately remain `opcode_XX`.

Added `tests/test_inspect_bin.py`. The tests read resources directly from
`CB/DD1.DAT` and cover:

- exactly 145 contiguous schema entries;
- complete decoding and command counts for four startup programs;
- the `INTRO.BIN` palette, art, and scene-change commands;
- every known command region in all 62 BIN resources;
- the signed-negative conditional extra word;
- both zero-filled gaps and all three `ROOM3.BIN` code regions;
- rejection of opcode-zero padding and unterminated strings.

The first focused run was:

```sh
chmod +x tools/inspect_bin.py
python3 -m py_compile tools/inspect_bin.py tests/test_inspect_bin.py
python3 -m unittest -v tests.test_inspect_bin
```

All eight BIN tests passed. Whole-archive statistics from the validated
regions are:

```text
62 BIN members
179,200 expanded bytes
64 command regions
25,837 decoded commands
122 distinct opcodes used
```

Sixty resources linearly decode through EOF. `CP2.BIN` has a command region
through `0x1D5A` and a 251-byte structured trailer. `ROOM3.BIN` has command
regions `0x0000..0x0336`, `0x0C96..0x1754`, and `0x1768..0x19DB`, separated
by zero blocks of 2,400 and 20 bytes. Saved listings of the latter two regions
as `build/analysis/room3-region2-bin.txt` and
`build/analysis/room3-region3-bin.txt`.

Exercised the user-facing decoder paths with:

```sh
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0xc96 --limit 0x1754
tools/inspect_bin.py \
  build/dd1/all/334_ROOM3.BIN --start 0x1768
```

The first command reports all 39 commands and 184 bytes. The bounded ROOM3
listings report 180 commands over 2,750 bytes and 122 commands over 627 bytes.
Adjusted the summary line after this check so a nonzero `--start` reports the
decoded byte count, plus its absolute range, rather than mislabeling the final
file offset as a byte count.

Recomputed the archive totals and repeated the QEMU pointer check with the
self-contained Python snippets above. Then verified the new Rizin symbols:

```sh
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~bin_; afl~palette_resource; afl~music_resource; afl~scene; q' \
  build/analysis/CB_UNPACKED.EXE
```

Rizin listed all eight intended names at `0x3A1E`, `0x3A30`, `0x3A64`,
`0x4001`, `0x4091`, `0x451B`, `0x6631`, and `0x7997`.

During final review, noticed that the documented `0xFF` string-offset escape
in `0x3A64` was not yet implemented in the host decoder because none of the
linearly decoded regions exercised it. Added `string_offset` operand handling,
displayed such references as `@0xNNNN`, and added a focused regression using
`01 FF 34 12`. Updated the chapter's `z` schema to describe both encodings.

### Scene-bytecode documentation

Added `docs/src/scene-bytecode.md` and linked it from `SUMMARY.md`. The chapter
documents the interpreter model, live data-segment state, operand notation,
identified commands, startup sequence, mixed-content resources, inspection
tool, and executable routines. Added a concise interpreter section and the
new names to `static-analysis.md`.

Updated `README.md` with decoder examples and the two resources that require
explicit command-region bounds. Marked BIN scene-command recovery complete in
`PLAN.md`. Also corrected segment:offset notation in the chapter to show the
resource base as `4C13:0000` and live cursor as `4C13:004B`; the memory words
are stored offset first because x86 is little-endian.

### BIN-pass verification

Ran the complete repository verification rather than only the focused BIN
tests:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/inspect_bin.py --help > build/analysis/inspect-bin-help.txt
tools/inspect_bin.py build/dd1/all/005_INTRO.BIN \
  > build/analysis/intro-bin.txt
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~bin_; afl~palette_resource; afl~music_resource; afl~scene; q' \
  build/analysis/CB_UNPACKED.EXE > build/analysis/bin-symbols.txt
mdbook build docs
test -f build/docs-book/scene-bytecode.html
git diff --check
git status --short
git diff --stat
```

All 33 unit tests passed in 1.261 seconds before the explicit string-offset
regression was added. Every Python source compiled and
both shell scripts parsed. The decoder's help and full INTRO listing were
written successfully, Rizin loaded all requested symbols, and mdBook produced
`build/docs-book/scene-bytecode.html`. The tracked-source whitespace check
passed. The graphics and BIN source changes remain uncommitted at this
checkpoint.

After adding the string-offset case, repeated the full test, compile, shell,
decoder, Rizin, mdBook, generated-page, and whitespace checks. All 34 tests
passed in 1.267 seconds. The direct probe decoded `01 FF 34 12` as a
`load_art` operand of kind `string_offset`, value `0x1234`, and displayed it as
`@0x1234`. Confirmed both new command-line tools retain executable file modes.

## 2026-07-15: Audio resource formats

### Remaining-format inventory

After the user asked work to continue, reported that the next pass would
classify the unresolved audio and text-bearing resources, correlate sound
loads with the executable, and turn stable findings into tools, tests, and
book documentation.

Confirmed the working tree was clean after commit `b6c50df`, reread
`PLAN.md`, the file inventory, the `DD1.DAT` chapter, and the archive listing.
Used `DD1Archive` to group every expanded member by extension and print the
names, sizes, and first 24 bytes of the unclassified groups.

Results:

- The 33 extensionless members are translation-specific Bible text. Names
  begin with `T`, `R`, `N`, or `K`, and their payloads visibly start with
  verse references followed by `|`-delimited prose.
- All 21 `MAP` members are 768 bytes.
- The 32 `XMI` members start with `FORM`, `XDIR`, and `INFO` IFF identifiers.
  There are 16 `MUS###` and 16 `IBM###` resources.
- The 41 `ABT` members share a compact binary header and contain 205,513
  expanded bytes.

Ran `file` and `ffprobe` on representative `MUS001.XMI` and `D003.ABT` files.
`file` recognized XMI only as generic IFF and misidentified ABT as GeoSwath
RDF. `ffprobe` rejected both. These host heuristics were recorded but not used
as format evidence.

Searched existing documentation and executable strings for `ABT`, `XMI`,
`MUS`, `IBM`, DIGPAK, and MIDPAK references. The executable templates are
`MUS000.XMI` at load offset `0xF1DA` and `D000.ABT` at `0xF1E6`.
An initial Rizin command used `/ ABT`, which is not valid in the installed
Rizin version and printed search-command help. Switched to data-offset and
function inspection rather than treating that failed search as a result.

### Digital-effect loader and decoder

Saved focused disassembly in ignored files:

```text
build/analysis/audio-xrefs.txt
build/analysis/audio-functions.txt
build/analysis/digital-audio-loader.txt
build/analysis/abt-decoder.txt
build/analysis/audio-opcode-handlers.txt
```

The critical path is:

- Scene opcode `0x57` reads a byte and word and calls `0x417F`.
- `0x417F` writes the effect number into `D000.ABT`, stops and releases the
  previous effect, loads the archive member, reads its first word as the
  decoded allocation size, calls far routine `0x92E0`, constructs the DIGPAK
  playback state, and submits it through the interrupt `66h` wrapper at
  `0x8F2E`.
- `0x4235` stops active digital playback and releases its allocation.
- `0x92D0` returns the word at resource offset 2.
- `0x92E0` is the complete ABT decoder, with packed-delta helpers at
  `0x93BE`, `0x94CB`, and `0x956E`.

Translated the decoder into a temporary Python probe. The nine-byte header is
decoded sample count, sample rate, delta-block output count, codec byte,
auxiliary word, and initial sample. The main stream has absolute-sample,
run-length, and adaptive packed-delta commands. The three helpers expand one-,
two-, and four-bit codes most-significant bits first, add signed table values,
and clamp each new sample to 0 through 255.

Ran the probe against every ABT member. All 41 files decode to their declared
length and consume their compressed bytes exactly. Header values are 9,000 Hz,
32 samples per delta block, and codec identifier 2 in every member. The
decoder ignores the auxiliary word; its population is 128 in 35 files, 32 in
four, 64 in one, and 320 in one.

The complete output is 412,282 unsigned eight-bit samples, approximately
45.809 seconds. The stream uses 71,094 absolute commands, 1,699 runs, 2,125
one-bit blocks, 1,185 two-bit blocks, and 6,533 four-bit blocks.

Enumerated all scene opcode `0x57` operands with `inspect_bin`. Nonzero
effects range from 1 through 41, and every nonzero invocation supplies rate
9,000. Several scenes use operands `0, 0` to stop playback. This connects the
script schema directly to `D001.ABT` through `D041.ABT`.

### XMI container and event structure

Inspected `MUS001.XMI` with `xxd` and a temporary recursive IFF walker. Its
complete structure is:

```text
FORM XDIR
  INFO
CAT  XMID
  FORM XMID
    TIMB
    EVNT
```

Repeated the walker across all 32 files. IFF lengths are big endian, `INFO`
contains little-endian sequence count 1, every catalog contains exactly one
`FORM XMID`, and each form contains `TIMB` followed by `EVNT`. `TIMB` is an
even-length series of patch/bank byte pairs.

Implemented a temporary XMIDI event parser. It sums sub-`0x80` delay bytes,
handles fixed-size channel events, reads the duration after each note-on,
handles variable-length system-exclusive and meta payloads, and stops on
`FF 2F 00`. Eleven EVNT chunks retain one zero byte after end-of-track.
Across the archive, the streams contain 7,087 events, including 6,608 notes,
and the TIMB chunks contain 173 pairs.

### QEMU decoded-PCM capture

Reported that QEMU would be used for an independent runtime codec check with
its visible Cocoa display and silent audio backend. Launched a snapshot-backed
copy of the persistent disk with the debugger paused:

```sh
qemu-system-i386 \
  -name 'Captain Bible ABT capture' \
  -machine pc -accel tcg -cpu pentium -m 16 -boot c \
  -drive file=build/captain-bible/captain-bible.img,format=raw,\
if=ide,index=0,media=disk,snapshot=on \
  -vga std \
  -audiodev none,id=audio0 \
  -device sb16,audiodev=audio0 \
  -device adlib,audiodev=audio0 \
  -display cocoa,zoom-to-fit=on \
  -monitor unix:build/qemu-trace/audio-monitor.sock,server=on,wait=off \
  -gdb tcp:127.0.0.1:1234 -S
```

The first LLDB batch attempt set a breakpoint at physical `0xA499` and hit
`0627:4229`, but the batch client disconnected after `continue` and allowed
the guest to resume before the buffer could be dumped. Stopped that QEMU
instance, relaunched it, and kept LLDB connected interactively.

At the same breakpoint, immediately before the interrupt `66h` playback call,
the registers included `CS=0627`, `EIP=4229`, `DS=14E1`, and `EAX=A0DE`.
Reading physical `0x1EEEE`, which corresponds to `DS:A0DE`, returned:

```text
0000 5A45 2368 79EC 14E1 2328 FFFF 0000
```

This state contains decoded buffer `5A45:0000`, sample count `0x2368` (9,064),
callback `14E1:79EC`, and rate `0x2328` (9,000). Used LLDB to write 9,064 bytes
from physical `0x5A450` to ignored file
`build/qemu-trace/d003-live.pcm`, then detached and terminated QEMU cleanly.

Compared the live bytes with the temporary host decoder. Both are 9,064 bytes,
are byte-for-byte equal, and have SHA-256:

```text
ca97ad22acf3cc39d078b619168fa026deb1606082999bfb8b9a1aac4957422b
```

Reported this result to the user. It independently validates every ABT command
family used by `D003.ABT`, including packed bit order, signed delta tables,
clamping, and output length.

### Reproducible audio tools

Added executable `tools/convert_abt.py`. It translates the executable's codec,
checks all bounds and exact input consumption, prints header and command
statistics, and optionally writes standard unsigned eight-bit mono WAV.

Added executable `tools/inspect_xmi.py`. It recursively validates IFF sizes,
padding, XDIR counts, XMID form and chunk order, TIMB pairs, event boundaries,
durations, variable-length quantities, end-of-track, and zero padding.

Added `tests/test_audio_formats.py`, backed directly by `CB/DD1.DAT`. Tests
cover all 41 ABT resources, the QEMU-validated D003 PCM hash, WAV properties,
ABT truncation and trailing data, all 32 XMI resources, MUS001 event counts,
and damaged XMI structures.

The first focused test run had six passes and one error. The whole-XMI test
rejected a high-bit channel parameter in `MUS016.XMI`. Inspection found the
deliberate event sequence `B1 00 FF`, alongside similar controller setup for
other channels. The temporary parser had already accepted it because fixed
event sizes make the boundary unambiguous. Removed the generic MIDI seven-bit
parameter restriction from the repository validator, preserving the supplied
XMIDI bytes, and repeated the run. All seven audio tests passed.

Exercised both command-line paths:

```sh
tools/convert_abt.py \
  build/dd1/all/306_D003.ABT --output build/audio/d003.wav
tools/inspect_xmi.py build/dd1/all/267_MUS001.XMI
file build/audio/d003.wav
ffprobe -v error \
  -show_entries stream=codec_name,sample_rate,channels,duration \
  -of default=noprint_wrappers=1 build/audio/d003.wav
```

The ABT tool reports 9,064 samples, rate 9,000, duration 1.007 seconds, and all
five command families. `file` and `ffprobe` independently recognize the output
as mono unsigned eight-bit PCM at 9,000 Hz. The XMI tool reports one sequence,
12 timbres, 446 events, 432 notes, eight meta events, and additive delay 3,016
for `MUS001.XMI`.

### Audio documentation and symbols

Added `docs/src/audio-formats.md` and linked it from `SUMMARY.md`. Updated the
README with ABT-to-WAV and XMI inspection examples, the static chapter with
the loader and decoder path, the dynamic chapter with the live QEMU buffer,
and the scene-bytecode chapter with opcodes `0x57` and `0x58`.

Named the effect loader, stop/release paths, ABT header helper, main decoder,
and three packed-delta helpers in `analysis/cb.rz`. Added corresponding names
for opcodes `0x57` and `0x58` in `tools/inspect_bin.py`. Marked ABT/XMI format
recovery and reproducible audio tooling complete in `PLAN.md`; the broader
format task remains open because text and map families still need dedicated
passes.

The first full verification run passed all source and documentation checks but
Rizin reported `Failed to run script 'analysis/cb.rz'`. The initial `aaa` pass
did not define every ABT helper as a function, so `afn` could not rename one of
the new offsets. Added explicit `af` commands for `0x4155`, `0x417F`, `0x4235`,
`0x92D0`, `0x92E0`, `0x93BE`, `0x94CB`, and `0x956E` before assigning names.

### Audio-pass verification

Repeated the complete verification after the symbol-script correction:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/convert_abt.py \
  build/dd1/all/306_D003.ABT \
  --output build/audio/final-d003.wav \
  > build/audio/d003-summary.txt
tools/inspect_xmi.py build/dd1/all/267_MUS001.XMI \
  > build/audio/mus001-summary.txt
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~sound_effect; afl~abt_; afl~decode_abt; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/audio/audio-symbols.txt
mdbook build docs
test -f build/docs-book/audio-formats.html
git diff --check
rg -n '[[:blank:]]+$' \
  docs/src/audio-formats.md tests/test_audio_formats.py \
  tools/convert_abt.py tools/inspect_xmi.py
git status --short
```

All 41 tests passed in 1.298 seconds. Every Python source compiled, both shell
scripts parsed, both audio CLIs completed, and Rizin listed all eight new
effect/ABT symbols at their intended offsets. mdBook generated the audio
chapter. Tracked and new files have no whitespace errors. The audio-pass
changes remain uncommitted pending a requested checkpoint.

## 2026-07-15: Annotated full-screen artwork gallery

### Full-screen frame and palette inventory

Started from a clean worktree and searched the archive for `ART` descriptors
whose origin is `(0, 0)` and whose dimensions are exactly 320×200. The first
short Python probe attempted to import a nonexistent `parse_art` helper from
`tools/render_art.py` and failed with `ImportError`. Inspected that module,
used its actual `ArtResource.from_bytes` interface, and repeated the probe.

The corrected enumeration found exactly 11 full-screen frames, all at frame
index 0: archive entries 006 `INTRO.ART`, 063 `PRAY.ART`, 073 `OVER.ART`, 090
`LAW1.ART`, 093 `KABLAM1.ART`, 097 `SPEAKER.ART`, 100 `HOLE.ART`, 122
`DOME.ART`, 130 `DENY1.ART`, 133 `CULTA.ART`, and 165 `BOSS.ART`.

Decoded the resource-loading command context in every `BIN` scene program.
Associated the active palette selected by opcode `0x4D` or `0x6D` with the
subsequent ART load at opcode `0x01`. This produced one unambiguous palette
for every full-screen resource:

```text
INTRO.ART   TITLE.PAL
PRAY.ART    PRAY.PAL
OVER.ART    1.PAL
LAW1.ART    LAW.PAL
KABLAM1.ART KABLAM.PAL
SPEAKER.ART 1.PAL
HOLE.ART    HOLE.PAL
DOME.ART    DOME.PAL
DENY1.ART   DENY.PAL
CULTA.ART   1.PAL
BOSS.ART    BOSS.PAL
```

### Reproducible gallery tool

Added executable `tools/render_fullscreen_gallery.py`. It reads `DD1.DAT`
directly, validates and discovers all full-screen ART frames, decodes the
known command regions of the scene programs to infer their palettes, and
renders an RGB contact sheet in archive order. Labels sit outside the game
frames and give the archive identifier, ART name, frame number, and palette.
The optional `--scale` argument enlarges pixels with nearest-neighbor sampling.

Added `tests/test_fullscreen_gallery.py`. Its tests lock down the exact set and
order of 11 identifiers, the inferred ART-to-PAL mapping, and the dimensions
and mode of the native four-column sheet. The first focused run passed the two
inventory tests but failed the layout assertion because the expected height
was miscalculated as 828 rather than 816 pixels. Corrected the expected value
and repeated the focused suite; all three tests passed.

Generated both native and two-times artifacts and inspected each rendered PNG:

```sh
chmod +x tools/render_fullscreen_gallery.py
python3 -m py_compile \
  tools/render_fullscreen_gallery.py tests/test_fullscreen_gallery.py
python3 -m unittest -v tests.test_fullscreen_gallery
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT \
  --output build/graphics/full-screen-gallery.png
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT --scale 2 \
  --output build/graphics/full-screen-gallery-2x.png
file \
  build/graphics/full-screen-gallery.png \
  build/graphics/full-screen-gallery-2x.png
shasum -a 256 \
  build/graphics/full-screen-gallery.png \
  build/graphics/full-screen-gallery-2x.png
```

The native sheet is a 1348×816 RGB PNG with SHA-256
`f9d5e6330041ad736f072ae9a90fc7328355857a8adc8f26bfc70e7dbf41dfcb`.
The enlarged sheet is a 2696×1632 RGB PNG with SHA-256
`d91fcb4254eddee5458713f661f08269d138410d1ef224662fc13ab8904d7ef1`.
Visual inspection confirmed all 11 labels, frame boundaries, palette colors,
and nearest-neighbor scaling.

`KABLAM1.ART` appeared almost entirely black, so counted its raw pixel values
to distinguish a rendering error from source content. It has 16 distinct
indices, dominated by indices 100 through 107; `KABLAM.PAL` maps those entries
to very dark colors. Retained it because it is a genuine full-screen base
frame used with subsequent KABLAM overlay artwork. Updated `README.md`,
`PLAN.md`, and this book's graphics chapter with the reproducible command,
inventory, and palette evidence. Reported the completed visual check and this
reason for retaining the dark frame to the user.

The user briefly expanded the requested scope to all ART resources, then
restored it to full-screen images only before implementation changed. During
that check, enumerated the broader population as 143 ART resources containing
1,178 frames. The scene-command association pass gives one palette to 113
resources, multiple possible palettes to 17, and no direct association to 13.
Kept the completed 11-frame gallery design and artifacts unchanged, as
requested.

### Gallery verification

Ran the complete repository verification after the scope confirmation:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT \
  --output build/graphics/full-screen-gallery.png
tools/render_fullscreen_gallery.py \
  CB/DD1.DAT --scale 2 \
  --output build/graphics/full-screen-gallery-2x.png
file \
  build/graphics/full-screen-gallery.png \
  build/graphics/full-screen-gallery-2x.png
shasum -a 256 \
  build/graphics/full-screen-gallery.png \
  build/graphics/full-screen-gallery-2x.png
mdbook build docs
test -f build/docs-book/graphics-formats.html
git diff --check
rg -n '[[:blank:]]+$' \
  PLAN.md README.md docs/src/graphics-formats.md \
  docs/src/progress-log.md tests/test_fullscreen_gallery.py \
  tools/render_fullscreen_gallery.py
git status --short
```

All 44 tests passed in 1.930 seconds. Every Python source compiled, both shell
scripts parsed, both gallery variants regenerated with the documented sizes
and hashes, and mdBook rebuilt the graphics chapter. The generated sources
have no whitespace errors. The gallery implementation and documentation are
uncommitted pending a requested checkpoint. Reported both image paths, the
reproduction command, test result, and the intentional inclusion of the dark
`KABLAM1.ART` frame to the user.

The user requested a commit checkpoint. Inspected the complete diff, including
the two new source files, and confirmed it contains only the full-screen
gallery generator, its regression tests, and the corresponding plan, README,
graphics chapter, and progress-log updates. Prepared these six files as one
cohesive gallery commit after the successful 44-test verification above.
Staged the six files, ran `git diff --cached --check`, and created the commit
with subject `docs: Add full-screen artwork gallery`. Verified that every
commit-message line is at most 72 characters and that the worktree is clean.

## 2026-07-15: Verse indexes and companion text

### Remaining-format inventory

After the user asked reverse-engineering work to continue, reported that the
next pass would recover the text-bearing resources and their runtime
consumers. Confirmed the worktree was clean at commit `e546d98`, reread the
open plan items and mdBook summary, and grouped all 369 `DD1.DAT` members by
extension and expanded size:

```text
ART       143 resources  4,864,835 bytes
BIN        62 resources    179,200 bytes
ABT        41 resources    205,513 bytes
PAL        37 resources     28,416 bytes
no suffix  33 resources    215,113 bytes
XMI        32 resources     34,618 bytes
MAP        21 resources     16,128 bytes
```

Selected the 33 extensionless resources because the executable's built-in
study export provides an independent validation path. The first inventory
probe incorrectly referenced `DD1Entry.packed_size`; the actual field is
`stored_size`, so Python raised `AttributeError`. A follow-up sample query
also tried nonexistent long names such as `GEN` and `MAT` before the complete
listing showed that the real names are two-character translation/bank pairs.
Corrected both assumptions and recorded all archive indexes, sizes, headers,
and tails.

The members are `T`, `R`, `N`, or `K` plus bank `A` through `G` or `R`.
These prefixes correspond to The Living Bible, Revised Standard Version, New
International Version, and King James Version. `NG` occurs at indexes 199 and
206 and the two expanded payloads are byte-identical.

### Verse-index structure

Dumped representative resources with `xxd`, counted control bytes and NUL
positions, and printed the text around candidate boundaries. Each ordinary
record begins with a nonzero selector byte, a little-endian word, and a
NUL-terminated CP437 string containing one `|`. The text on the left of the
pipe is a citation and the text on the right is a translated verse.

The initial parser treated every three-byte header as an ordinary record and
failed at the end of `TR` with `ValueError: ('string', 1287)`. Tail inspection
showed that the final three bytes are instead a zero selector and terminal
offset with no string. Corrected the parser and validated every extensionless
member to its exact end.

Compared the selector/offset pairs across translations. All four translations
have identical structural headers for each corresponding bank. Each bank's
terminal offset exactly equals its companion file size:

```text
A 0x2751  B 0x203d  C 0x0fb4  D 0x3a7d
E 0x28f9  F 0x2811  G 0x2709  R 0x02b8
```

Offsets can repeat. Those zero-length ranges identify verses that have no
companion text, rather than malformed records. There are 319 logical verse
records in every translation.

### Executable text path

Used Rizin with `analysis/cb.rz` to disassemble the existing
`export_game_text` function and its helpers. Saved ignored working output in
`build/analysis/export-game-text.txt`, `text-loader-629c.txt`,
`text-helper-functions.txt`, `text-selector-5ad6.txt`, and focused caller
dumps.

Function `0x629C` constructs the extensionless name from a translation table
and the requested bank letter, loads it from `DD1.DAT`, and parses exactly the
record layout above. It builds ten-byte runtime entries containing the far
verse pointer, selector, companion offset, and the span obtained by
subtracting the next offset. It then opens the matching `DDL` file.

Function `0x5AD6` linearly finds a record by selector. Function `0x5CE2`
copies either the citation/verse or a requested tagged string from the
companion range. Function `0x5EE7` wraps export text at 70 columns. Named these
functions `load_text_bank`, `find_text_record_by_selector`,
`copy_text_record_component`, and `write_wrapped_export_text` in
`analysis/cb.rz`.

The selector is an exact lookup key. The export routine separately checks for
selectors at or above `0xE0` when mature topics are disabled, establishing the
meaning of that range without assigning semantics to the remaining key bits.

### `DDL` tagged strings

Listed and hashed `DDLA` through `DDLR`, then parsed each entire file as an
ASCII tag followed by a NUL-terminated CP437 string. All 68,746 bytes consume
exactly as 1,058 records with tags `L`, `P`, `W`, `C`, `E`, `*`, or `M`.
Correlated the tags with literal export headings and mask checks in the
executable:

```text
L  CYBER LIE                         277 records
P  PARAPHRASE                        123 records
W  WRONG GUESS                       210 records
C  CORRECT GUESS                      67 records
E  EXPLANATION OF CORRECT GUESS       68 records
*  CONVERSATION WITH VICTIM           58 records
M  numeric/internal metadata         255 records
```

The index spans cover 1,057 of those records. `DDLF` has one 26-byte `E`
preamble before its first indexed offset, so retained it as validated but
unassociated data. The earlier count of 1,130 companion records was an
arithmetic mistake; summing the per-tag counts gives 1,058.

A manual search command initially passed a pattern beginning with `-` to
`rg` without its `--` option, producing `rg: unrecognized flag -|`. Repeated
the search as `rg -n -- ...` and found the advanced `-sXfilename` and `-gXX`
options in `MANUAL.TXT`, including the installation-lock warning and all six
export-mask values.

### Visible QEMU export validation

Created the ignored `build/text/export-autoexec.bat` and a copy-on-write clone
of the play image. Replaced both FreeDOS startup scripts in that clone with a
batch file that ran the game exporter, wrote an `EXPORT.OK` marker, and called
`FDAPM POWEROFF`. Verified the scripts with `mtype`, then launched QEMU visibly
and without audio:

```sh
qemu-system-i386 \
  -name 'Captain Bible text export' \
  -machine pc -accel tcg -cpu pentium -m 16 -boot c \
  -drive file=build/text/export.img,format=raw,if=ide,index=0,media=disk \
  -vga std \
  -audiodev none,id=audio0 \
  -device sb16,audiodev=audio0 \
  -device adlib,audiodev=audio0 \
  -display cocoa,zoom-to-fit=on \
  -no-reboot
```

Inside DOS, the batch invoked `CB -g63 -sTSTUDY.TXT`. QEMU powered off with
exit status zero after about 13 seconds. Extracted the generated study file
with `mcopy`; it is 132,510 bytes, 3,854 lines, and has SHA-256
`c9ebe2cc4fbd00cd709d87761b38f6a8843eae99ceaa75cef842b93364dad0bc`.

The output used NIV wording rather than the requested Living Bible wording.
Inspected `SOUND.5` as `01 00 00 00`; runtime translation index 1 is NIV, so
the installed lock overrode `-sT` exactly as the manual describes. Normalized
the exporter's line wrapping and compared every parsed NIV verse. All 302
emitted verses match. The 17 missing verses are exactly all records whose
selectors are `0xE1` through `0xE4`, independently validating the active
mature-topic filter. The game-authored headings and contents also match the
parsed companion tags.

### Reproducible inspector and focused tests

Added executable `tools/inspect_text_resources.py`. It validates the terminal
record, pipe delimiter, CP437 text, nondecreasing offsets, companion size,
known tags, exact NUL termination, duplicate-resource identity, and requested
translation/bank. It joins each verse to its tagged `DDL` span and can display
one record or a whole bank.

Added `tests/test_text_resources.py` with six tests covering all 32 logical
translation/bank pairs, header equality across translations, the duplicate
`NG` resources, the QEMU-validated first NIV record, valid zero-length spans,
and damaged index/companion rejection.

The first focused run produced four errors and one failure because the parser
compared an integer tag byte with string keys in `TAG_LABELS`. Converted the
byte to a character before validation. The next run passed five tests but the
aggregate count expected `4 * 1130`; corrected the arithmetic and explicitly
validated all companion bytes, including the single unindexed preamble. The
third focused run passed all six tests in 0.185 seconds.

Exercised the CLI against NIV bank A record zero and confirmed it prints the
archive index, selector, companion range, citation and verse, followed by the
expected `L`, `P`, four `W`, `C`, and `E` records. Added
`docs/src/text-formats.md`, linked it from the mdBook summary, updated the
file inventory and static function map, documented CLI usage in `README.md`,
and marked text recovery, tooling, and format documentation complete in
`PLAN.md`. Reported the corpus counts, exact QEMU validation, mature filtering,
and documentation consolidation to the user.

### Text-pass verification

Ran the complete repository verification after documentation and symbol
updates:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/inspect_text_resources.py \
  CB/DD1.DAT --data-dir CB \
  --translation N --bank A --record 0 \
  > build/text/inspect-niv-a0.txt
rizin -q -b 16 -a x86 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~text_; afl~export_game_text; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/text/text-symbols.txt
mdbook build docs
test -f build/docs-book/text-formats.html
git diff --check
rg -n '[[:blank:]]+$' \
  PLAN.md README.md analysis/cb.rz \
  docs/src/file-inventory.md docs/src/static-analysis.md \
  docs/src/SUMMARY.md docs/src/text-formats.md \
  docs/src/progress-log.md tests/test_text_resources.py \
  tools/inspect_text_resources.py
git status --short
```

All 50 tests passed in 2.185 seconds. Every Python source compiled, both shell
scripts parsed, the text inspector produced the expected joined NIV record,
and Rizin loaded the new text symbols at their intended offsets. mdBook built
the new text-format chapter successfully. Tracked and new files have no diff
or whitespace errors. The text-format changes remain uncommitted pending a
requested checkpoint.

The user requested a commit checkpoint for the text-format pass. Inspected
the final diff and confirmed it contains only the verse-index and `DDL`
recovery, inspector and tests, Rizin symbols, mdBook chapter, inventory,
README, plan, static-analysis, and progress-log updates. Prepared these ten
files as one cohesive commit after the successful 50-test verification above.
Staged all ten files, ran `git diff --cached --check`, and created the commit
with subject `text: Recover study resource formats`. Verified that every
commit-message line is at most 72 characters and that the worktree is clean.

## 2026-07-15: save-game format and player prefixes

The user asked to continue reverse engineering. Selected the next open file-
format milestone: fully recover the supplied save formats and player-name
behavior, turn the result into a strict inspector, and document it. Reported
that the work would begin from the ten supplied save files and static
comparisons, then trace filenames and scalar fields.

### Corpus inventory and comparisons

Ran `git status --short`, inspected the recent log, searched the plan, README,
book, and ignored analysis outputs with `rg`, and used `stat`, SHA-256, and
short Python scripts on `CB/DDGAMES.SV0` through `SV9`. The current starting
commit was `3c42783 text: Recover study resource formats`, and the tracked
worktree was clean. Confirmed again that `SV0` is 243 bytes and all nine state
files are 2,752 bytes.

Decoded `SV0` as nine 27-byte buffers. Every visible C string is `EMPTY`, but
bytes after the first NUL include fragments such as `id II` and `rney SL`.
These are stale buffer tails, not label text: the executable uses `strcpy`
rather than clearing all 27 bytes. Noted that the executable's missing-index
initializer is `(EMPTY)`, whereas the supplied file contains `EMPTY` without
parentheses.

Compared every state pair and each byte position across the corpus. Found
that `SV6` and `SV8` are identical, 2,477 of 2,752 offsets are constant, and
275 vary. The group containing `SV1`, `SV2`, `SV5`, `SV6`, `SV7`, and `SV8`
often differs by only one byte; `SV3` and `SV4` also differ by one byte, while
`SV9` differs more substantially.

Dumped every known block and compared the paired regions. Each 200-byte
primary pair differs at byte 56; `SV9` additionally differs at byte 54. The
two 768-byte blocks are identical inside each save. They are zero in most
files, while `SV3` and `SV4` each contain 112 nonzero bytes. The four 20-byte
buffers decode as `LOGO`, `LOGO`, `seg`, and `seg`; some files retain stale
bytes after those C strings' NUL terminators.

All supplied states contain translation index 1, music flag 1, effects flag
1, checkpoint bank word 67, and live bank word 67. The latter two are ASCII
`C`. All compact descriptor-state bytes are zero. Descriptor pointers in
`SV9` use a different segment from the other supplied files, an early sign
that those pointer words are process-dependent.

### Static save-path tracing

Generated these ignored evidence files with scripted Rizin sessions over
`build/analysis/CB_UNPACKED.EXE`:

- `build/analysis/save-pass-functions.txt`
- `build/analysis/game-main-save-pass.txt`
- `build/analysis/save-field-xrefs.txt`
- `build/analysis/save-name-control-flow.txt`
- `build/analysis/save-menu-flow.txt`
- `build/analysis/save-main-loop.txt`
- `build/analysis/save-snapshot-callers.txt`
- `build/analysis/save-snapshot-exact.txt`

The sessions ran `aaa` and `analysis/cb.rz`, then used `pdf`, `pd`, `axt`,
`px`, and `ps` around the save functions, `game_main`, the options menu, the
main event loop, and DS references `0042`, `0045`, `0048`, `004A`, `007C`,
`0080`, and `4A02`. One command requested `pdf @ main`, which failed because
the configured name is `game_main`; reran it with the correct symbol. Another
attempt used the unavailable `pdc` command; retained ordinary function and
recursive disassembly instead.

Recovered the exact checkpoint-copy behavior at load offsets `0x7D8E` and
`0x7E41`. The forward routine copies 200 bytes from DS `727A` to `7BF2`, byte
`+4` from each of 66 ten-byte descriptors at `B194` into `3A66`, all
16×16×3 bytes from `5B16` to `76EC`, the C strings at `B83E`/`AEFE` to
`6EA6`/`8938`, and word `0080` to `9FB0`. The inverse routine reverses those
copies and reloads the selected text bank. Forward-copy callers are new-
session initialization and a scene command, not the state writer itself.
This explains the manual's warning that saves in conversations can resume at
the beginning of a scene: the file contains both checkpoint and live state.

Recovered the ten-byte runtime descriptor layout as far pointer offset,
far pointer segment, persistent state byte, selector, companion offset, and
companion span. The loader reconstructs all structural and pointer fields
while preserving byte `+4`; the separate 66-byte block is its checkpoint
copy. Loaded NIV bank C through `tools/inspect_text_resources.py` and compared
it with `SV1`. All 46 active descriptors match exactly in selector, companion
offset, and span, and the remaining 20 structural records are zero.

The first ad-hoc comparison script failed with `ModuleNotFoundError` because
`inspect_text_resources.py` imports `extract_dd1` as a tool-directory module.
Added `tools` to that script's temporary `sys.path` and reran successfully.
This was an inspection-only correction; no source was changed to accommodate
the one-off command.

Traced the scalar cross-references. DS `0048` is the music-enabled flag:
music playback tests it and the options menu toggles it. DS `004A` is the
sound-effects flag and is likewise tested and toggled. DS `007C` is the
translation index established in the text pass. DS `0080` is the current
text-bank character, copied to checkpoint word `9FB0`.

Traced `game_main` and the suffix data. Startup copies the literal `DDGAMES`
to DS `4A02`. A non-option command-line argument replaces it verbatim via
unbounded `strcpy`; the executable does not enforce the manual's DOS filename,
path, or eight-character rules. The static suffix at DS `0042` is `.SV0`.
Both index and state routines create names by copying the player prefix and
appending this mutable suffix.

Disassembled slot selection at `0x2B6F` and the main loop around `0x891B`.
The menu changes the suffix's last byte to ASCII `1` through `9`. F10 changes
it to `Q`, updates live rendering/state, calls `write_save_state`, and restores
`0`. F9 makes the same temporary change around `read_save_state`. Reported to
the user that this proves `.SVQ` is the independent tenth state. The
empty-slot helper uses the selected digit to address one 27-byte label and,
when empty or equal to `(EMPTY)`, copies a generated `Game 1` through `Game 9`
default into it.

Confirmed the write routine emits the exact 15 blocks in the documented
order and rewrites `SV0` first. The read routine mirrors the layout. It
returns failure if `fopen` fails, but does not test the 15 individual `fread`
counts before refreshing sound/text state and reporting success. This is why
the host inspector rejects damaged sizes even though the original game does
not reliably do so.

### Reproducible save inspector

Added executable `tools/inspect_save.py`. It detects an index or state by the
two exact sizes, decodes CP437 C-string buffers, preserves and reports stale
label tails, parses all 66 text descriptors, names the recovered settings,
separates live/checkpoint regions, counts snapshot differences, and optionally
lists nonempty descriptors.

Added `tests/test_inspect_save.py` with seven tests. They cover all ten
supplied files, nine visible `EMPTY` labels and stale tails, exact parser size
selection, damaged-size rejection, scalar and C-string regressions, compact
state bytes versus descriptor byte `+4`, live/checkpoint table equality, the
known `SV6`/`SV8` duplicate, and the complete NIV bank C descriptor match.

Ran:

```sh
chmod +x tools/inspect_save.py
python3 -m unittest tests.test_inspect_save -v
tools/inspect_save.py CB/DDGAMES.SV0
tools/inspect_save.py CB/DDGAMES.SV3 --descriptors
```

All seven focused tests passed. The index CLI displayed nine labels and stale-
tail counts; the state CLI reported translation 1, both audio flags enabled,
bank C, four expected resource strings, 46 active descriptors, no active
state bytes, one primary checkpoint difference, and no three-byte-table
difference. Renamed an initially proposed `world_table` field to the
conservative `three_byte_table` because gameplay meaning is not yet proven.

### Documentation and symbols

Added `docs/src/save-formats.md` and linked it from `SUMMARY.md`. The chapter
documents player-prefix handling, all ten filenames, fixed label records,
stale bytes, every state block, checkpoint direction, descriptor structure,
supplied-file statistics, original error handling, inspector usage, open
questions, and relevant functions. Replaced the older preliminary save table
in `static-analysis.md` with a concise verified summary and chapter link;
updated the save inventory link and added inspector usage to `README.md`.

Marked save-format/player-prefix recovery and the inspector complete in
`PLAN.md`. Added `choose_save_slot` and `save_selected_slot` to
`analysis/cb.rz`. Reported during the pass that the major save blocks were
pinned down, that the snapshot relationship was established by copy direction,
and that filename and scalar tracing was in progress; later reported the exact
`.SV0`/slot/`.SVQ` mutation and the 46-record NIV bank C match.

### Save-pass verification

Reported that the inspector and focused tests were complete, that the book now
distinguishes checkpoint and live state from executable evidence, and that a
full repository verification was starting. Ran:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh tools/build_qemu_dos_trace.sh
tools/inspect_save.py CB/DDGAMES.SV0 \
  > build/analysis/save-index-inspection.txt
tools/inspect_save.py CB/DDGAMES.SV3 --descriptors \
  > build/analysis/save-state-inspection.txt
rizin -q -b 16 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~save_; afl~choose_save_slot; q' \
  build/analysis/CB_UNPACKED.EXE \
  > build/analysis/save-symbols.txt
mdbook build docs
test -f build/docs-book/save-formats.html
git diff --check
rg -n '[[:blank:]]+$' \
  PLAN.md README.md analysis/cb.rz \
  docs/src/SUMMARY.md docs/src/file-inventory.md \
  docs/src/static-analysis.md docs/src/save-formats.md \
  docs/src/progress-log.md tests/test_inspect_save.py \
  tools/inspect_save.py
git status --short
```

All 57 tests passed in 2.114 seconds. Every Python source compiled and both
shell scripts parsed. Both save-inspector modes ran successfully, Rizin loaded
the expanded symbol file, and mdBook built the new chapter at
`build/docs-book/save-formats.html`. The diff and whitespace checks were clean.
The save-format work remains uncommitted pending an explicit checkpoint
request.

Performed a final status/diff review and displayed the inspector's `--help`
output. An initial chained command stopped after the whitespace `rg` returned
status 1 for the expected “no matches” result, so it did not reach the status
commands that followed. Reran `git diff --check`, `git diff --stat`,
`git diff --numstat`, `git status --short`, and the help command independently.
The diff check remained clean, the CLI showed its positional save path and
optional `--descriptors` switch, and only the ten intended save-pass paths are
modified or new.

### Save-format commit preparation

At the user's request, prepared the completed save-format pass for a commit.
Ran `git status --short`, `git diff --check`, `git diff --stat`, and reviewed
the tracked plan, README, Rizin, summary, inventory, and static-analysis diff.
Confirmed that the ten modified or new paths form one cohesive change: save
format recovery, its reproducible inspector and tests, the dedicated mdBook
chapter, symbol additions, and project/log updates. The whitespace check was
clean, and the full 57-test verification immediately above remains current;
the only subsequent content change is this commit-preparation log entry.

Staged the ten intended paths and ran `git diff --cached --check`. Git found
one extra blank line at the end of `docs/src/save-formats.md`, so the chained
status/stat commands correctly stopped before commit. Inspected the final
bytes with `tail` and `xxd`, removed the redundant newline with `apply_patch`,
and prepared to restage both that correction and this log entry before running
the staged checks again.

Restaged the correction and log. The second staged whitespace check passed;
the staged summary contained exactly ten paths, with 801 insertions and 36
deletions. Created the requested checkpoint with subject
`save: Recover game-state formats` and a detailed five-paragraph body covering
the filename logic, state layout, text-resource correlation, inspector, tests,
and rationale. Verified the initial commit message with `awk`; every line is
at most 72 characters, and `git status --short` was empty. Added this final
commit action to the activity log and folded it into the same checkpoint.

### World-map resource and runtime-state recovery

After the user's next `continue`, checked the worktree, the three most recent
commits, the live plan, the scene-bytecode and save chapters, the BIN
inspector, and existing analysis notes. The tree was clean at commit
`3afe96f` (`save: Recover game-state formats`). Selected the unknown saved
16×16×3-byte table as the next bounded target and reported that the pass would
correlate BIN handlers, archive resources, and saved state, then add a tool
where the evidence supported one.

Used Rizin cross-references for the live table at `DS:5B16`, its checkpoint at
`DS:76EC`, script variables at `DS:727A`, and text descriptors at `DS:3A66`:

```text
axt @ 0x5b16
axt @ 0x76ec
axt @ 0x727a
axt @ 0x3a66
```

Saved the inspection output under the ignored `build/analysis/` directory as
`world-table-xrefs.txt`, `world-table-functions.txt`,
`world-grid-control.txt`, `world-map-ui-and-opcodes.txt`, and
`map-screen.txt`. Several Rizin `pdf` requests warned that the linear size
differed too much from the basic-block sum. Used `pdr` and direct bounded
`pd` listings instead. Rizin's inferred split around the map display is
imperfect, but direct callers and control flow establish `0x075F` as the
actual `show_map_screen` entry.

The references repeatedly calculate `48*y + 3*x` and access neighbors at
offsets ±3 and ±48. This proves a row-major 16×16 grid of three-byte cells.
Identified current coordinate words at `DS:7290` and `DS:7292`. Reported that
the saved table is live world-grid state, with `cell[y][x]` addressing, and
that the next step was tracing the opcode handlers and map UI.

Disassembled the handlers around load offsets `0x034F`, `0x0457`, `0x075F`,
and `0x0C6C`, plus the opcode dispatch region. The loader takes its level
letter from opcode `0x78`, indexes the executable literal `END` with script
variable zero, appends the literal `.MAP`, and loads 768 raw bytes into
`DS:5B16`. Checked the archive and found the complete 21-member product of
levels A through G and suffixes E, N, and D, all exactly 768 expanded bytes.
The manual names the corresponding modes Easy, Normal, and Difficult.
Reported this resource-name construction and the 21-member result to the
user.

An initial ad-hoc archive query failed with `AttributeError` because it used a
nonexistent `DD1Entry.full_name` property. Repeated it with the actual
`filename` property. Enumerated opcode `0x78` in every recovered BIN code
region and found all level letters: C in `FIRST` and `OUTC`, F in `OUTF`, E
in `OUTE`, D in `OUTD`, B in `OUTB`, A in `OUTA`, and G in `OUTGL`.
Also found broad use of current-cell processing and mutation commands in
power, room, combat, and hall programs.

Recovered these map-related opcode effects from direct handler behavior:

- `0x77` processes the current map cell and consults adjacent cells.
- `0x78 B` loads the selected level and current difficulty map.
- `0x7B H` replaces the current cell's low kind nibble while preserving its
  high nibble.
- `0x7C H` and `0x7F H` write the cell's second and third bytes.
- `0x87` normalizes loaded or changed map cells.
- `0x88` clears persistent byte `+4` in all 66 text descriptors.
- `0x89` sets `explored_rows[y] |= 1 << x` in the 16-word array at
  `DS:72C4`.

The F2 map display uses the exploration words to distinguish cells and splits
the first cell byte into high and low nibbles. The high nibble selects one of
16 map connection/shape frames, while the low nibble selects a location kind.
The screen uses the remaining bytes as text selectors for at least kinds
`0x6` and `0xA`. The manual independently says explored cells are gold,
unexplored cells gray, stations and communication locations show verse
references, and room markers use P, J, T, C, and V. Kept the field names
conservative because individual connection-bit directions, the complete kind
enumeration, and the general meanings of parameters A and B remain open.

Queried `MAP.ART` with the artwork renderer. It is archive index 12, expands
to 38,490 bytes, and contains 63 frames: a 189×167 background, small map
glyphs, and later UI assets. An attempted one-off import of `parse_art` from
`render_art` failed because that is not the module's public parser name; the
supported command below succeeded and supplied the needed frame inventory:

```sh
tools/render_art.py build/dd1/all/012_MAP.ART --list
```

Compared each supplied save's live grid at file offsets `0x4C0..0x7C0` with
all 21 archive maps. `SV3` and `SV4` are closest to—and exactly identify as—
`CE.MAP`, with only four changed fields: `(2,0)` parameter B changes
`38->00`, `(0,1)` parameter A changes `37->00`, `(1,1)` packed byte changes
`A2->AB`, and `(2,1)` packed byte changes `E5->EB`. The last two retain their
connection nibbles and change their location kind to B. The normalizer at
`0x0457` performs those kind changes; it also includes a transition from kind
6 to A that moves parameter B to A and clears B. Other supplied saves have
zeroed grids and cannot be identified from this field. Reported this closed
loop between the archive map and saved mutable state.

### World-map inspector and documentation

Added executable `tools/inspect_map.py`. It validates a level/difficulty
identifier, extracts the selected member directly from `DD1.DAT`, requires
the exact 768-byte size, exposes row-major coordinates and the packed nibbles,
prints a compact kind grid, optionally lists nonzero cells, and compares a
resource against the live world map in a state save.

Added `tests/test_inspect_map.py` with five tests. They prove the complete
21-map level/difficulty cross product and exact sizes, a row-major `CE.MAP`
coordinate regression, the four `SV3` field mutations, all seven level
letters supplied to opcode `0x78`, and rejection of bad sizes, names, and
coordinates. Added semantic names for opcodes `0x77`, `0x78`, `0x7B`,
`0x7C`, `0x7F`, `0x87`, `0x88`, and `0x89` to `inspect_bin.py`, and added
the four recovered map-function names to `analysis/cb.rz`.

The first focused run was:

```sh
git status --short
python3 -m unittest tests.test_inspect_map tests.test_inspect_bin -v
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

All 14 focused tests passed, but the inspector invocation failed with
`Permission denied` because its executable bit had not yet been set. Reported
that the format tests passed and that only the missing executable bit failed,
then ran:

```sh
chmod +x tools/inspect_map.py
tools/inspect_map.py \
  CB/DD1.DAT --map CE --compare-save CB/DDGAMES.SV3
```

The command printed the 16×16 low-nibble grid and the four expected save
differences.

Added `docs/src/world-maps.md` and linked it from the book summary. The chapter
documents resource naming, cell addressing, known fields, mutable runtime
state, exploration bits, map-screen behavior, save correlation, tool usage,
relevant functions, and explicitly open semantics. Updated the scene-bytecode
command table, save-format chapter, static-analysis summary and function map,
README inspector instructions, and `PLAN.md`. Marked world-map recovery and
its inspector complete while leaving entities, conversations, combat, and
progression open. Reported that documentation would distinguish proved
layout and lifecycle from still-unknown parameter meanings and bit
directions.

Ran the full verification:

```sh
git diff --check
git diff --stat
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
mdbook build docs
test -f build/docs-book/world-maps.html
rizin -q -b 16 -e scr.color=false \
  -i analysis/cb.rz \
  -c 'afl~map_; afl~show_map_screen; q' \
  build/analysis/CB_UNPACKED.EXE
```

All 62 tests passed in 2.226 seconds, all Python sources compiled, mdBook
built the new world-map page, the diff check was clean, and Rizin loaded and
listed all four added symbols at their expected offsets. This world-map pass
is not committed because the user has not requested a checkpoint yet.

Performed a final review that included untracked files, which are omitted by
ordinary `git diff --stat` output. Rebuilt the book, reran all 62 tests (all
passed in 2.201 seconds), checked every changed path for trailing whitespace,
listed line counts for the three new files, and displayed the inspector's
`--help` output. The final status contains nine modified tracked files and the
three intended new files: the world-map chapter, inspector, and focused test
module. No whitespace errors were found.

### World-map commit preparation

At the user's request, prepared the completed world-map pass for a commit.
Ran `git status --short`, `git diff --check`, and `git diff --stat`, then
reviewed the tracked plan, README, Rizin symbols, book links and chapters,
opcode-name additions, and all three new files. Confirmed that the 12 paths
form one cohesive change covering the recovered map format, runtime behavior,
save correlation, reproducible inspector, tests, symbols, and documentation.
The whitespace check was clean, and the most recent full verification remains
62 passing tests plus a successful mdBook build.

Staged the 12 intended paths and ran `git diff --cached --check`; it passed.
The staged summary contained 716 insertions and 8 deletions. Created the
requested checkpoint with subject `map: Recover world-state format` and a
detailed five-paragraph body covering the resource set, runtime evidence,
conservative inspector model, save correlation, tests, and documentation.
Verified the initial message with `awk`; every line is at most 72 characters.
Added this final commit action to the log and amended it into the same
checkpoint.

## 2026-07-15: script state and progression

### Initial state-block inventory

Continued with the next open game-system slice: player state, progression,
and the script commands which operate on them. Began by checking the worktree,
recent commits, plan, README, existing save documentation, scene-bytecode
notes, executable symbols, and the two primary 200-byte blocks already
identified in each save. Used commands including:

```sh
git status --short
git log --oneline -5
rg -n "primary|727a|7bf2|variable|faith|flag" \
  PLAN.md README.md analysis docs/src tools tests
xxd -g 2 -l 200 CB/DDGAMES.SV0
xxd -g 2 -s 200 -l 200 CB/DDGAMES.SV0
```

Examined initialization and references to `DS:727A` and `DS:7BF2` with
Rizin, saving larger listings under the ignored `build/analysis/` directory:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'aaa; axt @ 0x727a; axt @ 0x7bf2; q' \
  build/analysis/CB_UNPACKED.EXE
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'aaa; pdr @ 0x1191; q' build/analysis/CB_UNPACKED.EXE
```

Function `0x1191` sets `CX=0x64`, `DI=0x727A`, clears `AX`, and executes
`rep stosw`. This proves that the primary live block is 100 words rather than
an opaque 200-byte structure. The save snapshot at file offset `0x000` maps
to `DS:7BF2`, while the live copy at file offset `0x0C8` maps to `DS:727A`.

Initially described opcode `0x1F` too broadly and assigned the next operation
to `0x20`. That interpretation treated Rizin's decimal switch labels as
hexadecimal. Corrected the mistake before changing the parser: `0x1E` copies
a variable, `0x1F` assigns an immediate, `0x20` branches on zero, and `0x21`
branches on nonzero. Reported both the false start and the correction.

### Variable opcode family

Dumped the interpreter's switch handlers and direct byte ranges, then traced
the shift-and-index sequence used for variable operands:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'aaa; pdr @ 0x451b; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/variable-opcode-handlers.txt
rizin -q -b 16 -e scr.color=false \
  -c 'pD 8192 @ 0x451b; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/variable-opcode-linear.txt
```

Some Rizin listings crossed analyzed data or incorrectly inferred function
boundaries and displayed invalid instructions. Direct bytes, handler control
flow, and the complete BIN corpus were therefore compared before assigning
semantics. Recovered this core family:

- `0x1E..0x21`: copy, assign, branch on zero, branch on nonzero.
- `0x22..0x29`: equality, inequality, signed greater-than, and signed
  less-than branches using variable or immediate right operands.
- `0x2A..0x31`: addition, subtraction, signed multiplication, and signed
  division using variable or immediate right operands.
- `0x32..0x33`: increment and decrement.
- `0x8F..0x90`: bitwise AND with a variable or immediate.

The encoded references are even byte offsets within the 200-byte block. The
interpreter shifts each reference right once before indexing. A Python corpus
scan over all known executable regions in all 62 BIN resources found 39 of
the 100 slots in use and no odd or out-of-range core-variable operands. The
scan was saved as `build/analysis/script-state-usage.txt`.

An initial ad hoc scan passed a string to `DD1Archive.from_path` and failed
with `AttributeError: 'str' object has no attribute 'read_bytes'`. Re-ran it
with a `Path`. Attempts to render `247_GANTRY`, `242_FIRST`, and `296_ROBOT`
also failed because those archive indices were guessed incorrectly. Listing
the archive found the correct member paths: `317_GANTRY`, `325_FIRST`, and
`313_ROBOT`.

`FIRST.BIN` establishes initial gameplay values: X is zero, Y is six, one
unidentified variable is eight, state flag `0x36` is set, faith is `0x2710`
(10,000), and the current map cell is processed. Cross-references identify
the following live fields with high confidence:

- variable 0: difficulty (`0` easy, `1` normal, `2` difficult);
- variables 11 and 12: current map X and Y;
- variable 16: current map level letter;
- variables 17 and 18: current cell parameters A and B;
- variable 21: faith in hundredths of one percent.

### Flags, faith, and text state

Traced helpers at `0x43F5`, `0x4413`, and `0x4433`. Words 3 through 10 of
the primary state also form a 128-bit flag bank. The test helper selects word
`identifier >> 4` and mask `1 << (identifier & 15)`; the other helpers set
or clear the same bit. Scene opcodes `0x73..0x76` branch on clear/set and
clear/set a flag. Corpus analysis found 78 identifiers through `0x55`.

`process_current_map_cell` clears the first three flag words (`0x00..0x2F`)
and rebuilds them from the current cell and its neighbors. Flags `0x30` and
above survive this transient rebuild. UI checks establish these powerups:

- `0x30` sword, `0x31` shield, `0x32` no-trap protection;
- `0x33` candle and `0x34` flight.

Seven victim scene scripts set distinct rescue flags: JELO `0x3A`, FEAR
`0x3B`, CULT `0x3C`, LAW `0x3D`, RICH `0x3E`, DENY `0x3F`, and NAGE `0x40`.
`GANTRY.BIN` tests all seven and mirrors set members to `0x42..0x48` before
the Unibot sequence. The exact later meaning of that mirror bank remains
open and was not overnamed.

Traced `reduce_faith` at `0x3979`, called by scene opcode `0x81`. It skips the
loss while a no-combat state is active, halves the operand on Easy, preserves
it on Normal, and multiplies it by four on Difficult. The status renderer
clamps faith to `0..10000`, divides by 100, and presents a percentage.

The helpers at `0x5B24`, `0x5B76`, and `0x5BBF` get, set, and clear one of 66
text-descriptor state bytes. Opcodes `0x36..0x39` update them or branch on
their state; `0x88` clears all 66. This connects dialogue and study records
to scene progression, although the exact user-visible meaning varies by
record and remains documented conservatively.

Compared both primary blocks in every supplied save with `od`, `xxd`, and a
small Python decoder. All snapshots and live blocks have map-level variable
16 equal to `-1`. Live variable 28 contains
`191, 189, 192, 195, 193, 195, 192, 195, 204`; `SV9` also has variable 27
equal to five. None of the supplied blocks has an active state flag. Variables
27 and 28 were left unnamed because the evidence only supports their being
general scene temporaries.

### Inspectors, tests, and documentation

Extended `tools/inspect_save.py` with exact-size decoding of the 100 signed
words, the embedded flag bank, named fields, powerups, and victim flags. The
new `--variables` view prints named, nonzero, or changed variables without
misrepresenting the flag-bank words as independent values. Extended
`tools/inspect_bin.py` with the recovered opcode names and renders recognized
operands as, for example, `var[21:faith]@0x002a`.

Added focused tests for signed values, exact sizes, supplied-save
regressions, the complete-corpus even-offset invariant, semantic opcode
names, and the seven exact rescue flags. The first test edit accidentally
placed helper functions after `unittest.main()` and referenced
`self.decoded_regions` from another test module. The focused run produced
three errors. Corrected the imports and iterated archive BIN members and
their known executable regions directly; the next focused run passed all 22
tests.

Named the recovered executable functions in `analysis/cb.rz`. Added the
`Script State and Progression` mdBook chapter and linked it from the summary.
Updated the save-format, scene-bytecode, and static-analysis chapters, plus
the README and living plan. Reported that the recovered system consists of
three coordinated mechanisms: 100 signed script words, a 128-bit flag bank,
and 66 text-state bytes, with static proof for powerups, victim flags, and
faith handling.

### Script-state commit preparation

At the user's request, inspected the unstaged scope with:

```sh
git status --short
git diff --stat
git diff --check
git diff -- PLAN.md README.md docs/src/SUMMARY.md docs/src/game-state.md
git diff -- tools/inspect_bin.py tools/inspect_save.py \
  tests/test_inspect_bin.py tests/test_inspect_save.py
```

The diff check was clean. Found that the new state-flag helper row followed
the later bytecode-interpreter row in the high-confidence function table and
reordered those two rows before final validation. Reported that the set is a
cohesive, still-unstaged script-state change and that the chronological log
would include the failed experiments and the corrected opcode
interpretation.

Ran the complete verification set:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
mdbook build docs
test -f build/docs-book/game-state.html
tools/inspect_save.py CB/DDGAMES.SV9 --variables \
  > build/analysis/inspect-save-variables.txt
tools/inspect_bin.py build/dd1/all/325_FIRST.BIN \
  > build/analysis/inspect-first-bin.txt
rg -n 'faith|set_variable|state_flag' \
  build/analysis/inspect-first-bin.txt
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'afl~initialize_script_state; afl~reduce_faith; afl~state_flag; \
afl~text_record_state; q' build/analysis/CB_UNPACKED.EXE
git diff --check
```

All 68 tests passed in 2.228 seconds, every Python source compiled, mdBook
built `game-state.html`, and the whitespace check passed. The FIRST listing
showed the expected annotated map assignments, flag `0x36`, and faith
assignment `0x2710` to `var[21:faith]@0x002a`. Rizin loaded all eight added
symbols: script-state initialization, faith reduction, three flag helpers,
and three text-record-state helpers. Reported these results before staging.

Staged the 13 intended paths and ran `git diff --cached --check`; it passed.
The staged change contained 719 insertions and 15 deletions. Created the
requested checkpoint with subject `state: Recover script progression model`
and a four-paragraph body explaining the primary-state model, recovered
opcode families, named progression fields, conservative inspectors, tests,
and documentation. Added this final commit action to the progress log and
amended it into the same checkpoint.

## 2026-07-15: scene display objects

### Selecting and inventorying the subsystem

Continued with the open entity, conversation, and combat work. Chose to start
with scene objects and encounter presentation because the complete BIN
operand schema was already available. Checked the clean worktree, current
plan, recent commits, existing symbols, scene-bytecode notes, and every prior
mention of combat, encounters, entities, dialogue, victims, and powerups:

```sh
git status --short
sed -n '45,80p' PLAN.md
rg -n -i \
  "combat|encounter|entity|enemy|robot|conversation|dialog|victim|attack" \
  docs/src analysis/cb.rz README.md tools tests
git log -4 --oneline
```

Reported that the intended path was to inventory scene opcodes and runtime
structures, correlate them across the executable and BIN corpus, and use
visible, silent QEMU debugging where static evidence needed confirmation.

Dumped the 145-word dispatch table at `0x59AB` and the interpreter body:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'px 320 @ 0x59ab; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/bin-dispatch-table.txt
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'pdr @ execute_bin_commands; q' \
  build/analysis/CB_UNPACKED.EXE
```

Parsed the little-endian handler words into an opcode-to-handler map. Then
scanned all 64 known executable regions in the 62 BIN resources to count
each still-unnamed opcode and collect resource, offset, and operand examples.
The first Python attempt had a mismatched bracket in a formatted expression
and failed with `SyntaxError`. The corrected attempt used the nonexistent
`DD1Archive.members` attribute and failed with `AttributeError`; changed it
to the documented `entries` collection and completed the scan.

The corpus separated into dialogue-heavy and combat-heavy command clusters.
Reported that dialogue was concentrated around `0x44..0x4F`, `0x59..0x5B`,
and `0x85/0x86`, while the `COMBAT*.BIN` programs use another cluster. Began
with the former because its strings and seven victim scripts supply stronger
independent labels.

### From dialogue handlers to the display table

Saved direct disassemblies of the dialogue and record handlers:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'pD 1000 @ 0x50a2; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/dialogue-handler-disassembly.txt
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'pD 850 @ 0x54dc; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/dialogue-record-handlers.txt
```

Rendered complete listings for `NAGE.BIN` and the other victim programs.
An early attempt guessed archive prefixes `004_TITLE.BIN` and
`331_LOGO.BIN`; both failed with `FileNotFoundError`. Used `find` to obtain
the actual extracted paths `332_TITLE.BIN` and `001_LOGO.BIN`, then repeated
the listings successfully.

Handlers `0x85` and `0x86` multiply their operand by ten and set or clear bit
7 at `DS:A2B2 + index*10`. Neighboring commands use the same stride and
change adjacent bytes. Initially described this as a likely entity/object
table but explicitly withheld names until its renderer was traced; the high
bit could have represented flipping rather than visibility.

Searched the whole load-module disassembly for every indexed reference and
disassembled the creation and update paths around `0x3AFF`, `0x4A5C`, and
`0x55EC`. This established a record base of `DS:A2AC`, not `A2B2`:
`A2B2` is record offset `+6`. The record count is at `DS:00E2`, the stride is
ten bytes, and the updater rejects counts above 100.

The creation handlers append these type values:

- opcode `0x02` creates a command-thread record of type `0x02`;
- opcode `0x03` creates a direct record of type `0x03` with scale `0x0100`;
- opcodes `0x04` and `0x43` create direct records of type `0x43` with an
  explicit scale;
- opcode `0x06` starts animation state and creates a type-`0x06` record.

Disassembled the direct renderer at `0xBCAC`. Its arguments prove that the
three words are signed X, signed Y, and 8.8 scale; the four bytes are render
flags, one-based frame, ART slot, and record type. Frame zero suppresses the
render slot. Flags bit 7 suppresses drawing for values `0x80..0xEF`, while
bits 1 and 2 flip the axes. This resolved `0x85` as hide and `0x86` as show.
Opcodes `0x65` and `0x66` respectively clear consecutive frame bytes and
increment them with an inclusive minimum/maximum range.

Reported the key semantic boundary: the table is a scene display list shared
by characters, props, animation groups, and command threads. It is not yet
evidence for a distinct gameplay enemy/health model.

### Visible QEMU memory validation

Launched the existing trace mode:

```sh
./run.sh --trace-dos
```

This retained the Cocoa window requested by the user and used the existing
`-audiodev none` configuration, so the diagnostic run was visible and
silent. After the Bridgestone logo scene appeared, sent these commands to the
monitor socket:

```text
info registers
pmemsave 0 1048576 build/qemu-trace/entity-title-physical-1m.bin
screendump build/qemu-trace/entity-title-screen.ppm
```

The filename says `title`, but the screenshot confirmed that the capture was
the earlier Bridgestone `LOGO.BIN` scene. QEMU reported `DS=14E1`, placing
`DS:00E2` at physical `0x14EF2` and `DS:A2AC` at physical `0x1F0BC`.
Decoded the live table with `xxd` and Python. The count was 13. Records 7–9
were:

```text
7: x=303 y=0 scale=0x0100 flags=1 frame=4 art=1 type=0x43
8: x=3   y=0 scale=0x0100 flags=1 frame=4 art=0 type=0x43
9: x=3   y=0 scale=0x0100 flags=1 frame=1 art=0 type=0x43
```

These are byte-for-byte matches for the three `LOGO.BIN` opcode-`0x43`
definitions at `0x0122`, `0x012C`, and `0x0136`. The live type order also
matches four animation records, three thread records, the three direct
objects, another animation record, and two final thread records. Reported
that all 13 definitions align, then stopped QEMU cleanly with `quit` and
waited for the process to exit.

### Inspector, tests, and documentation

Extended `tools/inspect_bin.py` with conservative semantic names for the
definition, frame-control, hide, and show opcodes. Added a typed static
display-definition model and `--objects`, which appends source offsets,
types, and known definition fields in linear order. The output warns that
branches can skip or repeat definitions, so the summary is not presented as
a general control-flow simulation.

Added tests for the recovered opcode names and a QEMU-correlated LOGO
regression. The regression requires exactly 13 definitions, checks the full
type order, and checks all direct fields in record 7. Ran:

```sh
python3 -m unittest tests.test_inspect_bin -v
tools/inspect_bin.py build/dd1/all/001_LOGO.BIN --objects
```

All 14 focused tests passed. The inspector printed the 13 expected records,
including `display[07]` with the exact captured fields.

Named the reset, update, render-slot release, and direct-object renderer in
`analysis/cb.rz`. Added the `Scene Display Objects` chapter and linked it in
the book. Updated the bytecode and static-analysis chapters, README, and
living plan. Split the broad remaining task so the recovered display system
is complete while gameplay entities, conversation flow, combat, and other
progression remain open.

Ran the complete verification set:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh
mdbook build docs
test -f build/docs-book/scene-objects.html
tools/inspect_bin.py build/dd1/all/001_LOGO.BIN --objects \
  > build/analysis/logo-display-records.txt
rg '^display\[' build/analysis/logo-display-records.txt
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'afl~scene_display; afl~render_slot; q' \
  build/analysis/CB_UNPACKED.EXE
git diff --check
```

All 70 tests passed in 2.259 seconds, every Python source compiled, `run.sh`
passed shell syntax checking, and mdBook built `scene-objects.html`. The
inspector emitted all 13 expected LOGO definitions. Rizin loaded the reset,
display update, direct-object render, and render-slot release symbols at
`0x3AD2`, `0x3AFF`, `0xBCAC`, and `0xB948`. The whitespace check passed.
Reported these results and that the completed slice remains uncommitted until
the user requests a checkpoint.

### Final display-field correction

During final diff review, rechecked the renderer's stack arguments against
the three distinct bytes in LOGO records 7–9. The first live record had value
one in both byte `+6` and byte `+8`, which had hidden an ordering error in the
initial interpretation. The renderer indexes the loaded-ART table with byte
`+6`, reads the frame from byte `+7`, and derives flip flags from byte `+8`.
Thus byte `+6` is the ART slot plus high hidden marker, while byte `+8` holds
the separate render flags. Opcodes `0x85/0x86` still mean hide/show, but they
set/clear the ART-slot byte's high bit rather than a flags-byte bit.

Reported the correction before handoff. Corrected the inspector operand
mapping, tests, scene-object chapter, bytecode table, and static summary.
Added an assertion for LOGO record 8, whose distinct values (`art=1`,
`flags=0`) prevent the two fields from being swapped again. The corrected
QEMU interpretation is:

```text
7: x=303 y=0 scale=0x0100 flags=1 frame=4 art=1 type=0x43
8: x=3   y=0 scale=0x0100 flags=0 frame=4 art=1 type=0x43
9: x=3   y=0 scale=0x0100 flags=0 frame=1 art=1 type=0x43
```

An attempted consistency search put Markdown backticks inside a
double-quoted shell pattern. Bash treated `` `+8` `` as command substitution
and printed `/bin/bash: +8: command not found`. The search had `|| true`, did
not mutate files, and the validation block that followed still ran. Reported
the harmless command error and repeated the search with a single-quoted
pattern.

Reran all 70 tests after the field correction; they passed in 2.290 seconds.
Python compilation, mdBook, the corrected inspector output, all four Rizin
symbols, and `git diff --check` also passed. In particular, inspector records
8 and 9 now show `art_slot=0x0001` and `flags=0x0000`, matching the raw QEMU
bytes and their BIN operands.

### Preparing the display-object checkpoint

The user requested a commit. Inspected the worktree with `git status
--short`, checked whitespace with `git diff --check`, reviewed the diff
statistics and path list, and inspected the four most recent commits. The
whitespace check passed. The intended checkpoint contains ten paths: the
plan, README, Rizin symbol script, book summary, progress log, scene-bytecode
and static-analysis chapters, new scene-object chapter, inspector, and its
tests. The previously recorded verification remains current: all 70 tests
pass, Python sources compile, mdBook builds, the four Rizin symbols load, and
the corrected 13-record LOGO interpretation matches the QEMU dump.

Staged those ten paths explicitly, then ran `git diff --cached --check`,
`git status --short`, `git diff --cached --stat`, and `git diff --cached
--name-only`. The staged check passed and confirmed that no unrelated path
was included. Created the checkpoint with subject `scene: Recover
display-object runtime`; its detailed message records the runtime model,
inspector support, QEMU correlation, field-order regression coverage, and
documentation rationale. Amended this final log entry into the same commit
so the repository records the commit operation as part of the append-only
investigation history.

The first post-commit message audit used `git log -1 --pretty=%B` with an
`awk` line-length check. It found seven body lines between 73 and 76
characters, exceeding the repository's 72-character rule. The audit stopped
the chained status and summary checks before they ran. Rewrapped the message
without changing its meaning, staged this note, and amended the checkpoint
again before repeating the complete verification.

## 2026-07-15: Resuming gameplay-system analysis

The user asked to continue after the display-object checkpoint. Confirmed
that the worktree was clean, then read the living plan, README, tail of this
log, scene-bytecode chapter, static-analysis chapter, and complete Rizin
symbol script. The next open bounded area is the relationship among gameplay
entities, conversation, combat, and the remaining unidentified BIN handlers.
The investigation will begin with static handler and corpus correlation, then
use visible, silent QEMU evidence where live state is needed.

### Static dialogue-handler and corpus analysis

Parsed all 145 entries in the BIN dispatch table and compared the handlers
around the dialogue-heavy opcode cluster. Saved focused Rizin output under
the ignored `build/analysis/` tree, including `bin-dispatch-hex.txt`,
`conversation-handlers.txt`, `conversation-state-xrefs.txt`,
`choice-ui-functions.txt`, `dialogue-ui-disassembly.txt`, and
`study-selection-flow.txt`. Representative commands were:

```sh
rizin -q -b 16 -e scr.color=false \
  build/analysis/CB_UNPACKED.EXE \
  -c 's 0x51b7; pd 220; q' \
  > build/analysis/conversation-handlers.txt
rizin -q -b 16 -e scr.color=false \
  build/analysis/CB_UNPACKED.EXE \
  -c 'axt @ 0xb428; axt @ 0xb116; axt @ 0x8934; axt @ 0x7cba; q' \
  > build/analysis/conversation-state-xrefs.txt
rizin -q -b 16 -e scr.color=false \
  build/analysis/CB_UNPACKED.EXE \
  -c 's 0x2556; pd 300; s 0x2933; pd 300; q' \
  > build/analysis/dialogue-ui-disassembly.txt
```

The handler at `0x51B7` clears the word at `DS:B428` and dialogue state at
`DS:8934`. Handler `0x51C6` appends a record at `DS:B116 + 6*count` containing
an absolute BIN target word and a far pointer to its inline text. Handler
`0x5257` enters dialogue state 1 and suspends the current scene thread.
Function `0x2556` is the generic text-menu renderer and selection loop;
`poll_input_event` ultimately writes the selected record's target to
`DS:7CBA`. Handler `0x51FF` removes the first record with a matching target
and shifts all later six-byte records, although no recovered BIN uses that
opcode.

Wrote short Python analyses against the existing decoded command model to
count opcodes across all 64 known code regions and list their resource,
source offset, target, and string operands. The results were:

```text
0x44 add choices:        40 uses in 6 resources
0x45 clear choices:      11 uses in 6 resources
0x46 present choices:    14 uses in 7 resources
0x14 adversary dialogue: 10 uses, all in FACE.BIN
0x48 character dialogue: 306 uses in 12 resources
0x4E Captain channel:    281 uses in 25 resources
```

The differing choice counts show that scripts conditionally add entries and
reuse menus; a linear command inventory is useful evidence but not a full
control-flow reconstruction. The three string commands share handler
`0x52A3`. Their dominant uses establish separate adversary, character, and
Captain Bible presentation channels, but `0x4E` is also reused for captions
and system text, so the documentation does not claim an enforced speaker
type.

Decoded the study-request path separately. Opcode `0x7D` stores its byte at
`DS:0066` and the value of its variable operand at `DS:0068`. The prompt
renderer at `0x446F` maps `0x2A` to the `*` victim-conversation component,
`0x64` to the `P` paraphrase, and other nonzero values to the `L` lie.
Opcode `0x49` sets `DS:79F0` and suspends the thread. The main loop calls the
study browser through `0x834E`; it clears flags `0x14` and `0x15`, sets
`0x14` after the expected descriptor is selected, and sets `0x15` on the
nonmatching departure path. Saved focused `NAGE.BIN` and `JELO.BIN` listings
as `build/analysis/nage-listing.txt` and `jelo-listing.txt`. `NAGE.BIN`
demonstrates the complete configure, request, suspend, and result-branch
sequence.

The initial attempt to add all new names to `analysis/cb.rz` in one patch did
not apply because the expected `poll_input_event` context appeared in a
different order. Inspected the file with numbered lines and applied smaller
patches. The script now names `show_study_bible`, `select_from_text_menu`,
`show_dialogue_message`, `render_study_prompt`, and
`handle_study_bible_request`, plus the identified dialogue and suspension
handlers.

### Live BOSS choice-table correlation

Started the normal diagnostic VM with:

```sh
./run.sh --trace-dos
```

This retained the requested Cocoa window and the existing silent audio
backend. Used QEMU monitor `sendkey ret` commands to advance through the title
sequence into the BOSS conversation. Captured screenshots and physical
memory with commands of this form:

```text
screendump build/qemu-trace/conversation-menu2.ppm
pmemsave 0 1048576 build/qemu-trace/conversation-menu2-physical-1m.bin
info registers
```

The raw PPM was not accepted by the local image-viewing path, so converted it
to PNG with macOS `sips` and inspected the result. This was only a format
conversion of ignored evidence, not an edit to game data. The visible screen
contained the five expected BOSS questions.

At the stable menu, the game data segment was `14E1`. This placed the choice
count at physical `0x20238` and the record table at physical `0x1FF26`. The
count word was five. A Python decoder over the memory capture printed:

```text
0: target=0644 text=4C13:045F
1: target=07E8 text=4C13:0485
2: target=0751 text=4C13:04A5
3: target=0519 text=4C13:04C6
4: target=095C text=4C13:04FE
```

Dereferencing each far pointer in the same physical dump produced, byte for
byte, the five inline strings statically decoded from `BOSS.BIN`:

```text
So what do I do when I get inside?
Can I expect any resistance?
What about the people inside?
Should I expect any problems with my computer bible?
OK!  I'd better go do it!
```

Before selection, `DS:8934` was 1 and `DS:7CBA` was zero. Highlighted the
last choice and selected it, then captured
`conversation-selected.png` and another one-megabyte memory image. The
selected-target word became `0x095C`, dialogue state became 2, and the next
visible line was `Before you go, I think that we should pray.` That string is
the opcode-`0x48` message at the exact static target `0x095C`. Stopped QEMU
cleanly with the monitor `quit` command and waited for the process to exit.

### Choice inspector and documentation

Extended `tools/inspect_bin.py` with conservative semantic names for opcodes
`0x13`, `0x14`, `0x44` through `0x46`, `0x48`, `0x49`, `0x4E`, `0x72`, and
`0x7D`. Added a typed `DialogueChoiceDefinition` model and `--choices` output
that lists the source, absolute target, and decoded text for every linear
opcode-`0x44` definition. The output warns that branches can alter the menu
presented at runtime.

Added three focused regression tests: semantic opcode names, the exact five
BOSS target/text pairs correlated in QEMU, and a complete-corpus total of 40
choice definitions while respecting mixed code regions. Ran:

```sh
python3 -m unittest tests.test_inspect_bin -v
tools/inspect_bin.py build/dd1/all/327_BOSS.BIN --choices
```

All 17 focused tests passed in 0.116 seconds, and the inspector printed the
five expected BOSS records.

Added the `Conversation Flow` chapter and linked it from the book summary.
Updated the scene-bytecode, static-analysis, script-state, and text-format
chapters; README now demonstrates `--choices`; and the plan now marks choice
flow, dialogue channels, and study integration complete while leaving combat,
gameplay entities, and other progression open. The first combined
documentation patch failed because its expected context split one sentence
differently in `text-formats.md`; reapplied the changes against the exact
numbered context. This failure changed no file contents.

### Validation and symbol-script correction

Ran the complete validation set in three independent groups:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh
mdbook build docs
test -f build/docs-book/conversation-flow.html
tools/inspect_bin.py build/dd1/all/327_BOSS.BIN --choices \
  > build/analysis/boss-dialogue-choices.txt
git diff --check
```

All 73 tests passed in 2.263 seconds. Every Python source compiled, `run.sh`
passed shell syntax checking, mdBook built `conversation-flow.html`, the BOSS
inspector output contained all five expected choices, and the whitespace
check passed.

The first Rizin symbol audit exposed a script defect despite returning exit
status zero. The eight new handler lines used `f` to create flags at addresses
where recursive analysis had already created switch-case flags, so Rizin
printed name-collision errors. Replaced those lines with `fr` commands that
rename the existing `case.0x4552.*` flags. A second audit initially used bare
`f` to list flags; current Rizin requires `fl`, so that audit itself printed a
usage error unrelated to the symbol script. Repeated it correctly with:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'afl; fl; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/conversation-symbol-audit.txt \
  2> build/analysis/conversation-symbol-audit.err
rg 'show_study_bible|select_from_text_menu|show_dialogue_message|\
render_study_prompt|handle_study_bible_request|bin_handler_' \
  build/analysis/conversation-symbol-audit.txt
```

The corrected output contains all five conversation/study functions and all
eight handler flags at their expected addresses, with no collision or usage
errors from the script. Ran `git diff --check` again after the correction; it
passed.

### Preparing the conversation-flow checkpoint

The user requested a commit. Inspected `git status --short`, ran
`git diff --check`, reviewed the diff statistics and path list, and read the
four most recent commit subjects. The whitespace check passed. The intended
checkpoint contains the plan, README, Rizin names, book summary, progress
log, scene-bytecode, static-analysis, script-state, and text-format updates,
the new conversation-flow chapter, the BIN inspector, and its tests. The
current verification remains valid: all 73 tests pass, Python sources
compile, `run.sh` passes shell syntax checking, mdBook builds the new chapter,
the BOSS choice inventory matches QEMU, and all eight handler names load in
Rizin.

Staged those 12 paths explicitly, then ran `git diff --cached --check`,
`git status --short`, `git diff --cached --stat`, and
`git diff --cached --name-only`. The staged check passed and confirmed that
no unrelated path was included. Created checkpoint `a0ed22e` with subject
`scene: Recover conversation runtime` and a detailed body covering the
runtime model, QEMU evidence, inspector, regression tests, and documentation.

The immediate `awk` audit of `git log -1 --pretty=%B` found three body lines
of 250, 195, and 126 characters. Multiple `git commit -m` paragraph arguments
had not wrapped their contents, so the message violated the repository's
72-character rule. The commit content itself was correct. Added this audit to
the log and amended the same checkpoint with explicitly wrapped body lines,
then repeated the message, status, and cleanliness checks.

## 2026-07-15: Combat and gameplay entities

The user asked to continue after checkpoint `953f414`. Confirmed that the
worktree was clean and reviewed the living plan, the scene-bytecode command
table, the display-object boundary, and earlier opcode-clustering notes. The
next open slice is the combat-heavy BIN command cluster and any executable
runtime structures that connect it to display records, collision, faith
damage, and encounter completion. The investigation begins with static corpus
and handler analysis; visible, silent QEMU will be used only where live state
is needed to distinguish competing interpretations.

### Combat-program corpus

Listed and decoded `COMBAT1.BIN` through `COMBAT7.BIN`, then counted their
commands, opcode-`0x06` animation headers, contiguous opcode-`0x07` steps, and
opcode-`0x3A` definitions. The seven programs contain 5,443 commands in
35,449 bytes, 214 animation sequences, 2,596 steps, and 27 selectable-action
definitions. Six programs define four actions and `COMBAT6.BIN` defines
three. Selector counts are seven `.11`, six `.12`, seven `.13`, and seven
`.14` strings.

Compared each program's resource loads. All seven load `COMBTAGS` first and
`COMBAT` second, followed by encounter-specific artwork: `BIG*`, `HELMET`,
`MANTIS*`, `SNAKE*`, `CRAB`, `GUARD*`, or `ZAP*`/`SPRK`. Attempted to render
`162_COMBTAGS.ART` with a guessed `054_ZAP.PAL`; that command failed because
the guessed path does not exist. Located the real `019_ZAP.PAL` member and
rendered all four frames under the ignored
`build/graphics/combat-tags/` directory. Visual inspection identified the
frames as `ATTACK`, `DEFEND`, `RETREAT`, and `COMBAT`, establishing the
`.11` through `.14` mapping independently of action control flow.

Decoded the exact `COMBAT7.BIN` action definitions:

```text
0x0C06 -> 0x0EC8  (151,  61)  .11 ATTACK
0x0C11 -> 0x0EAB  (136, 153)  .12 DEFEND
0x0C1C -> 0x1053  ( 15, 167)  .13 RETREAT
0x0C27 -> 0x0FA7  (157,  62)  .14 COMBAT
```

### Executable tables and handlers

Used Rizin disassembly and cross-references around the interpreter handlers,
then followed their callees into the scene update and input paths. Opcode
`0x3A` appends ten-byte records at `DS:480E`, counted at `DS:6EA4`. The fields
are an absolute BIN target, X, Y, current-BIN selector offset, active byte,
and one padding byte. Opcodes `0x3B` and `0x3C` set and clear the active byte.
The routine at `0x6A23` searches active records near the pointer and draws the
selected label; the keyboard search is at `0x8558`. Selection dispatches the
record's target through `0x7A5C`.

Animation definitions create 12-byte slots at `DS:6EBA`, counted at
`DS:B114`. Recovered first-step and current-step BIN offsets, the sequence
interval, linked/parent index, mode/state, and render/display slot. The final
two timing bytes remain only partly understood. The nine-byte step following
an opcode-`0x07` is frame, ART slot, signed X, signed Y, 8.8 scale, and flags.
Followed the linked-transform resolver at `0x3B9B`, single-slot renderer at
`0x3D08`, all-slot updater at `0x3DA8`, start routine at `0x3F59`, and stop
routine at `0x3FDF`. The updater implements modes 1 through 10 and advances
the cursor by the ten-byte opcode-plus-payload step size.

Recovered additional interpreter operations from their handlers:

- `0x08`, `0x5F`, and `0x09` start, start-linked, and stop animations;
- `0x3F` waits for an active animation and `0x80` branches on its state;
- `0x41` and `0x42` enable and disable selectable-action input;
- `0x3E` starts a true BIN scheduler slot at an absolute target and `0x61`
  stops a slot;
- `0x59` waits for digital playback, using a simulated timer without a
  digital driver;
- `0x60` is a no-op which shares the main interpreter continuation;
- `0x82` stores the runtime pseudorandom value modulo an immediate in a
  selected script variable.

The true BIN scheduler uses 16-byte records beginning at `DS:8D44`, with the
current index at `DS:7DB4`. Proven fields are cursor `+0`, delay/timer
`+0x0C`, active byte `+0x0E`, and status `+0x0F`. This is distinct from the
other 16-byte record family created by opcode `0x02` and connected to a
type-`0x02` display record. The evidence therefore supports a script-driven
combat system composed of actions, animations, random branches, progression
flags, and faith loss. It does not support labeling a display record or
action record as an enemy-health object.

### Inspector and regression tests

Extended `tools/inspect_bin.py` with conservative names for the recovered
combat/runtime opcodes, typed animation and action definitions, and two new
views. `--animations` groups every opcode-`0x06` header with its immediately
following steps; `--actions` lists source, target, coordinates, selector, and
the four rendered label names. Added variable annotation for the destination
of opcode `0x82` and for the already identified variable operand of opcode
`0x7D`.

Added focused tests for all new semantic names, the exact four
`COMBAT7.BIN` actions, its first animation sequence, and the complete
seven-program corpus totals. The first focused test run failed with three
`NameError` exceptions: an ambiguous patch had accidentally inserted the new
imports below the file's `unittest.main()` call. Inspected the file tail,
moved those imports into the existing import block, removed the stray lines,
and wrapped the affected assertions. Repeated:

```sh
python3 -m unittest tests.test_inspect_bin -v
tools/inspect_bin.py \
  build/dd1/all/337_COMBAT7.BIN --animations --actions
```

All 21 focused tests passed in 0.130 seconds, and the inspector printed 35
animation sequences, 293 steps, and the four expected labeled targets.

### Visible QEMU attempt

Started the game with the required visible Cocoa window and silent audio:

```sh
./run.sh --trace-dos
```

The trace process used session 98634. Advanced from the intro, opened the
Escape menu, checked Load Game, and found all nine labels `EMPTY`. Returned
through TITLE and BOSS dialogue, selected the fifth response (`OK! I'd better
go do it!`), and advanced the following prayer/transition. Automated input
then left a black framebuffer. Repeated register checks remained at
`CS=0D66`, `DS=0000`, `EIP=3E04` in a loaded sound-driver segment rather than
the game's code/data segments. Waiting more than eight seconds did not change
the screen; the most recent DOS trace also ended in that transition.

Captured the ignored transition frames under `build/qemu-trace/`, then sent
`quit` through the monitor and confirmed QEMU exited with status zero. This
run did not reach a verifiable encounter, so no animation, action, or thread
table claim relies on it. A live combat capture remains open.

### Documentation, symbols, and validation

Added the `Combat Runtime` chapter and linked it from the book. It documents
the seven-resource corpus, animation steps and slots, selectable-action
records and labels, true BIN scheduler, synchronization operations, inspector
commands, QEMU boundary, and remaining questions. Updated the scene-bytecode,
scene-display-object, static-analysis, README, and plan material. The plan now
marks the action/animation/thread slice complete while leaving exact combat
outcomes and remaining gameplay entities open.

The first combined `analysis/cb.rz` patch failed because it assumed
`initialize_scene` and `update_scene_threads` were adjacent. Inspected the
numbered file and reapplied the additions against their actual locations. A
later combined scene-bytecode patch also failed because it expected separate
`0x38` and `0x39` rows where the table has one combined row. Reapplied smaller
patches against the exact context. Neither failed patch changed a file.

Named the five animation routines, action overlay, action-key search, and
BIN-thread starter in `analysis/cb.rz`, and renamed the 14 existing switch
case flags for the recovered handlers. Audited the script with:

```sh
rizin -q -b 16 -e scr.color=false -i analysis/cb.rz \
  -c 'afl; fl; q' build/analysis/CB_UNPACKED.EXE \
  > build/analysis/combat-symbol-audit.txt \
  2> build/analysis/combat-symbol-audit.err
```

All requested function and handler names appeared at the expected offsets.
The five-byte standard-error file contains only a terminal progress escape,
not a Rizin analysis or name-collision error.

Generated `build/analysis/combat7-runtime.txt`, checked its four action rows,
and ran the complete validation set:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/*.py tests/*.py
bash -n run.sh
mdbook build docs
test -f build/docs-book/combat-runtime.html
git diff --check
```

All 77 tests passed in 2.319 seconds. Python compilation and shell syntax
checking passed, mdBook generated `combat-runtime.html`, the COMBAT7 inspector
output matched the recovered records, the Rizin symbol audit succeeded, and
the whitespace check passed.

Performed one final consistency pass after completing the progress log:
rebuilt mdBook, reran the 21 focused BIN tests (all passed in 0.134 seconds),
recompiled the two changed Python files, reviewed status and the documentation,
plan, README, and symbol-script diffs, and repeated `git diff --check`. The
book and focused checks remained clean. Left the work uncommitted for review.

### Preparing the combat-runtime checkpoint

The user requested a commit. Rechecked `git status --short` and
`git diff --check`, confirmed that the only changed paths belong to this
combat-runtime investigation, and retained the successful validation results:
all 77 tests pass, the changed Python files compile, `run.sh` passes shell
syntax checking, mdBook builds the new chapter, the COMBAT7 inventory matches
the recovered action records, and the Rizin symbol audit contains every new
name without collision errors. Prepared one checkpoint with the inspector,
tests, symbol map, combat chapter, related documentation, plan, README, and
this append-only activity record.

The first staged `git diff --cached --check` reported one extra blank line at
the end of `combat-runtime.md`. Removed that blank line, recorded the finding
here, and restaged the chapter and progress log before repeating the complete
staged audit.

Created the checkpoint as `a83072d` with subject
`combat: Recover scripted encounter runtime`. The immediate 72-column audit
found three commit-body lines of 73 characters. The subject and committed
content were correct, but the message missed the repository limit by one
column on those lines. Recorded the correction here and amended the same
checkpoint with shorter wrapping.
