# Diccionario de datos

Generado automáticamente por `tools/generar_diccionario.py` a partir de la base `data/processed/empresas.db`. Los ejemplos corresponden a una misma empresa de la muestra.

![Modelo de datos](modelo_datos.png)

## `fact_empresa`

Hechos. Una fila por empresa o establecimiento del registro mercantil.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `id_empresa` | entero · PK | Identificador técnico, asignado por el orden de la empresa en el archivo de origen. No es la matrícula mercantil (que se elimina por ser un identificador directo). | `5` |
| `mun_codigo` | texto · FK → dim_municipio.mun_codigo | Municipio del establecimiento (código DIVIPOLA de 5 dígitos). `00000` = sin dato. | `52001` |
| `ciiu_codigo` | texto · FK → dim_sector.ciiu_codigo | Actividad económica principal (CIIU-1), clase de 4 dígitos. `0000` = sin clasificar. | `5611` |
| `anio_matricula` | entero · FK → dim_tiempo.anio | Año en que se matriculó la empresa. | `2018` |
| `est_datos` | texto | Código de estado de la matrícula tal como viene en la fuente (1, 2, 4, 6, 7, 8 o `SIN DATO`). La fuente no trae diccionario oficial, por eso **no se interpreta** su significado. | `6` |
| `fec_matricula` | texto | Fecha de la matrícula mercantil (AAAA-MM-DD). | `2018-01-09` |
| `fec_renovacion` | texto | Fecha de la renovación más reciente (AAAA-MM-DD). | `2019-01-14` |
| `ult_ano_ren` | entero | Último año en que la empresa renovó su matrícula. | `2019` |
| `antiguedad_anios` | decimal | Años transcurridos entre la matrícula y la fecha de corte de la extracción (renovación más reciente del archivo), con un decimal. | `1.3` |
| `n_actividades` | entero | Cantidad de actividades económicas registradas (1 a 4). Resume CIIU-1 a CIIU-4, que tenían entre 59 % y 89 % de nulos. | `4` |
| `ciiu_estado` | texto | Resultado del cruce con el catálogo CIIU: `ok`, `codigo_no_encontrado` (el registro trae un código que el catálogo 2020 no tiene) o `sin_ciiu`. | `ok` |
| `barrio_codigo` | texto | Código del barrio (5 dígitos). **Solo Pasto trae barrio**: en los otros 41 municipios es nulo por diseño de la fuente, no por datos faltantes. En Pasto, el 91,8 % de las empresas lo informa. | `600.0` |
| `barrio_nombre` | texto | Nombre del barrio, en mayúsculas y sin espacios dobles. Nulo fuera de Pasto (ver `barrio_codigo`). | `LAS AMERICAS` |
| `actividad` | texto | Descripción de la actividad en texto libre, normalizada. Se eliminan teléfonos y correos si aparecen escritos. | `EXPENDIO A LA MESA DE COMIDAS PREPARADAS` |
| `vlr_establecimiento` | decimal | Valor del establecimiento declarado, en pesos colombianos (COP), sin modificar. | `10000000.0` |
| `vlr_no_reportado` | entero | 1 si el valor es cero o nulo (se trata como dato no reportado, no como un valor real); 0 en caso contrario. | `0` |
| `vlr_winsorizado` | decimal | Valor recortado a los percentiles 1 y 99 de los valores reportados. Nulo si no se reportó. Aun así es muy asimétrico: para resumir, **usar la mediana** y no el promedio. | `10000000.0` |
| `vlr_outlier` | entero | 1 si el valor reportado está fuera del rango P1-P99; 0 en caso contrario. | `0` |

## `dim_municipio`

Dimensión. Un municipio de la jurisdicción de la Cámara de Comercio de Pasto.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `mun_codigo` | texto · PK | Código DIVIPOLA de 5 dígitos. `00000` = sin dato. | `52001` |
| `mun_nombre` | texto | Nombre del municipio, en mayúsculas. | `PASTO` |

## `dim_sector`

Dimensión. Una clase de la clasificación CIIU Rev. 4 A.C. con su jerarquía hasta macro sector.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `ciiu_codigo` | texto · PK | Código CIIU de la clase (4 dígitos). `0000` = sin clasificar. | `5611` |
| `clase_nombre` | texto | Nombre de la clase. `SIN CLASIFICAR` si el código no está en el catálogo. | `Expendio a la mesa de comidas preparadas` |
| `grupo_codigo` | texto | Código del grupo (3 dígitos). | `561` |
| `grupo_nombre` | texto | Nombre del grupo. | `Actividades de restaurantes, cafeterías...` |
| `division_codigo` | texto | Código de la división (2 dígitos). | `56` |
| `division_nombre` | texto | Nombre de la división. | `Actividades de servicios de comidas y b...` |
| `seccion_letra` | texto | Letra de la sección CIIU (A a U). `-` = sin clasificar. | `I` |
| `seccion_nombre` | texto | Nombre de la sección. | `ALOJAMIENTO Y SERVICIOS DE COMIDA` |
| `macro_sector` | texto | Primario (secciones A-B), Secundario (C-F) o Terciario (G-U); `SIN CLASIFICAR` si no hay CIIU. | `Terciario` |
| `en_catalogo` | entero | 1 si la clase existe en el catálogo CIIU 2020 del DANE; 0 si el registro la trae pero el catálogo no (o es el miembro `sin clasificar`). | `1` |

## `dim_tiempo`

Dimensión. Un año de matrícula.

| Columna | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `anio` | entero · PK | Año calendario. La dimensión no tiene huecos entre el primer y el último año. | `2018` |
| `decada` | texto | Década del año (por ejemplo `2010s`). | `2010s` |
| `anio_parcial` | entero | 1 si el año tiene matrículas incompletas por la fecha de corte de la extracción; 0 en caso contrario. No leer un año parcial como una caída real. | `0` |

## Vista `v_empresas`

Une `fact_empresa` con sus tres dimensiones (agrega `mun_nombre`, `clase_nombre`, `grupo_nombre`, `division_nombre`, `seccion_letra`, `seccion_nombre`, `macro_sector`, `decada` y `anio_parcial`). Es la que consume el dashboard.
