"""
Lógica compartida para clasificar movimientos en Flujo de Caja.

Un crédito bancario que es "depósito de efectivo en cuenta" no es cobranza de ventas:
si además contás retiros de caja (banco EFECTIVO), contarlo como ingreso bancario
duplica el dinero y dispara el flujo neto (p. ej. +18M).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict


def _sin_tildes(s: str) -> str:
    if not s:
        return ""
    n = unicodedata.normalize("NFKD", s)
    return "".join(c for c in n if not unicodedata.combining(c))


def es_credito_deposito_efectivo_en_banco(mov: Dict[str, Any]) -> bool:
    """
    True si el crédito representa efectivo ingresado a la cuenta (caja → banco).

    No debe sumarse a "Cobrado (Bancos)" en el flujo operativo.
    """
    cat = _sin_tildes(mov.get("categoria") or "").upper()
    desc = _sin_tildes(mov.get("descripcion") or "").upper()
    ref = _sin_tildes(mov.get("referencia") or "").upper()
    texto = f"{desc} {ref}"

    if "DEPOSITO" in cat or "DEPOSITOS" in cat:
        return True
    # Texto típico extractos AR
    if re.search(r"\bDEP\.?\s*EFECT", texto):
        return True
    if "DEPOSITO" in texto:
        return True
    if "INGRESO EFECTIVO" in texto:
        return True
    return False
