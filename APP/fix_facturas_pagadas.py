"""
Script de migración: crea pagos automáticos para facturas PAGADA
que no tienen registros en la tabla pagos.

Ejecutar UNA sola vez:
    python fix_facturas_pagadas.py
"""
from APP.db import SessionLocal
from sqlalchemy import text
from datetime import date

db = SessionLocal()

try:
    # Buscar facturas PAGADA sin pagos o con saldo pendiente
    rows = db.execute(text("""
        SELECT f.id, f.folio, f.monto, f.fecha, f.metodo_pago,
               COALESCE(SUM(p.monto), 0) AS total_pagado
        FROM facturas f
        LEFT JOIN pagos p ON p.factura_id = f.id
        WHERE f.estatus = 'PAGADA'
        GROUP BY f.id
        HAVING f.monto - COALESCE(SUM(p.monto), 0) > 0.01
        ORDER BY f.id
    """)).mappings().all()

    print(f"Facturas PAGADA con saldo pendiente: {len(rows)}")

    for r in rows:
        saldo = float(r["monto"]) - float(r["total_pagado"])
        print(f"  Folio {r['folio']}: monto=${r['monto']}, pagado=${r['total_pagado']}, saldo=${saldo:.2f} → creando pago...")

        db.execute(text("""
            INSERT INTO pagos (factura_id, monto, fecha, metodo_pago, referencia, notas)
            VALUES (:fid, :monto, :fecha, :mp, 'MIGRACION', 'Pago retroactivo - migración automática')
        """), {
            "fid": r["id"],
            "monto": round(saldo, 2),
            "fecha": r["fecha"] or date.today(),
            "mp": r["metodo_pago"],
        })

    db.commit()
    print(f"\nListo. {len(rows)} pagos creados.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
    


