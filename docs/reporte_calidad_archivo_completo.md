# Reporte de calidad de datos

- **Fuente:** `PASTO.xlsx` (Archivo completo, 19.273 registros)
- **Generado:** 2026-10-10T18:16:27

## Volumen e integridad

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Número de registros | 19.273 | 19.273 | No se descarta ningún registro |
| Registros duplicados (por matrícula) | 0 | 0 |  |
| Valores nulos en columnas clave (municipio, CIIU, fecha de matrícula) | 3 | 0 | Los nulos pasan a miembros explícitos 'SIN DATO' / 'SIN CLASIFICAR'; ningún registro se descarta |
| Número de columnas | 25 | 28 | Se retiran datos personales y se derivan variables |

## Privacidad

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Columnas con datos personales | 13 | 0 | Matrícula, razón social, direcciones, propietario y contacto |
| Teléfonos o correos escritos en texto libre | 1 | 0 | Se eliminan de ACTIVIDAD y BARRIO; si queda vacío, el valor pasa a nulo |

## Fechas

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Fechas de matrícula no interpretables | 0 | 0 | AAAAMMDD -> fecha |
| Antigüedad negativa (matrícula posterior al corte) | - | 0 | Fecha de corte: 2019-04-25 |
| Registros del año de corte (matrícula parcial) | - | 1.594 | Marcados con anio_parcial; no son una caída real |

## Municipio, barrio y clasificación CIIU

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Municipio nulo | 1 | 0 | Reemplazado por 'SIN DATO' (código 00000) |
| Registros sin CIIU principal | 2 | 2 | Se conservan como 'SIN CLASIFICAR' |
| Códigos CIIU sin coincidencia en el catálogo | - | 65 | Códigos: 6514, 7110, 8890; se conservan (left join) |
| Registros perdidos en el join con CIIU | - | 0 | Cobertura del catálogo: 99,65 % |
| Letra CIIU del registro distinta de la sección del catálogo | - | 0 | Coherencia entre fuentes |
| Barrios con formato 'código - nombre' separado | 12.211 | 12.211 | El 100 % de los barrios informados sigue el patrón |
| Municipios con barrio informado | - | 1 | Solo Pasto trae barrio: en los demás es nulo por diseño de la fuente, no por falta de datos |

## Valor del establecimiento

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Valores del establecimiento en cero | 285 | 0 | Marcados vlr_no_reportado; no se tratan como valor real |
| Valores del establecimiento negativos | 0 | 0 | Rango válido: mayor que cero; los no válidos se marcan como no reportado |
| Valores reportados menores a $1.000 | 19 | 0 | Posibles errores de digitación (p. ej. $0,1 o $1); la winsorización los lleva al P1 |
| Valor mínimo del establecimiento (COP) | 0,1 | 500.000 | Winsorización inferior en P1 = $500.000 |
| Valor máximo del establecimiento (COP) | 666.121.541.996 | 5.005.741.431 | Winsorización superior en P99 = $5.005.741.431 |
| Registros marcados como outlier de valor | - | 346 | Fuera del rango P1-P99 |

## Texto

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| ACTIVIDAD con espacios dobles | 6.381 | 0 |  |
| BARRIO con espacios dobles | 3 | 0 |  |

## Carga a la base (Load)

| Verificación | Antes | Después | Nota |
|---|---|---|---|
| Registros: CSV procesado -> fact_empresa | 19.273 | 19.273 | Sin pérdida entre Transform y Load |
| Claves foráneas huérfanas | - | 0 | PRAGMA foreign_key_check |
| Integridad de la base | - | ok | PRAGMA integrity_check |
| Clases del catálogo en dim_sector | 499 | 499 | dim_sector total: 503 (incluye códigos ausentes del catálogo) |
| Conteos por macro sector: CSV = base | - | coinciden | Primario: 180, SIN CLASIFICAR: 2, Secundario: 2057, Terciario: 17034 |
