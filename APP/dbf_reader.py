"""
Lector ligero de archivos .dbf (dBASE III/IV/Visual FoxPro).
Solo usa la stdlib (struct), sin dependencias externas.
Devuelve una lista de dicts con los nombres de columna como claves.
"""

import struct
from io import BytesIO
from typing import BinaryIO


def read_dbf(source: bytes | BinaryIO) -> list[dict]:
    """
    Lee un archivo .dbf y devuelve lista de dicts.
    `source` puede ser bytes crudos o un file-like object en modo binario.
    """
    if isinstance(source, bytes):
        f = BytesIO(source)
    else:
        f = source

    # --- Header (32 bytes) ---
    header = f.read(32)
    if len(header) < 32:
        raise ValueError("Archivo DBF inválido: header demasiado corto")

    num_records = struct.unpack_from("<I", header, 4)[0]
    header_size = struct.unpack_from("<H", header, 8)[0]
    record_size = struct.unpack_from("<H", header, 10)[0]

    # --- Field descriptors (32 bytes each, terminated by 0x0D) ---
    fields: list[tuple[str, str, int, int]] = []  # (name, type, size, decimal)
    while True:
        field_data = f.read(32)
        if len(field_data) < 32 or field_data[0] == 0x0D:
            break
        name = field_data[:11].split(b"\x00")[0].decode("ascii", errors="replace").strip()
        field_type = chr(field_data[11])
        size = field_data[16]
        decimal = field_data[17]
        fields.append((name, field_type, size, decimal))

    # Avanzar al inicio de los registros
    f.seek(header_size)

    # --- Records ---
    records: list[dict] = []
    for _ in range(num_records):
        raw = f.read(record_size)
        if len(raw) < record_size:
            break

        # Primer byte: flag de borrado (* = borrado, espacio = activo)
        if raw[0:1] == b"*":
            continue

        offset = 1
        row: dict = {}
        for name, ftype, size, decimal in fields:
            value_bytes = raw[offset: offset + size]
            offset += size

            # Intentar decodificar como latin-1 (común en DBFs mexicanos)
            try:
                value_str = value_bytes.decode("latin-1").strip()
            except Exception:
                value_str = value_bytes.decode("ascii", errors="replace").strip()

            # Convertir según tipo
            if ftype in ("C", "M"):  # Character / Memo
                row[name] = value_str
            elif ftype == "N":  # Numeric
                if value_str == "" or value_str == ".":
                    row[name] = None
                else:
                    try:
                        row[name] = float(value_str) if decimal > 0 or "." in value_str else int(value_str)
                    except ValueError:
                        row[name] = None
            elif ftype == "F":  # Float
                try:
                    row[name] = float(value_str) if value_str else None
                except ValueError:
                    row[name] = None
            elif ftype == "L":  # Logical
                row[name] = value_str.upper() in ("T", "Y", "1")
            elif ftype == "D":  # Date YYYYMMDD
                row[name] = value_str if value_str else None
            else:
                row[name] = value_str

        records.append(row)

    return records
