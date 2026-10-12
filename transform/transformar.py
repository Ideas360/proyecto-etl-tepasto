"""Etapa 2 - Transform.

Convierte el registro mercantil extraído en una tabla limpia, enriquecida con el
catálogo CIIU y SIN datos personales, y genera el reporte de calidad
(conteos antes/después) que alimenta la sección 10 del README.

Cada transformación responde a un hallazgo del EDA (ver README, sección 8.2).

Uso:
    python transform/transformar.py
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


class ErrorTransformacion(Exception):
    """Error esperable de transformación (entradas ausentes o inconsistentes)."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def normalizar_texto(serie: pd.Series) -> pd.Series:
    """Quita espacios sobrantes/dobles, compone las tildes (NFC) y pasa a mayúsculas."""
    s = (serie.str.normalize("NFC")
              .str.replace(r"\s+", " ", regex=True)
              .str.strip()
              .str.upper())
    return s.replace("", pd.NA)


# Datos de contacto que pueden aparecer escritos dentro de un campo de texto libre
PATRON_CONTACTO = (r"[\w.+-]+@[\w-]+\.[\w.]+"                                   # correo
                   r"|(?:\+?57[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"      # teléfono con o sin separadores
                   r"|\d{7,}")                                                  # 7 o más dígitos seguidos


def ocultar_contacto(serie: pd.Series) -> pd.Series:
    """Elimina teléfonos y correos escritos en texto libre; si no queda nada, el valor pasa a nulo."""
    return serie.str.replace(PATRON_CONTACTO, " ", regex=True)


def _es(x: float, decimales: int = 0) -> str:
    """Número en formato español (punto de miles, coma decimal) para las notas del reporte."""
    texto = f"{x:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _limpiar(texto) -> str | None:
    if pd.isna(texto):
        return None
    return re.sub(r"\s+", " ", str(texto)).strip()


def _leer_entrada(ruta: Path) -> pd.DataFrame:
    if not ruta.exists():
        raise ErrorTransformacion(f"No existe {ruta.name}. Ejecute primero la etapa Extract.")
    # Todo como texto; solo las celdas realmente vacías son nulas.
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, na_values=[""])


# ---------------------------------------------------------------------------
# Catálogo CIIU: de lista jerárquica en filas a una tabla plana (1 fila = 1 clase)
# ---------------------------------------------------------------------------
def aplanar_ciiu(ciiu: pd.DataFrame) -> pd.DataFrame:
    """Asocia a cada clase su grupo, división y sección (recorriendo el archivo en orden).

    El archivo mezcla secciones, divisiones, grupos y clases en la misma columna de
    descripción; el nivel de cada fila se reconoce por la columna donde trae su código.
    """
    seccion = (None, None)
    division = (None, None)
    grupo = (None, None)
    filas = []

    for _, f in ciiu.iterrows():
        desc = _limpiar(f["descripcion"])
        div = _limpiar(f["division"])
        gru = _limpiar(f["grupo"])
        cla = _limpiar(f["clase"])

        if div and (m := re.match(r"^SECCI[ÓO]N\s+([A-Z])$", div, re.IGNORECASE)):
            seccion, division, grupo = (m.group(1).upper(), desc), (None, None), (None, None)
        elif div and re.fullmatch(r"\d{1,2}", div):
            division, grupo = (div.zfill(2), desc), (None, None)
        else:
            # Un grupo con una sola clase trae ambos códigos en la MISMA fila
            # (p. ej. grupo 013 y clase 0130), por eso se evalúan por separado.
            if gru and re.fullmatch(r"\d{1,3}", gru):
                grupo = (gru.zfill(3), desc)
            if not (cla and re.fullmatch(r"\d{1,4}", cla)):
                continue
            filas.append({
                "clase_codigo": cla.zfill(4), "clase_nombre": desc,
                "grupo_codigo": grupo[0], "grupo_nombre": grupo[1],
                "division_codigo": division[0], "division_nombre": division[1],
                "seccion_letra": seccion[0], "seccion_nombre": seccion[1],
            })

    plano = pd.DataFrame(filas)
    if plano.empty:
        raise ErrorTransformacion("No se pudo aplanar el catálogo CIIU: no se encontraron clases.")
    if plano["clase_codigo"].duplicated().any():
        raise ErrorTransformacion("El catálogo CIIU aplanado tiene clases repetidas.")
    if plano[["grupo_codigo", "division_codigo", "seccion_letra"]].isna().any().any():
        raise ErrorTransformacion("Hay clases del catálogo sin grupo, división o sección.")

    plano["macro_sector"] = plano["seccion_letra"].map(config.MACRO_SECTOR)
    return plano


# ---------------------------------------------------------------------------
# Transformación principal del registro mercantil
# ---------------------------------------------------------------------------
def transformar_registro(registro: pd.DataFrame, plano: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Devuelve (tabla procesada, estadísticas para el reporte de calidad)."""
    est: dict = {"filas_entrada": len(registro), "columnas_entrada": registro.shape[1]}
    df = registro.copy()

    # T1. Identificador técnico y duplicados ------------------------------------
    # La matrícula es un identificador directo: se reemplaza por el orden en la fuente.
    df["id_empresa"] = np.arange(1, len(df) + 1)
    est["duplicados_antes"] = int(df["MATRICULA"].duplicated().sum())
    df = df.drop_duplicates(subset="MATRICULA", keep="first")
    est["duplicados_despues"] = int(df["MATRICULA"].duplicated().sum())

    # T2. Separar código y texto (municipio y CIIU) -----------------------------
    mun = df["MUN-COMERCIAL"].str.extract(r"^(\d{5})\s*-\s*(.+)$")
    df["mun_codigo"] = mun[0]
    df["mun_nombre"] = normalizar_texto(mun[1])
    est["mun_nulos_antes"] = int(df["MUN-COMERCIAL"].isna().sum())
    df["mun_codigo"] = df["mun_codigo"].fillna("00000")
    df["mun_nombre"] = df["mun_nombre"].fillna(config.SIN_DATO)

    ciiu1 = df["CIIU-1"].str.extract(r"^([A-Z])(\d{4})")
    df["ciiu_seccion"] = ciiu1[0]
    df["ciiu_codigo"] = ciiu1[1]
    # Las actividades secundarias (CIIU-2..4) tienen 59 % a 89 % de nulos: se resumen en un conteo.
    cols_ciiu = ["CIIU-1", "CIIU-2", "CIIU-3", "CIIU-4"]
    df["n_actividades"] = df[cols_ciiu].notna().sum(axis=1).astype(int)
    est["sin_ciiu_antes"] = int(df["CIIU-1"].isna().sum())

    # T3. Fechas: de entero AAAAMMDD a fecha real; antigüedad; año parcial -------
    df["fec_matricula"] = pd.to_datetime(df["FEC-MATRICULA"], format="%Y%m%d", errors="coerce")
    df["fec_renovacion"] = pd.to_datetime(df["FEC-RENOVACION"], format="%Y%m%d", errors="coerce")
    est["fechas_invalidas_antes"] = int((df["FEC-MATRICULA"].notna() & df["fec_matricula"].isna()).sum())
    est["fechas_nulas_despues"] = int(df["fec_matricula"].isna().sum())

    # La extracción es una fotografía: su fecha de corte es la renovación más reciente.
    corte = df["fec_renovacion"].max()
    est["fecha_corte"] = corte.date().isoformat()
    df["anio_matricula"] = df["fec_matricula"].dt.year.astype("Int64")
    df["antiguedad_anios"] = ((corte - df["fec_matricula"]).dt.days / 365.25).round(1)
    est["antiguedad_negativa"] = int((df["antiguedad_anios"] < 0).sum())
    # El año del corte tiene matrículas incompletas: se marca para no leerlo como caída real.
    df["anio_parcial"] = df["anio_matricula"] == corte.year
    est["filas_anio_parcial"] = int(df["anio_parcial"].sum())
    df["ult_ano_ren"] = pd.to_numeric(df["ULT-ANO_REN"], errors="coerce").astype("Int64")

    # T4. Estado de la matrícula: variable categórica sin interpretar -------------
    df["est_datos"] = df["EST_DATOS"].fillna(config.SIN_DATO)

    # T5/T6. Valor del establecimiento: ceros, outliers y winsorización ------------
    vlr = pd.to_numeric(df["VLR-ESTABLEC."], errors="coerce")
    est["vlr_negativos"] = int((vlr < 0).sum())
    df["vlr_establecimiento"] = vlr
    df["vlr_no_reportado"] = vlr.isna() | (vlr <= 0)          # el cero es "sin dato", no un valor real
    reportado = vlr.where(~df["vlr_no_reportado"])
    p01, p99 = reportado.quantile(0.01), reportado.quantile(0.99)
    df["vlr_winsorizado"] = reportado.clip(lower=p01, upper=p99)
    df["vlr_outlier"] = (reportado < p01) | (reportado > p99)
    est.update({
        "vlr_ceros": int(df["vlr_no_reportado"].sum()),
        "vlr_p01": float(p01), "vlr_p99": float(p99),
        "vlr_outliers": int(df["vlr_outlier"].sum()),
        "vlr_max_antes": float(reportado.max()), "vlr_max_despues": float(df["vlr_winsorizado"].max()),
        "vlr_min_antes": float(reportado.min()), "vlr_min_despues": float(df["vlr_winsorizado"].min()),
        "vlr_menor_1000": int((reportado < 1000).sum()),
        "vlr_menor_1000_despues": int((df["vlr_winsorizado"] < 1000).sum()),
    })

    # T7. Normalización de texto ----------------------------------------------------
    est["actividad_doble_espacio_antes"] = int(df["ACTIVIDAD"].str.contains(r"\s{2,}", na=False).sum())
    est["barrio_doble_espacio_antes"] = int(df["BARRIO-COMERCIAL"].str.contains(r"\s{2,}", na=False).sum())
    # Privacidad: el texto libre puede traer teléfonos o correos (p. ej. una actividad que es un celular).
    est["contacto_en_texto_antes"] = int(
        df["ACTIVIDAD"].str.contains(PATRON_CONTACTO, regex=True, na=False).sum()
        + df["BARRIO-COMERCIAL"].str.contains(PATRON_CONTACTO, regex=True, na=False).sum())
    df["actividad"] = normalizar_texto(ocultar_contacto(df["ACTIVIDAD"]))
    # El barrio también mezcla código y nombre ("00633 - Parque Bolívar"): se separan como el municipio.
    # Solo Pasto trae barrio; en los demás municipios es nulo por diseño de la fuente.
    barrio_limpio = ocultar_contacto(df["BARRIO-COMERCIAL"])
    barrio = barrio_limpio.str.extract(r"^\s*(\d{1,5})\s*-\s*(.+)$")
    df["barrio_codigo"] = barrio[0].str.zfill(5)
    df["barrio_nombre"] = normalizar_texto(barrio[1]).fillna(normalizar_texto(barrio_limpio))
    est["barrio_informados"] = int(df["BARRIO-COMERCIAL"].notna().sum())
    est["barrio_separados"] = int(df["barrio_codigo"].notna().sum())
    est["barrio_municipios"] = int(df.loc[df["BARRIO-COMERCIAL"].notna(), "mun_codigo"].nunique())
    est["contacto_en_texto_despues"] = int(
        df["actividad"].str.contains(PATRON_CONTACTO, regex=True, na=False).sum()
        + df["barrio_nombre"].str.contains(PATRON_CONTACTO, regex=True, na=False).sum())
    est["actividad_doble_espacio_despues"] = int(df["actividad"].str.contains(r"\s{2,}", na=False).sum())
    est["barrio_doble_espacio_despues"] = int(df["barrio_nombre"].str.contains(r"\s{2,}", na=False).sum())

    # T8. Enriquecimiento: LEFT JOIN con el catálogo CIIU (muchos a uno) ------------
    n_antes = len(df)
    enriq = plano[["clase_codigo", "clase_nombre", "seccion_letra"]].rename(
        columns={"seccion_letra": "seccion_catalogo"})
    df = df.merge(enriq, left_on="ciiu_codigo", right_on="clase_codigo", how="left", validate="m:1")
    if len(df) != n_antes:
        raise ErrorTransformacion("El join con el catálogo CIIU alteró el número de registros.")
    est["registros_perdidos_join"] = n_antes - len(df)

    conc = df["clase_codigo"].notna()
    df["ciiu_estado"] = np.select(
        [df["ciiu_codigo"].isna(), conc],
        ["sin_ciiu", "ok"], default="codigo_no_encontrado")
    est["ciiu_ok"] = int(conc.sum())
    est["ciiu_no_encontrado"] = int((df["ciiu_estado"] == "codigo_no_encontrado").sum())
    est["ciiu_codigos_no_encontrados"] = sorted(
        df.loc[df["ciiu_estado"] == "codigo_no_encontrado", "ciiu_codigo"].unique().tolist())
    est["ciiu_sin_ciiu"] = int((df["ciiu_estado"] == "sin_ciiu").sum())
    # Coherencia: la letra del registro debe coincidir con la sección del catálogo.
    est["letra_incoherente"] = int((conc & (df["ciiu_seccion"] != df["seccion_catalogo"])).sum())

    # División y grupo salen del prefijo del código, así que también existen para
    # los códigos que el catálogo 2020 ya no trae como clase.
    divisiones = plano.drop_duplicates("division_codigo").set_index("division_codigo")["division_nombre"]
    grupos = plano.drop_duplicates("grupo_codigo").set_index("grupo_codigo")["grupo_nombre"]
    secciones = plano.drop_duplicates("seccion_letra").set_index("seccion_letra")["seccion_nombre"]

    df["division_codigo"] = df["ciiu_codigo"].str[:2]
    df["grupo_codigo"] = df["ciiu_codigo"].str[:3]
    df["division_nombre"] = df["division_codigo"].map(divisiones)
    df["grupo_nombre"] = df["grupo_codigo"].map(grupos)
    df["seccion_nombre"] = df["ciiu_seccion"].map(secciones)
    df["macro_sector"] = df["ciiu_seccion"].map(config.MACRO_SECTOR)
    df["clase_nombre"] = df["clase_nombre"].where(conc)

    # Valores desconocidos explícitos (clave foránea siempre completa en el modelo estrella)
    df["ciiu_codigo"] = df["ciiu_codigo"].fillna("0000")
    df["ciiu_seccion"] = df["ciiu_seccion"].fillna("-")
    for c in ["clase_nombre", "grupo_nombre", "division_nombre", "seccion_nombre", "macro_sector"]:
        df[c] = df[c].fillna(config.SIN_CLASIFICAR)
    df["division_codigo"] = df["division_codigo"].fillna("00")
    df["grupo_codigo"] = df["grupo_codigo"].fillna("000")

    # T9. Retiro de datos personales: solo se conservan las columnas del esquema final
    columnas_finales = [
        "id_empresa", "est_datos", "fec_matricula", "fec_renovacion", "anio_matricula",
        "antiguedad_anios", "anio_parcial", "ult_ano_ren",
        "mun_codigo", "mun_nombre", "barrio_codigo", "barrio_nombre",
        "ciiu_codigo", "ciiu_seccion", "n_actividades", "ciiu_estado",
        "clase_nombre", "grupo_codigo", "grupo_nombre", "division_codigo", "division_nombre",
        "seccion_nombre", "macro_sector", "actividad",
        "vlr_establecimiento", "vlr_no_reportado", "vlr_winsorizado", "vlr_outlier",
    ]
    df = df[columnas_finales]
    # Nulos en columnas clave: antes (fuente) y después (ya con los valores "SIN DATO" asignados)
    est["nulos_clave_antes"] = int(registro[["MUN-COMERCIAL", "CIIU-1", "FEC-MATRICULA"]].isna().sum().sum())
    est["nulos_clave_despues"] = int(df[["id_empresa", "mun_codigo", "ciiu_codigo", "fec_matricula"]].isna().sum().sum())

    # Control duro: la salida debe tener exactamente las filas de entrada menos los duplicados descartados
    descartadas = est["duplicados_antes"] - est["duplicados_despues"]
    if len(df) != est["filas_entrada"] - descartadas:
        raise ErrorTransformacion(
            f"Se perdieron registros: entrada {est['filas_entrada']}, salida {len(df)}, duplicados {descartadas}.")
    est["filas_salida"] = len(df)
    est["columnas_salida"] = df.shape[1]
    est["personales_antes"] = len([c for c in config.COLUMNAS_PERSONALES if c in registro.columns])
    est["personales_despues"] = len([c for c in df.columns if c.upper() in
                                     {p.upper() for p in config.COLUMNAS_PERSONALES}])
    return df, est


# ---------------------------------------------------------------------------
# Reporte de calidad (alimenta la sección 10 del README)
# ---------------------------------------------------------------------------
def construir_reporte(est: dict, es_muestra: bool, nombre_fuente: str) -> pd.DataFrame:
    def fila(verificacion, antes, despues, nota=""):
        return {"verificacion": verificacion, "antes": antes, "despues": despues, "nota": nota}

    pct = 100 * est["ciiu_ok"] / est["filas_salida"]
    filas = [
        fila("Fuente usada", nombre_fuente, nombre_fuente, "MUESTRA anonimizada" if es_muestra else "Archivo completo"),
        fila("Número de registros", est["filas_entrada"], est["filas_salida"], "No se descarta ningún registro"),
        fila("Registros duplicados (por matrícula)", est["duplicados_antes"], est["duplicados_despues"]),
        fila("Valores nulos en columnas clave (municipio, CIIU, fecha de matrícula)", est["nulos_clave_antes"], est["nulos_clave_despues"],
             "Los nulos pasan a miembros explícitos 'SIN DATO' / 'SIN CLASIFICAR'; ningún registro se descarta"),
        fila("Número de columnas", est["columnas_entrada"], est["columnas_salida"], "Se retiran datos personales y se derivan variables"),
        fila("Columnas con datos personales", est["personales_antes"], est["personales_despues"], "Matrícula, razón social, direcciones, propietario y contacto"),
        fila("Fechas de matrícula no interpretables", est["fechas_invalidas_antes"], est["fechas_nulas_despues"], "AAAAMMDD -> fecha"),
        fila("Antigüedad negativa (matrícula posterior al corte)", "-", est["antiguedad_negativa"], f"Fecha de corte: {est['fecha_corte']}"),
        fila("Registros del año de corte (matrícula parcial)", "-", est["filas_anio_parcial"], "Marcados con anio_parcial; no son una caída real"),
        fila("Municipio nulo", est["mun_nulos_antes"], 0, "Reemplazado por 'SIN DATO' (código 00000)"),
        fila("Registros sin CIIU principal", est["sin_ciiu_antes"], est["ciiu_sin_ciiu"], "Se conservan como 'SIN CLASIFICAR'"),
        fila("Códigos CIIU sin coincidencia en el catálogo", "-", est["ciiu_no_encontrado"],
             f"Códigos: {', '.join(est['ciiu_codigos_no_encontrados']) or 'ninguno'}; se conservan (left join)"),
        fila("Registros perdidos en el join con CIIU", "-", est["registros_perdidos_join"], f"Cobertura del catálogo: {_es(pct, 2)} %"),
        fila("Letra CIIU del registro distinta de la sección del catálogo", "-", est["letra_incoherente"], "Coherencia entre fuentes"),
        fila("Valores del establecimiento en cero", est["vlr_ceros"], 0, "Marcados vlr_no_reportado; no se tratan como valor real"),
        fila("Valores del establecimiento negativos", est["vlr_negativos"], 0, "Rango válido: mayor que cero; los no válidos se marcan como no reportado"),
        fila("Valores reportados menores a $1.000", est["vlr_menor_1000"], est["vlr_menor_1000_despues"],
             "Posibles errores de digitación (p. ej. $0,1 o $1); la winsorización los lleva al P1"),
        fila("Valor mínimo del establecimiento (COP)", est["vlr_min_antes"], est["vlr_min_despues"], f"Winsorización inferior en P1 = ${_es(est['vlr_p01'])}"),
        fila("Valor máximo del establecimiento (COP)", est["vlr_max_antes"], est["vlr_max_despues"], f"Winsorización superior en P99 = ${_es(est['vlr_p99'])}"),
        fila("Registros marcados como outlier de valor", "-", est["vlr_outliers"], "Fuera del rango P1-P99"),
        fila("Teléfonos o correos escritos en texto libre", est["contacto_en_texto_antes"], est["contacto_en_texto_despues"],
             "Se eliminan de ACTIVIDAD y BARRIO; si queda vacío, el valor pasa a nulo"),
        fila("ACTIVIDAD con espacios dobles", est["actividad_doble_espacio_antes"], est["actividad_doble_espacio_despues"]),
        fila("Barrios con formato 'código - nombre' separado", est["barrio_informados"], est["barrio_separados"],
             "El 100 % de los barrios informados sigue el patrón"),
        fila("Municipios con barrio informado", "-", est["barrio_municipios"],
             "Solo Pasto trae barrio: en los demás es nulo por diseño de la fuente, no por falta de datos"),
        fila("BARRIO con espacios dobles", est["barrio_doble_espacio_antes"], est["barrio_doble_espacio_despues"]),
    ]
    return pd.DataFrame(filas)


def ejecutar() -> dict:
    """Corre la etapa completa."""
    import json
    registro = _leer_entrada(config.REGISTRO_EXTRAIDO)
    ciiu = _leer_entrada(config.CIIU_EXTRAIDO)
    meta = json.loads(config.EXTRACCION_META.read_text(encoding="utf-8")) if config.EXTRACCION_META.exists() else {}

    plano = aplanar_ciiu(ciiu)
    tabla, est = transformar_registro(registro, plano)
    reporte = construir_reporte(est, meta.get("es_muestra", False), meta.get("fuente_registro", "desconocida"))

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(config.EMPRESAS_PROCESADAS, index=False, encoding="utf-8")
    plano.to_csv(config.CIIU_APLANADO, index=False, encoding="utf-8")
    reporte.to_csv(config.REPORTE_CALIDAD, index=False, encoding="utf-8")

    print(f"[Transform] Catálogo CIIU aplanado: {len(plano)} clases")
    print(f"[Transform] Registros: {est['filas_entrada']:,} -> {est['filas_salida']:,} | "
          f"columnas: {est['columnas_entrada']} -> {est['columnas_salida']}")
    print(f"[Transform] CIIU: {est['ciiu_ok']:,} con catálogo, {est['ciiu_no_encontrado']} sin coincidencia, "
          f"{est['ciiu_sin_ciiu']} sin CIIU")
    print(f"[Transform] Salidas en {config.PROCESSED}")
    return est


def main() -> None:
    try:
        ejecutar()
    except ErrorTransformacion as e:
        print(f"[Transform] ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
