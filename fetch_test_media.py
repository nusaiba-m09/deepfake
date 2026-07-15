#!/usr/bin/env python3
"""Provision presentation-ready MP4 samples into ./NSU_Demo_Videos."""

from __future__ import annotations

import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "NSU_Demo_Videos"
VENDOR_DIR = ROOT / ".vendor"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SAMPLES = [
    {
        "filename": "sample_real.mp4",
        "label": "Reference Clip A (Authentic Profile)",
        "mode": "real",
    },
    {
        "filename": "sample_fake.mp4",
        "label": "Reference Clip B (Synthetic Distortion)",
        "mode": "fake",
    },
    {
        "filename": "sample_alt.mp4",
        "label": "Reference Clip C (Synthetic Morph Drift)",
        "mode": "alt",
    },
]


def ease_wave(value: float) -> float:
    return 0.5 + 0.5 * math.sin(value)


def blend_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    return tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))


def draw_hud_overlay(draw: ImageDraw.ImageDraw, width: int, height: int, frame_index: int, accent: tuple[int, int, int]) -> None:
    inset = 20
    pulse = ease_wave(frame_index * 0.18)
    alpha = int(150 + 50 * pulse)
    color = (*accent, alpha)
    draw.rectangle((inset, inset, width - inset, height - inset), outline=color, width=2)
    draw.line((width * 0.1, height * 0.18, width * 0.9, height * 0.18), fill=color, width=1)
    draw.line((width * 0.1, height * 0.82, width * 0.9, height * 0.82), fill=color, width=1)
    for x_pos in np.linspace(width * 0.22, width * 0.78, 5):
        draw.line((x_pos, height * 0.16, x_pos, height * 0.84), fill=(accent[0], accent[1], accent[2], 35), width=1)


def render_face_frame(frame_index: int, mode: str, size: tuple[int, int] = (640, 360)) -> np.ndarray:
    width, height = size
    image = Image.new("RGBA", size, (3, 7, 18, 255))
    draw = ImageDraw.Draw(image, "RGBA")

    for y_pos in range(height):
        mix = y_pos / max(height - 1, 1)
        color = blend_color((5, 10, 24), (7, 24, 48), mix)
        draw.line((0, y_pos, width, y_pos), fill=(*color, 255))

    accent = (0, 240, 255) if mode == "real" else (255, 54, 125)
    halo_color = (*accent, 45)
    center_x = width * 0.5 + math.sin(frame_index * 0.08) * (3 if mode == "real" else 10)
    center_y = height * 0.5 + math.cos(frame_index * 0.06) * (4 if mode == "real" else 12)

    for radius in (130, 95, 64):
        bbox = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
        draw.ellipse(bbox, outline=halo_color, width=2)

    face_width = 178 + (8 if mode != "real" else 0) * math.sin(frame_index * 0.32)
    face_height = 226 + (12 if mode == "alt" else 0) * math.cos(frame_index * 0.27)
    face_box = (
        center_x - face_width / 2,
        center_y - face_height / 2,
        center_x + face_width / 2,
        center_y + face_height / 2,
    )
    draw.ellipse(face_box, outline=(*accent, 170), width=3, fill=(8, 25, 48, 120))

    eye_offset_x = 42 + (4 if mode != "real" else 0) * math.sin(frame_index * 0.52)
    eye_offset_y = 20 + (6 if mode == "fake" else 0) * math.cos(frame_index * 0.31)
    blink = 2 + max(0.0, math.sin(frame_index * 0.4)) * (2 if mode == "real" else 6)
    left_eye = (center_x - eye_offset_x, center_y - eye_offset_y)
    right_eye = (center_x + eye_offset_x, center_y - eye_offset_y + (4 if mode == "fake" else 0))
    for x_pos, y_pos in (left_eye, right_eye):
        draw.ellipse((x_pos - 15, y_pos - blink, x_pos + 15, y_pos + blink), fill=(225, 245, 255, 220))
        pupil_shift = math.sin(frame_index * 0.15) * (2 if mode == "real" else 6)
        draw.ellipse((x_pos - 4 + pupil_shift, y_pos - 4, x_pos + 4 + pupil_shift, y_pos + 4), fill=(*accent, 255))

    nose_top = (center_x, center_y - 6)
    nose_left = (center_x - 12, center_y + 34)
    nose_right = (center_x + 12, center_y + 34 + (6 if mode == "alt" else 0))
    draw.line((nose_top, nose_left, nose_right), fill=(*accent, 165), width=2)

    mouth_width = 54 + (12 if mode != "real" else 4) * math.sin(frame_index * 0.33)
    mouth_height = 12 + (8 if mode == "fake" else 3) * math.cos(frame_index * 0.24)
    draw.arc(
        (
            center_x - mouth_width,
            center_y + 48 - mouth_height,
            center_x + mouth_width,
            center_y + 48 + mouth_height,
        ),
        start=12,
        end=168,
        fill=(*accent, 220),
        width=3,
    )

    if mode != "real":
        for row in range(0, height, 22):
            jitter = int(math.sin(frame_index * 0.25 + row * 0.1) * (12 if mode == "fake" else 7))
            draw.line((0, row, width, row), fill=(255, 255, 255, 12), width=1)
            if row % 44 == 0:
                draw.line((0 + jitter, row + 3, width + jitter, row + 3), fill=(255, 32, 112, 38), width=2)

    draw_hud_overlay(draw, width, height, frame_index, accent)

    image = image.filter(ImageFilter.GaussianBlur(radius=0.25))
    return np.asarray(image.convert("RGB"))


def write_generated_video(destination: pathlib.Path, mode: str) -> None:
    writer = imageio.get_writer(destination, fps=24, codec="libx264", quality=7, macro_block_size=None)
    try:
        for frame_index in range(96):
            writer.append_data(render_face_frame(frame_index, mode))
    finally:
        writer.close()


def main() -> int:
    print("==================================================")
    print("   NSU CYBER LAB - AUTOMATED MEDIA ACQUISITION   ")
    print("==================================================")
    print(f"[*] Target Directory: {OUTPUT_DIR}\n")

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover
        print(f"[-] Critical: Failed to create directory structure. Error: {exc}")
        return 1

    for sample in SAMPLES:
        destination = OUTPUT_DIR / sample["filename"]
        print(f"[*] Provisioning payload: {sample['label']}...")
        print(f"    -> Destination: {destination.name}")
        try:
            write_generated_video(destination, sample["mode"])
            print("[+] Success: Generated local MP4 reference clip.\n")
        except Exception as exc:  # pragma: no cover
            print(f"[-] Error: Could not generate {destination.name}. Details: {exc}\n")
            return 1

    print("==================================================")
    print("[!] Environmental setup finalized.")
    print("[!] Local demo videos ready for drag-and-drop presentation testing.")
    print("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
