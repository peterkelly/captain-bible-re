#!/usr/bin/env python3
"""Build a bootable FreeDOS 1.4 raw disk without running its installer."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


FREEDOS_LITEUSB_URL = (
    "https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/"
    "distributions/1.4/FD14-LiteUSB.zip"
)
FREEDOS_LITEUSB_SHA256 = (
    "857dcd2ebf9d3d094320154db5fb5b830acba6fb98f981a95a0ca7ab3350338b"
)
DEFAULT_OUTPUT = Path("build/freedos/freedos.img")
DEFAULT_CACHE_DIR = Path("build/downloads")
DEFAULT_IMAGE_SIZE_MIB = 1024

SECTOR_SIZE = 512
PARTITION_START_LBA = 2048
PARTITION_TYPE_FAT16_LBA = 0x0E
DISK_HEADS = 32
DISK_SECTORS_PER_TRACK = 63
FAT16_SECTORS_PER_CLUSTER = 64
MBR_SIGNATURE = b"\x55\xaa"

PROMPT_BOOT_SCRIPT = """@ECHO OFF
SET DOSDIR=C:\\FDOS
SET PATH=C:\\FDOS\\BIN;C:\\
PROMPT $P$G
CD \\
"""


class ImageBuildError(RuntimeError):
    """Raised when source media or requested image geometry is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    """Download through a temporary name and publish only verified content."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    temporary.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual_sha256 = sha256_file(temporary)
        if actual_sha256.lower() != expected_sha256.lower():
            raise ImageBuildError(
                f"sha256 mismatch for {destination}: expected {expected_sha256}, "
                f"got {actual_sha256}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise ImageBuildError(f"required tool not found on PATH: {name}")


def run_mtools(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def validate_mbr(mbr: bytes) -> None:
    if len(mbr) != SECTOR_SIZE or mbr[510:512] != MBR_SIGNATURE:
        raise ImageBuildError("FreeDOS source image has no valid MBR boot sector")


def first_partition_offset(mbr: bytes) -> int | None:
    """Return the first populated MBR partition offset, or None."""
    validate_mbr(mbr)
    for index in range(4):
        entry_offset = 446 + index * 16
        entry = mbr[entry_offset : entry_offset + 16]
        partition_type = entry[4]
        first_lba, sector_count = struct.unpack_from("<II", entry, 8)
        if partition_type != 0 and sector_count != 0:
            return first_lba * SECTOR_SIZE
    return None


def mtools_image(path: Path) -> str:
    """Return mtools partition-offset syntax for a disk or plain FAT image."""
    with path.open("rb") as handle:
        mbr = handle.read(SECTOR_SIZE)
    offset = first_partition_offset(mbr)
    return str(path) if offset is None else f"{path}@@{offset}"


def chs_address(lba: int) -> bytes:
    """Encode an LBA as an MBR CHS triplet for the declared geometry."""
    cylinder, remainder = divmod(
        lba, DISK_HEADS * DISK_SECTORS_PER_TRACK
    )
    head, sector_index = divmod(remainder, DISK_SECTORS_PER_TRACK)
    sector = sector_index + 1
    if cylinder > 1023:
        return b"\xfe\xff\xff"
    return bytes(
        (head, sector | ((cylinder >> 2) & 0xC0), cylinder & 0xFF)
    )


def partitioned_mbr(source_mbr: bytes, image_size: int) -> bytes:
    """Preserve source boot code and define one active FAT16 LBA partition."""
    validate_mbr(source_mbr)
    if image_size % SECTOR_SIZE:
        raise ImageBuildError("image size must be a multiple of 512 bytes")

    total_sectors = image_size // SECTOR_SIZE
    partition_sectors = total_sectors - PARTITION_START_LBA
    if partition_sectors <= 0:
        raise ImageBuildError("image is too small for the partition offset")

    result = bytearray(source_mbr)
    result[446:510] = b"\x00" * 64
    entry = (
        b"\x80"
        + chs_address(PARTITION_START_LBA)
        + bytes((PARTITION_TYPE_FAT16_LBA,))
        + chs_address(total_sectors - 1)
        + struct.pack(
            "<II", PARTITION_START_LBA, partition_sectors
        )
    )
    result[446:462] = entry
    result[510:512] = MBR_SIGNATURE
    return bytes(result)


def largest_image_member(zip_path: Path) -> zipfile.ZipInfo:
    with zipfile.ZipFile(zip_path) as archive:
        members = [
            info
            for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".img")
        ]
    if not members:
        raise ImageBuildError(f"no .img member found in {zip_path}")
    return max(members, key=lambda info: info.file_size)


def extract_member(zip_path: Path, member: zipfile.ZipInfo, output: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive, archive.open(member) as source:
        with output.open("wb") as target:
            shutil.copyfileobj(source, target)


def read_sector(path: Path, offset: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(offset)
        sector = handle.read(SECTOR_SIZE)
    if len(sector) != SECTOR_SIZE:
        raise ImageBuildError(f"cannot read a complete sector at offset {offset}")
    return sector


def copy_volume_tree(source_image: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    run_mtools(["mcopy", "-s", "-i", source_image, "::/*", str(destination)])


def write_dos_text(image: str, dos_path: str, contents: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="ascii", newline="\r\n", delete=False
    ) as handle:
        host_path = Path(handle.name)
        handle.write(contents)
    try:
        run_mtools(["mcopy", "-o", "-i", image, str(host_path), f"::{dos_path}"])
    finally:
        host_path.unlink(missing_ok=True)


def patch_boot_scripts(image: str) -> None:
    write_dos_text(image, "/AUTOEXEC.BAT", PROMPT_BOOT_SCRIPT)
    write_dos_text(image, "/FDAUTO.BAT", PROMPT_BOOT_SCRIPT)


def build_image(zip_path: Path, output: Path, image_size_mib: int) -> str:
    """Construct the image atomically and return the source ZIP member name."""
    image_size = image_size_mib * 1024 * 1024
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    temporary_output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="freedos-source-") as temp_dir:
        work_dir = Path(temp_dir)
        source_image = work_dir / "source.img"
        volume_tree = work_dir / "volume"
        boot_sector_path = work_dir / "source-boot-sector.bin"

        member = largest_image_member(zip_path)
        extract_member(zip_path, member, source_image)

        source_mbr = read_sector(source_image, 0)
        source_offset = first_partition_offset(source_mbr)
        if source_offset is None:
            raise ImageBuildError("FreeDOS source image has no populated partition")
        source_boot_sector = read_sector(source_image, source_offset)
        if source_boot_sector[510:512] != MBR_SIGNATURE:
            raise ImageBuildError(
                "FreeDOS source partition has no valid boot sector"
            )

        boot_sector_path.write_bytes(source_boot_sector)
        copy_volume_tree(f"{source_image}@@{source_offset}", volume_tree)
        members = sorted(volume_tree.iterdir())
        if not members:
            raise ImageBuildError("FreeDOS source filesystem is empty")

        try:
            with temporary_output.open("wb") as target:
                target.truncate(image_size)
                target.seek(0)
                target.write(partitioned_mbr(source_mbr, image_size))

            target_image = (
                f"{temporary_output}@@{PARTITION_START_LBA * SECTOR_SIZE}"
            )
            run_mtools(
                [
                    "mformat",
                    "-i",
                    target_image,
                    "-B",
                    str(boot_sector_path),
                    "-v",
                    "FD14-LITE",
                    "-H",
                    str(PARTITION_START_LBA),
                    "-h",
                    str(DISK_HEADS),
                    "-n",
                    str(DISK_SECTORS_PER_TRACK),
                    "-c",
                    str(FAT16_SECTORS_PER_CLUSTER),
                    "::",
                ]
            )
            run_mtools(
                [
                    "mcopy",
                    "-s",
                    "-o",
                    "-i",
                    target_image,
                    *(str(path) for path in members),
                    "::/",
                ]
            )
            patch_boot_scripts(target_image)
            temporary_output.replace(output)
        finally:
            temporary_output.unlink(missing_ok=True)

    return member.filename


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--image-size-mib",
        type=int,
        default=DEFAULT_IMAGE_SIZE_MIB,
        help="raw disk size from 64 through 2048 MiB (default: 1024)",
    )
    parser.add_argument("--url", default=FREEDOS_LITEUSB_URL)
    parser.add_argument("--sha256", default=FREEDOS_LITEUSB_SHA256)
    parser.add_argument("--print-mtools-image", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 64 <= args.image_size_mib <= 2048:
        raise SystemExit("--image-size-mib must be between 64 and 2048")

    if args.print_mtools_image and args.output.exists() and not args.force:
        print(mtools_image(args.output))
        return 0
    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists; pass --force to replace it")

    try:
        for tool in ("mformat", "mcopy", "mmd", "mdir"):
            require_tool(tool)

        archive_name = Path(urllib.parse.urlparse(args.url).path).name
        zip_path = args.cache_dir / archive_name
        if zip_path.exists():
            actual_sha256 = sha256_file(zip_path)
            if actual_sha256.lower() != args.sha256.lower():
                raise ImageBuildError(
                    f"sha256 mismatch for {zip_path}: expected {args.sha256}, "
                    f"got {actual_sha256}"
                )
        else:
            print(f"downloading: {args.url}")
            download_verified(args.url, zip_path, args.sha256)

        member_name = build_image(zip_path, args.output, args.image_size_mib)
    except (ImageBuildError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error

    image = mtools_image(args.output)
    print(f"zip: {zip_path}")
    print(f"extracted: {member_name}")
    print(f"image: {args.output}")
    print(f"image size: {args.image_size_mib} MiB")
    print(f"mtools image: {image}")
    if args.print_mtools_image:
        print(image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
