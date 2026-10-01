#!/usr/bin/env python3
import sys, glob, os
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from generar_featured import ANCHO, ALTO, COLOR_FONDO_TOP, COLOR_FONDO_BOTTOM

MARCA = os.path.join(BASE_DIR, "marca_r.png")

def color_gradiente_en_y(y):
    t = y / ALTO
    r = int(COLOR_FONDO_TOP[0] + (COLOR_FONDO_BOTTOM[0] - COLOR_FONDO_TOP[0]) * t)
    g = int(COLOR_FONDO_TOP[1] + (COLOR_FONDO_BOTTOM[1] - COLOR_FONDO_TOP[1]) * t)
    b = int(COLOR_FONDO_TOP[2] + (COLOR_FONDO_BOTTOM[2] - COLOR_FONDO_TOP[2]) * t)
    return (r, g, b)

def reponer(path_featured):
    img = Image.open(path_featured).convert("RGB")
    if img.size != (ANCHO, ALTO):
        print(f"AVISO: {path_featured} tiene tamaño distinto ({img.size}), se omite")
        return

    wm = Image.open(MARCA).convert("RGBA")
    wm.thumbnail((48, 48))
    alpha = wm.split()[3]
    wm.putalpha(alpha)

    px, py = 24, ALTO - 24 - wm.height

    for yy in range(py, py + wm.height):
        color = color_gradiente_en_y(yy)
        for xx in range(px, px + wm.width):
            img.putpixel((xx, yy), color)

    img = img.convert("RGBA")
    img.paste(wm, (px, py), wm)
    img.convert("RGB").save(path_featured, quality=92)
    print(f"-> {path_featured}")

if __name__ == "__main__":
    patron = os.path.join(BASE_DIR, "..", "content", "posts", "**", "featured.png")
    rutas = glob.glob(patron, recursive=True)
    if not rutas:
        print("No se encontraron featured.png")
        sys.exit(0)
    print(f"Encontrados {len(rutas)} featured.png")
    for r in rutas:
        reponer(r)
