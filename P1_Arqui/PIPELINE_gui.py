
import pygame
from PIPELINE import TEAPipeline
#from TEA_PROGRAM import tea_program

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
        ['CTR', 'SUM', 'KEYPTR', 'DATAPTR']
    ]

    for col_idx, col in enumerate(columns):
        x = 50 + col_idx * 250
        for i, reg in enumerate(col):
            value = pipeline.reg[reg] & 0xFFFFFFFF
            text = f"{reg}: {value:08x}"
            text_surf = font.render(text, True, FONT_COLOR)
            screen.blit(text_surf, (x, y + i * 30))


def draw_memory(screen, font, pipeline):
    y = MEMORY_START_Y
    header = font.render("Direcciones de Memoria:", True, FONT_COLOR)
    screen.blit(header, (50, y))

    for i in range(8):
        addr = i * 4
        mem_val = pipeline.memory[i] & 0xFFFFFFFF
        text = f"[{addr:04x}]: {mem_val:08x}"
        text_surf = font.render(text, True, FONT_COLOR)
        screen.blit(text_surf, (50 + (i % 4) * 250, y + 30 + (i // 4) * 30))


def run_pipeline(program):
    
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TEA PIPELINE")
    font = pygame.font.Font(None, FONT_SIZE)
    clock = pygame.time.Clock()

    pipeline = TEAPipeline()

    # Configura registros iniciales (igual que antes)
    pipeline.reg['DATAPTR'] = 0x200
    pipeline.reg['KEYPTR'] = 0x100

    # Cargar datos de ejemplo
    pipeline.memory[0x100 // 4] = 0x12345678  # key[0]
    pipeline.memory[0x104 // 4] = 0x9ABCDEF0  # key[1]
    pipeline.memory[0x200 // 4] = 0x01234567  # v0
    pipeline.memory[0x204 // 4] = 0x89ABCDEF  # v1

    pipeline.load_program(program)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Con la tecla SPACE avanzamos un ciclo de pipeline
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if pipeline.reg['PC'] < len(program) or any(pipeline.pipeline.values()):
                    pipeline.execute_cycle(program)
                else:
                    print(f"SUM final = 0x{pipeline.reg['SUM']:08X}")
                    running = False

        # Dibujo de fondo y de secciones habituales
        screen.fill(BG_COLOR)
        draw_pipeline(screen, font, pipeline)
        draw_registers(screen, font, pipeline)
        draw_memory(screen, font, pipeline)

        # ------------------ BARRA DE PROGRESO ------------------
        # Cálculo del porcentaje de instrucciones "fetched" (PC / len)
        total_insn = len(program)
        fetched_insn = pipeline.reg['PC']
        if fetched_insn > total_insn:
            fetched_insn = total_insn

        progress_pct = fetched_insn / total_insn if total_insn > 0 else 1.0

        # Dimensiones de la barra de progreso
        bar_margin = 50
        bar_width = WIDTH - 2 * bar_margin
        bar_height = 20
        bar_x = bar_margin
        bar_y = HEIGHT - bar_height - 30  # 30 px encima del borde inferior

        # Color de fondo de la barra (gris oscuro para el “track”)
        pygame.draw.rect(screen,
                         (50, 50, 50),
                         (bar_x, bar_y, bar_width, bar_height),
                         border_radius=5)

        # Color de la parte llena (verde):
        filled_width = int(bar_width * progress_pct)
        pygame.draw.rect(screen,
                         (0, 200, 0),
                         (bar_x, bar_y, filled_width, bar_height),
                         border_radius=5)

        # Texto de porcentaje encima de la barra
        pct_text = f"{int(progress_pct * 100)} %"
        pct_surf = font.render(pct_text, True, FONT_COLOR)
        # Centrar el texto dentro de la barra
        pct_rect = pct_surf.get_rect(center=(bar_x + bar_width // 2, bar_y + bar_height // 2))
        screen.blit(pct_surf, pct_rect)
        # -------------------------------------------------------

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()

