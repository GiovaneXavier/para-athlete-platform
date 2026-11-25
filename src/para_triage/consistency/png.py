"""A tiny PNG writer and reader for 8-bit RGB images, with `zlib` and `struct` only.

It exists so the image-and-report check package needs no image library (design note section 4.1). The reader only
understands what the writer produces (non-interlaced, filter 0): it is not a general decoder.
"""
from __future__ import annotations

import struct
import zlib

import numpy as np

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def encode_png(pixels: np.ndarray) -> bytes:
    """`pixels` is a (height, width, 3) uint8 array. The output is deterministic."""
    if pixels.ndim != 3 or pixels.shape[2] != 3 or pixels.dtype != np.uint8:
        raise ValueError("expected a (height, width, 3) uint8 array")
    height, width, _ = pixels.shape
    rows = np.concatenate([np.zeros((height, 1), np.uint8), pixels.reshape(height, width * 3)], axis=1)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(rows.tobytes(), 6)) + _chunk(b"IEND", b"")


def decode_png(data: bytes) -> np.ndarray:
    if data[:8] != SIGNATURE:
        raise ValueError("not a PNG")
    position, width, height, idat = 8, 0, 0, b""
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        body = data[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", data[position + 8 + length : position + 12 + length])
        if crc != zlib.crc32(kind + body) & 0xFFFFFFFF:
            raise ValueError(f"bad checksum in {kind!r}")
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, color, interlace) != (8, 2, 0):
                raise ValueError("only 8-bit RGB, non-interlaced PNG is supported")
        elif kind == b"IDAT":
            idat += body
        position += 12 + length
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(height, 1 + width * 3)
    if raw[:, 0].any():
        raise ValueError("only filter 0 is supported")
    return raw[:, 1:].reshape(height, width, 3).copy()
