import pygame
from TEA_ISA import TEACPU 
from TEA_PROGRAM import *

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


class TEAPipeline(TEACPU):
    def __init__(self):
        super().__init__()
        # Alias para compatibilidad con ISA _mov
        self.registers = self.reg
        self.DELTA = 0x9E3779B9
        # Inicializar pipeline stages e if_delay
        self.pipeline = {stage: None for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']}
        self.if_delay = False
        self.screen, self.font = self.initialize_pygame()
        self.clock = pygame.time.Clock()
        self.addr_modes = self.addr_modes
        
    def initialize_pygame(self):
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("TEA PIPELINE")
        return screen, pygame.font.Font(None, FONT_SIZE)

    def execute_cycle(self, program):
        # --- WB stage ---
        if self.pipeline['WB']:
            self.write_back(self.pipeline['WB'])
            self.pipeline['WB'] = None

        # --- MEM stage ---
        if self.pipeline['MEM']:
            mem_out = self.memory_access(self.pipeline['MEM'])
            if mem_out:
                self.pipeline['WB'] = mem_out.copy()
            self.pipeline['MEM'] = None

        # --- EX stage ---
        if self.pipeline['EX']:
            instr = self.pipeline['EX']
            decoded = self.decode_instruction(instr)
            self.execute_instruction(decoded)
            # Pasa a MEM solo si produce resultado
            if 'dest' in decoded and 'result' in decoded:
                self.pipeline['MEM'] = decoded.copy()
            self.pipeline['EX'] = None

            if decoded['opcode'] == 'CRYPT_LOOP' and self.reg[decoded['operands'][1]] > 0:
                self.pipeline['IF'] = None
                self.pipeline['ID'] = None
                self.if_delay = False

            if self.pipeline['EX'] and self.pipeline['EX']['opcode'] == 'CRYPT_ROUND':
                current_sum = self.reg['SUM']
                # Actualizar cualquier etapa que necesite SUM
                if self.pipeline['MEM'] and 'SUM' in self.pipeline['MEM'].get('operands', []):
                    self.pipeline['MEM']['result'] = current_sum
                if self.pipeline['WB'] and 'SUM' in self.pipeline['WB'].get('operands', []):
                    self.pipeline['WB']['result'] = current_sum

        # --- ID → EX ---
        if self.pipeline['ID'] and self.pipeline['EX'] is None:
            self.pipeline['EX'] = self.pipeline['ID'].copy()
            self.pipeline['ID'] = None

        # --- IF → ID / Fetch ---
        if self.pipeline['IF'] and self.pipeline['ID'] is None:
            self.pipeline['ID'] = self.pipeline['IF'].copy()
            self.pipeline['IF'] = None

        elif not self.if_delay and self.reg['PC'] < len(program):
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True
        else:
            self.if_delay = False

    def write_back(self, instr):
        if 'dest' in instr and 'result' in instr:
            print(f"WB: Escribiendo {instr['result']} en {instr['dest']}")
            self.reg[instr['dest']] = instr['result']

    def memory_access(self, instr):
        """
        Acceso a memoria usando instrucciones decodificadas.
        Usa 'operands' para extraer registers/modes.
        """
        opcode = instr.get('opcode')
        # operands: [Rd, mode] or [Rs, mode]
        if opcode == 'LOAD_CRYPT':
            rd, mode = instr['operands']
            mode_type, offset = mode
            addr = self.addr_modes[mode_type](offset)
            instr['dest'] = rd
            instr['result'] = self.memory[addr // 4]
            return instr
        elif opcode == 'STORE_CRYPT':
            rs, mode = instr['operands']
            mode_type, offset = mode
            addr = self.addr_modes[mode_type](offset)
            self.memory[addr // 4] = self.reg[rs]
            return None
        else:
            return instr

    def execute_instruction(self, instr):
        opcode = instr['opcode']
        ops = instr['operands']
        # Ejecuta usando el ISA
        super().execute([opcode] + ops)
        # Capturar dest/result
        if opcode == 'MOV':
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd]
        elif opcode == 'LOAD_CRYPT':
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd]
        elif opcode in ('TEA_SBOX', 'TEA_MIX'):
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd]
        elif opcode == 'CRYPT_ROUND':
            # Registrar acumulador SUM tras la ronda
            #print(f"[execute_instruction] SUM actualizado en EX: {hex(self.reg['SUM'])}")
            #instr['dest'] = 'SUM'
            #instr['result'] = self.reg['SUM']
            pass
        # STORE_CRYPT no pasan resultado a MEM

    def decode_instruction(self, raw_instr):
        opcode = raw_instr['opcode']
        decoded = {'opcode': opcode, 'operands': []}
        if opcode == 'MOV':
            decoded['operands'] = [raw_instr['dest'], f"#{raw_instr['value']}"]
        elif opcode == 'LOAD_CRYPT':
            decoded['operands'] = [raw_instr['dest'], raw_instr['mode']]
        elif opcode == 'STORE_CRYPT':
            decoded['operands'] = [raw_instr['src'], raw_instr['mode']]
        elif opcode == 'CRYPT_ROUND':
            # Aquí convertimos Kptr (nombre de registro) en dirección de memoria
            rd_v0 = raw_instr['v0']
            rd_v1 = raw_instr['v1']
            kptr_addr = self.reg[raw_instr['kptr']]
            direction = int(raw_instr['dir'])  
            decoded['operands'] = [rd_v0, rd_v1, kptr_addr, direction]
        elif opcode in ('TEA_SBOX', 'TEA_MIX', 'CRYPT_LOOP'):
            # Mapea names de fmt a claves de raw_instr
            fmt = self.isa[opcode]['fmt']
            # Diccionario de mapeo de fmt->raw_instr keys
            field_map = {
                'Rd': 'dest', 'Rs': 'src', 'Rs1': 'src1', 'Rs2': 'src2',
                'Imm': 'imm', 'Imm/Reg': 'value', 'AddrMode': 'mode',
                'Label': 'label', 'Reg': 'reg'
            }
            ops = []
            for name in fmt:
                key = field_map.get(name)
                if key is None:
                    raise KeyError(f"No hay mapeo para field '{name}' en fmt de {opcode}")
                if key not in raw_instr:
                    raise KeyError(f"Falta el campo '{key}' en la instrucción {raw_instr}")
                ops.append(raw_instr[key])
            decoded['operands'] = ops
            return decoded
        else:
            raise ValueError(f"Decode: opcode desconocido {opcode}")

        return decoded

    def instruction_fetch(self, program):
        if not self.if_delay and self.reg['PC'] < len(program):
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True
        else:
            if self.pipeline['IF'] and self.pipeline['ID'] is None:
                self.pipeline['ID'] = self.pipeline['IF'].copy()
                self.pipeline['IF'] = None
            self.if_delay = False

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
            if instr and 'mode' in instr and instr['mode']:
                text += f" [{instr['mode'][0]}]"
            text_surface = self.font.render(text, True, FONT_COLOR)
            self.screen.blit(text_surface, (x + 10, PIPELINE_START_Y + 15))

    def draw_registers(self):
        y = REGISTER_START_Y
        text = self.font.render("Seccion de Registros:", True, FONT_COLOR)
        self.screen.blit(text, (50, y-45))
        columns = [
            ['V0', 'V1', 'T0', 'T1'],
            ['K0', 'K1', 'K2', 'K3'],
            ['CTR', 'SUM', 'KEYPTR', 'DATAPTR']
        ]
        
        for col_idx, col in enumerate(columns):
            x = 50 + col_idx * 250
            for i, reg in enumerate(col):
                text = f"{reg}: {self.reg[reg]:08x}"
                text_surface = self.font.render(text, True, FONT_COLOR)
                self.screen.blit(text_surface, (x, y + i * 30))

    def draw_memory(self):
        y = MEMORY_START_Y
        text = self.font.render("Seccion de Memoria:", True, FONT_COLOR)
        self.screen.blit(text, (50, y))
        
        for i in range(8):
            addr = i * 4
            text = f"[{addr:04x}]: {self.memory[i]:08x}"
            text_surface = self.font.render(text, True, FONT_COLOR)
            self.screen.blit(text_surface, (50 + (i % 4) * 250, y + 30 + (i // 4) * 30))

    def run_simulation(self, program):
        """Ejecuta simulación del pipeline hasta vaciarlo"""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self.execute_cycle(program)
            # continúa corriendo mientras haya etapas ocupadas o insn por fetch
            if not any(self.pipeline.values()) and self.reg['PC'] >= len(program):
                running = False
            self.screen.fill((30, 30, 30))
            self.draw_pipeline()
            self.draw_registers()
            self.draw_memory()
            pygame.display.flip()
            self.clock.tick(30)
        print(f"SUM final = 0x{self.reg['SUM']:08X}")
        pygame.quit()


if __name__ == "__main__":
    pipeline = TEAPipeline()
    
    # Configurar estado inicial
    pipeline.reg['DATAPTR'] = 0x200  # Dirección de datos
    pipeline.reg['KEYPTR'] = 0x100    # Dirección de clave
    
    # Cargar datos de ejemplo
    pipeline.memory[0x100//4] = 0x12345678  # key[0]
    pipeline.memory[0x104//4] = 0x9ABCDEF0  # key[1]
    pipeline.memory[0x200//4] = 0x01234567  # v0
    pipeline.memory[0x204//4] = 0x89ABCDEF  # v1

    # Carga el programa 
    pipeline.load_program(tea_program)

    # Simulación en pipeline
    pipeline.run_simulation(tea_program)