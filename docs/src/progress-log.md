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
