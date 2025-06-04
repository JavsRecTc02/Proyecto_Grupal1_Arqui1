import pygame


"""

Este Pipeline NO se Usa

"""


# Configuración inicial de Pygame
WIDTH, HEIGHT = 1200, 800
BG_COLOR = (30, 30, 30)
FONT_COLOR = (255, 255, 255)
ACTIVE_COLOR = (50, 150, 50)
INACTIVE_COLOR = (100, 100, 100)
FONT_SIZE = 18
PIPELINE_START_Y = 50
REGISTER_START_Y = 250
MEMORY_START_Y = 500

class TEAPipeline:
    def __init__(self):
        self.screen, self.font = self.initialize_pygame()
        self.registers = {
            'V0': 0, 'V1': 0, 'T0': 0, 'T1': 0,
            'K0': 0, 'K1': 0, 'K2': 0, 'K3': 0,
            'CTR': 0, 'SUM': 0, 'KEYPTR': 0, 'DATAPTR': 0,
            'PC': 0
        }
        self.memory = [0] * 1024
        self.pipeline = {"IF": None, "ID": None, "EX": None, "MEM": None, "WB": None}
        self.if_delay = False
        self.delta = 0x9E3779B9
        
    def initialize_pygame(self):
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("TEA-CRYPT Pipeline Simulator")
        return screen, pygame.font.Font(None, FONT_SIZE)

    def draw_interface(self):
        self.screen.fill(BG_COLOR)
        self.draw_pipeline()
        self.draw_registers()
        self.draw_memory()
        pygame.display.flip()

    def draw_pipeline(self):
        stages = ["IF", "ID", "EX", "MEM", "WB"]
        block_width, block_height = 200, 60
        spacing = 30
        
        for i, stage in enumerate(stages):
            x = 50 + i * (block_width + spacing)
            color = ACTIVE_COLOR if self.pipeline[stage] else INACTIVE_COLOR
            pygame.draw.rect(self.screen, color, (x, PIPELINE_START_Y, block_width, block_height))
            
            instr = self.pipeline[stage]
            text = f"{stage}: {instr['opcode'] if instr else 'Vacío'}"
            text_surface = self.font.render(text, True, FONT_COLOR)
            self.screen.blit(text_surface, (x + 10, PIPELINE_START_Y + 15))

    def draw_registers(self):
        y = REGISTER_START_Y
        columns = [
            ['V0', 'V1', 'T0', 'T1'],
            ['K0', 'K1', 'K2', 'K3'],
            ['CTR', 'SUM', 'KEYPTR', 'DATAPTR']
        ]
        
        for col_idx, col in enumerate(columns):
            x = 50 + col_idx * 250
            for i, reg in enumerate(col):
                text = f"{reg}: {self.registers[reg]:08x}"
                text_surface = self.font.render(text, True, FONT_COLOR)
                self.screen.blit(text_surface, (x, y + i * 30))

    def draw_memory(self):
        y = MEMORY_START_Y
        text = self.font.render("Memoria Criptográfica (Bloques clave y datos):", True, FONT_COLOR)
        self.screen.blit(text, (50, y))
        
        # Mostrar primeros 8 words de memoria
        for i in range(8):
            addr = i * 4
            text = f"[{addr:04x}]: {self.memory[i]:08x}"
            text_surface = self.font.render(text, True, FONT_COLOR)
            self.screen.blit(text_surface, (50 + (i % 4) * 250, y + 30 + (i // 4) * 30))

    def execute_cycle(self, program):
    # Etapa WB (Modificado)
        if self.pipeline["WB"]:
            instr = self.pipeline["WB"]
            if 'result' in instr and 'dest' in instr:  # Verificar ambos campos
                if instr['opcode'] in ['TEA_SBOX', 'TEA_MIX', 'MOV']:
                    self.registers[instr['dest']] = instr['result']
                elif instr['opcode'] == 'LOAD_CRYPT':
                    self.registers[instr['dest']] = instr['result']
            elif instr['opcode'] == 'CRYPT_ROUND':
                pass  # No necesita escritura en WB

        self.pipeline["WB"] = None
        # Etapa MEM
        if self.pipeline["MEM"]:
            instr = self.pipeline["MEM"]
            if instr['opcode'] == 'LOAD_CRYPT':
                addr = self.calculate_address(instr['mode'])
                instr['result'] = self.memory[addr // 4]
            elif instr['opcode'] == 'STORE_CRYPT':
                addr = self.calculate_address(instr['mode'])
                self.memory[addr // 4] = self.registers[instr['src']]
            self.pipeline["WB"] = instr.copy()  # Crear copia para WB
            self.pipeline["MEM"] = None

        # Etapa EX
        if self.pipeline["EX"]:
            instr = self.pipeline["EX"]
            try:
                if instr['opcode'] == 'TEA_SBOX':
                    rs1 = self.registers[instr['rs1']]
                    rs2 = self.registers[instr['rs2']]
                    instr['result'] = ((rs1 << 4) + rs2) & 0xFFFFFFFF
                elif instr['opcode'] == 'TEA_MIX':
                    rs1 = self.registers[instr['rs1']]
                    rs2 = self.registers[instr['rs2']]
                    mix = (rs1 + self.registers['SUM']) ^ (rs2 >> 5)
                    instr['result'] = self.registers[instr['dest']] ^ mix
                elif instr['opcode'] == 'CRYPT_ROUND':
                    self.execute_crypt_round(instr)
                    instr['result'] = 0  # Resultado no aplicable
                elif instr['opcode'] == 'MOV':
                    instr['result'] = instr['value']
            except KeyError as e:
                print(f"Error en EX: Falta clave {e} en {instr}")
            self.pipeline["MEM"] = instr.copy()
            self.pipeline["EX"] = None

        # Etapa ID
        if self.pipeline["ID"]:
            self.pipeline["EX"] = self.pipeline["ID"].copy()
            self.pipeline["ID"] = None

        # Etapa IF (corregida)
        if not self.if_delay and self.registers['PC'] < len(program):
            self.pipeline["IF"] = program[self.registers['PC']].copy()
            self.registers['PC'] += 1
            self.if_delay = True
        else:
            if self.pipeline["IF"] and self.pipeline["ID"] is None:
                self.pipeline["ID"] = self.pipeline["IF"].copy()
                self.pipeline["IF"] = None
            self.if_delay = False

    def calculate_address(self, mode):
        if mode[0] == 'KEY_IDX':
            return self.registers['KEYPTR'] + mode[1] * 4
        elif mode[0] == 'DATA_IDX':
            return self.registers['DATAPTR'] + mode[1] * 4
        return 0

    def execute_crypt_round(self, instr):
        v0 = instr['v0']
        v1 = instr['v1']
        kptr = instr['kptr']
        direction = instr['dir']
        
        if direction == 1:  # Cifrado
            self.registers['SUM'] = (self.registers['SUM'] + self.delta) & 0xFFFFFFFF
            # Operaciones para v0
            self.registers['T0'] = ((self.registers[v1] << 4) + self.memory[kptr//4]) & 0xFFFFFFFF
            mix = (self.registers['T0'] + self.registers['SUM']) ^ ((self.registers[v1] >> 5) + self.memory[kptr//4 +1])
            self.registers[v0] = (self.registers[v0] + mix) & 0xFFFFFFFF
            # Operaciones para v1
            self.registers['T1'] = ((self.registers[v0] << 4) + self.memory[kptr//4 +2]) & 0xFFFFFFFF
            mix = (self.registers['T1'] + self.registers['SUM']) ^ ((self.registers[v0] >> 5) + self.memory[kptr//4 +3])
            self.registers[v1] = (self.registers[v1] + mix) & 0xFFFFFFFF
        else:  # Descifrado
            # Operaciones para v1
            self.registers['T1'] = ((self.registers[v0] << 4) + self.memory[kptr//4 +2]) & 0xFFFFFFFF
            mix = (self.registers['T1'] + self.registers['SUM']) ^ ((self.registers[v0] >> 5) + self.memory[kptr//4 +3])
            self.registers[v1] = (self.registers[v1] - mix) & 0xFFFFFFFF
            # Operaciones para v0
            self.registers['T0'] = ((self.registers[v1] << 4) + self.memory[kptr//4]) & 0xFFFFFFFF
            mix = (self.registers['T0'] + self.registers['SUM']) ^ ((self.registers[v1] >> 5) + self.memory[kptr//4 +1])
            self.registers[v0] = (self.registers[v0] - mix) & 0xFFFFFFFF
            self.registers['SUM'] = (self.registers['SUM'] - self.delta) & 0xFFFFFFFF

    def run_simulation(self, program):
        clock = pygame.time.Clock()
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.execute_cycle(program)
            
            self.draw_interface()
            clock.tick(30)

        pygame.quit()

# Ejemplo de programa TEA
tea_program = [
    {'opcode': 'MOV', 'dest': 'KEYPTR', 'value': 0x100},
    {'opcode': 'MOV', 'dest': 'DATAPTR', 'value': 0x200},
    {'opcode': 'LOAD_CRYPT', 'dest': 'V0', 'mode': ('DATA_IDX', 0)},
    {'opcode': 'LOAD_CRYPT', 'dest': 'V1', 'mode': ('DATA_IDX', 1)},
    {'opcode': 'MOV', 'dest': 'CTR', 'value': 32},
    {'opcode': 'CRYPT_ROUND', 'v0': 'V0', 'v1': 'V1', 'kptr': 0x100, 'dir': 1},
    {'opcode': 'STORE_CRYPT', 'src': 'V0', 'dest': None, 'mode': ('DATA_IDX', 0)},  # Añadir 'dest'
    {'opcode': 'STORE_CRYPT', 'src': 'V1', 'dest': None, 'mode': ('DATA_IDX', 1)}
]

#def main():
#    pipeline = TEAPipeline()
    #pipeline.registers['KEYPTR'] = 0x100
    #pipeline.registers['DATAPTR'] = 0x200
#    pipeline.run_simulation(tea_program)

#if __name__ == "__main__":
#    main()