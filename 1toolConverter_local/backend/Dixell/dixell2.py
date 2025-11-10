import sys
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from openpyxl import Workbook
import logging
import re
import numpy as np
# ====================================================
# Configuración de logging
# ====================================================
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
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
    "Device Status": ["DEVICE STATUS", "STATUS"],
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
COLUMNAS_VALIDAS = {
    "Name": ["Name", "NAME", "Nombre", "name"],
    "Unit": ["Unit", "UNIT", "unit", "unidades"],
    "Read Register": ["Read Register", "Reading Registers", "Read Addr", "Reg Read", "Reading Registers N"],
    "Num. Elements Read": ["Num. Elements Read", "Num.Elements Read", "Num. of Elements to Read", "Number of Read Elements", "um. of Elements to Rea"],
    "Write Register": ["Write Register", "Writing Registers", "Write Addr", "Reg Write", "d Writing Registers"],
    "Num. Elements Write": ["Num. Elements Write", "Num.Elements Write", "Num. of Elements to Write", "Number of Write Elements"],
    "Gain": ["Gain", "Factor", "G"],
    "Dec": ["Dec", "Decimals", "Resolution"],
    "Offset": ["Offset", "Offs", "Displacement"],
    "Byte ORDER": ["Byte ORDER", "Byte Order", "ByteOrder"],
    "Format": ["Format", "Formato", "Data Type"],
    "R / W": ["R / W", "RW", "Access", "Acceso", "R/W"],
    "Register": ["Register", "Reg", "Dir"],
    "Value": ["Value", "Valor", "Default Value", "Initial Value"],
    "Modbus Command": ["Modbus Command", "Command", "CMD"],
    "DEC": ["DEC", "DECIMAL"] ,
    "REGISTER[hex]": ["REGISTER[hex]", "HEX"],
    "VAR NAME": ["VAR NAME", "VAR"],
    "DESCRIPTION": ["DESCRIPTION", "description"],
    "GROUP": ["GROUP", "group"],
    "LENGHT": ["LENGHT", "lenght"],
    "TYPE": ["TYPE", "type"]
}

COLUMN_MAPPING = {
    "Name": "name",
    "VAR NAME": "name",
    "DESCRIPTION": "description",
    "GROUP": "category",
    "Unit": "unit",
    "Read Register": "register",
    "Write Register": "register",
    "Dec": "register",
    "Register": "register",
    "Offset": "offset",
    "Format": "length",
    "LENGHT": "lenght",
    "Value": "value",
    "TYPE": "value"
}

DEFAULT_VALUES = {
    "system_category": "DEFAULT",
    "category": "",
    "description": "",
    "view": "basic",
    "unit": "",
    "read": 0,
    "write": 0,
    "sampling": 0,
    "minvalue": 0,
    "maxvalue": 0,
    "addition": 0,
    "mask": 0,
    "value": 0,
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
        return df
    return df.reset_index(drop=True)

def eliminar_filas_vacias_completas(df):
    if df is None or df.empty:
        return df
    return df.dropna(how="all")

def deduplicar_columnas(cols):
    """Evita columnas duplicadas en pandas >=2.1"""
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
    """Convierte un valor hexadecimal (string) a decimal. Devuelve el mismo valor si no es hex válido."""
    if pd.isna(val):
        return ""
    val = str(val).strip().replace(" ", "")
    try:
        if val.lower().startswith("0x"):
            return int(val, 16)
        elif all(c in "0123456789abcdefABCDEF" for c in val) and val != "":
            return int(val, 16)
        else:
            return val
    except Exception:
        return val
    
def _process_specific_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de categorías específicas (insensible a mayúsculas)."""
    if 'system_category' in df.columns:
        df = df.copy()
        df['system_category'] = df['system_category'].astype(str).str.strip().str.lower()

        # Mapeo normal
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
            'device id': 'SYSTEM'
        }

        df['system_category'] = df['system_category'].replace(mapping)
        df['system_category'] = df['system_category'].str.upper()

        # Filtrar categorías vacías o nulas
        df = df[~df['system_category'].isin(['NONE', '', 'NAN', None])].copy()

        if "system_category" in df.columns:
            system_type = df['system_category'].astype(str).str.upper().str.strip()
            df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
        
        mask_do = df['name'].str.contains(r'output', case=False, na=False)
        df.loc[mask_do, 'system_category'] = 'DIGITAL_OUTPUT'
        logger.info(f"{mask_do.sum()} filas marcadas como DIGITAL_OUTPUT")

        mask_di = df['name'].str.contains(r'input', case=False, na=False)
        df.loc[mask_di, 'system_category'] = 'DIGITAL_INPUT'
        logger.info(f"{mask_di.sum()} filas marcadas como DIGITAL_INPUT")


    return df


def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna permisos de lectura/escritura en función del tipo de dato y categoría."""
    if 'read' not in df.columns:
        df['read'] = 0
    if 'write' not in df.columns:
        df['write'] = 0

    df.columns = df.columns.astype(str).str.strip()
    only_read = pd.Series(False, index=df.index)
    rw = pd.Series(False, index=df.index)

    # Mapeo por "R / W"
    if 'R / W' in df.columns:
        access = df['R / W'].astype(str).str.upper().str.strip()

        only_read = access == 'R'
        rw = access == 'R/W'

        df.loc[access == 'R', 'read'] = 4
        df.loc[access == 'W', 'write'] = 6
        df.loc[access == 'R/W', 'read'] = 3
        df.loc[access == 'R/W', 'write'] = 6

        df.drop(columns=['R / W'], inplace=True, errors='ignore')

    # Ajustes por tipo de sistema
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
            df.loc[mask, 'write'] = 10

        mask = rw & system_type.isin(['DIGITAL_OUTPUT'])
        if mask.any():
            df.loc[mask, 'read'] = 1
            df.loc[mask, 'write'] = 0

        mask = rw & system_type.isin(['DIGITAL_INPUT'])
        if mask.any():
            df.loc[mask, 'read'] = 1

    return df

def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "ALARM": 30, 
        "SET_POINT": 300, 
        "DEFAULT": 0, 
        "COMMAND": 0, 
        "STATUS": 60, 
        "SYSTEM": 0, 
        "CONFIG_PARAMETER": 0, 
        "ANALOG_INPUT": 60, 
        "ANALOG_OUTPUT":60,
        "DIGITAL_INPUT": 60, 
        "DIGITAL_OUTPUT":60,
        }
    df["sampling"] = df["system_category"].map(mapping).fillna(0)
    return df

def _apply_view_rules(df: pd.DataFrame) -> pd.DataFrame:
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
        'CONFIG_PARAMETER': '16bit',
        'ANALOG_OUTPUT': '16bit',
        'DIGITAL_OUTPUT': '1bit',
        'SERIAL_OUTPUT': '16bit',
        'SYSTEM': '16bit'
    }

    df["length"] = None
    if "system_category" in df.columns:
        df.loc[df["system_category"].isin(category_mapping.keys()), 
               "length"] = df["system_category"].map(category_mapping)

    return df

def _apply_unit_rules(df: pd.DataFrame) -> pd.DataFrame:
    unit = {
        'par "CF"': "°C",
        'RPM': "rpm"
    }
    df['unit'] = df['unit'].map(unit).fillna('')
    return df

# ====================================================
# Función principal
# ====================================================
def process_dixell(pdf_path, salida_excel="tablas_extraidas.xlsx"):
    descripcion = []
    zonas_colores = []
    tablas_detectadas = 0
    hojas = {}
    ultima_hoja_valida = None

    # --- Detectar zonas coloreadas ---
    with fitz.open(pdf_path) as pdf:
        for num, pagina in enumerate(pdf, start=1):
            for d in pagina.get_drawings():
                color = d.get("fill")
                if color and any(c > 0 for c in color):
                    zonas_colores.append((num, color))
        descripcion.append(f"🔹 Zonas con color detectadas: {len(zonas_colores)}")

    # --- Detectar tablas ---
    with pdfplumber.open(pdf_path) as pdf:
        for num, pagina in enumerate(pdf.pages, start=1):
            tablas = pagina.extract_tables()
            if tablas:
                tablas_detectadas += len(tablas)
                descripcion.append(f"📄 Página {num}: {len(tablas)} tabla(s) detectada(s).")

                for i, tabla in enumerate(tablas, start=1):
                    df = pd.DataFrame(tabla)
                    encabezado = ", ".join([str(x).strip() for x in tabla[0] if x]) if len(tabla) > 0 else ""

                    encabezado_principal = None

                    # --- Buscar coincidencia exacta (sensible a mayúsculas/minúsculas) ---
                    for clave, alias_list in ENCABEZADOS_EQUIVALENTES.items():
                        if any(alias.strip() == encabezado.strip() for alias in alias_list):
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
                        # --- Si no coincide con ningún encabezado, asignar a la última hoja válida o SinClasificar ---
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


    # --- Limpiar, eliminar primeras filas y guardar ---
    with pd.ExcelWriter(salida_excel, engine='openpyxl') as escritor:
        hojas_limpiadas = {}

        for nombre, df in hojas.items():
            df_limpio = limpiar_dataframe(df)
            df_limpio = eliminar_filas_vacias_completas(df_limpio)

            if len(df_limpio) > 3:
                df_limpio = df_limpio.iloc[6:].reset_index(drop=True)

            if not df_limpio.empty:
                encabezado_detectado = ", ".join(
                    [str(x) for x in df_limpio.iloc[0].tolist() if pd.notna(x)]
                )
            else:
                encabezado_detectado = "Sin encabezado (hoja vacía)"

            logger.info(f"Encabezado detectado en hoja '{nombre}' (tras eliminar 3 filas): {encabezado_detectado}")

            hojas_limpiadas[nombre] = df_limpio
            # --- Limpiar nombre de hoja ---
            nombre_hoja = re.sub(r'[:\\/*?\[\]/]', '_', nombre)[:31]
            df_limpio.to_excel(escritor, sheet_name=nombre_hoja, index=False, header=False)

        # --- Concatenar todas las tablas válidas ---
        todas = []
        for nombre, df in hojas_limpiadas.items():
            if nombre != "SinClasificar" and not df.empty:
                df_copy = df.copy()
                df_copy.columns = df_copy.iloc[0]
                df_copy = df_copy[1:].reset_index(drop=True)

                # 🔹 Normalizar nombres de columnas
                columnas_nuevas = []
                for col in df_copy.columns:
                    col_limpio = str(col).strip()
                    encontrado = False
                    for canonico, alias_list in COLUMNAS_VALIDAS.items():
                        if col_limpio.lower() in [a.lower() for a in alias_list]:
                            columnas_nuevas.append(canonico)
                            encontrado = True
                            break
                    if not encontrado:
                        columnas_nuevas.append(col_limpio)  # deja igual si no hay equivalencia
                # --- LOG: columnas detectadas antes del mapeo
                                
                logger.info(f"Columnas detectadas antes del mapeo: {list(df_copy.columns)}")
                logger.info(f"Columnas tras aplicar equivalencias: {columnas_nuevas}")

                logger.info(f"\n==== HOJA: {nombre} - Antes de mapear columnas 1====")
                logger.info(df_copy.head(10))  # correcto: usar df_copy

                # Aplicar equivalencias
                df_copy.columns = columnas_nuevas

                # 🔹 Eliminar encabezados duplicados
                df_copy.columns = deduplicar_columnas(df_copy.columns)
                logger.info(f"\n==== HOJA: {nombre} - Después de eliminar duplicados 2 ====")
                logger.info(df_copy.head(10))

                # 🔹 Filtrar solo columnas válidas presentes
                columnas_finales = list(COLUMNAS_VALIDAS.keys())
                logger.info(f"Columnas finales posibles: {columnas_finales}")

                df_copy = df_copy[[col for col in df_copy.columns if col in columnas_finales]]
                logger.info(f"\n==== HOJA: {nombre} - Después de filtrar solo columnas válidas presentes 3====")
                logger.info(df_copy.head(10))

                # 🔹 Reordenar columnas según el orden de columnas_finales, conservando solo las presentes
                columnas_reordenadas = [col for col in columnas_finales if col in df_copy.columns]
                df_copy = df_copy[columnas_reordenadas]
                df_copy.insert(0, "system_category", nombre)
                logger.info(f"\n==== HOJA: {nombre} - Después de reordenar columnas 4====")
                logger.info(df_copy.head(10))
                todas.append(df_copy)


        if todas:
            df_final = pd.concat(todas, ignore_index=True)
            logger.info("\n==== df_final - Después de concatenar todas las hojas 5====")
            logger.info(df_final.head(10))
            
            # ✅ Combinar "Read Register" y "Write Register" correctamente
            read_vals = df_final["Read Register"] if "Read Register" in df_final.columns else pd.Series([""] * len(df_final))
            write_vals = df_final["Write Register"] if "Write Register" in df_final.columns else pd.Series([""] * len(df_final))
            reg_vals = df_final["Register"] if "Register" in df_final.columns else pd.Series([""] * len(df_final))
            dec_vals = df_final["Dec"] if "Dec" in df_final.columns else pd.Series([""]* len(df_final))
            

            df_final["register"] = read_vals.fillna("").astype(str)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), write_vals)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), reg_vals)
            df_final["register"] = df_final["register"].mask(df_final["register"].eq(""), dec_vals)

            logger.info("\n==== df_final - Después de combinar registers 6====")
            logger.info(df_final.head(10))

            # Copiar las demás columnas según el mapeo
            for col_origen, col_destino in COLUMN_MAPPING.items():
                if col_destino != "register" and col_origen in df_final.columns:
                    df_final[col_destino] = df_final[col_origen]
            logger.info("\n==== df_final - Después de aplicar COLUMN_MAPPING 7====")
            logger.info(df_final.head(10))

            # Añadir columnas faltantes del modelo final
            for col in LIBRARY_COLUMNS:
                if col not in df_final.columns:
                    df_final[col] = DEFAULT_VALUES.get(col, "")
            logger.info("\n==== df_final - Después de añadir columnas faltantes 8====")
            logger.info(df_final.head(10))

            # 🔹 Eliminar filas sin 'register' ni 'name'
            df_final = df_final[
                ~((df_final["register"].fillna("").astype(str).str.strip() == "") &
                  (df_final["name"].fillna("").astype(str).str.strip() == ""))
            ].reset_index(drop=True)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 9====")
            logger.info(df_final.head(10))

            # 🔹 Convertir columnas 'register' y 'value' a decimal
            if "register" in df_final.columns:
                df_final["register"] = df_final["register"].apply(hex_to_dec).astype(str)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 10====")
            logger.info(df_final.head(10))

            if "value" in df_final.columns:
            #    # Convertir hexadecimales a decimal
                df_final["value"] = df_final["value"].apply(hex_to_dec).astype(str)
                logger.info("\n==== df_final - Después de añadir columnas faltantes 11====")
                logger.info(df_final.head(10))

                # Reemplazar valores no numéricos o con símbolos especiales por 0
                df_final["value"] = df_final["value"].apply(
                    lambda x: x if re.fullmatch(r"^-?\d+(\.\d+)?$", x.strip()) else "0"
                )
                logger.info("\n==== df_final - Después de añadir columnas faltantes 12====")
                logger.info(df_final.head(10))


            # Procesar columnas específicas
            df_final = _process_specific_columns(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.1====")
            logger.info(df_final.head(10))
            df_final = _process_access_permissions(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.2====")
            logger.info(df_final.head(10))
            df_final = _apply_sampling_rules(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.3====")
            logger.info(df_final.head(10))
            df_final = _apply_view_rules(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.4====")
            logger.info(df_final.head(10))
            df_final = _determine_data_length(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.5====")
            logger.info(df_final.head(10))
            df_final = _apply_unit_rules(df_final)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 12.6====")
            logger.info(df_final.head(10))

            # Reordenar según el modelo
            df_final = df_final[LIBRARY_COLUMNS]
            logger.info("\n==== df_final - Reordenar segun el modelo 13====")
            logger.info(df_final.head(10))

            # 🔹 Eliminar filas sin 'register' (vacías o NaN)
            #df_final = df_final[df_final["register"].fillna("").astype(str).str.strip() != ""]
            
            # 🔹 Eliminar filas cuyo system_category sea 'CLOCK' (insensible a mayúsculas)
            df_final = df_final[~df_final["system_category"].astype(str).str.upper().str.contains("CLOCK", na=False)]
            df_final = df_final[~df_final["system_category"].astype(str).str.upper().str.contains("SERIAL_OUTPUT", na=False)]

            df_final.to_excel(escritor, sheet_name="Todas las Tablas", index=False)
            logger.info("\n==== df_final - Después de añadir columnas faltantes 14====")
            logger.info(df_final.head(10))
    descripcion.append(f"🔹 Total de tablas detectadas: {tablas_detectadas}")
    descripcion.append(f"🔹 Total de zonas coloreadas: {len(zonas_colores)}")

    print("\n==== DESCRIPCIÓN DEL PDF ====\n")
    for linea in descripcion:
        print(linea)
    print(f"\n✅ Análisis completado. Se eliminaron las primeras 3 filas, se limpiaron filas vacías y se convirtieron valores a decimal correctamente.\n")


# ====================================================
# Ejecución
# ====================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python process_dixell.py <archivo.pdf> [salida.xlsx]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    salida_excel = sys.argv[2] if len(sys.argv) > 2 else "tablas_extraidas.xlsx"

    try:
        process_dixell(pdf_path, salida_excel)
    except Exception as e:
        logger.error(f"❌ Error al analizar el PDF: {e}")
