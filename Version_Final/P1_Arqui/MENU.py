import os
import pygame
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from PIPELINE_gui import run_pipeline, TEAPipeline
from file_crypto_helpers import select_file_dialog, read_file_blocks, write_file_from_blocks

# ----------------- Constantes de la interfaz gráfica -----------------
MENU_WIDTH, MENU_HEIGHT   = 600, 700
BG_COLOR_MENU            = (30, 30, 30)
BUTTON_COLOR             = (0, 150, 0)
BUTTON_HOVER_COLOR       = (0, 200, 0)
TEXT_COLOR               = (240, 240, 240)
TITLE_COLOR              = (255, 255, 255)
FONT_SIZE_TITLE          = 60
FONT_SIZE_BUTTON         = 36
FONT_SIZE_LABEL          = 28
BUTTON_WIDTH             = 220
BUTTON_HEIGHT            = 60
BUTTON_SPACING           = 40
DROPDOWN_WIDTH           = 180
DROPDOWN_HEIGHT          = 50
DROPDOWN_OPTION_HEIGHT   = 40
DROPDOWN_COLOR           = (50, 50, 50)
DROPDOWN_HOVER_COLOR     = (70, 70, 70)

# ---------------------------------------------------------------------
# Carga de llaves desde keys.txt (mismo directorio)
# ---------------------------------------------------------------------
def load_keys_from_txt(path):
    with open(path, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
    if len(lines) != 4:
        raise ValueError("El fichero debe contener exactamente 4 llaves.")
    keys = []
    for hexstr in lines:
        if hexstr.lower().startswith('0x'):
            hexstr = hexstr[2:]
        if len(hexstr) != 32:
            raise ValueError(f"Longitud incorrecta: {hexstr}")
        full = int(hexstr, 16)
        parts = tuple((full >> (96 - 32*i)) & 0xFFFFFFFF for i in range(4))
        keys.append(parts)
    return keys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_PATH  = os.path.join(SCRIPT_DIR, "keys.txt")
try:
    KEYS = load_keys_from_txt(KEYS_PATH)
except Exception as e:
    tk.Tk().withdraw()
    messagebox.showerror("Error al leer keys.txt", str(e))
    exit(1)

# ---------------------------------------------------------------------
# Dibujo de botones y texto
# ---------------------------------------------------------------------
def draw_button(screen, font, text, rect, mouse_pos):
    x,y,w,h = rect
    color = BUTTON_HOVER_COLOR if rect.collidepoint(mouse_pos) else BUTTON_COLOR
    pygame.draw.rect(screen, color, rect, border_radius=8)
    surf = font.render(text, True, TEXT_COLOR)
    screen.blit(surf, surf.get_rect(center=rect.center))

def draw_text(screen, font, text, pos, color=TEXT_COLOR):
    surf = font.render(text, True, color)
    screen.blit(surf, surf.get_rect(topleft=pos))

# ---------------------------------------------------------------------
# Generación del programa TEA
# ---------------------------------------------------------------------
def build_tea_program_for_blocks(blocks, key_slot, decrypt=False):
    program = []
    # 1) Traemos la llave desde la bóveda a K0–K3 usando el slot elegido
    program.append({'opcode': 'LOAD_KEY', 'index': key_slot})

    DELTA = 0x9E3779B9
    SUM_START = (DELTA * 32) & 0xFFFFFFFF

    for idx, (v0, v1) in enumerate(blocks):
        label = f"loop_block_{idx}"

        # Cargamos los datos
        program += [
            {'opcode': 'ASN', 'dest': 'V0', 'value': v0},
            {'opcode': 'ASN', 'dest': 'V1', 'value': v1},
        ]

        # Inicializamos SUM y CTR
        if decrypt:
            program.append({'opcode': 'ASN', 'dest': 'SUM', 'value': SUM_START})
        else:
            program.append({'opcode': 'ASN', 'dest': 'SUM', 'value': 0})
        program.append({'opcode': 'ASN', 'dest': 'CTR', 'value': 32})

        # Bucle de 32 rondas
        program.append({
            'opcode': 'CRYPT_ROUND',
            'v0': 'V0',
            'v1': 'V1',
            'kptr': 'KEYPTR',
            'dir': 0 if decrypt else 1,
            'label': label           
        })
        program.append({
            'opcode': 'CRYPT_LOOP',
            'label': label,
            'reg': 'CTR'
        })

        # Almacenamos el bloque cifrado/descifrado
        program += [
            {'opcode': 'STORE_CRYPT', 'src': 'V0', 'mode': ('DATA_IDX', 2*idx)},
            {'opcode': 'STORE_CRYPT', 'src': 'V1', 'mode': ('DATA_IDX', 2*idx+1)},
        ]

    return program
# ---------------------------------------------------------------------
# Fujo del procesamiento del archivo 
# ---------------------------------------------------------------------
def process_file_with_tea(decrypt, slot):
    # 1) Selección de archivo
    root = tk.Tk(); root.withdraw()
    filepath = filedialog.askopenfilename(title="Selecciona archivo a procesar")
    root.destroy()
    if not filepath:
        return

    # 2) Leer bloques *y* longitud original
    blocks = read_file_blocks(filepath)

    # 3) — PRE-CARGA en la bóveda — 
    # Instancia temporal para almacenar las llaves
    pipeline = TEAPipeline()
    for i,key in enumerate(KEYS):
        pipeline.vault.store_key(i, *key)

    # 4) Generar programa TEA dependiendo de los bloques
    TEA_prog = build_tea_program_for_blocks(blocks, key_slot=slot, decrypt=decrypt)

    # —— Depuración: mostrar en consola el programa generado ——
    print("=== Programa TEA ===")
    for i,inst in enumerate(TEA_prog):
        print(f"{i:03d}: {inst}")
    
    # 5) Ejecutar:
    # Pasamos la misma instancia pipeline_temp para que use esa bóveda con la llave
    encrypted_blocks = run_pipeline(TEA_prog, pipeline=pipeline)

    # 6) Guardar bloques resultantes en un nuevo archivo
    base,ext = os.path.splitext(os.path.basename(filepath))
    suffix = "_dec" if decrypt else "_enc"
    out_path = os.path.join(os.path.dirname(filepath), f"{base}{suffix}{ext}")
    write_file_from_blocks(out_path, encrypted_blocks)

    tk.Tk().withdraw()
    messagebox.showinfo("Completado", f"Archivo guardado en:\n{out_path}")
    tk.Tk().withdraw()
    pygame.quit()
    sys.exit(0)

# ---------------------------------------------------------------------
# Menú principal 
# ---------------------------------------------------------------------
def main_menu():
    pygame.init()
    screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT))
    pygame.display.set_caption("TEA Algorithm")
    clock = pygame.time.Clock()

    title_font  = pygame.font.Font(None, FONT_SIZE_TITLE)
    btn_font    = pygame.font.Font(None, FONT_SIZE_BUTTON)
    label_font  = pygame.font.Font(None, FONT_SIZE_LABEL)
    offset_y = int(MENU_HEIGHT * 0.150)

    # Botones Encriptar/Desencriptar
    btn_x = (MENU_WIDTH - BUTTON_WIDTH)//2
    btn_y = offset_y + 120
    encrypt_btn = pygame.Rect(btn_x, btn_y, BUTTON_WIDTH, BUTTON_HEIGHT)
    decrypt_btn = pygame.Rect(btn_x, btn_y+BUTTON_HEIGHT+BUTTON_SPACING, BUTTON_WIDTH, BUTTON_HEIGHT)

    # Dropdown Llave
    dd_x = (MENU_WIDTH - DROPDOWN_WIDTH)//2
    dd_y = btn_y + 2*BUTTON_HEIGHT + BUTTON_SPACING // 1 + 40
    dd_rect = pygame.Rect(dd_x, dd_y, DROPDOWN_WIDTH, DROPDOWN_HEIGHT)
    options = [pygame.Rect(dd_x, dd_y + (i+1)*DROPDOWN_OPTION_HEIGHT, DROPDOWN_WIDTH, DROPDOWN_OPTION_HEIGHT) for i in range(4)]
    selected_slot = 0
    dropdown_open = False

    running = True
    while running:
        mouse = pygame.mouse.get_pos()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                # Toggle dropdown
                if dd_rect.collidepoint(mouse):
                    dropdown_open = not dropdown_open
                # Selección de opción
                elif dropdown_open:
                    for idx, opt in enumerate(options):
                        if opt.collidepoint(mouse):
                            selected_slot = idx
                            dropdown_open = False
                            break
                    else:
                        dropdown_open = False
                # Botones encrypt/decrypt
                if encrypt_btn.collidepoint(mouse):
                    process_file_with_tea(decrypt=False, slot=selected_slot)
                elif decrypt_btn.collidepoint(mouse):
                    process_file_with_tea(decrypt=True, slot=selected_slot)

        # Dibujado
        screen.fill(BG_COLOR_MENU)
        # Título
        title_surf = title_font.render("TEA Algorithm", True, TITLE_COLOR)
        screen.blit(title_surf, title_surf.get_rect(center=(MENU_WIDTH//2, offset_y)))

        # Dropdown label y cuadro
        draw_text(screen, label_font, "Seleccionar Llave", (dd_x, dd_y-30))
        pygame.draw.rect(screen, DROPDOWN_COLOR, dd_rect, border_radius=6)
        draw_text(screen, label_font, f"Key {selected_slot}", (dd_x+10, dd_y+12))

        # Opciones desplegadas
        if dropdown_open:
            for idx, opt in enumerate(options):
                color = DROPDOWN_HOVER_COLOR if opt.collidepoint(mouse) else DROPDOWN_COLOR
                pygame.draw.rect(screen, color, opt)
                draw_text(screen, label_font, f"Key {idx}", (opt.x+10, opt.y+8))

        # Botones
        draw_button(screen, btn_font, "Encriptar", encrypt_btn, mouse)
        draw_button(screen, btn_font, "Desencriptar", decrypt_btn, mouse)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main_menu()
