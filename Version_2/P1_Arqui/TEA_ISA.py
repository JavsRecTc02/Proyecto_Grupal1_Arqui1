"""
Registros Especializados:

'V0/V1': Almacenan el bloque de datos de 64 bits
'K0-K3': Guardan la clave de 128 bits en registros físicos
'SUM': Acumulador para delta (elimina accesos a memoria)
'KEYPTR/DATAPTR': Punteros dedicados (AGU integrado)

Instrucciones Fusionadas:

'TEA_SBOX': Combina shift + suma en 1 ciclo (2 instrucciones tradicionales)
'TEA_MIX': Fusiona XOR, suma y shift (3 operaciones en 1 ciclo)
'CRYPT_ROUND': Ronda completa en 2 ciclos vs 12 en x86

Modos de Direccionamiento:

'KEY_IDX': Acceso indexado a claves (0-3) sin cálculo de offset
'DATA_IDX': Acceso directo a bloques de datos
Optimización: Elimina 15 instrucciones de cálculo de direcciones por bloque

Control de Flujo:

'CRYPT_LOOP': Loop hardware con auto-decremento y salto condicional

Codificación:

Formato fijo de 32 bits:
[8b opcode][4b dest][4b src1][4b src2][12b inmediate/modo]

"""
from vault import Vault


class TEACPU:
    """
    - 12 registros de propósito específico
    - 4 modos de direccionamiento optimizados
    - 6 instrucciones personalizadas para operaciones criptográficas
    - Implementación completa de cifrado/descifrado en 32 rondas
    """

    # Constantes del algoritmo
    DELTA = 0x9E3779B9
    ROUNDS = 32

    def __init__(self):
        # ------------------------------------------
        # Registros Especializados (32 bits)
        # ------------------------------------------
        self.vault = Vault()

        self.DELTA = 0x9E3779B9

        self.reg = {
            # Registros de datos
            'V0': 0, 'V1': 0,    # Bloque de datos (v0, v1)
            'T0': 0, 'T1': 0,    # Temporales de cálculo
            
            # Registros de clave
            'K0': 0, 'K1': 0,     # Mitad baja de la clave
            'K2': 0, 'K3': 0,     # Mitad alta de la clave
            
            # Registros de control
            'CTR': 0,            # Contador de rondas 
            'SUM': 0,            # Acumulador delta
            'KEYPTR': 0,         # Puntero a clave en memoria
            'DATAPTR': 0,        # Puntero a datos en memoria
            'PC': 0              # Contador de programa
        }
        
        # ------------------------------------------
        # Memoria 4KB para datos y claves
        # ------------------------------------------
        self.memory = [0] * 1024  # 4096 bytes organizados en words de 32b
        
        # ------------------------------------------
        # Modos de Direccionamiento 
        # ------------------------------------------
        self.addr_modes = {
            'IMM': lambda v: v,                     # Inmediato 32b
            'REG': lambda r: self.reg[r],            # Registro directo
            'KEY_IDX': lambda o: self.reg['KEYPTR'] + o * 4,  # Indexado clave
            'DATA_IDX': lambda o: self.reg['DATAPTR'] + o * 4 # Indexado datos
        }
        
        # ------------------------------------------
        # Set de Instrucciones
        # ------------------------------------------

        self.isa = {
        # Instrucciones Unidas
        'TEA_SBOX': {
            'fmt': ('Rd', 'Rs1', 'Rs2'),
            'exec': lambda rd, rs1, rs2: self._tea_sbox(rd, rs1, rs2)
        },
        'TEA_MIX': {
            'fmt': ('Rd', 'Rs1', 'Rs2', 'Imm'),
            'exec': lambda rd, rs1, rs2, imm: self._tea_mix(rd, rs1, rs2, imm)
        },
        'CRYPT_ROUND': {
           'fmt': ('V0', 'V1', 'Kptr', 'Dir'),
           'exec': lambda v0, v1, kptr, dir: self._crypt_round(v0, v1, kptr, dir)
        },

        # Memoria 
        'LOAD_CRYPT': {
            'fmt': ('Rd', 'AddrMode'),
            'exec': lambda rd, mode: self._load_crypt(rd, mode)
        },
        'STORE_CRYPT': {
            'fmt': ('Rs', 'AddrMode'),
            'exec': lambda rs, mode: self._store_crypt(rs, mode)
        },

        # Control de Flujo 
        'CRYPT_LOOP': {
            'fmt': ('Label', 'Reg'),
            'exec': lambda lbl, reg: self._crypt_loop(lbl, reg)
        },

        # MOV -> Falta cambiarlo 
        'MOV': {
            'fmt': ('Rd', 'Imm/Reg'),
            'exec': lambda dst, src: self._mov(dst, src)
        },

        # Instrucciones de Bóveda de Llaves
        'LOAD_KEY': {
            'fmt': ('Idx',),
            'exec': lambda idx: self._load_key(idx)
        },
        'STORE_KEY': {  # Sólo para pruebas, no debe usarse en el ejecutable final
            'fmt': ('Idx', 'K0', 'K1', 'K2', 'K3'),
            'exec': lambda idx, k0, k1, k2, k3: self._store_key(idx, k0, k1, k2, k3)
        }

    }
        
    # ==================== CARGAR PROGRAMA AL ISA ====================    

    def load_program(self, program):
        """
        Carga el programa en memoria interna y construye la tabla de etiquetas
        para que _crypt_loop pueda resolverlas a índices.
        """
        self.program = program
        # Solo guardamos la última ocurrencia de cada etiqueta
        self.label_table = {
            instr['label']: idx
            for idx, instr in enumerate(program)
            if 'label' in instr
        }
        print("Label table:", self.label_table)


    # ==================== OPERACIONES DE TEA ====================
    def _tea_sbox(self, rd, rs1, rs2):
        """(Rs1 << 4) + Rs2 → Rd (Fusión SHL+ADD)"""
        self.reg[rd] = ((self.reg[rs1] << 4) + self.reg[rs2]) & 0xFFFFFFFF

    def _tea_mix(self, rd, rs1, rs2, imm):
        """Rd ^= (Rs1 + SUM) ^ (Rs2 >> 5) + Imm"""
        term1 = (self.reg[rs1] + self.reg['SUM']) & 0xFFFFFFFF
        term2 = (self.reg[rs2] >> 5) + imm
        self.reg[rd] ^= (term1 ^ term2) & 0xFFFFFFFF

    def _crypt_round(self, v0_reg, v1_reg, kptr, direction):
        """
        Ejecuta una única ronda de TEA.
        v0_reg, v1_reg: cadenas 'V0' y 'V1'
        kptr: (no lo usamos porque cargamos K0..K3 en registros directamente)
        direction: 1 = cifrar, 0 = descifrar
        """
        # Extraer valores de registro
        v0 = self.reg[v0_reg]
        v1 = self.reg[v1_reg]
        k0 = self.reg['K0']
        k1 = self.reg['K1']
        k2 = self.reg['K2']
        k3 = self.reg['K3']
        mask32 = 0xFFFFFFFF

        sum_val = self.reg['SUM']  # suma acumulada hasta justo antes de esta ronda

        if direction == 1:
            # CIFRADO: primero incrementar sum
            sum_val = (sum_val + self.DELTA) & mask32

            # v0 += ((v1 << 4) + k0) ^ (v1 + sum) ^ ((v1 >> 5) + k1)
            t0 = ((v1 << 4) + k0) & mask32
            t1 = (v1 + sum_val) & mask32
            t2 = ((v1 >> 5) + k1) & mask32
            v0 = (v0 + (t0 ^ t1 ^ t2)) & mask32

            # v1 += ((v0 << 4) + k2) ^ (v0 + sum) ^ ((v0 >> 5) + k3)
            t0 = ((v0 << 4) + k2) & mask32
            t1 = (v0 + sum_val) & mask32
            t2 = ((v0 >> 5) + k3) & mask32
            v1 = (v1 + (t0 ^ t1 ^ t2)) & mask32

        else:
            # DESCIFRADO: primero restar de v1/v0 usando sum
            t0 = ((v0 << 4) + k2) & mask32
            t1 = (v0 + sum_val) & mask32
            t2 = ((v0 >> 5) + k3) & mask32
            v1 = (v1 - (t0 ^ t1 ^ t2)) & mask32

            t0 = ((v1 << 4) + k0) & mask32
            t1 = (v1 + sum_val) & mask32
            t2 = ((v1 >> 5) + k1) & mask32
            v0 = (v0 - (t0 ^ t1 ^ t2)) & mask32

            # luego decrementamos sum
            sum_val = (sum_val - self.DELTA) & mask32

        # Guardar retornos
        self.reg[v0_reg] = v0
        self.reg[v1_reg] = v1
        self.reg['SUM'] = sum_val



    # ==================== ACCESO A MEMORIA  ====================
    def _load_crypt(self, rd, mode):
        """Carga desde memoria usando modo criptográfico"""
        addr = self.addr_modes[mode[0]](mode[1])
        self.reg[rd] = self.memory[addr // 4] & 0xFFFFFFFF

    def _store_crypt(self, rs, mode):
        """Almacena en memoria usando modo criptográfico"""
        addr = self.addr_modes[mode[0]](mode[1])
        self.memory[addr // 4] = self.reg[rs] & 0xFFFFFFFF

    # ==================== CONTROL DE FLUJO  ====================

    def _crypt_loop(self, label, reg):
        """Loop hardware para rondas criptográficas."""
        # Decrementa el contador
        self.reg[reg] -= 1

        # Mientras queden iteraciones, salta a la etiqueta
        if self.reg[reg] > 0:
            if not hasattr(self, 'label_table'):
                raise RuntimeError("Debe llamar a load_program(program) antes de ejecutar.")

            # Busca el índice de la etiqueta
            try:
                target_pc = self.label_table[label]
            except KeyError:
                raise ValueError(f"Etiqueta '{label}' no encontrada en label_table")

            # Ajusta el PC al índice numérico de la instrucción
            self.reg['PC'] = target_pc - 1

    # ==================== MOVIMIENTO DE DATOS ====================
    def _mov(self, dst, src):
    # src puede ser entero (inmediato) o nombre de registro
        value = src if isinstance(src, int) else self.reg[src]
        self.reg[dst] = value & 0xFFFFFFFF
        return value


    # ==================== EJECUCIÓN DE INSTRUCCIONES ====================
    def execute(self, instr):
        """Ejecuta una instrucción decodificada"""
        op = self.isa[instr[0]]
        operands = [self._decode_operand(o) for o in instr[1:]]
        op['exec'](*operands)

    def _decode_operand(self, op):
        """Decodifica operandos (registro, inmediato o modo dirección)"""
        if isinstance(op, str) and op.startswith('#'):
            return int(op[1:], 0)
        return op

    # ==================== BÓVEDA DE LLAVES ====================

    def _load_key(self, index):
        """
        Carga una clave desde la bóveda al conjunto de registros K0-K3.
        Solo accesible mediante instrucción LOAD_KEY.
        """
        if not isinstance(index, int) or not (0 <= index < 4):
            raise ValueError(f"Índice inválido para LOAD_KEY: {index}")
        k0, k1, k2, k3 = self.vault.load_key(index)
        self.reg['K0'] = k0
        self.reg['K1'] = k1
        self.reg['K2'] = k2
        self.reg['K3'] = k3

    def _store_key(self, index, k0, k1, k2, k3):
        """
        Guarda una clave en la bóveda desde los valores en registros K0–K3.
        Esta instrucción es opcional y puede usarse solo en fase de pruebas.
        """
        if not isinstance(index, int) or not (0 <= index < 4):
            raise ValueError(f"Índice inválido para STORE_KEY: {index}")
        self.vault.store_key(
            index,
            self.reg[k0],
            self.reg[k1],
            self.reg[k2],
            self.reg[k3]
        )

    


