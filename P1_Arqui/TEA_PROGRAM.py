
"""
Flujo completo:

    Carga de datos desde memoria
    Configuración de 32 iteraciones
    Bucle con auto-decremento usando CRYPT_LOOP
    Operaciones de ronda con TEA_SBOX, TEA_MIX y CRYPT_ROUND
    Almacenamiento de resultados

Uso de todos los modos de direccionamiento:

    IMM para constantes
    KEY_IDX y DATA_IDX para acceso a memoria
    REG para operaciones entre registros

Instrucciones:

    MOV para carga de constantes
    LOAD_CRYPT/STORE_CRYPT para transferencias memoria-registro
    TEA_SBOX y TEA_MIX para operaciones criptográficas básicas
    CRYPT_ROUND para Loops (rondas) completos
    CRYPT_LOOP para control de flujo optimizado

Resultados:

Registros:

    SUM mostrará el acumulador delta actualizado
    CTR decrementará de 32 a 0
    V0 y V1 mostrarán el bloque cifrado

Memoria:

    Las posiciones 0x200 y 0x204 tendrán los valores cifrados
    La zona de clave (0x300-0x30C) mantendrá los valores originales

"""



# Programa completo de cifrado TEA usando todas las instrucciones del ISA

tea_program = [

    # ---- Inicialización ----
    {   # MOV KEYPTR, #0x300 (clave en 0x300)
        'opcode': 'MOV',
        'dest': 'KEYPTR',
        'value': 0x300
    },
    {   # MOV DATAPTR, #0x200 (datos en 0x200)
        'opcode': 'MOV',
        'dest': 'DATAPTR',
        'value': 0x200
    },
    
    # ---- Cargar datos ----
    {   # LOAD_CRYPT V0, DATA[0]
        'opcode': 'LOAD_CRYPT',
        'dest': 'V0',
        'mode': ('DATA_IDX', 0)
    },
    {   # LOAD_CRYPT V1, DATA[1]
        'opcode': 'LOAD_CRYPT',
        'dest': 'V1',
        'mode': ('DATA_IDX', 1)
    },
    
    # ---- Configurar Loop ----
    {   # MOV CTR, 32 (32 iteraciones)
        'opcode': 'MOV',
        'dest': 'CTR',
        'value': 32
    },
    
    # ---- Bucle de cifrado ----
    {   # CRYPT_LOOP inicio_cifrado, CTR
        'opcode': 'CRYPT_LOOP',
        'label': 'inicio_cifrado',
        'reg': 'CTR'
    },
    
    # ---- Operaciones de Loop ----
    {   # TEA_SBOX T0, V1, K0 (v1 << 4 + K0)
        'opcode': 'TEA_SBOX',
        'dest': 'T0',
        'src1': 'V1',
        'src2': 'K0'
    },
    {   # TEA_MIX V0, T0, V1, KEY[1] (mezcla con key[1])
        'opcode': 'TEA_MIX',
        'dest': 'V0',
        'src1': 'T0',
        'src2': 'V1',
        'imm': ('KEY_IDX', 1)
    },
    {   # CRYPT_ROUND V0, V1, KEYPTR, 1 (loop completo)
        'opcode': 'CRYPT_ROUND',
        'v0': 'V0',
        'v1': 'V1',
        'kptr': 'KEYPTR',
        'dir': 1
    },
    
    # ---- Final del bucle ----
    {   # CRYPT_LOOP inicio_cifrado, CTR (auto-decrementa)
        'opcode': 'CRYPT_LOOP',
        'label': 'inicio_cifrado',
        'reg': 'CTR'
    },
    
    # ---- Almacenar resultado ----
    {   # STORE_CRYPT V0, DATA[0]
        'opcode': 'STORE_CRYPT',
        'src': 'V0',
        'mode': ('DATA_IDX', 0)
    },
    {   # STORE_CRYPT V1, DATA[1]
        'opcode': 'STORE_CRYPT',
        'src': 'V1',
        'mode': ('DATA_IDX', 1)
    },
    
    # ---- Operaciones adicionales demostrativas ----
    {   # MOV K0, #0x12345678 (cargar constante)
        'opcode': 'MOV',
        'dest': 'K0',
        'value': 0x12345678
    },
    {   # TEA_SBOX T1, V0, K0 (demo adicional)
        'opcode': 'TEA_SBOX',
        'dest': 'T1',
        'src1': 'V0',
        'src2': 'K0'
    }
]


# Otras pruebas

tea_program2 = [
    {   # MOV KEYPTR, #0x300
        'opcode': 'MOV',
        'dest': 'KEYPTR',
        'value': 0x300
    },
    {   # LOAD_CRYPT V0, DATA[0]
        'opcode': 'LOAD_CRYPT',
        'dest': 'V0',
        'mode': ('DATA_IDX', 0)
    },
    {   # CRYPT_ROUND V0, V1, KEYPTR, 1
        'opcode': 'CRYPT_ROUND',
        'v0': 'V0',
        'v1': 'V1',
        'kptr': 'KEYPTR',  # Usar nombre de registro
        'dir': 1
    }
]