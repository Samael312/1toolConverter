import sys
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from openpyxl import Workbook
import logging
import re
import numpy as np
from openpyxl import load_workbook
from io import BytesIO

# ====================================================
# Configuración de logging
# ====================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ====================================================
# Constantes
# ====================================================
LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

ENCABEZADOS_EQUIVALENTES = {
    "GENERAL RULES": ["GENERAL RULES", "GENERAL RULES:" ],
    "COMUNICATION INFO": ["COMUNICATION INFO", "COMMUNICATION INFO"],
    "DEVICE ID": ["DEVICE ID"],
    "ANALOG INPUT": ["ANALOG INPUT", "ANALOG"],
    "SET POINT": ["SET POINT", "SETPOINT", "SP"],
    "Device Status": ["DEVICE STATUS", "STATUS", "Device Status ", "Device Status"],
    "DIGITAL INPUT": ["DIGITAL INPUT", "DI"],
    "DIGITAL OUTPUT": ["DIGITAL OUTPUT", "DO"],
    "DIGITAL OUTPUT/INPUT": ["DIGITAL OUTPUT/INPUT", "DIGITAL I/O", "DIGITAL IN/OUT", "DIGITAL IO"],
    "CLOCK": ["CLOCK", "TIME"],
    "ALARMS": ["ALARM", "ALARMS"],
    "SERIAL OUTPUT": ["SERIAL OUTPUT", "SERIAL"],
    "COMMANDS": ["COMMANDS", "COMMAND"]
}

# ====================================================
# Mapeo de columnas (equivalentes)
# ====================================================
COLUMNAS_VALIDAS1 = {
    "Name": ["Name", "NAME", "Nombre", "name"],
    "Unit": ["Unit", "UNIT", "unit", "unidades"],
    "Read Register": ["Read Register", "Reading Registers", "Read Addr", "Reg Read", "Reading Registers N"],
    "Num. Elements Read": ["Num. Elements Read", "Num.Elements Read", "Num. of Elements to Read", "Number of Read Elements", "um. of Elements to Rea"],
    "Write Register": ["Write Register", "Writing Registers", "Write Addr", "Reg Write", "d Writing Registers"],
    "Num. Elements Write": ["Num. Elements Write", "Num.Elements Write", "Num. of Elements to Write", "Number of Write Elements"],
    "Gain": ["Gain", "Factor", "G"],
    "Offset": ["Offset", "Offs", "Displacement"],
    "Byte ORDER": ["Byte ORDER", "Byte Order", "ByteOrder"],
    "Format": ["Format", "Formato", "Data Type"],
    "R / W": ["R / W", "RW", "Access", "Acceso", "R/W"],
    "Register": ["Register", "Reg", "Dir"],
    "Value": ["Value", "Valor", "Default Value", "Initial Value"],
    "Modbus Command": ["Modbus Command", "Command", "CMD"],
}

COLUMNAS_VALIDAS2 = {
    "R/W": ["R / W", "RW", "Access", "Acceso", "R/W"],
    "REGISTER[hex]": ["Dec", "Decimals", "Resolution", "REGISTER[hex]", "HEX"],
    "DEC": ["DEC", "DECIMAL"],
    "VAR NAME": ["VAR NAME", "VAR"],
    "DESCRIPTION": ["DESCRIPTION", "description"],
    "GROUP": ["GROUP", "group"],
    "LENGHT": ["LENGHT", "LENGTH", "lenght", "length"],  # ← ampliado
    "TYPE": ["TYPE", "type"]
}


COLUMN_MAPPING1 = {
    "Name": "name",
    "Unit": "unit",
    "Read Register": "register",
    "Write Register": "register",
    "Register": "register",
    "Offset": "offset",
    "Format": "length",
    "Value": "value",
}

COLUMN_MAPPING2 = {
    "VAR NAME": "name",
    "DESCRIPTION": "description",
    "GROUP": "category",
    "REGISTER[hex]": "register",
    "LENGHT": "length",   
    "TYPE": "type"
}


DEFAULT_VALUES = {
    "system_category": "DEFAULT",
    "description": "",
    "view": "simple",
    "unit": "",
    "read": 0,
    "write": 0,
    "minvalue": 0,
    "maxvalue": 0,
    "sampling": 0,
    "addition": 0,
    "mask": 0,
    "general_icon": "",
    "alarm": '{"severity":"none"}',
    "metadata": "[]",
    "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
    "tags": "[]",
    "type": "modbus",
    "parameter_write_byte_position": 0,
    "mqtt": "",
    "json": "",
    "current_value": 0,
    "current_error_status": 0,
    "notes": ""
}

# ====================================================
# Funciones auxiliares
# ====================================================
def limpiar_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.reset_index(drop=True)

def eliminar_filas_vacias_completas(df):
    if df is None or df.empty:
        return df
    return df.dropna(how="all")

def deduplicar_columnas(cols):
    vistos = {}
    nuevas = []
    for c in cols:
        if c in vistos:
            vistos[c] += 1
            nuevas.append(f"{c}.{vistos[c]}")
        else:
            vistos[c] = 0
            nuevas.append(c)
    return nuevas

def hex_to_dec(val):
    if pd.isna(val):
        return ""
    val = str(val).strip().replace(" ", "")
    try:
        if val.lower().startswith("0x"):
            return int(val, 16)
        elif all(c in "0123456789abcdefABCDEF" for c in val) and val != "":
            return int(val, 16)
        elif re.match(r'^\d+$', val):
            return int(val)
        else:
            # keep as-is (may be descriptive)
            return val
    except Exception:
        return val

# ====================================================
# Reglas y transformaciones defensivas
# ====================================================
def _ensure_columns(df: pd.DataFrame, cols: list, default_vals: dict = None) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame()
    for col in cols:
        if col not in df.columns:
            if default_vals and col in default_vals:
                df[col] = default_vals[col]
            else:
                df[col] = ""
    return df

def normalize_unit(unit: str) -> str:
    """Normaliza unidades conocidas a un formato estándar"""
    unit = str(unit).strip().lower()
    if unit in ["º", "°"]:
        return "°C"
    if unit == "m":
        return "min"
    if unit in ["sec", "s", "seg"]:
        return "s"
    if unit == "%":
        return "%"
    if unit in ["h"]:
        return "h"
    if unit in ["°c", "c"]:
        return "°C"
    return unit

def extract_min_max_from_type_safe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae minvalue, maxvalue y unidad de la columna 'Type' de manera tolerante.
    No elimina filas aunque no tengan rango.
    """
    # Regex más flexible para rango
    rango_regex = re.compile(
        r"([-+]?\d+(?:[\.,]\d+)?)\s*([°ºCF%rpmsechmsVАОΩohmbarkPa]*)\s*(?:to|-)\s*([-+]?\d+(?:[\.,]\d+)?)\s*([°ºCF%rpmsechmsVАОΩohmbarkPa]*)",
        re.IGNORECASE
    )

    min_vals, max_vals, units = [], [], []

    for val in df["type"].astype(str):
        val = val.strip()
        if not val:
            min_vals.append("")
            max_vals.append("")
            units.append("")
            continue

        match = rango_regex.search(val)
        if match:
            min_num, min_unit, max_num, max_unit = match.groups()
            min_vals.append(min_num.replace(",", "."))
            max_vals.append(max_num.replace(",", "."))
            unit_final = normalize_unit(max_unit) or normalize_unit(min_unit)
            units.append(unit_final)
        else:
            min_vals.append("")
            max_vals.append("")
            units.append("")

    df["minvalue"] = min_vals
    df["maxvalue"] = max_vals
    df["unit"] = units

    # Limpiar la columna Type
    df["type"] = ""

    return df

def map_data_type(df, col="length"):
    mapping = {
        "1bit": "1bit",
        "2bit": "2bit",
        "4bit": "4bit",
        "byte": "u8",
        "word": "s16",
        "16 bit Signed": "s16",
        "16 bit Unsigned": "16bit",
        "lock": "1bit"  
    }
    df[col] = df[col].astype(str).str.lower().map(mapping).fillna("16bit")
    return df

def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    # defensiva: si no existe 'name' o 'system_category', crearlas
    df = df.copy()
    if 'name' not in df.columns:
        df['name'] = ""
    if 'system_category' not in df.columns:
        df['system_category'] = ""

    # normalizar
    df['name'] = df['name'].astype(str).str.strip()
    df['system_category'] = df['system_category'].astype(str).str.strip().str.lower()

    mapping = {
        'set point': 'SET_POINT',
        'analog input': 'ANALOG_INPUT',
        'alarms': 'ALARM',
        'commands': 'COMMAND',
        'digital input': 'DIGITAL_INPUT',
        'digital output': 'DIGITAL_OUTPUT',
        'serial output': 'SERIAL_OUTPUT',
        'device status': 'STATUS',
        'sistema': 'SYSTEM',
        'device id': 'SYSTEM',
        'general rules': 'CONFIG_PARAMETER'
    }

    df['system_category'] = df['system_category'].replace(mapping)
    df['system_category'] = df['system_category'].str.upper()

    # eliminar filas con categorías inválidas
    df = df[~df['system_category'].isin(['NONE', '', 'NAN', None])].copy()

    # tags based on system_category
    system_type = df['system_category'].astype(str).str.upper().str.strip()
    df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")

    # marcar por 'name' si contiene output/input
    mask_do = df['name'].str.contains(r'output', case=False, na=False)
    df.loc[mask_do, 'system_category'] = 'DIGITAL_OUTPUT'
    logger.info(f"{mask_do.sum()} filas marcadas como DIGITAL_OUTPUT")

    mask_di = df['name'].str.contains(r'input', case=False, na=False)
    df.loc[mask_di, 'system_category'] = 'DIGITAL_INPUT'
    logger.info(f"{mask_di.sum()} filas marcadas como DIGITAL_INPUT")

    return df

def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    # defensiva: asegurar columnas
    df = _ensure_columns(df, ['read', 'write'])
    df.columns = df.columns.astype(str).str.strip()
    only_read = pd.Series(False, index=df.index)
    rw = pd.Series(False, index=df.index)

    # Unificar la columna de acceso si existe
    if 'R / W' in df.columns:
        df.rename(columns={'R / W': 'R_W'}, inplace=True)
    elif 'R/W' in df.columns:
        df.rename(columns={'R/W': 'R_W'}, inplace=True)

    if 'R_W' in df.columns:
        access = df['R_W'].astype(str).str.upper().str.strip()

        only_read = access == 'R'
        only_write = access == 'W'
        rw = access == 'R/W'

        df.loc[only_read, 'read'] = 4
        df.loc[only_write, 'write'] = 6
        df.loc[rw, 'read'] = 3
        df.loc[rw, 'write'] = 6

        df.drop(columns=['R_W'], inplace=True, errors='ignore')

    # Ajustes por system_category
    if 'system_category' in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()

        df.loc[only_read & system_type.isin(['ANALOG_INPUT', 'ANALOG_OUTPUT', 'SYSTEM']), 'read'] = 3
        df.loc[only_read & system_type.isin(['ALARM']), 'read'] = 1
        df.loc[only_read & system_type.isin(['STATUS']), 'read'] = 1
        df.loc[only_read & system_type.isin(['COMMAND']), 'write'] = 5
        df.loc[only_read & system_type.isin(['SYSTEM']), 'read'] = 3

        mask = rw & system_type.isin(['SET_POINT'])
        if mask.any():
            df.loc[mask, 'read'] = 3
            df.loc[mask, 'write'] = 16

        mask = rw & system_type.isin(['CONFIG_PARAMETER'])
        if mask.any():
            df.loc[mask, 'read'] = 3
            df.loc[mask, 'write'] = 16

        mask = rw & system_type.isin(['DIGITAL_OUTPUT'])
        if mask.any():
            df.loc[mask, 'read'] = 1
            df.loc[mask, 'write'] = 0

        mask = rw & system_type.isin(['DIGITAL_INPUT'])
        if mask.any():
            df.loc[mask, 'read'] = 1

    # asegurar tipo int para read/write cuando correspondan
    for col in ['read', 'write']:
        try:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        except Exception:
            df[col] = df[col].apply(lambda x: int(x) if str(x).isdigit() else 0)

    return df

def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    # defensiva: si falta system_category, crearla
    if "system_category" not in df.columns:
        df["system_category"] = "DEFAULT"

    mapping = {
        "ALARM": 30,
        "SET_POINT": 300,
        "DEFAULT": 0,
        "COMMAND": 0,
        "STATUS": 60,
        "SYSTEM": 0,
        "CONFIG_PARAMETER": 0,
        "ANALOG_INPUT": 60,
        "ANALOG_OUTPUT": 60,
        "DIGITAL_INPUT": 60,
        "DIGITAL_OUTPUT": 60,
    }
    df["sampling"] = df["system_category"].map(mapping).fillna(0)
    return df

def _apply_view_rules(df: pd.DataFrame) -> pd.DataFrame:
    if "system_category" not in df.columns:
        df["system_category"] = "DEFAULT"
    view = {
        'ALARM': 'simple',
        'SET_POINT': "simple",
        'DEFAULT': "simple",
        'COMMAND': "simple",
        'DIGITAL_INPUT': "simple",
        'DIGITAL_OUTPUT': "simple",
        'ANALOG_INPUT': "simple",
        'ANALOG_OUTPUT': "simple",
        'SERIAL_OUTPUT': "simple",
        'STATUS': "basic",
        'CONFIG_PARAMETER': "simple",
        'SYSTEM': 'simple'
    }
    df['view'] = df['system_category'].map(view).fillna('simple')
    return df

def _determine_data_length(df: pd.DataFrame) -> pd.DataFrame:
    category_mapping = {
        'SET_POINT': '16bit',
        'ANALOG_INPUT': '16bit',
        'ALARM': '1bit',
        'COMMAND': '1bit',
        'DIGITAL_INPUT': '1bit',
        'STATUS': '1bit',
        'ANALOG_OUTPUT': '16bit',
        'DIGITAL_OUTPUT': '1bit',
        'SERIAL_OUTPUT': '16bit',
        'SYSTEM': '16bit'
    }

    if "length" not in df.columns:
        df["length"] = None
    if "system_category" in df.columns:
        df.loc[df["system_category"].isin(category_mapping.keys()),
               "length"] = df["system_category"].map(category_mapping)

    return df

def _apply_unit_rules(df: pd.DataFrame) -> pd.DataFrame:
    unit = {
        'par "CF"': "°C",
        'RPM': "rpm",
        'ºC': "°C",
        'C': "°C"
    }
    # map donde hay coincidencias, dejar el resto como está
    df['unit'] = df['unit'].map(unit).fillna(df['unit'].astype(str).fillna(''))
    return df

def clean_special_characters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia caracteres especiales de columnas de texto como 'description', 'name', y 'category'.
    Mantiene solo letras, números y signos comunes (. , ; : _ - / % °C).
    Elimina acentos, emojis y caracteres no imprimibles.
    """
    import re
    import unicodedata

    def limpiar_texto(texto):
        if not isinstance(texto, str):
            return ""
        texto = unicodedata.normalize("NFKD", texto)
        texto = texto.encode("ascii", "ignore").decode("ascii")  # quita tildes y acentos
        texto = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/%°C]", "", texto)  # permite solo caracteres válidos
        texto = re.sub(r"\s+", " ", texto).strip()  # limpia espacios extra
        return texto

    columnas_a_limpiar = ["description"]

    for col in columnas_a_limpiar:
        if col in df.columns:
            df[col] = df[col].astype(str).apply(limpiar_texto)

    return df

def clean_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia caracteres especiales, acentos y saltos de línea de las columnas de texto del DataFrame.
    Aplica la limpieza a columnas comunes: 'description', 'name', 'category', 'system_category', 'unit'.
    """
    import re
    import unicodedata

    def limpiar_texto(texto: str) -> str:
        if not isinstance(texto, str):
            return ""
        # Sustituir saltos de línea, retornos de carro y tabulaciones por un espacio
        texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # Normalizar (elimina tildes y acentos)
        texto = unicodedata.normalize("NFKD", texto)
        texto = texto.encode("ascii", "ignore").decode("ascii")
        # Eliminar caracteres no permitidos
        texto = re.sub(r"[^a-zA-Z0-9\s\.,;:_\-/%°C]", "", texto)
        # Reducir espacios múltiples y limpiar extremos
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    columnas_a_limpiar = ["description", "name"]

    for col in columnas_a_limpiar:
        if col in df.columns:
            df[col] = df[col].astype(str).apply(limpiar_texto)

    return df

def _apply_range_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica reglas automáticas a minvalue y maxvalue solo si ambos están vacíos.
    No sobrescribe valores existentes.
    """
    # Normaliza los tipos
    for col in ["minvalue", "maxvalue"]:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = df[col].replace(["", " ", None], np.nan)

    # --- 0️⃣ Validación general ---
    if "system_category" in df.columns:
        system_type = df["system_category"].astype(str).str.upper().str.strip()

        mask_digital = system_type.isin(["DIGITAL_OUTPUT","DIGITAL_INPUT","STATUS", "ALARM"])
        mask_empty = df["minvalue"].isna() & df["maxvalue"].isna()
        df.loc[mask_digital & mask_empty, ["minvalue", "maxvalue"]] = [0, 1]

         # --- 3️⃣ Detectar y marcar ANALOG_OUTPUT ---
        mask_analog_output = system_type.isin(["ANALOG_OUTPUT", "ANALOG_INPUT"])
        mask_empty = df["minvalue"].isna() & df["maxvalue"].isna()
        df.loc[mask_analog_output & mask_empty, ["minvalue", "maxvalue"]] = [-270, 270]

    # --- 4️⃣ Detectar y marcar CONFIG_PARAMETER ---
    mask_pa = df["system_category"].astype(str).str.upper().eq("CONFIG_PARAMETER")
    mask_empty = df["minvalue"].isna() & df["maxvalue"].isna()
    df.loc[mask_pa & mask_empty, ["minvalue", "maxvalue"]] = [0, 100]

    # --- 5️⃣ Detectar y marcar set_point ---
    mask_sp = df["system_category"].astype(str).str.upper().eq("SET_POINT")
    mask_empty = df["minvalue"].isna() & df["maxvalue"].isna()
    df.loc[(mask_sp | mask_empty) & mask_empty, ["minvalue", "maxvalue"]] = [0, 9999]

    # --- 6 Detectar y marcar COMMAND ---
    mask_co = df["system_category"].astype(str).str.upper().eq("COMMAND")
    mask_empty = df["minvalue"].isna() & df["maxvalue"].isna()
    df.loc[mask_co & mask_empty, ["minvalue", "maxvalue"]] = [0, 100]

    return df
# ====================================================
# Función principal (robusta)
# ====================================================
def process_dixell(pdf_content: bytes) -> pd.DataFrame:
    logger.info("Procesando archivo PDF (en memoria, usando bytes)...")

    try:
        pdf_io = BytesIO(pdf_content)
    except Exception as e:
        logger.exception(f"Error creando BytesIO: {e}")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

    descripcion = []
    zonas_colores = []
    tablas_detectadas = 0
    hojas = {}
    ultima_hoja_valida = None

    # --- Detectar zonas coloreadas ---
    try:
        with fitz.open(stream=pdf_io, filetype="pdf") as pdf:
            for num, pagina in enumerate(pdf, start=1):
                # get_drawings puede fallar si la página no tiene dibujos
                try:
                    for d in pagina.get_drawings():
                        color = d.get("fill")
                        if color and any(c > 0 for c in color):
                            zonas_colores.append((num, color))
                except Exception:
                    continue
        descripcion.append(f"🔹 Zonas con color detectadas: {len(zonas_colores)}")
    except Exception as e:
        logger.warning(f"Imposible analizar dibujos con fitz: {e}")

    # --- Reiniciar el buffer para pdfplumber ---
    pdf_io.seek(0)

    # --- Detectar tablas con pdfplumber (más tolerante) ---
    try:
        with pdfplumber.open(pdf_io) as pdf:
            for num, pagina in enumerate(pdf.pages, start=1):
                try:
                    tablas = pagina.extract_tables()
                except Exception as e:
                    logger.warning(f"pdfplumber fallo en página {num}: {e}")
                    tablas = None

                if tablas:
                    tablas_detectadas += len(tablas)
                    descripcion.append(f"📄 Página {num}: {len(tablas)} tabla(s) detectada(s).")

                    for i, tabla in enumerate(tablas, start=1):
                        df = pd.DataFrame(tabla)
                        # construir encabezado textual para detectar secciones
                        encabezado = ", ".join([str(x).strip() for x in tabla[0] if x]) if len(tabla) > 0 else ""
                        encabezado_principal = None

                        for clave, alias_list in ENCABEZADOS_EQUIVALENTES.items():
                            if any(alias.strip().lower() == encabezado.strip().lower() for alias in alias_list):
                                encabezado_principal = clave
                                break

                        if encabezado_principal:
                            logger.info(f"🔹 Encabezado '{encabezado_principal}' detectado en página {num}, tabla {i}")
                            ultima_hoja_valida = encabezado_principal
                            hojas[encabezado_principal] = pd.concat(
                                [hojas.get(encabezado_principal, pd.DataFrame()), df],
                                ignore_index=True
                            )
                        else:
                            if ultima_hoja_valida:
                                hojas[ultima_hoja_valida] = pd.concat(
                                    [hojas[ultima_hoja_valida], df],
                                    ignore_index=True
                                )
                            else:
                                hojas.setdefault("SinClasificar", pd.DataFrame())
                                hojas["SinClasificar"] = pd.concat(
                                    [hojas["SinClasificar"], df],
                                    ignore_index=True
                                )
    except Exception as e:
        logger.exception(f"Error abriendo PDF con pdfplumber: {e}")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

    # --- Limpieza de datos ---
    hojas_limpiadas = {}

    # recorrer hojas detectadas y limpiar
    for nombre, df in hojas.items():
        df_limpio = limpiar_dataframe(df)
        df_limpio = eliminar_filas_vacias_completas(df_limpio)
        logger.info("\n==== df_final - df_limpio 1====")
        logger.info(df_limpio.head(10))

        # --- Buscar fila de encabezado válido ---
        fila_encabezado_idx = None
        for i, fila in df_limpio.iterrows():
            fila_str = [str(x).strip().lower() for x in fila]
            found = False
            for f in fila_str:
                if any(f in [a.lower() for a in alias_list] for alias_list in COLUMNAS_VALIDAS1.values()) \
                   or any(f in [a.lower() for a in alias_list] for alias_list in COLUMNAS_VALIDAS2.values()):
                    fila_encabezado_idx = i
                    found = True
                    break
            if found:
                break

        # --- Eliminar filas previas antes del encabezado ---
        if fila_encabezado_idx is not None:
            df_limpio = df_limpio.iloc[fila_encabezado_idx:].reset_index(drop=True)
            logger.info("\n==== df_final - df_limpio 2====")
            logger.info(df_limpio.head(10))

            # --- Verificar si la primera fila es 'meta' (HEX, DEC, etc.) ---
            if not df_limpio.empty:
                primera_fila = [str(x).strip().lower() for x in df_limpio.iloc[0].tolist()]
                palabras_meta = {"hex", "dec", "decimal", "direccion", "dir", ""}
                total = len([x for x in primera_fila if x != ""])
                coincidencias = sum(1 for x in primera_fila if x in palabras_meta)

                if total == 0 or coincidencias >= total * 0.2:
                    logger.info(f"Eliminando fila 'meta' en hoja '{nombre}' (parece ser encabezado falso tipo HEX)")
                    df_limpio = df_limpio.iloc[1:].reset_index(drop=True)
        else:
            logger.warning(f"No se encontró fila de encabezado válida en hoja '{nombre}'")

        hojas_limpiadas[nombre] = df_limpio

    # --- Concatenar todas las tablas válidas ---
        todas = []
        for nombre, df in hojas_limpiadas.items():
            if nombre != "SinClasificar" and not df.empty:
                df_copy = df.copy()
                df_copy.columns = df_copy.iloc[0]
                df_copy = df_copy[1:].reset_index(drop=True)

                # Mostrar columnas detectadas
                logger.info(f"Columnas detectadas: {list(df_copy.columns)}")
                logger.info(f"Primera fila (posible encabezado): {list(df_copy.iloc[0])}")
                for alias_list in COLUMNAS_VALIDAS1.values():
                    logger.info(f"Lista de alias: {list(alias_list)}")

                # Determinar qué mapping usar
                matches1 = sum(
                    any(str(col).strip().lower() == a.lower() for a in alias_list)
                    for col in df_copy.columns
                    for alias_list in COLUMNAS_VALIDAS1.values()
                )
                logger.info(f"Coincidencias con COLUMNAS_VALIDAS1: {matches1}")

                matches2 = sum(
                    any(str(col).strip().lower() == a.lower() for a in alias_list)
                    for col in df_copy.columns
                    for alias_list in COLUMNAS_VALIDAS2.values()
                )
                logger.info(f"Coincidencias con COLUMNAS_VALIDAS2: {matches2}")

                if matches1 >= matches2:
                    COLUMNAS_VALIDAS_USAR = COLUMNAS_VALIDAS1
                    COLUMN_MAPPING_USAR = COLUMN_MAPPING1
                else:
                    COLUMNAS_VALIDAS_USAR = COLUMNAS_VALIDAS2
                    COLUMN_MAPPING_USAR = COLUMN_MAPPING2

                logger.info("\n==== df_final - Se usara el ====")
                logger.info(COLUMN_MAPPING_USAR)
                logger.info("\n==== df_final - Se usara con las ====")
                logger.info(COLUMNAS_VALIDAS_USAR)

                # 🔹 Normalizar columnas
                columnas_nuevas = []
                for col in df_copy.columns:
                    col_limpio = str(col).strip()
                    encontrado = False
                    for canonico, alias_list in COLUMNAS_VALIDAS_USAR.items():
                        if col_limpio.lower() in [a.lower() for a in alias_list]:
                            columnas_nuevas.append(canonico)
                            encontrado = True
                            break
                    if not encontrado:
                        columnas_nuevas.append(col_limpio)
                df_copy.columns = columnas_nuevas

                # 🔹 Eliminar encabezados duplicados
                df_copy.columns = deduplicar_columnas(df_copy.columns)

                # 🔹 Asegurar todas las columnas válidas
                for col in COLUMNAS_VALIDAS_USAR.keys():
                    if col not in df_copy.columns:
                        df_copy[col] = ""

                # 🔹 Reordenar columnas
                df_copy = df_copy[list(COLUMNAS_VALIDAS_USAR.keys())]
                logger.info(f"🔍 COLUMN_MAPPING_USAR aplicado: {COLUMN_MAPPING_USAR}")
                df_copy.insert(0, "system_category", nombre)
                todas.append(df_copy)
                logger.info("\n==== df_COPY ====")
                logger.info(f"Columnas detectadas: {list(df_copy.columns)}")
                logger.info(df_copy.head(10).to_string())

        if todas:
            df_final = pd.concat(todas, ignore_index=True)
            logger.info("\n==== df_final - 1====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())


            # 🔹 Combinar "Read Register" y "Write Register" correctamente
            read_vals = df_final["Read Register"] if "Read Register" in df_final.columns else pd.Series([""] * len(df_final))
            write_vals = df_final["Write Register"] if "Write Register" in df_final.columns else pd.Series([""] * len(df_final))
            reg_vals = df_final["Register"] if "Register" in df_final.columns else pd.Series([""] * len(df_final))
            rh_vals = df_final["REGISTER[hex]"] if "REGISTER[hex]" in df_final.columns else pd.Series([""]* len(df_final))
            
            df_final["register"] = read_vals.fillna("").astype(str)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), write_vals)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), reg_vals)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), rh_vals)

            logger.info("\n==== df_final - 2====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

            # Copiar las demás columnas según el mapeo
            for col_origen, col_destino in COLUMN_MAPPING_USAR.items():
                if col_destino != "register" and col_origen in df_final.columns:
                    df_final[col_destino] = df_final[col_origen]

            # Añadir columnas faltantes
            for col in LIBRARY_COLUMNS:
                if col not in df_final.columns:
                    df_final[col] = DEFAULT_VALUES.get(col, "")
            logger.info("\n==== df_final - 3====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

            # 🔹 Eliminar filas sin 'register' ni 'name'
            df_final = df_final[
                ~((df_final["register"].fillna("").astype(str).str.strip() == "") &
                  (df_final["name"].fillna("").astype(str).str.strip() == ""))
            ].reset_index(drop=True)
            logger.info("\n==== df_final - 3.5====")
            logger.info("\n==== df_COPY 3.5 ====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

            # 🔹 Convertir 'register' y 'value' a decimal
            if "register" in df_final.columns:
                df_final["register"] = df_final["register"].apply(hex_to_dec).astype(str)

            if "value" in df_final.columns:
                df_final["value"] = df_final["value"].apply(hex_to_dec).astype(str)
                df_final["value"] = df_final["value"].apply(
                    lambda x: x if re.fullmatch(r"^-?\d+(\.\d+)?$", x.strip()) else "0"
                )
            else:
                logger.warning("⚠️ No se encontró la columna 'register' tras mapeo.")

            # Procesar reglas
            df_final = _process_specific_columns(df_final)
            df_final = _process_access_permissions(df_final)
            df_final = _apply_sampling_rules(df_final)
            df_final = _apply_view_rules(df_final)
            df_final = _determine_data_length(df_final)
            df_final = _apply_unit_rules(df_final)
            df_final = extract_min_max_from_type_safe(df_final)
            df_final = map_data_type(df_final)
  

            logger.info("\n==== df_final - 4====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

            df_final = df_final[LIBRARY_COLUMNS]
            logger.info("\n==== df_final - 5====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

            # 🔹 Limpiar filas vacías y categorías no deseadas
            df_final = df_final[df_final["register"].fillna("").astype(str).str.strip() != ""]
            df_final = df_final[~df_final["system_category"].astype(str).str.upper().str.contains("CLOCK", na=False)]
            df_final = df_final[~df_final["system_category"].astype(str).str.upper().str.contains("SERIAL_OUTPUT", na=False)]

            # Asignar 'id' como número de fila empezando desde 1
            df_final['id'] = range(1, len(df_final) + 1)
            # Rellenar description vacía con 'Add'
            df_final['description'] = df_final['description'].fillna("").astype(str)
            df_final['description'] = df_final['description'].apply(lambda x: "Add" if x.strip() == "" else x[:60])
            # Rellenar toda la columna 'type' con "modbus"
            df_final['type'] = "modbus"
            
            # Convertir 'offset' a float y rellenar vacíos con 0
            df_final['offset'] = pd.to_numeric(df_final['offset'], errors='coerce').fillna(0.0)

            # Hacer 'name' única agregando sufijo _# en caso de repetidos (sin diferenciar mayúsculas/minúsculas)
            name_counts = {}
            new_names = []

            for n in df_final['name']:
                n_str = str(n).strip()
                n_lower = n_str.lower()
                if n_lower in name_counts:
                    name_counts[n_lower] += 1
                    new_names.append(f"{n_str}_{name_counts[n_lower]}")
                else:
                    name_counts[n_lower] = 0
                    new_names.append(n_str)

            df_final['name'] = new_names

            df_final = clean_special_characters(df_final)
            df_final = clean_text_fields(df_final)
            df_final = _apply_range_rules(df_final)

            logger.info("\n==== df_final - 6====")
            logger.info(f"Columnas detectadas: {list(df_final.columns)}")
            logger.info(df_final.head(10).to_string())

    logger.info(f"✅ Total filas finales: {len(df_final)}")
    logger.info(f"==== DESCRIPCIÓN DEL PDF ====\n\n" + "\n".join(descripcion))

    return df_final

# ====================================================
# Función para procesar múltiples pdfs (interfaz)
# ====================================================
def process_multiple_pdfs(pdf_contents: list, salida_excel: str = "tablas_extraidas.xlsx") -> pd.DataFrame:
    """
    Procesa múltiples archivos PDF (dados como bytes) usando process_dixell()
    y concatena sus resultados en un único DataFrame.
    """
    resultados = []

    logger.info(f"📥 Recibidos {len(pdf_contents)} elementos para procesar")

    for i, pdf_content in enumerate(pdf_contents, start=1):
        logger.info(f"🔍 Elemento {i}: tipo {type(pdf_content).__name__}")

        if not isinstance(pdf_content, (bytes, bytearray)):
            logger.warning(f"⚠️ El elemento {i} no es bytes, se omitirá")
            continue

        logger.info(f"🔹 Procesando archivo {i} ({len(pdf_content)} bytes)")
        df_temp = process_dixell(pdf_content)
        if df_temp is None:
            logger.warning(f"❌ process_dixell devolvió None para el elemento {i}")
            continue
        resultados.append(df_temp)

    if resultados:
        df_concat = pd.concat(resultados, ignore_index=True)

        # 🔹 Recalcular 'id' único para todo el conjunto
        if not df_concat.empty:
            df_concat['id'] = range(1, len(df_concat) + 1)

        try:
            df_concat.to_excel(salida_excel, index=False)
            logger.info(f"✅ Archivos concatenados guardados en {salida_excel}")
        except Exception as e:
            logger.warning(f"No se pudo guardar el Excel: {e}")
        return df_concat
    else:
        logger.warning("⚠️ No se detectaron datos válidos en ninguno de los PDFs.")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

# ====================================================
# Ejecución directa (CLI)
# ====================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python process_dixell.py <archivo1.pdf> [archivo2.pdf ...] [salida.xlsx]")
        sys.exit(1)

    # Si el último argumento es un .xlsx, lo tomamos como salida
    if sys.argv[-1].endswith(".xlsx"):
        salida_excel = sys.argv[-1]
        pdf_paths = sys.argv[1:-1]
    else:
        salida_excel = "tablas_extraidas.xlsx"
        pdf_paths = sys.argv[1:]

    try:
        pdf_bytes_list = []
        for p in pdf_paths:
            try:
                with open(p, "rb") as f:
                    pdf_bytes_list.append(f.read())
            except Exception as e:
                logger.warning(f"No se pudo leer {p}: {e}")

        if not pdf_bytes_list:
            logger.error("No se pudieron leer archivos PDF. Abortando.")
            sys.exit(1)

        df_final = process_multiple_pdfs(pdf_bytes_list, salida_excel)
        if df_final is not None and not df_final.empty:
            print("\n✅ Primeras filas del DataFrame:")
            print(df_final.head())
            print(f"\n📘 Datos exportados a Excel (si lo permitía el entorno): {salida_excel}")
        else:
            print("⚠️ No se extrajo información útil de los PDFs.")
    except Exception as e:
        logger.error(f"❌ Error al analizar los PDF: {e}")
