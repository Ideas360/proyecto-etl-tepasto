"""Capa de datos del dashboard.

Consulta la base SQLite (vista v_empresas) y devuelve los agregados que se grafican.
No depende de Plotly ni de matplotlib, por eso se puede probar sola y la reutilizan
tanto el dashboard interactivo como las figuras estáticas de la documentación.

Decisiones de análisis (ver README, secciones 8.2 y 12):
  - El valor del establecimiento se resume con la MEDIANA: aun winsorizado, su promedio
    sigue muy por encima de la mediana.
  - El año de corte se marca como parcial: no es una caída real de la dinámica empresarial.
  - El barrio solo existe para Pasto: el gráfico de barrios se limita a ese municipio.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

ORDEN_MACRO = ["Terciario", "Secundario", "Primario", config.SIN_CLASIFICAR]


class ErrorDashboard(Exception):
    """Error esperable al preparar los datos del dashboard."""


def cargar() -> pd.DataFrame:
    """Lee la vista v_empresas completa (una fila por empresa, ya sin datos personales)."""
    if not config.BASE_DATOS.exists():
        raise ErrorDashboard(f"No existe {config.BASE_DATOS.name}. Ejecute primero el pipeline (python pipeline.py).")
    con = sqlite3.connect(config.BASE_DATOS)
    try:
        df = pd.read_sql_query("SELECT * FROM v_empresas", con)
    finally:
        con.close()
    if df.empty:
        raise ErrorDashboard("La vista v_empresas no tiene registros.")
    return df


def _meta() -> dict:
    if config.EXTRACCION_META.exists():
        return json.loads(config.EXTRACCION_META.read_text(encoding="utf-8"))
    return {}


def indicadores(df: pd.DataFrame) -> dict:
    """Cifras de las tarjetas del encabezado."""
    n = len(df)
    pasto = (df["mun_codigo"] == "52001").sum()
    terciario = (df["macro_sector"] == "Terciario").sum()
    reportado = df.loc[df["vlr_no_reportado"] == 0, "vlr_establecimiento"]
    return {
        "empresas": int(n),
        "municipios": int(df.loc[df["mun_codigo"] != "00000", "mun_codigo"].nunique()),
        "pct_pasto": 100 * pasto / n,
        "pct_terciario": 100 * terciario / n,
        "mediana_valor": float(reportado.median()),
        "mediana_antiguedad": float(df["antiguedad_anios"].median()),
        "pct_valor_no_reportado": 100 * (df["vlr_no_reportado"] == 1).mean(),
        "fecha_corte": df["fec_renovacion"].max(),
        "fuente": _meta().get("fuente_registro", "desconocida"),
        "es_muestra": bool(_meta().get("es_muestra", False)),
    }


def por_macro_sector(df: pd.DataFrame) -> pd.DataFrame:
    t = df.groupby("macro_sector").size().rename("empresas").reset_index()
    t["pct"] = 100 * t["empresas"] / t["empresas"].sum()
    t["orden"] = t["macro_sector"].map({m: i for i, m in enumerate(ORDEN_MACRO)})
    return t.sort_values("orden").drop(columns="orden").reset_index(drop=True)


def por_municipio(df: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    t = df.groupby("mun_nombre").size().rename("empresas").reset_index()
    t["pct"] = 100 * t["empresas"] / t["empresas"].sum()
    return t.sort_values("empresas", ascending=False).head(top).reset_index(drop=True)


def por_seccion(df: pd.DataFrame) -> pd.DataFrame:
    """Empresas por sección CIIU, con su macro sector (para colorear)."""
    t = (df.groupby(["macro_sector", "seccion_letra", "seccion_nombre"]).size()
           .rename("empresas").reset_index())
    t["pct"] = 100 * t["empresas"] / t["empresas"].sum()
    return t.sort_values("empresas", ascending=False).reset_index(drop=True)


def evolucion_matriculas(df: pd.DataFrame, desde: int = 1990) -> pd.DataFrame:
    """Nuevas matrículas por año, indicando si el año es parcial por el corte."""
    t = (df.dropna(subset=["anio_matricula"]).groupby("anio_matricula")
           .agg(empresas=("id_empresa", "size"), anio_parcial=("anio_parcial", "max")).reset_index())
    t["anio_matricula"] = t["anio_matricula"].astype(int)
    t["anio_parcial"] = t["anio_parcial"].astype(bool)
    return t[t["anio_matricula"] >= desde].reset_index(drop=True)


def valor_por_macro_sector(df: pd.DataFrame) -> pd.DataFrame:
    """Mediana del valor del establecimiento (solo valores reportados) por macro sector."""
    rep = df[(df["vlr_no_reportado"] == 0) & (df["macro_sector"] != config.SIN_CLASIFICAR)]
    t = (rep.groupby("macro_sector")["vlr_establecimiento"]
            .agg(mediana="median", n="size").reset_index())
    t["orden"] = t["macro_sector"].map({m: i for i, m in enumerate(ORDEN_MACRO)})
    return t.sort_values("orden").drop(columns="orden").reset_index(drop=True)


def barrios_pasto(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Barrios con más empresas. Solo Pasto trae barrio en la fuente."""
    t = (df.dropna(subset=["barrio_nombre"]).groupby("barrio_nombre").size()
           .rename("empresas").reset_index())
    t["pct"] = 100 * t["empresas"] / t["empresas"].sum()
    return t.sort_values("empresas", ascending=False).head(top).reset_index(drop=True)


def todos() -> dict:
    """Todos los agregados del dashboard en un solo diccionario."""
    df = cargar()
    return {
        "indicadores": indicadores(df),
        "macro_sector": por_macro_sector(df),
        "municipio": por_municipio(df),
        "seccion": por_seccion(df),
        "matriculas": evolucion_matriculas(df),
        "valor": valor_por_macro_sector(df),
        "barrios": barrios_pasto(df),
        "total_barrios": int(df["barrio_nombre"].notna().sum()),
    }
