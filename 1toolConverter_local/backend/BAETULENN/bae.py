import sys
import pandas as pd
import re

# Diccionario de variantes y sinónimos de los headers
HEADER_VARIANTS = {
    "address": ["address", "adress", "addr"],
    "content": ["content", "contents", "value", "val", "default value", "defalut value", "defaultvalue"],
    "step": ["step", "paso", "etapa"],
    "scope": ["scope", "scop", "alcance"],
    "state": ["state", "status", "condition"],
    "unit": ["unit", "units", "unidad", "u"],
}

# Lista con todas las variantes
ALL_VARIANTS = [v for variants in HEADER_VARIANTS.values() for v in variants]


def normalize(text):
    """Convierte texto a forma normalizada sin espacios ni mayúsculas."""
    return re.sub(r"\s+", "", str(text).strip().lower())


def fila_parece_encabezado(fila):
    """
    Devuelve True si una fila contiene al menos 4 posibles encabezados conocidos.
    """
    fila_norm = [normalize(x) for x in fila if pd.notna(x) and str(x).strip() != ""]
    coincidencias = 0
    for cell in fila_norm:
        # Si el contenido de la celda coincide con alguna variante conocida
        if any(v in cell for v in ALL_VARIANTS):
            coincidencias += 1
    return coincidencias >= 4  # puedes ajustar el umbral según tu caso


def header_canonico(nombre):
    """Asigna un header normalizado según su variante."""
    n = normalize(nombre)
    for canonico, variantes in HEADER_VARIANTS.items():
        if any(v in n for v in variantes):
            return canonico
    return nombre  # si no se reconoce, se deja igual


def extraer_tabla(df, fila_inicio):
    """Extrae una tabla desde una fila de encabezados hasta la siguiente fila vacía,
    limpia duplicados, mueve R/W, elimina filas vacías y ajusta columnas según LIBRARY_COLUMNS.
    """
    # === 1️⃣ LECTURA DE ENCABEZADOS ===
    headers_originales = df.iloc[fila_inicio].tolist()
    headers_norm = [header_canonico(str(h)) for h in headers_originales]

    # Eliminar encabezados duplicados
    vistos = set()
    headers_sin_duplicados = []
    indices_sin_duplicados = []
    for idx, h in enumerate(headers_norm):
        if h not in vistos:
            vistos.add(h)
            headers_sin_duplicados.append(h)
            indices_sin_duplicados.append(idx)

    # === 2️⃣ EXTRAER DATOS ===
    data = []
    for i in range(fila_inicio + 1, len(df)):
        if df.iloc[i].isnull().all():
            break
        fila = df.iloc[i].tolist()
        fila_filtrada = [fila[j] for j in indices_sin_duplicados if j < len(fila)]
        data.append(fila_filtrada)

    tabla = pd.DataFrame(data, columns=headers_sin_duplicados)

    # Mantener columnas relevantes
    columnas_validas = [c for c in tabla.columns if c in HEADER_VARIANTS.keys()]
    if columnas_validas:
        tabla = tabla[columnas_validas]
    else:
        return pd.DataFrame()

    # === 3️⃣ MOVER scope -> state (R/W) ===
    if "scope" in tabla.columns:
        if "state" not in tabla.columns:
            tabla["state"] = ""

        patron_rw = re.compile(r"^\s*(r/?w?)\s*$", re.IGNORECASE)
        for idx, val in tabla["scope"].items():
            if isinstance(val, str) and patron_rw.match(val.strip()):
                tabla.at[idx, "state"] = val.strip()
                tabla.at[idx, "scope"] = ""

    # === 4️⃣ FUSIONAR FILAS INCOMPLETAS (content vacío, pero scope/state/unit llenos) ===
    if "content" in tabla.columns:
        for i in range(1, len(tabla)):
            if (
                pd.isna(tabla.at[i, "content"]) or str(tabla.at[i, "content"]).strip() == ""
            ) and (
                str(tabla.at[i - 1, "content"]).strip() != ""
            ):
                # Fila actual tiene datos de scope/state/unit
                tiene_datos = any(
                    str(tabla.at[i, c]).strip() != ""
                    for c in ["scope", "state", "unit"]
                    if c in tabla.columns
                )
                if tiene_datos:
                    # Fusionar hacia arriba
                    for c in ["scope", "state", "unit"]:
                        if c in tabla.columns and str(tabla.at[i, c]).strip() != "":
                            tabla.at[i - 1, c] = tabla.at[i, c]
                    tabla.at[i, "content"] = None  # marcar fila fusionada

        # Eliminar filas que quedaron sin content tras fusión
        tabla = tabla[tabla["content"].notna()]
        tabla = tabla[tabla["content"].astype(str).str.strip() != ""]
        tabla.reset_index(drop=True, inplace=True)

    # === 5️⃣ RENOMBRAR COLUMNAS SEGÚN COLUMN_MAPPING_PDF ===
    COLUMN_MAPPING_PDF = {
        "address": "register",
        "content": "description", 
        "value" : "value",
        "default value" : "value",
        "defalut value" : "value"
    }
    tabla.rename(columns=COLUMN_MAPPING_PDF, inplace=True)

    # === 6️⃣ INTERPRETAR scope COMO RANGO minvalue / maxvalue ===
    if "scope" in tabla.columns:
        min_values, max_values = [], []
        for val in tabla["scope"]:
            if isinstance(val, str):
                match = re.match(r"^\s*(\d+)\s*[~-]\s*(\d+)\s*$", val)
                if match:
                    min_values.append(match.group(1))
                    max_values.append(match.group(2))
                else:
                    min_values.append("")
                    max_values.append("")
            else:
                min_values.append("")
                max_values.append("")
        tabla["minvalue"] = min_values
        tabla["maxvalue"] = max_values
    else:
        tabla["minvalue"] = ""
        tabla["maxvalue"] = ""

    # === 7️⃣ DIVIDIR state EN read / write ===
    tabla["read"] = ""
    tabla["write"] = ""

    if "state" in tabla.columns:
        for idx, val in tabla["state"].items():
            if not isinstance(val, str):
                continue
            v = val.strip().lower()
            if v in ["r", "read"]:
                tabla.at[idx, "read"] = "R"
            elif v in ["w", "write"]:
                tabla.at[idx, "write"] = "W"
            elif v in ["r/w", "rw", "wr"]:
                tabla.at[idx, "read"] = "R"
                tabla.at[idx, "write"] = "W"

    # === 8️⃣ AGREGAR COLUMNAS FALTANTES SEGÚN LIBRARY_COLUMNS ===
    LIBRARY_COLUMNS = [
        "id", "register", "name", "description", "system_category", "category", "view",
        "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
        "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
        "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
        "current_value", "current_error_status", "notes"
    ]
    for col in LIBRARY_COLUMNS:
        if col not in tabla.columns:
            tabla[col] = ""

    tabla = tabla[LIBRARY_COLUMNS]
    return tabla



def buscar_y_concatenar_tablas(excel_path):
    xls = pd.ExcelFile(excel_path)
    todas_las_tablas = []

    for hoja in xls.sheet_names:
        print(f"📄 Analizando hoja: {hoja}")
        df = pd.read_excel(excel_path, sheet_name=hoja, header=None)

        for i in range(len(df)):
            fila = df.iloc[i].tolist()
            if fila_parece_encabezado(fila):
                print(f"   🔹 Posible encabezado en fila {i+1}: {[str(x) for x in fila if pd.notna(x)]}")
                tabla = extraer_tabla(df, i)
                if not tabla.empty:
                    tabla["__origen__"] = f"{hoja} (fila {i+1})"
                    todas_las_tablas.append(tabla)

    if not todas_las_tablas:
        print("⚠️ No se detectaron tablas con encabezados similares a los esperados.")
        sys.exit(1)

    concatenado = pd.concat(todas_las_tablas, ignore_index=True)
    return concatenado


def process_excel_bae(excel_path):
    resultado = buscar_y_concatenar_tablas(excel_path)
    output = "resultado_concatenado.xlsx"
    resultado.to_excel(output, index=False)
    print(f"\n✅ Tablas concatenadas guardadas en '{output}'")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python bae.py <archivo_excel.xlsx>")
        sys.exit(1)
    process_excel_bae(sys.argv[1])
