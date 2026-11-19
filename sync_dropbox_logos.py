#!/usr/bin/env python3
"""Import the 261 user-supplied HLCA mascot PNGs from the public Dropbox shared folder.
The manifest explicitly maps real-school filenames to fictional Hoop Land team filenames.
"""
import csv
import io
import pathlib
import time
import urllib.request
import zipfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
LOGOS = ROOT / "logos"
MANIFEST = ROOT / "logo_manifest.csv"
DROPBOX_ZIP = "https://www.dropbox.com/scl/fo/l8l9qdawrlpw98xakaqrl/AKGGpo2TrPeccWTO512CGyM?rlkey=g1lctxcods04ujjiy055mrtv5&dl=1"


def download_zip():
    data = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                DROPBOX_ZIP,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
                    "Accept": "application/zip,application/octet-stream,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as response:
                data = response.read()
            if zipfile.is_zipfile(io.BytesIO(data)):
                print(f"Downloaded valid Dropbox folder ZIP ({len(data):,} bytes)")
                return zipfile.ZipFile(io.BytesIO(data))
            raise ValueError(f"Dropbox returned a non-ZIP response; first bytes: {data[:140]!r}")
        except Exception as exc:
            print(f"Dropbox download attempt {attempt + 1}/4 failed: {exc}")
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Could not download folder")


def entry_priority(archive_path):
    name = archive_path.lower()
    if "hlca_final_61_bigger_no_circles_256px/" in name:
        return 300
    if "hlca_16_redesigned_logos_only/" in name:
        return 200
    if "hlca_selected_10_logo_fixes/" in name:
        return 100
    return 10 - archive_path.count("/")


def as_256_png(raw, target):
    try:
        with Image.open(io.BytesIO(raw)) as loaded:
            loaded.load()
            image = loaded.convert("RGBA")
    except Exception as exc:
        raise ValueError(f"Invalid source PNG for {target}: {exc}")
    if image.size != (256, 256):
        print(f"Resizing {target}: source image {image.size} => 256x256")
        image.thumbnail((248, 248), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((256 - image.width) // 2, (256 - image.height) // 2))
        image = canvas
    dest = LOGOS / target
    with io.BytesIO() as mem:
        image.save(mem, format="PNG", optimize=True)
        dest.write_bytes(mem.getvalue())


def main():
    mapping = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    assert len(mapping) == 261, f"Expected 261 entries, got {len(mapping)}"
    zf = download_zip()
    candidates = {}
    for info in zf.infolist():
        p = pathlib.PurePosixPath(info.filename)
        if info.is_dir() or p.suffix.lower() != ".png" or p.name.startswith("."):
            continue
        candidates.setdefault(p.name.casefold(), []).append(info.filename)
    LOGOS.mkdir(exist_ok=True)
    for row in mapping:
        target = row["target_filename"]
        src = row["dropbox_source_filename"]
        paths = candidates.get(src.casefold())
        if not paths:
            raise RuntimeError(f"Missing Dropbox source for {target}: {src}")
        best = max(paths, key=entry_priority)
        as_256_png(zf.read(best), target)
    result = list(LOGOS.glob("*.png"))
    if len(result) != 261:
        raise RuntimeError(f"Expected 261 published logos, got {len(result)}")
    print(f"Prepared {len(result)} public 256x256 PNG assets in {LOGOS}")


if __name__ == "__main__":
    main()
