#!/usr/bin/env python3
import sys, os, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ANCHO, ALTO = 1120, 400
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUENTE_TITULO = os.path.join(BASE_DIR, "fuente.ttf")

COLOR_FONDO_TOP = (15, 23, 42)
COLOR_FONDO_BOTTOM = (23, 37, 74)
COLOR_ACCENT = (59, 130, 246)
COLOR_TEXTO = (248, 250, 252)

def degradado_vertical(w, h, top, bottom):
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0]-top[0])*t)
        g = int(top[1] + (bottom[1]-top[1])*t)
        b = int(top[2] + (bottom[2]-top[2])*t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img

def recortar_margenes(img):
    img = img.convert("RGBA")
    alpha = img.split()[3]
    if alpha.getextrema() != (255, 255):
        bbox = alpha.getbbox()
    else:
        gris = img.convert("L")
        bg = Image.new("L", gris.size, 255)
        # umbral para que fondos casi blancos (p.ej. 250) también se recorten
        diff = ImageChops.difference(gris, bg).point(lambda v: 255 if v > 12 else 0)
        bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def parsear_spec(spec):
    # "ruta.png:0.8" -> ("ruta.png", 0.8); sin factor -> 1.0
    if ":" in spec:
        ruta, factor_str = spec.rsplit(":", 1)
        try:
            return ruta, float(factor_str)
        except ValueError:
            pass
    return spec, 1.0

def logo_con_tarjeta(logo_spec, lado=220, margen=30, radio=28):
    logo_path, factor = parsear_spec(logo_spec)
    tarjeta = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    mask = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, lado, lado], radius=radio, fill=255)
    fondo_blanco = Image.new("RGBA", (lado, lado), (255, 255, 255, 255))
    tarjeta.paste(fondo_blanco, (0, 0), mask)

    logo = recortar_margenes(Image.open(logo_path))
    # aplanar sobre blanco ANTES de reducir tamaño, para no arrastrar
    # halos oscuros de píxeles de borde semitransparentes
    base_blanca = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    base_blanca.alpha_composite(logo)
    logo = base_blanca

    # el factor escala el hueco del logo; mínimo 8px de margen con la tarjeta
    hueco = min(int((lado - margen*2) * factor), lado - 16)
    logo.thumbnail((hueco, hueco))
    pos = ((lado - logo.width)//2, (lado - logo.height)//2)
    tarjeta.paste(logo, pos)
    return tarjeta

def tamano_ajustado(tamano_img, alto_objetivo):
    w, h = tamano_img
    factor = alto_objetivo / h
    return max(1, int(w * factor)), alto_objetivo

def logos_combinados(logo_specs_raw, lado=220, radio=28):
    tarjeta = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    mask = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, lado, lado], radius=radio, fill=255)
    fondo_blanco = Image.new("RGBA", (lado, lado), (255, 255, 255, 255))
    tarjeta.paste(fondo_blanco, (0, 0), mask)

    margen_ext = 18
    gap = 12
    ancho_disp = lado - margen_ext * 2
    alto_disp = lado - margen_ext * 2

    pares = []
    for spec in logo_specs_raw:
        ruta, factor = parsear_spec(spec)
        logo = recortar_margenes(Image.open(ruta))
        base_blanca = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        base_blanca.alpha_composite(logo)
        pares.append((base_blanca.convert("RGB"), factor))

    UMBRAL_PANORAMICO = 1.6
    panoramicos = [pf for pf in pares if pf[0].size[0] / pf[0].size[1] >= UMBRAL_PANORAMICO]
    compactos = [pf for pf in pares if pf[0].size[0] / pf[0].size[1] < UMBRAL_PANORAMICO]

    filas = [[pf] for pf in panoramicos]
    if compactos:
        filas = [compactos] + filas
    if not filas:
        filas = [pares]

    n_filas = len(filas)
    alto_fila_base = (alto_disp - gap * (n_filas - 1)) // n_filas

    y = margen_ext
    for fila in filas:
        tamanos = [tamano_ajustado(l.size, max(1, int(alto_fila_base * f))) for l, f in fila]
        ancho_total = sum(w for w, _ in tamanos) + gap * (len(fila) - 1)

        if ancho_total > ancho_disp:
            factor_ajuste = ancho_disp / ancho_total
            tamanos = [(max(1, int(w * factor_ajuste)), max(1, int(h * factor_ajuste))) for w, h in tamanos]
            ancho_total = sum(w for w, _ in tamanos) + gap * (len(fila) - 1)

        x = margen_ext + (ancho_disp - ancho_total) // 2
        for (l, f), (w, h) in zip(fila, tamanos):
            logo_r = l.resize((w, h), Image.LANCZOS)
            tarjeta.paste(logo_r, (x, y + (alto_fila_base - h) // 2))
            x += w + gap

        y += alto_fila_base + gap

    return tarjeta

def generar(titulo, logo_path, salida, marca_agua=None):
    img = degradado_vertical(ANCHO, ALTO, COLOR_FONDO_TOP, COLOR_FONDO_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 10, ALTO], fill=COLOR_ACCENT)

    margen_der = 70
    lado_tarjeta = 220
    logos = [p.strip() for p in logo_path.split(",")] if logo_path and logo_path != "-" else []
    if logos:
        if len(logos) == 1:
            tarjeta = logo_con_tarjeta(logos[0], lado_tarjeta)
        else:
            tarjeta = logos_combinados(logos, lado_tarjeta)
        pos_x = ANCHO - lado_tarjeta - margen_der
        pos_y = (ALTO - lado_tarjeta)//2
        img.paste(tarjeta, (pos_x, pos_y), tarjeta)
        ancho_disponible_titulo = pos_x - 130
    else:
        ancho_disponible_titulo = ANCHO - 160

    tam_fuente = 48
    fuente = ImageFont.truetype(FUENTE_TITULO, tam_fuente)

    def ajustar_lineas(texto, fuente, ancho_max):
        palabras = texto.split()
        lineas, actual = [], ""
        for palabra in palabras:
            prueba = (actual + " " + palabra).strip()
            ancho = draw.textbbox((0, 0), prueba, font=fuente)[2]
            if ancho <= ancho_max or not actual:
                actual = prueba
            else:
                lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
        return lineas[:3]

    lineas = ajustar_lineas(titulo.upper(), fuente, ancho_disponible_titulo)

    alto_linea = tam_fuente + 10
    alto_total_texto = alto_linea * len(lineas)
    y_inicial = (ALTO - alto_total_texto) // 2

    # capa de sombra, desenfocada, bien visible
    sombra_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sombra_draw = ImageDraw.Draw(sombra_layer)
    y = y_inicial
    for linea in lineas:
        sombra_draw.text((70 + 3, y + 3), linea, font=fuente, fill=(0, 0, 0, 200))
        y += alto_linea
    sombra_layer = sombra_layer.filter(ImageFilter.GaussianBlur(3))
    img = Image.alpha_composite(img, sombra_layer)
    draw = ImageDraw.Draw(img)

    y = y_inicial
    for linea in lineas:
        draw.text((70, y), linea, font=fuente, fill=COLOR_TEXTO)
        y += alto_linea

    if marca_agua:
        wm = Image.open(marca_agua).convert("RGBA")
        wm.thumbnail((48, 48))
        alpha = wm.split()[3]
        wm.putalpha(alpha)  # opacidad original, sin atenuar
        img.paste(wm, (24, ALTO - 24 - wm.height), wm)

    img.convert("RGB").save(salida, quality=92)
    print(f"-> {salida}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: generar_featured.py \"Título\" ruta_logo.png salida.png [marca_agua.png]")
        sys.exit(1)
    titulo, logo, salida = sys.argv[1], sys.argv[2], sys.argv[3]
    marca = sys.argv[4] if len(sys.argv) > 4 else None
    generar(titulo, logo, salida, marca)
