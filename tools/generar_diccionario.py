"""Genera docs/diccionario_datos.md a partir de la base SQLite.

Lee la estructura REAL de la base (tablas, columnas, tipos y claves) y le agrega la
descripción de cada columna. Si una columna de la base no tiene descripción, o hay
una descripción de una columna que ya no existe, el script falla: así el diccionario
no puede quedar desactualizado respecto al modelo.

Los ejemplos salen de UNA misma empresa de la base y de las filas de las dimensiones
que ella referencia, para que se lean como un registro coherente.

Uso (después de ejecutar el pipeline):
    python tools/generar_diccionario.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SALIDA = config.DOCS / "diccionario_datos.md"

TIPOS = {"TEXT": "texto", "INTEGER": "entero", "REAL": "decimal"}

TABLAS = {
    "fact_empresa": "Hechos. Una fila por empresa o establecimiento del registro mercantil.",
    "dim_municipio": "Dimensión. Un municipio de la jurisdicción de la Cámara de Comercio de Pasto.",
    "dim_sector": "Dimensión. Una clase de la clasificación CIIU Rev. 4 A.C. con su jerarquía hasta macro sector.",
    "dim_tiempo": "Dimensión. Un año de matrícula.",
}

DESCRIPCIONES = {
    # ---- fact_empresa ----
    ("fact_empresa", "id_empresa"): "Identificador técnico, asignado por el orden de la empresa en el archivo de origen. No es la matrícula mercantil (que se elimina por ser un identificador directo).",
    ("fact_empresa", "mun_codigo"): "Municipio del establecimiento (código DIVIPOLA de 5 dígitos). `00000` = sin dato.",
    ("fact_empresa", "ciiu_codigo"): "Actividad económica principal (CIIU-1), clase de 4 dígitos. `0000` = sin clasificar.",
    ("fact_empresa", "anio_matricula"): "Año en que se matriculó la empresa.",
    ("fact_empresa", "est_datos"): "Código de estado de la matrícula tal como viene en la fuente (1, 2, 4, 6, 7, 8 o `SIN DATO`). La fuente no trae diccionario oficial, por eso **no se interpreta** su significado.",
    ("fact_empresa", "fec_matricula"): "Fecha de la matrícula mercantil (AAAA-MM-DD).",
    ("fact_empresa", "fec_renovacion"): "Fecha de la renovación más reciente (AAAA-MM-DD).",
    ("fact_empresa", "ult_ano_ren"): "Último año en que la empresa renovó su matrícula.",
    ("fact_empresa", "antiguedad_anios"): "Años transcurridos entre la matrícula y la fecha de corte de la extracción (renovación más reciente del archivo), con un decimal.",
    ("fact_empresa", "n_actividades"): "Cantidad de actividades económicas registradas (1 a 4). Resume CIIU-1 a CIIU-4, que tenían entre 59 % y 89 % de nulos.",
    ("fact_empresa", "ciiu_estado"): "Resultado del cruce con el catálogo CIIU: `ok`, `codigo_no_encontrado` (el registro trae un código que el catálogo 2020 no tiene) o `sin_ciiu`.",
    ("fact_empresa", "barrio_codigo"): "Código del barrio (5 dígitos). **Solo Pasto trae barrio**: en los otros 41 municipios es nulo por diseño de la fuente, no por datos faltantes. En Pasto, el 91,8 % de las empresas lo informa.",
    ("fact_empresa", "barrio_nombre"): "Nombre del barrio, en mayúsculas y sin espacios dobles. Nulo fuera de Pasto (ver `barrio_codigo`).",
    ("fact_empresa", "actividad"): "Descripción de la actividad en texto libre, normalizada. Se eliminan teléfonos y correos si aparecen escritos.",
    ("fact_empresa", "vlr_establecimiento"): "Valor del establecimiento declarado, en pesos colombianos (COP), sin modificar.",
    ("fact_empresa", "vlr_no_reportado"): "1 si el valor es cero o nulo (se trata como dato no reportado, no como un valor real); 0 en caso contrario.",
    ("fact_empresa", "vlr_winsorizado"): "Valor recortado a los percentiles 1 y 99 de los valores reportados. Nulo si no se reportó. Aun así es muy asimétrico: para resumir, **usar la mediana** y no el promedio.",
    ("fact_empresa", "vlr_outlier"): "1 si el valor reportado está fuera del rango P1-P99; 0 en caso contrario.",
    # ---- dim_municipio ----
    ("dim_municipio", "mun_codigo"): "Código DIVIPOLA de 5 dígitos. `00000` = sin dato.",
    ("dim_municipio", "mun_nombre"): "Nombre del municipio, en mayúsculas.",
    # ---- dim_sector ----
    ("dim_sector", "ciiu_codigo"): "Código CIIU de la clase (4 dígitos). `0000` = sin clasificar.",
    ("dim_sector", "clase_nombre"): "Nombre de la clase. `SIN CLASIFICAR` si el código no está en el catálogo.",
    ("dim_sector", "grupo_codigo"): "Código del grupo (3 dígitos).",
    ("dim_sector", "grupo_nombre"): "Nombre del grupo.",
    ("dim_sector", "division_codigo"): "Código de la división (2 dígitos).",
    ("dim_sector", "division_nombre"): "Nombre de la división.",
    ("dim_sector", "seccion_letra"): "Letra de la sección CIIU (A a U). `-` = sin clasificar.",
    ("dim_sector", "seccion_nombre"): "Nombre de la sección.",
    ("dim_sector", "macro_sector"): "Primario (secciones A-B), Secundario (C-F) o Terciario (G-U); `SIN CLASIFICAR` si no hay CIIU.",
    ("dim_sector", "en_catalogo"): "1 si la clase existe en el catálogo CIIU 2020 del DANE; 0 si el registro la trae pero el catálogo no (o es el miembro `sin clasificar`).",
    # ---- dim_tiempo ----
    ("dim_tiempo", "anio"): "Año calendario. La dimensión no tiene huecos entre el primer y el último año.",
    ("dim_tiempo", "decada"): "Década del año (por ejemplo `2010s`).",
    ("dim_tiempo", "anio_parcial"): "1 si el año tiene matrículas incompletas por la fecha de corte de la extracción; 0 en caso contrario. No leer un año parcial como una caída real.",
}


def _estructura(con: sqlite3.Connection) -> dict:
    """{tabla: [(columna, tipo, es_pk, referencia_fk)]} leído de la base real."""
    estructura = {}
    for tabla in TABLAS:
        fks = {f[3]: f"{f[2]}.{f[4]}" for f in con.execute(f"PRAGMA foreign_key_list({tabla})")}
        columnas = [(c[1], c[2], bool(c[5]), fks.get(c[1]))
                    for c in con.execute(f"PRAGMA table_info({tabla})")]
        estructura[tabla] = columnas
    return estructura


def _verificar_cobertura(estructura: dict) -> None:
    reales = {(t, c[0]) for t, cols in estructura.items() for c in cols}
    sin_descripcion = sorted(reales - DESCRIPCIONES.keys())
    sobrantes = sorted(DESCRIPCIONES.keys() - reales)
    if sin_descripcion or sobrantes:
        raise SystemExit(f"Diccionario desactualizado.\n  Columnas sin descripción: {sin_descripcion}\n"
                         f"  Descripciones de columnas inexistentes: {sobrantes}")


def _ejemplos(con: sqlite3.Connection) -> dict:
    """Una empresa completa y las filas de dimensión que ella referencia."""
    con.row_factory = sqlite3.Row
    hecho = con.execute(
        """SELECT * FROM fact_empresa
           WHERE barrio_nombre IS NOT NULL AND actividad IS NOT NULL
             AND vlr_winsorizado IS NOT NULL AND anio_matricula IS NOT NULL
             AND ciiu_estado = 'ok'
           ORDER BY id_empresa LIMIT 1""").fetchone()
    if hecho is None:
        raise SystemExit("No hay una empresa completa para usar como ejemplo. Ejecute antes el pipeline.")
    return {
        "fact_empresa": dict(hecho),
        "dim_municipio": dict(con.execute("SELECT * FROM dim_municipio WHERE mun_codigo = ?", (hecho["mun_codigo"],)).fetchone()),
        "dim_sector": dict(con.execute("SELECT * FROM dim_sector WHERE ciiu_codigo = ?", (hecho["ciiu_codigo"],)).fetchone()),
        "dim_tiempo": dict(con.execute("SELECT * FROM dim_tiempo WHERE anio = ?", (hecho["anio_matricula"],)).fetchone()),
    }


def _formato(valor) -> str:
    if valor is None:
        return "(nulo)"
    texto = str(valor)
    texto = texto if len(texto) <= 42 else texto[:39] + "..."
    return f"`{texto.replace('|', '/')}`"


def generar() -> str:
    if not config.BASE_DATOS.exists():
        raise SystemExit(f"No existe {config.BASE_DATOS.name}. Ejecute primero: python pipeline.py")
    con = sqlite3.connect(config.BASE_DATOS)
    estructura = _estructura(con)
    _verificar_cobertura(estructura)
    ejemplos = _ejemplos(con)
    con.close()

    lineas = ["# Diccionario de datos", "",
              "Generado automáticamente por `tools/generar_diccionario.py` a partir de la base "
              "`data/processed/empresas.db`. Los ejemplos corresponden a una misma empresa de la muestra.", "",
              "![Modelo de datos](modelo_datos.png)", ""]
    for tabla, descripcion in TABLAS.items():
        lineas += [f"## `{tabla}`", "", descripcion, "",
                   "| Columna | Tipo | Descripción | Ejemplo |", "|---|---|---|---|"]
        for nombre, tipo, es_pk, fk in estructura[tabla]:
            etiqueta = TIPOS.get(tipo, tipo.lower())
            if es_pk:
                etiqueta += " · PK"
            if fk:
                etiqueta += f" · FK → {fk}"
            lineas.append(f"| `{nombre}` | {etiqueta} | {DESCRIPCIONES[(tabla, nombre)]} | {_formato(ejemplos[tabla][nombre])} |")
        lineas.append("")
    lineas += ["## Vista `v_empresas`", "",
               "Une `fact_empresa` con sus tres dimensiones (agrega `mun_nombre`, `clase_nombre`, `grupo_nombre`, "
               "`division_nombre`, `seccion_letra`, `seccion_nombre`, `macro_sector`, `decada` y `anio_parcial`). Es la que consume el dashboard.", ""]
    return "\n".join(lineas)


def main() -> None:
    texto = generar()
    config.DOCS.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(texto, encoding="utf-8")
    n = sum(1 for linea in texto.splitlines() if linea.startswith("| `"))
    print(f"Diccionario generado: {SALIDA} ({n} columnas documentadas)")


if __name__ == "__main__":
    main()
