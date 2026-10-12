"""Etapa 3 - Load.

Carga los datos procesados en una base SQLite con modelo estrella
(fact_empresa + dim_municipio, dim_sector, dim_tiempo), valida la carga y agrega
las verificaciones al reporte de calidad.

Modo de carga: REEMPLAZO. La base se construye en un archivo temporal y solo si
todo sale bien reemplaza a la anterior; si algo falla, la base previa no se toca.

Uso:
    python load/cargar.py
"""
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

PREFIJO_REPORTE = "[Load] "


class ErrorCarga(Exception):
    """Error esperable de carga (entradas ausentes o que violan el modelo)."""


# ---------------------------------------------------------------------------
# Lectura de entradas
# ---------------------------------------------------------------------------
def _leer_procesados() -> tuple[pd.DataFrame, pd.DataFrame]:
    for ruta in (config.EMPRESAS_PROCESADAS, config.CIIU_APLANADO):
        if not ruta.exists():
            raise ErrorCarga(f"No existe {ruta.name}. Ejecute primero la etapa Transform.")

    texto = {"ciiu_codigo": str, "mun_codigo": str, "est_datos": str, "grupo_codigo": str, "division_codigo": str}
    empresas = pd.read_csv(config.EMPRESAS_PROCESADAS, dtype=texto)
    plano = pd.read_csv(config.CIIU_APLANADO, dtype=str)
    if empresas.empty:
        raise ErrorCarga("empresas_procesadas.csv no tiene registros.")
    return empresas, plano


# ---------------------------------------------------------------------------
# Construcción de las dimensiones
# ---------------------------------------------------------------------------
def construir_dim_municipio(empresas: pd.DataFrame) -> pd.DataFrame:
    dim = empresas[["mun_codigo", "mun_nombre"]].drop_duplicates()
    if dim["mun_codigo"].duplicated().any():
        raise ErrorCarga("Hay códigos de municipio con más de un nombre.")
    return dim.sort_values("mun_codigo").reset_index(drop=True)


def construir_dim_sector(empresas: pd.DataFrame, plano: pd.DataFrame) -> pd.DataFrame:
    """Catálogo completo + códigos que el registro trae y el catálogo no tiene.

    La dimensión se construye desde el catálogo (no solo desde las empresas), para que
    existan también las clases que hoy no tienen ninguna empresa.
    """
    cols = ["ciiu_codigo", "clase_nombre", "grupo_codigo", "grupo_nombre", "division_codigo",
            "division_nombre", "seccion_letra", "seccion_nombre", "macro_sector"]

    catalogo = plano.rename(columns={"clase_codigo": "ciiu_codigo"})[cols].copy()
    catalogo["en_catalogo"] = 1

    # Códigos del registro ausentes del catálogo (incluye '0000' = sin clasificar)
    faltantes = empresas.loc[~empresas["ciiu_codigo"].isin(catalogo["ciiu_codigo"])].copy()
    faltantes = faltantes.rename(columns={"ciiu_seccion": "seccion_letra"})
    faltantes = faltantes[cols].drop_duplicates("ciiu_codigo")
    faltantes["en_catalogo"] = 0

    # Miembro "sin clasificar" siempre presente (para claves foráneas completas)
    if "0000" not in set(catalogo["ciiu_codigo"]) | set(faltantes["ciiu_codigo"]):
        s = config.SIN_CLASIFICAR
        desconocido = pd.DataFrame([{
            "ciiu_codigo": "0000", "clase_nombre": s, "grupo_codigo": "000", "grupo_nombre": s,
            "division_codigo": "00", "division_nombre": s, "seccion_letra": "-",
            "seccion_nombre": s, "macro_sector": s, "en_catalogo": 0}])
        faltantes = pd.concat([faltantes, desconocido], ignore_index=True)

    dim = pd.concat([catalogo, faltantes], ignore_index=True)
    if dim["ciiu_codigo"].duplicated().any():
        raise ErrorCarga("dim_sector tiene códigos CIIU repetidos.")
    return dim.sort_values("ciiu_codigo").reset_index(drop=True)


def construir_dim_tiempo(empresas: pd.DataFrame) -> pd.DataFrame:
    anios = empresas["anio_matricula"].dropna().astype(int)
    parciales = set(empresas.loc[empresas["anio_parcial"], "anio_matricula"].dropna().astype(int))
    rango = range(int(anios.min()), int(anios.max()) + 1)   # sin huecos entre años
    return pd.DataFrame({
        "anio": list(rango),
        "decada": [f"{a // 10 * 10}s" for a in rango],
        "anio_parcial": [int(a in parciales) for a in rango],
    })


def construir_hechos(empresas: pd.DataFrame) -> pd.DataFrame:
    cols = ["id_empresa", "mun_codigo", "ciiu_codigo", "anio_matricula", "est_datos", "fec_matricula",
            "fec_renovacion", "ult_ano_ren", "antiguedad_anios", "n_actividades", "ciiu_estado",
            "barrio_codigo", "barrio_nombre", "actividad", "vlr_establecimiento", "vlr_no_reportado",
            "vlr_winsorizado", "vlr_outlier"]
    h = empresas[cols].copy()
    for c in ["vlr_no_reportado", "vlr_outlier"]:
        h[c] = h[c].astype(int)
    return h


# ---------------------------------------------------------------------------
# Inserción y validación
# ---------------------------------------------------------------------------
def _insertar(con: sqlite3.Connection, tabla: str, df: pd.DataFrame) -> None:
    """Inserta un DataFrame; los nulos de pandas pasan a NULL de SQL."""
    limpio = df.astype(object).where(df.notna(), None)
    marcas = ", ".join("?" * df.shape[1])
    columnas = ", ".join(df.columns)
    con.executemany(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})",
                    limpio.itertuples(index=False, name=None))


def _validar(con: sqlite3.Connection, empresas: pd.DataFrame, plano: pd.DataFrame) -> list[dict]:
    """Verifica la base recién cargada. Lanza ErrorCarga si algo está mal."""
    def uno(sql):
        return con.execute(sql).fetchone()[0]

    n_hechos = uno("SELECT COUNT(*) FROM fact_empresa")
    huerfanas = len(con.execute("PRAGMA foreign_key_check").fetchall())
    integridad = uno("PRAGMA integrity_check")
    n_sectores = uno("SELECT COUNT(*) FROM dim_sector")
    n_catalogo = uno("SELECT COUNT(*) FROM dim_sector WHERE en_catalogo = 1")

    # Conteo por macro sector: la base debe coincidir con el CSV de origen
    bd = dict(con.execute("SELECT macro_sector, COUNT(*) FROM v_empresas GROUP BY macro_sector").fetchall())
    csv = empresas["macro_sector"].value_counts().to_dict()

    if n_hechos != len(empresas):
        raise ErrorCarga(f"fact_empresa tiene {n_hechos} filas y el CSV {len(empresas)}.")
    if huerfanas:
        raise ErrorCarga(f"Hay {huerfanas} claves foráneas huérfanas.")
    if integridad != "ok":
        raise ErrorCarga(f"integrity_check falló: {integridad}")
    if bd != csv:
        raise ErrorCarga(f"Los conteos por macro sector no coinciden: base={bd} csv={csv}")
    if n_catalogo != len(plano):
        raise ErrorCarga(f"dim_sector trae {n_catalogo} clases del catálogo y el catálogo tiene {len(plano)}.")

    def fila(v, antes, despues, nota=""):
        return {"verificacion": PREFIJO_REPORTE + v, "antes": antes, "despues": despues, "nota": nota}

    return [
        fila("Registros: CSV procesado -> fact_empresa", len(empresas), n_hechos, "Sin pérdida entre Transform y Load"),
        fila("Claves foráneas huérfanas", "-", huerfanas, "PRAGMA foreign_key_check"),
        fila("Integridad de la base", "-", integridad, "PRAGMA integrity_check"),
        fila("Clases del catálogo en dim_sector", len(plano), n_catalogo, f"dim_sector total: {n_sectores} (incluye códigos ausentes del catálogo)"),
        fila("Conteos por macro sector: CSV = base", "-", "coinciden", ", ".join(f"{k}: {v}" for k, v in sorted(bd.items()))),
    ]


def _actualizar_reporte(filas: list[dict]) -> None:
    """Agrega las filas de Load al reporte de calidad (reemplazando las de una corrida anterior)."""
    if not config.REPORTE_CALIDAD.exists():
        return
    rep = pd.read_csv(config.REPORTE_CALIDAD, dtype=str)
    rep = rep[~rep["verificacion"].str.startswith(PREFIJO_REPORTE, na=False)]
    rep = pd.concat([rep, pd.DataFrame(filas).astype(str)], ignore_index=True)
    rep.to_csv(config.REPORTE_CALIDAD, index=False, encoding="utf-8")


# ---------------------------------------------------------------------------
# Etapa completa
# ---------------------------------------------------------------------------
def ejecutar() -> dict:
    empresas, plano = _leer_procesados()
    dim_mun = construir_dim_municipio(empresas)
    dim_sec = construir_dim_sector(empresas, plano)
    dim_tie = construir_dim_tiempo(empresas)
    hechos = construir_hechos(empresas)

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    temporal = config.BASE_DATOS.with_suffix(".db.tmp")
    if temporal.exists():
        temporal.unlink()

    con = sqlite3.connect(temporal)
    try:
        con.executescript(config.ESQUEMA_SQL.read_text(encoding="utf-8"))
        con.execute("PRAGMA foreign_keys = ON")
        # Las dimensiones primero: los hechos referencian sus claves.
        _insertar(con, "dim_municipio", dim_mun)
        _insertar(con, "dim_sector", dim_sec)
        _insertar(con, "dim_tiempo", dim_tie)
        _insertar(con, "fact_empresa", hechos)
        con.commit()
        filas_reporte = _validar(con, empresas, plano)
    except sqlite3.IntegrityError as e:
        con.close()
        temporal.unlink(missing_ok=True)
        raise ErrorCarga(f"Los datos violan una restricción del modelo: {e}") from e
    except Exception:
        con.close()
        temporal.unlink(missing_ok=True)
        raise
    con.close()

    os.replace(temporal, config.BASE_DATOS)   # reemplazo atómico
    _actualizar_reporte(filas_reporte)

    resumen = {"fact_empresa": len(hechos), "dim_municipio": len(dim_mun),
               "dim_sector": len(dim_sec), "dim_tiempo": len(dim_tie)}
    print("[Load] Base creada:", config.BASE_DATOS)
    print("[Load] Filas cargadas:", ", ".join(f"{k}={v:,}" for k, v in resumen.items()))
    print("[Load] Validaciones: integridad ok, 0 claves huérfanas, conteos CSV = base")
    return resumen


def main() -> None:
    try:
        ejecutar()
    except ErrorCarga as e:
        print(f"[Load] ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
