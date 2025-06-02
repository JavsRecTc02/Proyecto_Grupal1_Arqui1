# vault.py

class Vault:
    def __init__(self):
        # 4 llaves de 128 bits = 4 x 4 registros de 32 bits
        self.slots = [ [0, 0, 0, 0] for _ in range(4) ]

    def load_key(self, index):
        """
        Retorna la llave de 128 bits (K0-K3) como lista de 4 enteros.
        """
        if not (0 <= index < 4):
            raise ValueError(f"Índice de bóveda inválido: {index}")
        return self.slots[index]

    def store_key(self, index, k0, k1, k2, k3):
        """
        Guarda una llave de 128 bits en la bóveda (desde 4 enteros).
        """
        if not (0 <= index < 4):
            raise ValueError(f"Índice de bóveda inválido: {index}")
        self.slots[index] = [k0 & 0xFFFFFFFF, k1 & 0xFFFFFFFF,
                             k2 & 0xFFFFFFFF, k3 & 0xFFFFFFFF]

    def __repr__(self):
        out = []
        for i, key in enumerate(self.slots):
            out.append(f"Slot {i}: {[hex(k) for k in key]}")
        return "\n".join(out)
