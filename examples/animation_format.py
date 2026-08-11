#!/usr/bin/env python3
"""
Encode/decode the Echo Button LED animation step format documented in
PROTOCOL.md:

    [ duration_ms : 2 bytes big-endian ]
    [ color       : 3 bytes raw RGB    ]
    [ blend       : 1 byte (0x00=false, 0x01=true) ]

repeated back to back for each step of an animation.

Named colors below are taken from Amazon's own official (Amazon Software
License) sample skill:
https://github.com/alexa/skill-sample-nodejs-buttons-colorchanger
(button_animations/colorsList.js) - reproduced here only as reference
ground-truth hex values, not as a copy of Amazon's code.
"""
import struct

NAMED_COLORS = {
    "white": "ffffff",
    "red": "ff0000",
    "orange": "ff3300",
    "green": "00ff00",
    "dark green": "004411",
    "blue": "0000ff",
    "light blue": "00a0b0",
    "purple": "4b0098",
    "yellow": "ffd400",
    "black": "000000",
}


def encode_step(duration_ms: int, color_hex: str, blend: bool) -> bytes:
    color = bytes.fromhex(color_hex)
    assert len(color) == 3, "color must be a 3-byte RGB hex string"
    return struct.pack(">H", duration_ms) + color + bytes([1 if blend else 0])


def encode_animation(steps) -> bytes:
    """steps: list of (duration_ms, color_hex, blend) tuples"""
    return b"".join(encode_step(*s) for s in steps)


def decode_steps(raw: bytes):
    """Split a raw animation-step blob back into (duration_ms, color_hex, blend) tuples."""
    steps = []
    for i in range(0, len(raw) - 5, 6):
        chunk = raw[i : i + 6]
        if len(chunk) < 6:
            break
        duration_ms = struct.unpack(">H", chunk[0:2])[0]
        color_hex = chunk[2:5].hex()
        blend = bool(chunk[5])
        steps.append((duration_ms, color_hex, blend))
    return steps


if __name__ == "__main__":
    # Reproduces the exact animation used to reverse the color byte
    # positions: cycle through every named color, 2500ms on, 500ms off gap.
    steps = []
    for name, hex_color in NAMED_COLORS.items():
        steps.append((2500, hex_color, False))
        steps.append((500, "000000", False))

    raw = encode_animation(steps)
    print("encoded:", raw.hex())

    decoded = decode_steps(raw)
    for duration_ms, color_hex, blend in decoded:
        print(f"{duration_ms:5}ms  #{color_hex}  blend={blend}")
