from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

SRC = Path(
    r"C:\Users\SS\.cursor\projects\c-Users-SS-RoomOS\assets"
    r"\c__Users_SS_AppData_Roaming_Cursor_User_workspaceStorage_12a7bf08a071c35502471143f42f7681_images"
    r"_ChatGPT_Image_Jun_16__2026__06_46_34_PM-c8acd626-5af0-4107-b697-2a9d0b6888dd.png"
)
OUT_DIR = Path(__file__).resolve().parents[1] / "public" / "brand"


def trim_near_black(image: Image.Image, threshold: int = 18, pad: int = 8) -> Image.Image:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    width, height = rgb.size
    min_x, min_y, max_x, max_y = width, height, 0, 0

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > threshold or g > threshold or b > threshold:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x <= min_x or max_y <= min_y:
        return image

    return image.crop(
        (
            max(0, min_x - pad),
            max(0, min_y - pad),
            min(width, max_x + pad + 1),
            min(height, max_y + pad + 1),
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(SRC).convert("RGBA")
    width, height = img.size
    margin_x = int(width * 0.04)
    margin_y = int(height * 0.06)
    half_w = width // 2
    half_h = height // 2

    crops = {
        "haven-mark": (margin_x, margin_y, half_w - margin_x, half_h - margin_y),
        "haven-lockup": (half_w + margin_x, margin_y, width - margin_x, half_h - margin_y),
        "haven-lockup-mono": (margin_x, half_h + margin_y, half_w - margin_x, height - margin_y),
        "haven-favicon-ref": (half_w + margin_x, half_h + margin_y, width - margin_x, height - margin_y),
    }

    for name, box in crops.items():
        crop = trim_near_black(img.crop(box))
        crop.save(OUT_DIR / f"{name}.png")
        print(name, crop.size)

    mark = Image.open(OUT_DIR / "haven-mark.png")
    for size in (32, 180, 512):
        resized = mark.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(OUT_DIR / f"icon-{size}.png")

    # Primary lockup for backwards-compatible path
    lockup = Image.open(OUT_DIR / "haven-lockup.png")
    lockup.save(OUT_DIR.parent / "haven-logo.png")
    mark.save(OUT_DIR.parent / "haven-mark.png")
    print("done")


if __name__ == "__main__":
    main()
