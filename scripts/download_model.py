#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import pathlib
import sys
import urllib.request

ARTIFACTS_DIR = pathlib.Path("artifacts/model")

FILES = [
    {
        "path": ARTIFACTS_DIR / "model.onnx",
        "url": "https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/resolve/d3017b38272765ae30e68f73de1fcb432bb97f3d/my_subfolder/model.onnx",
        "sha256": "23ea44ed3eb302e22045900ba8565dd672a9f4c127f5514ce182f01d83fe2e3a",
    },
    {
        "path": ARTIFACTS_DIR / "config.json",
        "url": "https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/resolve/d3017b38272765ae30e68f73de1fcb432bb97f3d/my_subfolder/config.json",
        "sha256": "3049b86c8f85f0bb54c79b359c9b91f6581e13f2a28d5e5eaac97381b53cb077",
    },
    {
        "path": ARTIFACTS_DIR / "tokenizer.json",
        "url": "https://huggingface.co/philschmid/tiny-bert-sst2-distilled/resolve/874eb28543ea7a7df80b6158bbf772d203efcab6/tokenizer.json",
        "sha256": "99e552efd3b68340ef1b1106ea152526659a9c525992f008fe4c182a5a587234",
    },
    {
        "path": ARTIFACTS_DIR / "licenses" / "onnx-export-README.md",
        "url": "https://huggingface.co/fxmarty/tiny-bert-sst2-distilled-onnx-subfolder/raw/d3017b38272765ae30e68f73de1fcb432bb97f3d/README.md",
        "sha256": "98b45ea81164d1e1a1dd82255207053b15cd6c69d922a1c5cf3387ce604d4b74",
    },
    {
        "path": ARTIFACTS_DIR / "licenses" / "source-model-README.md",
        "url": "https://huggingface.co/philschmid/tiny-bert-sst2-distilled/raw/874eb28543ea7a7df80b6158bbf772d203efcab6/README.md",
        "sha256": "8b2aeb54de195d4023fdb47af43646271c9b354a6e853d3a41ed93b3f52d0b7d",
    },
]


def verify_sha256(file_path: pathlib.Path, expected_sha256: str) -> bool:
    if not file_path.exists():
        return False
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest() == expected_sha256


def download_file(url: str, dest_path: pathlib.Path, expected_sha256: str) -> None:
    if verify_sha256(dest_path, expected_sha256):
        print(f"File {dest_path} exists and matches SHA-256 checksum.")
        return

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

    print(f"Downloading {url} -> {temp_path}...")
    urllib.request.urlretrieve(url, temp_path)

    if not verify_sha256(temp_path, expected_sha256):
        temp_path.unlink(missing_ok=True)
        raise ValueError(f"Checksum mismatch for downloaded file {url}")

    os.replace(temp_path, dest_path)
    print(f"Successfully downloaded and verified {dest_path}")


def main() -> None:
    for item in FILES:
        download_file(item["url"], item["path"], item["sha256"])


if __name__ == "__main__":
    main()
