
from TEA_ISA import TEACPU


class TEAPipeline(TEACPU):
    def __init__(self):
        super().__init__()
        # Alias para compatibilidad con el método _mov del ISA
        self.registers = self.reg

        # Pipeline stages: IF, ID, EX, MEM, WB
        self.pipeline = {stage: None for stage in ['IF', 'ID', 'EX', 'MEM', 'WB']}
        self.if_delay = False

    def execute_cycle(self, program):
        """
        Ejecuta un ciclo del pipeline: WB → MEM → EX → ID → IF
        program: lista de diccionarios con las instrucciones (tea_program).
        """

        # --- WB stage ---
        if self.pipeline['WB']:
            self.write_back(self.pipeline['WB'])
            self.pipeline['WB'] = None

        # --- MEM stage ---
        if self.pipeline['MEM']:
            mem_out = self.memory_access(self.pipeline['MEM'])
            if mem_out:
                # Si la instrucción produce un resultado (por ejemplo LOAD_CRYPT o CRYPT_ROUND),
                # lo copiamos a WB.
                self.pipeline['WB'] = mem_out.copy()
            self.pipeline['MEM'] = None

        # --- EX stage ---
        if self.pipeline['EX']:
            instr = self.pipeline['EX']
            decoded = self.decode_instruction(instr)
            self.execute_instruction(decoded)

            # Solo pasamos a MEM si se generó 'dest' y 'result'
            if 'dest' in decoded and 'result' in decoded:
                self.pipeline['MEM'] = decoded.copy()

            self.pipeline['EX'] = None

            #if decoded['opcode'] == 'CRYPT_LOOP' and self.reg[decoded['operands'][1]] > 0:
            #    self.pipeline['IF'] = None
            #    self.pipeline['ID'] = None
            #    self.if_delay = False

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
            # Mover de IF a ID
            self.pipeline['ID'] = self.pipeline['IF'].copy()
            self.pipeline['IF'] = None
            self.if_delay = False
        elif not self.if_delay and self.reg['PC'] < len(program):
            # Si no hay delay, hacemos fetch de la siguiente instrucción
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True
        else:
            # Desactivamos el delay para permitir el próximo fetch en el siguiente ciclo
            self.if_delay = False

    def write_back(self, instr):
        if 'dest' in instr and 'result' in instr:
            print(f"WB: Escribiendo {instr['result']} en {instr['dest']}")
            self.reg[instr['dest']] = instr['result']

    def memory_access(self, instr):
        """
        Acceso a memoria para LOAD_CRYPT y STORE_CRYPT.
        Usa instr['operands'] para extraer [Rd, mode] o [Rs, mode].
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
            # Para instrucciones que no tocan memoria, devolvemos el mismo instr
            return instr

    def execute_instruction(self, instr):
        """
        Ejecuta una instrucción decodificada (instr ya fue obtenida por decode_instruction)
        y captura 'dest'/'result' cuando corresponda.
        """
        opcode = instr['opcode']
        ops = instr['operands']

        # Llama a la rutina de ejecución del ISA
        super().execute([opcode] + ops)

        # Después de ejecutar, capturamos el registro destino y su valor
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
            # En cada CRYPT_ROUND actualizamos el acumulador SUM internamente en _crypt_round().
            # Aquí capturamos ese valor para escribirlo en WB.
            instr['dest'] = 'SUM'
            instr['result'] = self.reg['SUM'] & 0xFFFFFFFF

        # STORE_CRYPT no genera resultado que pase a WB, así que no hacemos nada más.

    def decode_instruction(self, raw_instr):
        """
        Convierte la instrucción en crudo (raw_instr) a un dict with:
          { 'opcode': ..., 'operands': [...] }
        usando self.isa[...] y el mapeo de campos.
        """
        opcode = raw_instr['opcode']
        decoded = {'opcode': opcode, 'operands': []}

        if opcode == 'MOV':
            # MOV Rd, #IMM
            decoded['operands'] = [ raw_instr['dest'], f"#{raw_instr['value']}" ]

        elif opcode == 'LOAD_CRYPT':
            # LOAD_CRYPT Rd, [modo]
            decoded['operands'] = [ raw_instr['dest'], raw_instr['mode'] ]

        elif opcode == 'STORE_CRYPT':
            # STORE_CRYPT Rs, [modo]
            decoded['operands'] = [ raw_instr['src'], raw_instr['mode'] ]

        elif opcode == 'CRYPT_ROUND':
            # CRYPT_ROUND V0, V1, Kptr, Dir
            rd_v0 = raw_instr['v0']
            rd_v1 = raw_instr['v1']
            kptr_addr = self.reg[ raw_instr['kptr'] ]     # resolvemos la dirección entera
            direction = int(raw_instr['dir'])
            decoded['operands'] = [rd_v0, rd_v1, kptr_addr, direction]

        elif opcode in ('TEA_SBOX', 'TEA_MIX', 'CRYPT_LOOP'):
            # Mapeo dinámico gracias a fmt en self.isa
            fmt = self.isa[opcode]['fmt']
            field_map = {
                'Rd':        'dest',
                'Rs':        'src',
                'Rs1':       'src1',
                'Rs2':       'src2',
                'Imm':       'imm',
                'Imm/Reg':   'value',
                'AddrMode':  'mode',
                'Label':     'label',
                'Reg':       'reg'
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
        if not self.if_delay and self.reg['PC'] < len(program):
            self.pipeline['IF'] = program[self.reg['PC']].copy()
            self.reg['PC'] += 1
            self.if_delay = True
        else:
            if self.pipeline['IF'] and self.pipeline['ID'] is None:
                self.pipeline['ID'] = self.pipeline['IF'].copy()
                self.pipeline['IF'] = None
            self.if_delay = False



