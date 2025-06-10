
import os
import pygame
import tkinter as tk
from tkinter import filedialog

from PIPELINE_gui import run_pipeline
from file_crypto_helpers import select_file_dialog, read_file_blocks, write_file_from_blocks

# ----------------- Constantes de la interfaz gráfica -----------------
MENU_WIDTH, MENU_HEIGHT = 600, 600
BG_COLOR_MENU       = (0, 0, 0)
BUTTON_COLOR        = (0, 200, 0)
BUTTON_HOVER_COLOR  = (0, 150, 0)
TEXT_COLOR          = (255, 255, 255)
TITLE_COLOR         = (255, 255, 255)
FONT_SIZE_TITLE     = 55
FONT_SIZE_BUTTON    = 36
BUTTON_WIDTH        = 200
BUTTON_HEIGHT       = 60
BUTTON_SPACING      = 40

def draw_button(screen, font, text, rect, mouse_pos):
    """
    Dibuja un botón rectangular con el texto 'text'.
    Si el ratón está sobre el botón, se usa BUTTON_HOVER_COLOR, sino BUTTON_COLOR.
    """
    x, y, w, h = rect
    if x <= mouse_pos[0] <= x + w and y <= mouse_pos[1] <= y + h:
        color = BUTTON_HOVER_COLOR
    else:
        color = BUTTON_COLOR

    pygame.draw.rect(screen, color, rect, border_radius=8)
    text_surf = font.render(text, True, TEXT_COLOR)
    text_rect = text_surf.get_rect(center=(x + w // 2, y + h // 2))
    screen.blit(text_surf, text_rect)

def build_tea_program_for_blocks(blocks, key_tuple, decrypt=False):
    """
    Construye dinámicamente un programa TEA que:
      1) Carga la clave 128 bits en K0..K3.
      2) Por cada bloque de 64 bits:
         a) MOV V0,#v0; MOV V1,#v1
         b) Si decrypt:  MOV SUM,#(DELTA*32); MOV CTR,#32 
            Si encrypt:  MOV SUM,#0;          MOV CTR,#32 
         c) label_i: CRYPT_ROUND V0, V1, KEYPTR, dir 
                      CRYPT_LOOP  label_i, CTR
         d) STORE_CRYPT V0, ('DATA_IDX', 2*idx)
            STORE_CRYPT V1, ('DATA_IDX', 2*idx+1)
    """
    program = []

    # 1) Cargar clave en registros K0..K3
    program.append({'opcode': 'MOV', 'dest': 'K0', 'value': key_tuple[0]})
    program.append({'opcode': 'MOV', 'dest': 'K1', 'value': key_tuple[1]})
    program.append({'opcode': 'MOV', 'dest': 'K2', 'value': key_tuple[2]})
    program.append({'opcode': 'MOV', 'dest': 'K3', 'value': key_tuple[3]})

    # Constante DELTA en 32 bits:
    DELTA = 0x9E3779B9
    SUM_START = (DELTA * 32) & 0xFFFFFFFF

    # 2) Procesar cada bloque
    for idx, (v0, v1) in enumerate(blocks):
        label_name = f"loop_block_{idx}"

        # a) Cargar datos en V0, V1
        program.append({'opcode': 'MOV', 'dest': 'V0', 'value': v0})
        program.append({'opcode': 'MOV', 'dest': 'V1', 'value': v1})

        # b) Inicialización de SUM y CTR
        if decrypt:
            # Para descifrar: SUM = DELTA * 32
            program.append({'opcode': 'MOV', 'dest': 'SUM', 'value': SUM_START})
        else:
            # Para cifrar: SUM = 0
            program.append({'opcode': 'MOV', 'dest': 'SUM', 'value': 0})

        # Ambos casos: CTR = 32
        program.append({'opcode': 'MOV', 'dest': 'CTR', 'value': 32})

        # c) Bucle de 32 rondas exactas:
        #    1) CRYPT_ROUND … 
        #    2) CRYPT_LOOP label, CTR  (decrementa y salta)
        program.append({
            'opcode': 'CRYPT_ROUND',
            'v0': 'V0',
            'v1': 'V1',
            'kptr': 'KEYPTR',
            'dir': 0 if decrypt else 1
        })
        program.append({
            'opcode': 'CRYPT_LOOP',
            'label': label_name,
            'reg': 'CTR'
        })

        # d) Almacenar resultado cifrado/descifrado en memoria
        program.append({
            'opcode': 'STORE_CRYPT',
            'src': 'V0',
            'mode': ('DATA_IDX', idx * 2)
        })
        program.append({
            'opcode': 'STORE_CRYPT',
            'src': 'V1',
            'mode': ('DATA_IDX', idx * 2 + 1)
        })

    return program

def process_file_with_tea(decrypt=False):
    """
    1) Selecciona un archivo (diálogo).
    2) Lee sus bytes en bloques de 64 bits (padding con ceros si hace falta).
    3) Define una clave de 128 bits (ejemplo fijo).
    4) Construye el programa TEA usando build_tea_program_for_blocks(...).
    5) Llama a run_pipeline(program) y recupera encrypted_blocks.
    6) Reensambla bloques y escribe el archivo de salida (_enc o _dec).
    """
    # 1) Diálogo de selección de archivo
    filepath = select_file_dialog()
    if not filepath:
        return  # El usuario canceló

    # 2) Leer bloques de 64 bits
    blocks = read_file_blocks(filepath)

    # 3) Clave TEA (128 bits) — la misma para cifrar y descifrar
    demo_key = (0xA56BABCD, 0x00000000, 0xFFFFFFFF, 0x12345678)

    # 4) Generar el “programa TEA” corregido
    tea_prog = build_tea_program_for_blocks(blocks, demo_key, decrypt)

    # —— Depuración: mostrar en consola el programa generado ——
    print("===== Programa TEA generado =====")
    for idx, instr in enumerate(tea_prog):
        print(f"{idx:03d}: {instr}")
    print("=================================")

    # 5) Ejecutar pipeline (con interfaz Pygame) y devolver lista de bloques procesados
    encrypted_blocks = run_pipeline(tea_prog)

    # 6) Guardar bloques resultantes en un nuevo archivo
    base, ext = os.path.splitext(os.path.basename(filepath))
    suffix = "_dec" if decrypt else "_enc"
    out_name = f"{base}{suffix}{ext}"
    out_path = os.path.join(os.path.dirname(filepath), out_name)

    write_file_from_blocks(out_path, encrypted_blocks)
    print(f"Archivo de salida escrito en: {out_path}")

def main_menu():
    """
    Menú principal con dos botones:
      - "Encriptar"   → abre diálogo, construye programa con decrypt=False
      - "Desencriptar"→ idem, pero decrypt=True
    """
    pygame.init()
    screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT))
    pygame.display.set_caption("TEA Algorithm")

    title_font = pygame.font.Font(None, FONT_SIZE_TITLE)
    button_font = pygame.font.Font(None, FONT_SIZE_BUTTON)
    clock = pygame.time.Clock()

    # Centrar verticalmente los botones
    total_buttons_height = 2 * BUTTON_HEIGHT + BUTTON_SPACING
    start_y = (MENU_HEIGHT - total_buttons_height) // 2

    btn_x = (MENU_WIDTH - BUTTON_WIDTH) // 2
    btn1_y = start_y
    btn2_y = start_y + BUTTON_HEIGHT + BUTTON_SPACING

    encrypt_rect = pygame.Rect(btn_x, btn1_y, BUTTON_WIDTH, BUTTON_HEIGHT)
    decrypt_rect = pygame.Rect(btn_x, btn2_y, BUTTON_WIDTH, BUTTON_HEIGHT)

    title_surf = title_font.render("TEA Algorithm", True, TITLE_COLOR)
    title_rect = title_surf.get_rect(center=(MENU_WIDTH // 2, 80))

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if encrypt_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    process_file_with_tea(decrypt=False)
                    return

                elif decrypt_rect.collidepoint(mouse_pos):
                    pygame.quit()
                    process_file_with_tea(decrypt=True)
                    return

        screen.fill(BG_COLOR_MENU)
        screen.blit(title_surf, title_rect)
        draw_button(screen, button_font, "Encriptar", encrypt_rect, mouse_pos)
        draw_button(screen, button_font, "Desencriptar", decrypt_rect, mouse_pos)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

if __name__ == "__main__":
    main_menu()
