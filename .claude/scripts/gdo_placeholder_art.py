#!/usr/bin/env python3
"""
Game Development OS — placeholder art generator.

Produces original, trivial placeholder assets so an ART-NNN ticket never
blocks the pipeline waiting on real art: solid-color or "missing texture"
checkerboard PNGs for 2D sprites/textures/icons, or silent WAVs for audio
placeholders. Stdlib only (hand-rolled PNG/WAV encoding) — no PIL or other
image library dependency.

Out of scope on purpose: 3D models and anything else that can't be
meaningfully faked this way. gdo-artist escalates those rather than writing
a fake file — see CLAUDE.md.

Commands:
  image <output.png> <width> <height>
        [--pattern solid|checker] [--color RRGGBB] [--color2 RRGGBB]
  audio <output.wav> <seconds>
"""

import argparse
import struct
import sys
import wave
import zlib
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

MISSING_TEXTURE_MAGENTA = (230, 0, 230)
MISSING_TEXTURE_BLACK = (20, 20, 20)


def _chunk(chunk_type, data):
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def write_png(path, width, height, pixel_fn):
    """pixel_fn(x, y) -> (r, g, b), each 0-255."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type: none
        for x in range(width):
            r, g, b = pixel_fn(x, y)
            raw += bytes((r, g, b))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    idat = zlib.compress(bytes(raw), 9)

    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def hex_to_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def cmd_image(args):
    if args.pattern == "solid":
        color = hex_to_rgb(args.color) if args.color else MISSING_TEXTURE_MAGENTA
        pixel_fn = lambda x, y: color
    else:  # checker — classic "missing texture" look by default
        c1 = hex_to_rgb(args.color) if args.color else MISSING_TEXTURE_MAGENTA
        c2 = hex_to_rgb(args.color2) if args.color2 else MISSING_TEXTURE_BLACK
        tile = max(1, min(args.width, args.height) // 8)
        pixel_fn = lambda x, y: c1 if ((x // tile) + (y // tile)) % 2 == 0 else c2

    out = Path(args.output)
    if ".placeholder." not in out.name:
        print(
            f"note: '{out.name}' doesn't contain '.placeholder.' — CLAUDE.md's "
            f"convention is a name like 'player_idle.placeholder.png' so placeholder "
            f"art is easy to grep for later. Not blocking on it, just flagging.",
            file=sys.stderr,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    write_png(out, args.width, args.height, pixel_fn)
    print(f"wrote {out} ({args.width}x{args.height}, {args.pattern})")
    return 0


def cmd_audio(args):
    out = Path(args.output)
    if ".placeholder." not in out.name:
        print(
            f"note: '{out.name}' doesn't contain '.placeholder.' — see CLAUDE.md's "
            f"placeholder-naming convention.",
            file=sys.stderr,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    framerate = 44100
    n_frames = int(framerate * args.seconds)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * n_frames)
    print(f"wrote {out} ({args.seconds}s silent, {framerate}Hz mono)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_img = sub.add_parser("image")
    p_img.add_argument("output")
    p_img.add_argument("width", type=int)
    p_img.add_argument("height", type=int)
    p_img.add_argument("--pattern", choices=["solid", "checker"], default="checker")
    p_img.add_argument("--color", help="hex RRGGBB, primary/solid color")
    p_img.add_argument("--color2", help="hex RRGGBB, checker secondary color")
    p_img.set_defaults(func=cmd_image)

    p_audio = sub.add_parser("audio")
    p_audio.add_argument("output")
    p_audio.add_argument("seconds", type=float)
    p_audio.set_defaults(func=cmd_audio)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
