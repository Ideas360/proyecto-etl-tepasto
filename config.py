"""Configuración compartida por todas las etapas del pipeline.

Centraliza rutas y nombres de archivos para que ninguna etapa dependa de desde
qué carpeta se ejecuta.
"""
from pathlib import Path

# Raíz del repositorio (la carpeta que contiene este archivo)
RAIZ = Path(__file__).resolve().parent

RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
DOCS = RAIZ / "docs"

# --- Fuentes de entrada ---------------------------------------------------
# Si existe el archivo completo se usa; si no, la muestra anonimizada.
FUENTE_COMPLETA = RAW / "PASTO.xlsx"
FUENTE_MUESTRA = RAW / "muestra_anonimizada.xlsx"
CIIU_XLSX = RAW / "CIIU_Rev4AC_estructura_detallada_2020.xlsx"

# --- Salidas de Extract ---------------------------------------------------
REGISTRO_EXTRAIDO = RAW / "registro_mercantil_extraido.csv"
CIIU_EXTRAIDO = RAW / "ciiu_extraido.csv"
EXTRACCION_META = RAW / "extraccion_meta.json"

# --- Esquema esperado del registro mercantil (25 columnas) ----------------
COLUMNAS_REGISTRO = [
    "MATRICULA", "EST_DATOS", "RAZON SOCIAL", "FEC-MATRICULA", "FEC-RENOVACION",
    "ULT-ANO_REN", "DIR-COMERCIAL", "BARRIO-COMERCIAL", "MUN-COMERCIAL",
    "DIR-NOTIFICACION", "CIIU-1", "CIIU-2", "CIIU-3", "CIIU-4", "ACTIVIDAD",
    "VLR-ESTABLEC.", "MAT-PROP.", "IDE-PROP.", "NIT-PROP.", "CAM-PROP.",
    "NOM-PROP", "DIR-PROP", "TEL-1-PROP", "TEL-2-PROP", "MUN-PROP",
]

# Columnas del catálogo CIIU tal como vienen en el archivo (fila 2 = encabezado)
COLUMNAS_CIIU = ["division", "grupo", "clase", "descripcion"]

# --- Salidas de Transform -------------------------------------------------
EMPRESAS_PROCESADAS = PROCESSED / "empresas_procesadas.csv"
CIIU_APLANADO = PROCESSED / "ciiu_aplanado.csv"
REPORTE_CALIDAD = PROCESSED / "reporte_calidad.csv"

# --- Reglas de transformación ---------------------------------------------
# Macro sector según la sección CIIU (letra). Convención usada en el EDA.
MACRO_SECTOR = {
    **{s: "Primario" for s in "AB"},
    **{s: "Secundario" for s in "CDEF"},
    **{s: "Terciario" for s in "GHIJKLMNOPQRSTU"},
}

# Columnas con datos personales o identificadores directos: NO pasan a processed.
COLUMNAS_PERSONALES = [
    "MATRICULA", "RAZON SOCIAL", "DIR-COMERCIAL", "DIR-NOTIFICACION",
    "MAT-PROP.", "IDE-PROP.", "NIT-PROP.", "CAM-PROP.", "NOM-PROP",
    "DIR-PROP", "TEL-1-PROP", "TEL-2-PROP", "MUN-PROP",
]

# Etiquetas para registros que no se pueden clasificar (no se eliminan)
SIN_CLASIFICAR = "SIN CLASIFICAR"
SIN_DATO = "SIN DATO"

# --- Salidas de Load --------------------------------------------------------
BASE_DATOS = PROCESSED / "empresas.db"
ESQUEMA_SQL = RAIZ / "load" / "esquema.sql"
