"""Render the Graphite LED theme materials: a wavy perforated-dot background and a brushed graphite tile.

    python scripts/make_graphite_materials.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "public" / "materials-ui"
OUT.mkdir(parents=True, exist_ok=True)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def dot_wave(width=2560, height=1440, spacing=10.0):
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    xn, yn = x / width, y / height
    # A soft ridge sweeping down the right side, plus a gentle swell.
    path = 0.70 + 0.10 * np.sin(yn * np.pi * 1.6 + 0.6) + 0.04 * np.sin(yn * np.pi * 4.1)
    d = xn - path
    h = np.exp(-(d / 0.10) ** 2) * 1.0 + 0.35 * np.exp(-(d / 0.30) ** 2) + 0.12 * np.sin(xn * 5.0 + yn * 3.0)
    gy, gx = np.gradient(h)
    nx, ny, nz = -gx * 260, -gy * 260, np.ones_like(h)
    norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny, nz = nx / norm, ny / norm, nz / norm
    L = np.array([0.55, -0.35, 0.76]); L /= np.linalg.norm(L)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    diffuse = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    spec = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1) ** 60

    # Dots follow the surface: warp the grid by the height, hex-offset rows.
    U = x / spacing + h * 7.0
    V = y / spacing + h * 2.0
    row = np.floor(V)
    U = U + 0.5 * (row % 2)
    fu, fv = U - np.floor(U) - 0.5, V - row - 0.5
    dist = np.sqrt(fu ** 2 + fv ** 2)
    dot = 1 - smoothstep(0.24, 0.32, dist)
    # each dot is a tiny dome with its own highlight towards the light
    hl = 1 - smoothstep(0.0, 0.22, np.sqrt((fu - 0.08) ** 2 + (fv + 0.08) ** 2))

    light = 0.06 + 0.94 * smoothstep(-0.55, 0.12, d) * (1 - smoothstep(0.10, 0.45, d))  # dark on the left
    lum_dot = (0.10 + 0.55 * diffuse + 1.1 * spec) * light + 0.22 * hl * light
    base = 0.012 + 0.03 * light
    lum = base * (1 - dot) + lum_dot * dot
    lum = np.clip(lum, 0, 1)
    rgb = np.stack([lum * 0.93, lum * 0.97, lum * 1.03], axis=-1)  # faintly cool
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    img.save(OUT / "dotwave.jpg", "JPEG", quality=86, optimize=True, progressive=True)


def brushed_tile(size=512, seed=7):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (size, size)).astype(np.float32)
    # long horizontal streaks (wrap-around blur keeps it tileable)
    k = 61
    acc = np.zeros_like(n)
    for s in range(-(k // 2), k // 2 + 1):
        acc += np.roll(n, s, axis=1)
    acc /= k
    acc += 0.25 * np.roll(rng.normal(0, 1, (size, size)).astype(np.float32), 0, axis=1)
    acc = (acc - acc.mean()) / acc.std()
    lum = np.clip(0.5 + acc * 0.06, 0, 1)
    Image.fromarray((lum * 255).astype(np.uint8), "L").save(OUT / "brushed-graphite.png", optimize=True)


if __name__ == "__main__":
    dot_wave()
    brushed_tile()
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size // 1024, "KB")
