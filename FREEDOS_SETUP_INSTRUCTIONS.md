# Noninteractive FreeDOS Image Setup

Build a fully noninteractive FreeDOS hard-disk image for QEMU.

Do not automate the graphical/text FreeDOS installer, press keys through install
screens, use OCR, or depend on screenshots. The correct design is to skip the
installer entirely: use the official FreeDOS LiteUSB image as a source of the
boot code and installed filesystem, then construct the target disk from the
host with mtools.

A working reference implementation is available at:

```text
/Users/peter/ai/agi/reverse/tools/setup_freedos_image.py
```

Adapt its image-building algorithm, but remove its project-specific imports,
game-copy support, and custom VGA BIOS integration.

## Requirements

1. Create a Python script at `tools/setup_freedos_image.py`.
2. Use only Python's standard library plus host commands from mtools:
   `mformat`, `mcopy`, `mmd`, `mdir`, and optionally `mtype`.
3. Default output: `build/freedos/freedos.img`.
4. Default download cache: `build/downloads/`.
5. Download:
   `https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.4/FD14-LiteUSB.zip`.
6. Verify this SHA-256 before using the archive:
   `857dcd2ebf9d3d094320154db5fb5b830acba6fb98f981a95a0ca7ab3350338b`.
7. Download through a temporary `.download` filename and rename it only after
   the transfer completes.
8. Accept `--force`, `--output`, `--cache-dir`, `--image-size-mib`, `--url`,
   `--sha256`, and `--print-mtools-image` options.
9. Support image sizes from 64 through 2048 MiB, defaulting to 1024 MiB.

## Image-construction algorithm

1. Open the ZIP and extract the largest `.img` member to a temporary directory.
2. Read its MBR and validate the `0x55AA` signature.
3. Parse the four MBR partition entries and locate the first populated
   partition. Its byte offset is `first_lba * 512`.
4. Save:
   - the source MBR sector;
   - the source partition boot sector;
   - the complete source FAT filesystem tree.
5. Extract the filesystem tree with `mcopy`, using mtools' partition-offset
   syntax:

   ```text
   source.img@@BYTE_OFFSET
   ```

6. Create a sparse raw target file of the requested size.
7. Construct a new MBR by preserving bytes 0 through 445 from the source MBR,
   clearing the old partition table, and adding one partition:
   - status: `0x80` (active);
   - type: `0x0E` (FAT16 LBA);
   - first LBA: 2048;
   - sector count: total target sectors minus 2048;
   - MBR signature: `0x55AA`.
8. Use a declared geometry of 32 heads and 63 sectors per track when producing
   the legacy CHS fields. Saturate out-of-range ending CHS values to
   `FE FF FF`.
9. The target FAT partition begins at byte offset 1048576. Refer to it as:

   ```text
   target.img@@1048576
   ```

10. Format that partition using `mformat` and the source FreeDOS partition boot
    sector as the boot-code template:

    ```bash
    mformat \
      -i target.img@@1048576 \
      -B source-boot-sector.bin \
      -v FD14-LITE \
      -H 2048 \
      -h 32 \
      -n 63 \
      -c 64 \
      ::
    ```

    This creates FAT16 with 32 KiB clusters. Do not simply overwrite the newly
    formatted boot sector afterward, because the new filesystem needs the BPB
    and size information generated for the target geometry.
11. Recursively copy the complete extracted FreeDOS filesystem into the new
    partition with `mcopy`.
12. Build through a temporary target file and atomically rename it to the final
    output only after formatting and copying succeed.

## Prevent installer startup

Overwrite both `/AUTOEXEC.BAT` and `/FDAUTO.BAT` in the target filesystem with
ASCII files using DOS CRLF line endings:

```bat
@ECHO OFF
SET DOSDIR=C:\FDOS
SET PATH=C:\FDOS\BIN;C:\
PROMPT $P$G
CD \
```

Patching both files is intentional. It bypasses the LiteUSB installer startup
and makes the machine land directly at `C:\`.

## Partition-offset support

Implement a helper that reads the MBR, finds the first populated partition,
and returns either:

```text
path/to/image.img@@BYTE_OFFSET
```

or the plain image filename when no partition table exists. Make
`--print-mtools-image` print this value so other scripts can safely run
`mcopy`, `mdir`, and `mmd` without hardcoding the offset.

## Verification

Add focused unit tests for:

- valid MBR signature checking;
- preservation of source MBR boot code;
- active partition status;
- partition type `0x0E`;
- first LBA 2048;
- correct target sector count;
- CHS encoding and saturation;
- rejection of an invalid source MBR.

Then perform these checks:

1. Build the image without launching QEMU.
2. Use `mdir` against `image.img@@1048576` and verify that the FreeDOS files,
   `AUTOEXEC.BAT`, and `FDAUTO.BAT` exist.
3. Use `mtype` to verify the boot-script contents.
4. Boot the image in QEMU only as a smoke test. Do not use screenshots as the
   automation mechanism.

For a screenshot-free boot smoke test, make a temporary clone of the image and
add this line to both boot scripts:

```bat
ECHO FREEDOS_READY>C:\BOOT.OK
```

Boot that clone for a bounded period, stop QEMU through its monitor, and then
use `mtype` or `mdir` on the stopped image to assert that `C:\BOOT.OK` exists.
Never access the raw filesystem with mtools while QEMU is running.

A basic QEMU invocation is:

```bash
qemu-system-i386 \
  -m 16 \
  -boot c \
  -drive file=build/freedos/freedos.img,format=raw,if=ide,index=0,media=disk \
  -display none \
  -monitor stdio
```

The result should be a reproducibly generated bootable raw disk. QEMU is only
a consumer and final smoke-test environment; it must not participate in
installation.

The essential technique is to copy a working FreeDOS filesystem and preserve
its boot code instead of driving the installer.
