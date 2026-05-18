#!/usr/bin/env python3
"""
Skin swap: Convierte una imagen de usuario en 6 frames animados para Claudy.
Genera animaciones de respiración, movimiento vertical y rotación suave.
"""

import os
import sys
import math
from PIL import Image, ImageDraw
import colorsys


def get_dominant_color(image_path):
    """Extrae el color dominante de la imagen."""
    img = Image.open(image_path).convert('RGB')
    img.thumbnail((150, 150))
    pixels = list(img.getdata())

    # Contar colores más frecuentes
    color_counts = {}
    for pixel in pixels:
        if pixel not in color_counts:
            color_counts[pixel] = 0
        color_counts[pixel] += 1

    dominant = max(color_counts, key=color_counts.get)
    return dominant


def hex_color(rgb):
    """Convierte RGB a hex."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def auto_crop_and_remove_bg(image, bg_tolerance=30):
    """
    Detecta el fondo (color más común en los bordes) y:
    1. Recorta a la bounding box del contenido
    2. Convierte el fondo a transparente
    """
    img = image.convert('RGBA')
    pixels = img.load()
    w, h = img.size

    # Detectar color de fondo: muestrea los 4 corners + bordes
    edge_samples = []
    for x in range(0, w, max(1, w // 20)):
        edge_samples.append(pixels[x, 0][:3])
        edge_samples.append(pixels[x, h - 1][:3])
    for y in range(0, h, max(1, h // 20)):
        edge_samples.append(pixels[0, y][:3])
        edge_samples.append(pixels[w - 1, y][:3])

    # Color de fondo = el más frecuente en los bordes
    color_counts = {}
    for c in edge_samples:
        color_counts[c] = color_counts.get(c, 0) + 1
    bg_color = max(color_counts, key=color_counts.get)
    print(f"[*] Fondo detectado: RGB{bg_color}")

    def is_bg(px):
        return (abs(px[0] - bg_color[0]) <= bg_tolerance and
                abs(px[1] - bg_color[1]) <= bg_tolerance and
                abs(px[2] - bg_color[2]) <= bg_tolerance)

    # 1) Convertir fondo a transparente
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if is_bg((r, g, b)):
                pixels[x, y] = (255, 255, 255, 0)

    # 2) Encontrar bounding box del contenido no transparente
    bbox = img.getbbox()
    if bbox is None:
        return img

    # 3) Filtrar texto / elementos pequeños desconectados:
    #    encuentra el "blob" más grande conexo (la pet) y recorta a eso.
    cropped = img.crop(bbox)
    cw, ch = cropped.size

    # Análisis simple: encuentra la fila con más píxeles opacos consecutivos
    # — eso representa el cuerpo del animal. Luego corta verticalmente
    # justo después de un gap grande (separación entre pet y texto).
    cpixels = cropped.load()
    row_density = []
    for y in range(ch):
        count = sum(1 for x in range(cw) if cpixels[x, y][3] > 0)
        row_density.append(count)

    # Encuentra gaps verticales (>5 filas vacías consecutivas) y corta la parte inferior
    gap_threshold = 5
    consecutive_empty = 0
    cut_y = ch
    found_content = False
    for y in range(ch):
        if row_density[y] > 0:
            if found_content and consecutive_empty >= gap_threshold:
                # Ya teniamos contenido, hubo un gap, y ahora vuelve contenido
                # — el contenido superior es la pet, el inferior es texto
                cut_y = y - consecutive_empty
                break
            found_content = True
            consecutive_empty = 0
        else:
            if found_content:
                consecutive_empty += 1

    if cut_y < ch:
        print(f"[*] Detectado gap en y={cut_y}, recortando texto/elementos secundarios")
        cropped = cropped.crop((0, 0, cw, cut_y))

    # Recortar de nuevo a contenido (por si quedaron padding)
    final_bbox = cropped.getbbox()
    if final_bbox:
        cropped = cropped.crop(final_bbox)

    print(f"[*] Recortado a: {cropped.size}")
    return cropped


def create_animated_frames(input_image_path, output_dir, frame_size=128):
    """
    Crea 6 frames animados a partir de una imagen.

    Pipeline:
    1. Auto-recorte: solo la pet (sin texto ni fondo)
    2. Fondo transparente
    3. 6 frames con animación de respiración + rotación
    """

    # Cargar imagen original
    original = Image.open(input_image_path).convert('RGBA')
    print(f"[*] Imagen original: {original.size}")

    # Auto-recortar y eliminar fondo
    cropped = auto_crop_and_remove_bg(original)

    # Crear directorio de salida si no existe
    os.makedirs(output_dir, exist_ok=True)

    # Calcular dimensiones para encajar en frame_size con padding
    # Dejamos ~10% de margen alrededor para que las animaciones no salgan del frame
    target = int(frame_size * 0.85)
    cw, ch = cropped.size
    ratio = min(target / cw, target / ch)
    new_width = int(cw * ratio)
    new_height = int(ch * ratio)

    # Redimensionar (nearest para preservar pixel art, lanczos si es muy chico)
    if cw < frame_size or ch < frame_size:
        resized = cropped.resize((new_width, new_height), Image.Resampling.NEAREST)
    else:
        resized = cropped.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Animación de "caminar en su sitio" con movimientos corporales reales.
    # Combina: bamboleo lateral + saltito sutil + squash/stretch del 2% (anticipación/aterrizaje).
    # Cabeza se mueve INDEPENDIENTE del cuerpo en X (head bob desfasado) para dar vida.
    #
    # Principios de animación aplicados:
    #   - Squash & Stretch sutil (2-3%) en el cuerpo al saltar/aterrizar
    #   - Head lag: la cabeza se inclina ligeramente desfasada al andar
    #   - Foot work: las patas (parte inferior) alternan posición
    frames_data = [
        # Frame 0: Reposo neutral
        {"body_x": 0,  "body_y": 0,  "v_stretch": 1.00, "head_x": 0,  "feet_x": 0},
        # Frame 1: Inicio paso derecho — cuerpo se prepara (anticipación)
        {"body_x": 1,  "body_y": 0,  "v_stretch": 0.98, "head_x": 0,  "feet_x": -1},
        # Frame 2: Pico del paso derecho — saltito + leve estiramiento vertical
        {"body_x": 2,  "body_y": -2, "v_stretch": 1.02, "head_x": 1,  "feet_x": -2},
        # Frame 3: Aterrizaje — squash leve (compresión vertical)
        {"body_x": 1,  "body_y": 0,  "v_stretch": 0.97, "head_x": 2,  "feet_x": 0},
        # Frame 4: Inicio paso izquierdo
        {"body_x": -1, "body_y": 0,  "v_stretch": 0.98, "head_x": 1,  "feet_x": 1},
        # Frame 5: Pico paso izquierdo — saltito + estiramiento
        {"body_x": -2, "body_y": -2, "v_stretch": 1.02, "head_x": -1, "feet_x": 2},
    ]

    # Detectar línea de división cabeza/patas: ~60% desde arriba.
    # Esto permite animar cabeza y patas con movimientos independientes.
    rw, rh = resized.size
    head_cut = int(rh * 0.65)  # Cabeza + torso
    feet_cut_top = int(rh * 0.55)  # Punto donde empiezan las patas (solapamiento sutil)

    head_part = resized.crop((0, 0, rw, head_cut))
    feet_part = resized.crop((0, feet_cut_top, rw, rh))

    for frame_idx, data in enumerate(frames_data):
        # Crear canvas para el frame
        canvas = Image.new('RGBA', (frame_size, frame_size), (0, 0, 0, 0))

        # Aplicar squash/stretch SOLO vertical (preserva ancho, evita "respiración" sicodélica)
        stretch = data["v_stretch"]
        stretched_height = int(rh * stretch)
        body_scaled = resized.resize((rw, stretched_height), Image.Resampling.NEAREST)

        bx = (frame_size - body_scaled.width) // 2 + data["body_x"]
        by = (frame_size - body_scaled.height) // 2 + data["body_y"]

        # 1) Pegar cuerpo completo (con squash/stretch vertical aplicado)
        canvas.paste(body_scaled, (bx, by), body_scaled)

        # 2) Overlay de patas con offset X independiente (foot work)
        # Se reescala con la misma deformación vertical y se pega en la parte inferior
        if data["feet_x"] != 0:
            feet_h = int(feet_part.height * stretch)
            feet_scaled = feet_part.resize((feet_part.width, feet_h), Image.Resampling.NEAREST)
            fx = (frame_size - feet_scaled.width) // 2 + data["body_x"] + data["feet_x"]
            fy = by + body_scaled.height - feet_scaled.height
            canvas.paste(feet_scaled, (fx, fy), feet_scaled)

        # 3) Overlay de cabeza con head bob desfasado (movimiento natural al andar)
        if data["head_x"] != 0:
            head_h = int(head_part.height * stretch)
            head_scaled = head_part.resize((head_part.width, head_h), Image.Resampling.NEAREST)
            hx = (frame_size - head_scaled.width) // 2 + data["body_x"] + data["head_x"]
            hy = by
            canvas.paste(head_scaled, (hx, hy), head_scaled)

        # Convertir a RGB con fondo magenta (#ff00ff = TRANSPARENT_COLOR en pet.py)
        # Esto hace que el fondo sea invisible cuando tkinter renderice el frame.
        rgb_frame = Image.new('RGB', (frame_size, frame_size), (255, 0, 255))
        rgb_frame.paste(canvas, (0, 0), canvas)

        # Guardar frame
        output_path = os.path.join(output_dir, f"claudy_orbit_frame_{frame_idx}.png")
        rgb_frame.save(output_path, 'PNG')
        print(f"[+] Frame {frame_idx}: {output_path}")

    return True


def backup_original_frames(frames_dir):
    """Hace backup de los frames originales de Claudy."""
    backup_dir = os.path.join(frames_dir, "backup_original")
    os.makedirs(backup_dir, exist_ok=True)

    for i in range(6):
        original = os.path.join(frames_dir, f"claudy_orbit_frame_{i}.png")
        if os.path.exists(original):
            import shutil
            backup_path = os.path.join(backup_dir, f"claudy_orbit_frame_{i}.png")
            shutil.copy(original, backup_path)

    print(f"[+] Backup guardado en: {backup_dir}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python skin_swap.py <imagen>")
        print("Ejemplo: python skin_swap.py animal.png")
        sys.exit(1)

    input_image = sys.argv[1]

    if not os.path.exists(input_image):
        print(f"[!] Imagen no encontrada: {input_image}")
        sys.exit(1)

    # Directorio de frames de Claudy
    script_dir = os.path.dirname(os.path.abspath(__file__))
    frames_dir = script_dir

    print(f"[*] Procesando imagen: {input_image}")
    print(f"[*] Directorio de frames: {frames_dir}")

    # Backup de frames originales
    print("\n[*] Haciendo backup de frames originales...")
    backup_original_frames(frames_dir)

    # Crear frames animados
    print("\n[*] Generando 6 frames animados...")
    create_animated_frames(input_image, frames_dir, frame_size=128)

    # Crear flag para que pet.py no sobreescriba los frames con generate_sprite()
    flag_path = os.path.join(frames_dir, "custom_skin.flag")
    with open(flag_path, 'w') as f:
        f.write(f"source: {input_image}\n")
    print(f"[+] Flag de skin personalizado creado: {flag_path}")

    # Extraer color dominante
    print("\n[*] Analizando color dominante...")
    dominant = get_dominant_color(input_image)
    hex_color_str = hex_color(dominant)
    print(f"[+] Color dominante: {dominant} -> {hex_color_str}")

    print("\n[+] Skin swap completado!")
    print(f"[*] Los frames están listos en: {frames_dir}")
    print("[*] Reinicia Claudy para ver el nuevo skin.")


if __name__ == "__main__":
    main()
