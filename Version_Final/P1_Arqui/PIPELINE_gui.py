# PIPELINE_gui.py

import pygame
from PIPELINE import TEAPipeline

# ----------------- Constantes de la interfaz gráfica (para el pipeline) -----------------
WIDTH, HEIGHT       = 1200, 800
BG_COLOR            = (0, 0, 0)
FONT_COLOR          = (255, 255, 255)
ACTIVE_COLOR        = (50, 150, 50)
INACTIVE_COLOR      = (100, 100, 100)
FONT_SIZE           = 23
PIPELINE_START_Y    = 50
REGISTER_START_Y    = 250
MEMORY_START_Y      = 500

def draw_pipeline(screen, font, pipeline):
    stages = ["IF", "ID", "EX", "MEM", "WB"]
    block_width, block_height = 200, 60
    spacing = 30

    for i, stage in enumerate(stages):
        x = 50 + i * (block_width + spacing)
        color = ACTIVE_COLOR if pipeline.pipeline[stage] else INACTIVE_COLOR
        pygame.draw.rect(screen, color, (x, PIPELINE_START_Y, block_width, block_height))

        instr = pipeline.pipeline[stage]
        text_str = f"{stage}: {instr['opcode'] if instr else 'Vacío'}"
        if instr and 'mode' in instr and instr['mode']:
            text_str += f" [{instr['mode'][0]}]"
        text_surf = font.render(text_str, True, FONT_COLOR)
        screen.blit(text_surf, (x + 10, PIPELINE_START_Y + 15))

def draw_registers(screen, font, pipeline):
    y = REGISTER_START_Y
    header = font.render("Sección de Registros:", True, FONT_COLOR)
    screen.blit(header, (50, y - 45))

    columns = [
        ['V0', 'V1', 'T0', 'T1'],
        ['K0', 'K1', 'K2', 'K3'],
        ['CTR', 'SUM']
    ]

    for col_idx, col in enumerate(columns):
        x = 50 + col_idx * 250
        for i, reg in enumerate(col):
            value = pipeline.reg[reg] & 0xFFFFFFFF
            text = f"{reg}: {value:08x}"
            text_surf = font.render(text, True, FONT_COLOR)
            screen.blit(text_surf, (x, y + i * 30))

def draw_memory(screen, font, pipeline):
    y = MEMORY_START_Y - 100
    header = font.render("Direcciones de Memoria:", True, FONT_COLOR)
    screen.blit(header, (50, y - 10))

    # Ahora limitamos a lo que realmente contenga pipeline.memory para evitar IndexError
    max_to_show = min(8, len(pipeline.memory))
    for i in range(max_to_show):
        addr = i * 4
        mem_val = pipeline.memory[i] & 0xFFFFFFFF
        text = f"[{addr:04x}]: {mem_val:08x}"
        text_surf = font.render(text, True, FONT_COLOR)
        screen.blit(text_surf, (50 + (i % 4) * 250, y + 30 + (i // 4) * 30))

def draw_vault(screen, font, pipeline):
    start_y = MEMORY_START_Y + 80  # un poco debajo de la memoria
    header = font.render("Bóveda de Claves (Vault):", True, FONT_COLOR)
    screen.blit(header, (50, start_y))

    for slot_index, key in enumerate(pipeline.vault.slots):
        slot_text = f"Slot {slot_index}: " + "  ".join([f"{word:08X}" for word in key])
        slot_surf = font.render(slot_text, True, FONT_COLOR)
        screen.blit(slot_surf, (50, start_y + 30 + slot_index * 30))

def run_pipeline(program, pipeline=None):
    """
    Ejecuta el pipeline con Pygame y, al cerrar, devuelve la lista `encrypted_blocks`
    extraída de pipeline.memory. Cada bloque ocupa dos posiciones consecutivas.
    Se soporta modo automático y modo paso a paso con tecla "s" y "espacio" para avanzar.
    """
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TEA PIPELINE")
    font = pygame.font.Font(None, FONT_SIZE)
    clock = pygame.time.Clock()

    if pipeline is None:
        pipeline = TEAPipeline()

    pipeline.reg['DATAPTR'] = 0
    pipeline.reg['KEYPTR'] = 0x100
    pipeline.load_program(program)

    store_count = sum(1 for instr in program if instr.get('opcode') == 'STORE_CRYPT')
    num_blocks = store_count // 2
    pipeline.memory = [0] * (num_blocks * 2)

    # Parámetros de velocidad y control
    CYCLES_PER_FRAME = 500  # Ciclos automaticos
    step_mode = False       # Modo SteByStep
    step_requested = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    step_mode = not step_mode
                elif event.key == pygame.K_SPACE:
                    step_requested = True

        # Ejecución de ciclos
        if step_mode:
            if step_requested:
                if pipeline.reg['PC'] < len(program) or any(pipeline.pipeline.values()):
                    pipeline.execute_cycle(program)
                else:
                    print(f"SUM final = 0x{pipeline.reg['SUM']:08X}")
                    running = False
                step_requested = False
        else:
            for _ in range(CYCLES_PER_FRAME):
                if pipeline.reg['PC'] < len(program) or any(pipeline.pipeline.values()):
                    pipeline.execute_cycle(program)
                else:
                    print(f"SUM final = 0x{pipeline.reg['SUM']:08X}")
                    running = False
                    break

        # Dibujar todo
        screen.fill(BG_COLOR)
        draw_pipeline(screen, font, pipeline)
        draw_registers(screen, font, pipeline)
        draw_memory(screen, font, pipeline)
        draw_vault(screen, font, pipeline)

        # Mostrar modo arriba
        mode_text = ("Modo: StepByStep, avanzar con tecla espacio"
                     if step_mode else f"Modo: Automático ({CYCLES_PER_FRAME} ciclos/frame)")
        mode_surf = font.render(mode_text, True, FONT_COLOR)
        screen.blit(mode_surf, (50, 10))

        # Barra de progreso (igual que antes)
        total_insn = len(program)
        fetched_insn = min(pipeline.reg['PC'], total_insn)
        pct = fetched_insn / total_insn if total_insn else 1.0
        bar_margin, bar_height = 50, 20
        bar_width = WIDTH - 2 * bar_margin
        bar_x, bar_y = bar_margin, HEIGHT - bar_height - 30
        pygame.draw.rect(screen, (50,50,50), (bar_x, bar_y, bar_width, bar_height), border_radius=5)
        pygame.draw.rect(screen, ACTIVE_COLOR, (bar_x, bar_y, int(bar_width * pct), bar_height), border_radius=5)
        pct_surf = font.render(f"{int(pct*100)} %", True, FONT_COLOR)
        pct_rect = pct_surf.get_rect(center=(bar_x + bar_width//2, bar_y + bar_height//2))
        screen.blit(pct_surf, pct_rect)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

    # Recolectar bloques procesados
    encrypted_blocks = []
    for i in range(num_blocks):
        v0_enc = pipeline.memory[i*2] & 0xFFFFFFFF
        v1_enc = pipeline.memory[i*2 + 1] & 0xFFFFFFFF
        encrypted_blocks.append((v0_enc, v1_enc))

    return encrypted_blocks
