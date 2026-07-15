# Environment and Running the Game

## Host tools

The first inventory found:

- QEMU 11.0.2 (`qemu-system-i386` and `qemu-img`)
- Rizin 0.9.1
- mdBook 0.5.3

The host is macOS on Apple Silicon. QEMU therefore runs the i386 guest using
software emulation rather than hardware virtualization.

## Guest operating system

The selected guest is the stable FreeDOS 1.4 release. The FreeDOS project
recommends its LiveCD for installation in a virtual machine. Its published
minimum is an Intel-compatible processor, 640 KiB of memory, and at least a
20 MB hard disk.

The repository-specific setup instructions require a noninteractive build
rather than the FreeDOS installer. `tools/setup_freedos_image.py` downloads and
verifies the official LiteUSB archive, extracts the largest image member,
preserves its boot code and filesystem, and builds a new 1 GiB raw disk with a
single active FAT16 LBA partition.

The base image is:

```text
build/freedos/freedos.img
```

It has a 1 MiB partition offset (LBA 2048), so its mtools path is:

```text
build/freedos/freedos.img@@1048576
```

The base disk remains a clean FreeDOS image. `run.sh` clones it to a separate
persistent play image, copies `CB/` to `C:\CB`, installs CuteMouse from the
LiteUSB package set, and replaces the clone's boot scripts so the game starts
automatically.

## Run the game

From the repository root:

```sh
./run.sh
```

The persistent play disk is
`build/captain-bible/captain-bible.img`. Use `./run.sh --setup-only` to prepare
the disk without opening QEMU or `./run.sh --rebuild` to replace it from the
current `CB/` tree. Rebuilding discards saves stored only in the old play disk.

The QEMU machine provides:

- a Pentium-class i386-compatible CPU with 16 MiB RAM;
- standard VGA in a visible Cocoa window with zoom-to-fit enabled on macOS;
- a PS/2 mouse served through the CuteMouse DOS driver;
- Sound Blaster 16 digital audio; and
- AdLib-compatible FM synthesis.

The supplied `SOUND.1` identifies itself as a Sound Blaster 16 driver, and
`SOUND.2` identifies itself as a Sound Blaster Pro FM driver. These match the
emulated devices.

## Verification result

The base image passed a screenshot-free boot smoke test. A temporary clone
wrote `FREEDOS_READY` to `C:\BOOT.OK` from both patched boot-script paths, and
the marker was read with mtools after QEMU stopped. A separate bounded launch
of the play image reached the Captain Bible title screen at 640×400.

## Initial game requirements

The supplied `MANUAL.TXT` says to change to the installation directory and
run `CB`. It reports that the game needs approximately 500 KiB of conventional
memory. It also documents optional command-line switches and a player name,
which will be investigated in a later phase.
