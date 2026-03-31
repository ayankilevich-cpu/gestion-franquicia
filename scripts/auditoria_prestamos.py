#!/usr/bin/env python3
"""
Auditoría de cuotas de préstamos bancarios cargados en MySQL.

Uso (desde la raíz del proyecto, con .env o secrets con MYSQL_*):
  python scripts/auditoria_prestamos.py

Comprueba movimientos con categoría "Préstamos Bancarios" y además
filas cuya descripción contiene PRESTAMO pero quedaron en otra categoría.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
)

from db.connection import get_connection

CAT = "Préstamos Bancarios"
BANCOS_ESPERADOS = ("MACRO", "NACION", "SANTANDER")


def main() -> int:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        print("=== Resumen: categoría 'Préstamos Bancarios' (por banco, año, mes) ===\n")
        cur.execute(
            """
            SELECT banco, YEAR(fecha) AS anio, MONTH(fecha) AS mes,
                   COUNT(*) AS cnt,
                   ROUND(SUM(debito), 2) AS total_debito,
                   ROUND(SUM(credito), 2) AS total_credito
            FROM movimientos_bancarios
            WHERE categoria = %s
            GROUP BY banco, YEAR(fecha), MONTH(fecha)
            ORDER BY banco, anio, mes
            """,
            (CAT,),
        )
        rows = cur.fetchall()
        if not rows:
            print("(Sin movimientos con esta categoría.)\n")
        else:
            for r in rows:
                print(
                    f"  {r['banco']:10}  {r['anio']}-{r['mes']:02d}  "
                    f"n={r['cnt']}  débito={r['total_debito']}  crédito={r['total_credito']}"
                )

        print("\n=== Bancos con al menos un movimiento en 'Préstamos Bancarios' ===")
        cur.execute(
            """
            SELECT DISTINCT banco FROM movimientos_bancarios
            WHERE categoria = %s ORDER BY banco
            """,
            (CAT,),
        )
        con_prest = {r["banco"] for r in cur.fetchall()}
        print(", ".join(sorted(con_prest)) if con_prest else "(ninguno)")
        faltan = [b for b in BANCOS_ESPERADOS if b not in con_prest]
        if faltan:
            print(f"\n⚠️  Ningún movimiento de préstamo categorizado para: {', '.join(faltan)}")
            print(
                "    (Puede ser que no haya cuota en el período o que el texto del extracto "
                "no coincida con los patrones del parser.)"
            )

        print(
            "\n=== Posibles préstamos mal categorizados "
            "(descripción con PRESTAMO, categoría ≠ Préstamos Bancarios) ===\n"
        )
        cur.execute(
            """
            SELECT banco, fecha, descripcion, categoria, debito, credito
            FROM movimientos_bancarios
            WHERE UPPER(IFNULL(descripcion, '')) LIKE %s
              AND IFNULL(categoria, '') <> %s
            ORDER BY banco, fecha
            """,
            ("%PRESTAMO%", CAT),
        )
        otros = cur.fetchall()
        if not otros:
            print("(Ninguno.)\n")
        else:
            for r in otros:
                print(
                    f"  {r['banco']} {r['fecha']} | {r['categoria']} | "
                    f"{r['descripcion'][:70]!r}... débito={r['debito']}"
                )

        print("\n=== Detalle línea a línea (solo categoría Préstamos Bancarios) ===\n")
        cur.execute(
            """
            SELECT banco, fecha, descripcion, debito, credito
            FROM movimientos_bancarios
            WHERE categoria = %s
            ORDER BY banco, fecha, id
            """,
            (CAT,),
        )
        for r in cur.fetchall():
            print(
                f"  {r['banco']} {r['fecha']} | {r['descripcion'][:75]!r} | "
                f"débito={r['debito']}"
            )

    finally:
        cur.close()
        conn.close()

    print("\nListo. Para Nación (dic + enero), revisá que existan filas en los meses")
    print("que correspondan a esos extractos (p. ej. 2025-12 y 2026-01).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
