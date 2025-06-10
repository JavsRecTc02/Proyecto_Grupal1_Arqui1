from TEA_ISA import TEACPU
from vault import Vault


class TEAPipeline(TEACPU):
    def __init__(self):
        super().__init__()
        # Alias para compatibilidad con _mov del ISA
        self.registers = self.reg
        self.vault = Vault()

        # Inicializamos las etapas del pipeline
        self.pipeline = {stage: None for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']}
        self.if_delay = False

        # Ajustamos DATAPTR = 0 para que STORE_CRYPT ('DATA_IDX', offset) vaya a memory[offset]
        self.reg['DATAPTR'] = 0
        # Dejamos KEYPTR = 0x100 sólo en caso de que alguna instrucción LOAD_CRYPT
        # necesite leer clave de alguna posición, pero en nuestro flujo no lo usamos.
        self.reg['KEYPTR'] = 0x100


    def execute_cycle(self, program):
        """
        WB → MEM → EX → ID → IF
        """
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

            # Pasar a MEM si 'dest' y 'result' existen
            if 'dest' in decoded and 'result' in decoded:
                self.pipeline['MEM'] = decoded.copy()

            self.pipeline['EX'] = None

        # --- ID → EX ---
        if self.pipeline['ID'] and self.pipeline['EX'] is None:
            self.pipeline['EX'] = self.pipeline['ID'].copy()
            self.pipeline['ID'] = None

        # --- IF → ID / Fetch ---
        if self.pipeline['IF'] and self.pipeline['ID'] is None:
            self.pipeline['ID'] = self.pipeline['IF'].copy()
            self.pipeline['IF'] = None
            self.if_delay = False

        elif not self.if_delay and self.reg['PC'] < len(program):
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True

        else:
            self.if_delay = False


    def write_back(self, instr):
        if 'dest' in instr and 'result' in instr:
            print(f"WB: Escribiendo {instr['result']:08X} en {instr['dest']}")
            self.reg[instr['dest']] = instr['result'] & 0xFFFFFFFF


    def memory_access(self, instr):
        """
        LOAD_CRYPT y STORE_CRYPT: utiliza instr['operands'] = [reg, (modo, offset)].
        """
        opcode = instr.get('opcode')

        if opcode == 'LOAD_CRYPT':
            rd, mode = instr['operands']
            mode_type, offset = mode
            addr = self.addr_modes[mode_type](offset)
            instr['dest'] = rd
            instr['result'] = self.memory[addr // 4] & 0xFFFFFFFF
            return instr

        elif opcode == 'STORE_CRYPT':
            rs, mode = instr['operands']
            mode_type, offset = mode
            addr = self.addr_modes[mode_type](offset)
            self.memory[addr // 4] = self.reg[rs] & 0xFFFFFFFF
            return None

        else:
            return instr


    def execute_instruction(self, instr):
        """
        Ejecuta la instrucción decodificada (opcode + operands) y captura 'dest'/'result'.
        """
        opcode = instr['opcode']
        ops = instr['operands']

        # Ejecutar la instrucción a nivel de ISA
        super().execute([opcode] + ops)

        # A continuación, si corresponde, marcamos dest/result para pasar a MEM/WB:
        if opcode == 'MOV':
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd] & 0xFFFFFFFF

        elif opcode == 'LOAD_CRYPT':
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd] & 0xFFFFFFFF

        elif opcode in ('TEA_SBOX', 'TEA_MIX'):
            rd = ops[0]
            instr['dest'] = rd
            instr['result'] = self.reg[rd] & 0xFFFFFFFF

        elif opcode == 'CRYPT_ROUND':
            instr['dest'] = 'SUM'
            instr['result'] = self.reg['SUM'] & 0xFFFFFFFF

        # STORE_CRYPT no genera resultado para WB.


    def decode_instruction(self, raw_instr):
        """
        Traduce raw_instr en { 'opcode': ..., 'operands': [...] } según self.isa.
        """
        opcode = raw_instr['opcode']
        decoded = {'opcode': opcode, 'operands': []}

        if opcode == 'MOV':
            decoded['operands'] = [raw_instr['dest'], f"#{raw_instr['value']}"]

        elif opcode == 'LOAD_CRYPT':
            decoded['operands'] = [raw_instr['dest'], raw_instr['mode']]

        elif opcode == 'STORE_CRYPT':
            decoded['operands'] = [raw_instr['src'], raw_instr['mode']]

        elif opcode == 'CRYPT_ROUND':
            rd_v0 = raw_instr['v0']
            rd_v1 = raw_instr['v1']
            kptr_addr = self.reg[raw_instr['kptr']]
            direction = int(raw_instr['dir'])
            decoded['operands'] = [rd_v0, rd_v1, kptr_addr, direction]

        elif opcode == 'LOAD_KEY':
            decoded['operands'] = [raw_instr['index']]

        elif opcode == 'STORE_KEY':
            decoded['operands'] = [
                raw_instr['index'],
                raw_instr['k0'],
                raw_instr['k1'],
                raw_instr['k2'],
                raw_instr['k3']
            ]

        elif opcode in ('TEA_SBOX', 'TEA_MIX', 'CRYPT_LOOP'):
            fmt = self.isa[opcode]['fmt']
            field_map = {
                'Rd': 'dest',
                'Rs': 'src',
                'Rs1': 'src1',
                'Rs2': 'src2',
                'Imm': 'imm',
                'Imm/Reg': 'value',
                'AddrMode': 'mode',
                'Label': 'label',
                'Reg': 'reg'
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

        else:
            raise ValueError(f"Decode: opcode desconocido {opcode}")

        return decoded


    def instruction_fetch(self, program):
        """
        Mueve de IF → ID, o hace fetch de la instrucción en PC.
        """
        if not self.if_delay and self.reg['PC'] < len(program):
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True
        else:
            if self.pipeline['IF'] and self.pipeline['ID'] is None:
                self.pipeline['ID'] = self.pipeline['IF'].copy()
                self.pipeline['IF'] = None
            self.if_delay = False
