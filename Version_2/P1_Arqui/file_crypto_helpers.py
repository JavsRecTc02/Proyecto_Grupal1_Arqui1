
import os
import struct
import tkinter as tk
from tkinter import filedialog

def select_file_dialog():
    """
    Abre un diálogo para seleccionar un único archivo y devuelve la ruta absoluta.
    Retorna None si el usuario cancela.
    """
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal de tkinter
    file_path = filedialog.askopenfilename(
        title="Seleccione un archivo para encriptar/desencriptar",
        initialdir=os.path.expanduser("~/Desktop"),
        filetypes=[("Todos los archivos", "*.*")]
    )
    root.destroy()
    return file_path if file_path else None

def read_file_blocks(path):
    """
    Lee todos los bytes del archivo en 'path' y devuelve una lista de tuplas (v0, v1),
    donde cada entero ocupa 32 bits (word). Si el último bloque no completa 8 bytes,
    lo rellenamos con ceros (padding).
    """
    with open(path, "rb") as f:
        data = f.read()

    blocks = []
    # Recorremos de 8 en 8 bytes (64 bits). Si falta, hacemos padding con b"\x00".
    for i in range(0, len(data), 8):
        chunk = data[i:i + 8]
        if len(chunk) < 8:
            chunk = chunk.ljust(8, b'\x00')
        # struct.unpack("<II", ...) descompone a 2 enteros little-endian de 32 bits
        v0, v1 = struct.unpack("<II", chunk)
        blocks.append((v0, v1))

    return blocks

def write_file_from_blocks(path_out, blocks):
    """
    Recibe una lista de tuplas [(c0, c1), (c0, c1), ...], donde cada elemento 
    es un par de enteros de 32 bits. Los empaca como little-endian de 8 bytes
    y escribe en 'path_out'. Si se generó padding en bloques, lo dejamos tal cual,
    o bien podrías recortar ceros al final si supieras su longitud original.
    """
    with open(path_out, "wb") as f:
        for v0, v1 in blocks:
            # Empaquétalos de nuevo a 8 bytes (little endian)
            data_bytes = struct.pack("<II", v0 & 0xFFFFFFFF, v1 & 0xFFFFFFFF)
            f.write(data_bytes)
