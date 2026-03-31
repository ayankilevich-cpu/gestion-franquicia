"""
Gráficos con montos en formato argentino: $ y separador de miles (.), decimales (,).
Los ejes pueden mostrar números compactos; el monto exacto va en tooltip y etiquetas.
"""
from typing import Optional, Sequence

import altair as alt
import pandas as pd
import streamlit as st

from utils.formato import formato_moneda


def _serie_fmt(serie: pd.Series) -> pd.Series:
    return serie.apply(
        lambda v: formato_moneda(float(v)) if pd.notna(v) and v is not None else "-"
    )


def grafico_barras_moneda(
    df: pd.DataFrame,
    cat_col: str,
    val_col: str,
    titulo: str = "",
    horizontal: bool = True,
) -> None:
    """Barras con etiqueta y tooltip en formato $1.234.567,89."""
    if df.empty or cat_col not in df.columns or val_col not in df.columns:
        st.info("Sin datos para el gráfico.")
        return
    d = df[[cat_col, val_col]].dropna(subset=[val_col]).copy()
    if d.empty:
        st.info("Sin datos para el gráfico.")
        return
    d["_fmt"] = _serie_fmt(d[val_col])
    if horizontal:
        base = alt.Chart(d).encode(
            y=alt.Y(f"{cat_col}:N", sort="-x", title=""),
            x=alt.X(f"{val_col}:Q", title="Monto"),
            tooltip=[
                alt.Tooltip(f"{cat_col}:N", title=cat_col),
                alt.Tooltip("_fmt:N", title="Monto"),
            ],
        )
        bars = base.mark_bar()
        text = base.mark_text(align="left", baseline="middle", dx=4).encode(
            text=alt.Text("_fmt:N"),
        )
    else:
        base = alt.Chart(d).encode(
            x=alt.X(f"{cat_col}:N", sort="-y", title=""),
            y=alt.Y(f"{val_col}:Q", title="Monto"),
            tooltip=[
                alt.Tooltip(f"{cat_col}:N", title=cat_col),
                alt.Tooltip("_fmt:N", title="Monto"),
            ],
        )
        bars = base.mark_bar()
        text = base.mark_text(align="center", baseline="bottom", dy=-4).encode(
            text=alt.Text("_fmt:N"),
        )
    chart = (bars + text).properties(title=titulo or None)
    st.altair_chart(chart, use_container_width=True)


def grafico_barras_desde_serie(
    serie: pd.Series, titulo: str = "", horizontal: bool = False
) -> None:
    """Serie con índice = categoría (ej. mes) y valores numéricos."""
    df = serie.reset_index()
    if df.shape[1] < 2:
        return
    c0, c1 = df.columns[0], df.columns[1]
    grafico_barras_moneda(
        df.rename(columns={c0: "Categoría", c1: "Monto"}),
        "Categoría",
        "Monto",
        titulo,
        horizontal=horizontal,
    )


def grafico_lineas_multiserie_moneda(
    df: pd.DataFrame,
    x_col: str,
    columnas_valor: Sequence[str],
    etiquetas: Optional[Sequence[str]] = None,
    titulo: str = "",
) -> None:
    """Líneas múltiples; tooltip con montos formateados."""
    if df.empty or x_col not in df.columns:
        st.info("Sin datos para el gráfico.")
        return
    nombres = list(etiquetas) if etiquetas is not None else list(columnas_valor)
    if len(nombres) != len(columnas_valor):
        nombres = list(columnas_valor)
    partes = []
    for col, nombre in zip(columnas_valor, nombres):
        if col not in df.columns:
            continue
        d2 = df[[x_col, col]].copy()
        d2 = d2.rename(columns={col: "Monto"})
        d2["Serie"] = nombre
        d2["_fmt"] = _serie_fmt(d2["Monto"])
        partes.append(d2)
    if not partes:
        st.info("Sin datos para el gráfico.")
        return
    long_df = pd.concat(partes, ignore_index=True)
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X(f"{x_col}:N", sort=None, title=""),
            y=alt.Y("Monto:Q", title="Monto ($)"),
            color=alt.Color("Serie:N", title=""),
            tooltip=[
                alt.Tooltip(f"{x_col}:N", title="Período"),
                alt.Tooltip("Serie:N", title="Serie"),
                alt.Tooltip("_fmt:N", title="Monto"),
            ],
        )
        .properties(title=titulo or None)
    )
    st.altair_chart(chart, use_container_width=True)


def grafico_barras_agrupadas_moneda(
    df: pd.DataFrame,
    cat_col: str,
    columnas_periodo: Sequence[str],
    titulo: str = "",
) -> None:
    """Barras agrupadas (ej. dos períodos); tooltip con formato argentino."""
    if df.empty or cat_col not in df.columns:
        st.info("Sin datos para el gráfico.")
        return
    partes = []
    for col in columnas_periodo:
        if col not in df.columns:
            continue
        d2 = df[[cat_col, col]].copy()
        d2 = d2.rename(columns={col: "Monto"})
        d2["Período"] = str(col)
        d2["_fmt"] = _serie_fmt(d2["Monto"])
        partes.append(d2)
    if not partes:
        st.info("Sin datos para el gráfico.")
        return
    long_df = pd.concat(partes, ignore_index=True)
    chart = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X(f"{cat_col}:N", title="", sort=None),
            y=alt.Y("Monto:Q", title="Monto"),
            xOffset="Período:N",
            color=alt.Color("Período:N", title=""),
            tooltip=[
                alt.Tooltip(f"{cat_col}:N", title="Concepto"),
                alt.Tooltip("Período:N", title="Período"),
                alt.Tooltip("_fmt:N", title="Monto"),
            ],
        )
        .properties(title=titulo or None)
    )
    st.altair_chart(chart, use_container_width=True)


def grafico_barras_apiladas_mes_moneda(
    df: pd.DataFrame,
    x_col: str,
    columnas: Sequence[str],
    etiquetas: Optional[Sequence[str]] = None,
    titulo: str = "",
) -> None:
    """Barras apiladas por mes (ej. bancarios + efectivo)."""
    if df.empty:
        return
    nombres = list(etiquetas) if etiquetas is not None else list(columnas)
    if len(nombres) != len(columnas):
        nombres = list(columnas)
    partes = []
    for col, nombre in zip(columnas, nombres):
        if col not in df.columns:
            continue
        d2 = df[[x_col, col]].copy()
        d2 = d2.rename(columns={col: "Monto"})
        d2["Tipo"] = nombre
        d2["_fmt"] = _serie_fmt(d2["Monto"])
        partes.append(d2)
    if not partes:
        return
    long_df = pd.concat(partes, ignore_index=True)
    chart = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X(f"{x_col}:N", sort=None, title=""),
            y=alt.Y("Monto:Q", title="Monto", stack="zero"),
            color=alt.Color("Tipo:N", title=""),
            tooltip=[
                alt.Tooltip(f"{x_col}:N", title="Mes"),
                alt.Tooltip("Tipo:N", title="Tipo"),
                alt.Tooltip("_fmt:N", title="Monto"),
            ],
        )
        .properties(title=titulo or None)
    )
    st.altair_chart(chart, use_container_width=True)
