#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the local pykrx wheel from a hash-verified upstream artifact."""

import argparse
import base64
import csv
import hashlib
import io
from pathlib import Path
import stat
import subprocess
import tempfile
from urllib.request import urlopen
import zipfile

UPSTREAM_URL = (
    "https://files.pythonhosted.org/packages/cd/87/"
    "c54da498f80f0839ec7b4145119b2d395600542d1301f626716538356e93/"
    "pykrx-1.2.9-py3-none-any.whl"
)
UPSTREAM_SHA256 = "e768a64830d21dee46b1a5dd3e9e33112c390d65dbdf931a6bb89ac5a7bea8ea"
VERSION = "1.2.9+cookie.1"
WHEEL_NAME = f"pykrx-{VERSION}-py3-none-any.whl"


def rebuild(upstream: bytes, output: Path) -> str:
    if hashlib.sha256(upstream).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("Upstream wheel SHA256 mismatch")
    with tempfile.TemporaryDirectory(prefix="pykrx-wheel-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(io.BytesIO(upstream)) as source:
            names = source.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate wheel entries")
            for item in source.infolist():
                target = root / item.filename
                if not target.resolve().is_relative_to(root):
                    raise ValueError("Wheel path escapes build directory")
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("Wheel symlinks are not supported")
            source.extractall(root)
        patch = Path(__file__).with_name("transport.patch").read_bytes()
        subprocess.run(
            ["patch", "--batch", "--forward", "-p1"], input=patch,
            cwd=root, check=True, timeout=30,
        )
        original_info = root / "pykrx-1.2.9.dist-info"
        info = root / f"pykrx-{VERSION}.dist-info"
        original_info.rename(info)
        metadata = info / "METADATA"
        text = metadata.read_text(encoding="utf-8")
        if text.count("\nVersion: 1.2.9\n") != 1:
            raise ValueError("Unexpected upstream version metadata")
        metadata.write_text(text.replace("\nVersion: 1.2.9\n", f"\nVersion: {VERSION}\n"), encoding="utf-8", newline="\n")
        wheel = info / "WHEEL"
        wheel.write_text(wheel.read_text(encoding="utf-8").replace(
            "Generator: setuptools (84.0.0)", "Generator: repo-pykrx-cookie-fix"
        ), encoding="utf-8", newline="\n")
        record = info / "RECORD"
        record.unlink()
        files = {path.relative_to(root).as_posix(): path.read_bytes()
                 for path in sorted(root.rglob("*")) if path.is_file()}
        rows = io.StringIO(newline="")
        writer = csv.writer(rows, lineterminator="\n")
        for name, content in files.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
            writer.writerow([name, "sha256=" + digest, len(content)])
        record_name = record.relative_to(root).as_posix()
        writer.writerow([record_name, "", ""])
        files[record_name] = rows.getvalue().encode()
        # Fixed timestamps, permissions and uncompressed entries make bytes reproducible.
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(files):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(entry, files[name])
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-wheel", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name(WHEEL_NAME))
    args = parser.parse_args()
    if args.upstream_wheel:
        upstream_bytes = args.upstream_wheel.read_bytes()
    else:
        with urlopen(UPSTREAM_URL, timeout=30) as response:
            upstream_bytes = response.read()
    print(rebuild(upstream_bytes, args.output))
