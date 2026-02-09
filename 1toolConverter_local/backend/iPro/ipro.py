"""
Backend iPro: Procesamiento de archivos Excel (variables de sistema) y conversión a DataFrame.
Este módulo no genera interfaz ni escribe archivos. 
Solo devuelve un DataFrame procesado para uso en la UI de main.py.
"""

from asyncio import run
import os
import pandas as pd
import numpy as np
import re
import logging
from io import BytesIO
from typing import Optional, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =====================================================
# CONFIGURACIÓN DE LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================
# CONSTANTES
# =====================================================

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

COLUMN_MAPPING = {
    'Name': 'name',
    'Nombre': 'name',
    'Address': 'register',
    'Dirección.1': 'register',
    'Dimension': 'dimension',
    'Dimensión': 'dimension',
    'Comment': 'description',
    'Commentario': 'description',
    'Wiring': 'category',
    'Cableado': 'category',
    'String Size': 'length',
    'Tamaño de la cadena': 'length',
    'Attribute': 'attribute',  
    'Atributo': 'attribute',
    'Groups': 'groups',
    'Grupos': 'groups'
}

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def extract_min_max_from_dimension(value: str):
    """Extrae valores mínimo y máximo de un texto como '[1...23]' o '1-23'."""
    if not isinstance(value, str):
        return np.nan, np.nan
    value = value.strip()
    match = re.search(r'\[?\s*(\-?\d+)\s*(?:\.\.\.|\.{2,}|-|–)\s*(\-?\d+)\s*\]?', value)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            return np.nan, np.nan
    return np.nan, np.nan


def expand_dimension_to_rows_name_bits(df, default_bits=1):
    """Expande variables con dimension [min..max] en filas hijas."""
    new_rows = []
    for _, row in df.iterrows():
        if 'dimension' in row and pd.notna(row['dimension']):
            min_val, max_val = extract_min_max_from_dimension(row['dimension'])
            if not np.isnan(min_val) and not np.isnan(max_val):
                n = int(max_val - min_val + 1)
                total_bits = n * default_bits
                row['length'] = total_bits
                new_rows.append(row)
                base_register = np.nan
                if 'register' in row and pd.notna(row['register']):
                    try:
                        base_register = int(row['register'])
                    except:
                        base_register = np.nan
                for offset in range(n):
                    pos = int(min_val + offset)
                    new_row = row.copy()
                    new_row['name'] = f"{row['name']}_{pos}"
                    new_row['length'] = f"{default_bits}bit"
                    new_row['description'] = f"{row['name']} - Posición {pos}"
                    if not np.isnan(base_register):
                        new_row['register'] = base_register + offset + 1
                    new_rows.append(new_row)
                continue
        row['length'] = f"{default_bits}bit"
        new_rows.append(row)
    return pd.DataFrame(new_rows)


def normalize_length(val):
    """Normaliza longitudes a potencias de 2 válidas (1,2,4,8,16bit)."""
    try:
        if isinstance(val, str):
            num = re.findall(r'\d+', val)
            length = int(num[0]) if num else 1
        else:
            length = int(val)
    except Exception:
        length = 1
    valid_sizes = [1, 2, 4, 8, 16]
    valid_match = max([v for v in valid_sizes if v <= length], default=1)
    return f"{valid_match}bit"


def register_to_decimal(val):
    """Convierte un valor hexadecimal o numérico a entero."""
    val_str = str(val).strip()
    if re.fullmatch(r'[0-9a-fA-F]+', val_str):
        return int(val_str, 16)
    try:
        return int(val_str)
    except:
        return np.nan

def categorize_system(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna la categoría del sistema según las columnas 'groups' y 'name'."""
    
    if 'groups' not in df.columns or 'name' not in df.columns:
        logger.warning("El DataFrame no contiene las columnas requeridas: 'groups' o 'name'.")
        return df
    
    df = df.copy()
    df['system_category'] = np.nan

    # --- Normalización de texto ---
    df['groups'] = df['groups'].astype(str).str.upper()
    df['name'] = df['name'].astype(str).str.upper()

    # --- Categorización por grupos ---
    df.loc[df['groups'].str.contains('PARAMETROS_CONFIGURACION', na=False), 'system_category'] = 'CONFIG_PARAMETER'
    df.loc[df['groups'].str.contains('ALARMAS|WARNINGS', na=False), 'system_category'] = 'ALARM'
    df.loc[df['groups'].str.contains('COMANDOS', na=False), 'system_category'] = 'COMMAND'
    df.loc[df['groups'].str.contains('ESTADOS', na=False), 'system_category'] = 'STATUS'
    df.loc[df['groups'].str.contains('INSTANCIAS|REGISTRO', na=False), 'system_category'] = 'DEFAULT'
    df.loc[df['groups'].str.contains('SISTEMA', na=False), 'system_category'] = 'SYSTEM'

    # --- Categorización por nombre ---
    mask_ai = df['name'].str.startswith(('PB_', 'SONDAS_'), na=False)
    df.loc[mask_ai, 'system_category'] = 'ANALOG_INPUT'
    logger.info(f"{mask_ai.sum()} filas marcadas como ANALOG_INPUT")

    mask_ao = df['name'].str.startswith(('AO_', 'SALIDA_ANALOG_'), na=False)
    df.loc[mask_ao, 'system_category'] = 'ANALOG_OUTPUT'
    logger.info(f"{mask_ao.sum()} filas marcadas como ANALOG_OUTPUT")

    mask_di = df['name'].str.startswith('DI_', na=False)
    df.loc[mask_di, 'system_category'] = 'DIGITAL_INPUT'
    logger.info(f"{mask_di.sum()} filas marcadas como DIGITAL_INPUT")

    mask_do = df['name'].str.startswith(('RELE_', 'RL_'), na=False)
    df.loc[mask_do, 'system_category'] = 'DIGITAL_OUTPUT'
    logger.info(f"{mask_do.sum()} filas marcadas como DIGITAL_OUTPUT")

    #mask_ir1 = df['name'].str.startswith(('time_', 'mSET_', 'recorte'), na=False)
    #df.loc[mask_ir1, 'system_category'] = 'CONFIG_PARAMETER'
    #logger.info(f"{mask_ir1.sum()} filas marcadas como CONFIG_PARAMETER")

    #mask_ir2 = df['name'].str.startswith(('Func_', 'INS_', 'AJUSTAR', 'reset_', 'export_'), na=False)
    #df.loc[mask_ir2, 'system_category'] = 'COMMAND'
    #logger.info(f"{mask_ir2.sum()} filas marcadas como COMMAND")

    #mask_ir3 = df['name'].str.startswith(('en_', 'GETT', 'DATA_', 'USB_', 'P2'), na=False)
    #df.loc[mask_ir3, 'system_category'] = 'STATUS'
    #logger.info(f"{mask_ir3.sum()} filas marcadas como STATUS")

    mask_ir4 = df['name'].str.startswith(('VERSION_'), na=False)
    df.loc[mask_ir4, 'system_category'] = 'SYSTEM'
    logger.info(f"{mask_ir4.sum()} filas marcadas como SYSTEM")


    if "system_category" in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
        
    # --- Filtrado final ---
    valid_categories = [
        'CONFIG_PARAMETER', 'ALARM', 'COMMAND', 'STATUS', 
        'ANALOG_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_INPUT', 'DIGITAL_OUTPUT', 'SYSTEM', 'DEFAULT'
    ]
    
    df_filtered = df[df['system_category'].isin(valid_categories)].reset_index(drop=True)
    logger.info(f"Total de filas categorizadas: {len(df_filtered)}")

    return df_filtered



def apply_min_max(df: pd.DataFrame) -> pd.DataFrame:
    """Define valores min y max según system_category."""
    df["minvalue"], df["maxvalue"] = 0, 0
    df.loc[df["system_category"].isin(["COMMAND", "CONFIG_PARAMETER", "ALARM"]), ["minvalue", "maxvalue"]] = [0, 1]
    return df


def apply_rw_permissions(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica permisos de lectura/escritura según 'attribute' y system_category."""
    df['read'], df['write'] = 0, 0
    if 'attribute' in df.columns:
        attr = df['attribute'].str.upper().str.strip()
        df.loc[attr == 'READ', ['read', 'write']] = [3, 0]
        df.loc[attr == 'READWRITE', ['read', 'write']] = [3, 16]
        df.loc[attr == 'WRITE', ['read', 'write']] = [0, 6]

    if 'system_category' in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        only_read = (df['read'] > 0) & (df['write'] == 0)
        rw = (df['read'] > 0) & (df['write'] > 0)
        df.loc[only_read & system_type.isin(['ALARM']), 'read'] = 1
        df.loc[only_read & system_type.isin(['STATUS']), 'read'] = 4
        df.loc[rw & system_type.isin(['COMMAND']), ['read', 'write']] = [0, 16]
        df.loc[rw & system_type.isin(['CONFIG_PARAMETER']), ['read', 'write']] = [3, 16]
    return df


def fix_duplicate_names(df: pd.DataFrame) -> pd.DataFrame:
    """Asegura que los nombres sean únicos agregando sufijos _2, _3, etc."""
    if "name" not in df.columns:
        return df
    df["name"] = df["name"].astype(str).str.strip()
    duplicates = df.groupby("name").cumcount()
    df["name"] = np.where(duplicates == 0, df["name"], df["name"] + "_" + (duplicates + 1).astype(str))
    return df


def assign_tags(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna tags según la categoría del sistema."""
    if "system_category" in df.columns:
        system_type = df["system_category"].astype(str).str.upper().str.strip()
        df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
    return df

def _apply_mask_logic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna máscaras (mask) a filas hijas basadas únicamente en el nombre del padre.
    
    Regla:
        Padre:  'SONDAS'
        Hijas:  'SONDAS_1', 'SONDAS_2', ... → mask = 0x1, 0x2, 0x4, ..., 0x8000
        Si hay más de 16 hijas, reinicia desde 0x1.
    """
    logger.info("=== Iniciando proceso de asignación de máscaras ===")
    df = df.copy()

    if "name" not in df.columns:
        logger.warning("No se encontró la columna 'name'. No se aplicarán máscaras.")
        return df

    # Asegurar que exista la columna mask
    if "mask" not in df.columns:
        df["mask"] = np.nan

    df["name"] = df["name"].astype(str).str.strip()
    total_filas = len(df)
    padres_detectados = 0
    hijas_asignadas_total = 0

    logger.info(f"Total de filas a procesar: {total_filas}")

    for i, row in df.iterrows():
        name = row["name"]

        # Padre: no contiene sufijo tipo _#
        if not re.search(r"_\d+$", name):
            padres_detectados += 1
            padre_name = name

            # Buscar hijas: nombres que comienzan con el nombre del padre + "_"
            hijas_mask = df["name"].str.match(rf"^{re.escape(padre_name)}_\d+$")
            hijas = df[hijas_mask]

            if not hijas.empty:
                num_hijas = len(hijas)
                masks = [f"0x{1 << (k % 16):X}" for k in range(num_hijas)]
                df.loc[hijas.index, "mask"] = masks
                hijas_asignadas_total += num_hijas
                #logger.info(f"→ Padre '{padre_name}' ({num_hijas} hijas) → {masks}")
            else:
                #logger.debug(f"Padre '{padre_name}' sin hijas detectadas")
                return df
            
    #logger.info(f"=== Finalizado proceso de asignación de máscaras ===")
    #logger.info(f"Padres detectados: {padres_detectados} | Hijas asignadas: {hijas_asignadas_total}")

    return df



def finalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica columnas por defecto, reordenamiento y limpieza final."""
    defaults = {
        "addition": 0,
        "value": 0,
        "general_icon": np.nan,
        "alarm": '{"severity":"none"}',
        "metadata": "[]",
        "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
        "tags": "[]",
        "type": "modbus",
        "parameter_write_byte_position": np.nan,
        "mqtt": np.nan,
        "json": np.nan,
        "current_value": np.nan,
        "current_error_status": np.nan,
        "notes": np.nan,
        #"category": np.nan,
    }
    for col, val in defaults.items():
        if col not in df.columns:
            df[col] = val
    df = df.reindex(columns=LIBRARY_COLUMNS, fill_value="0")
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

def merge_with_template(df_user: pd.DataFrame, template_df: pd.DataFrame) -> pd.DataFrame:
    """
    Combina la plantilla base con los datos del usuario.
    Regla: Mantiene TODO lo de la plantilla. Agrega lo del usuario solo si el 'register' no existe.
    """
    if template_df is None or template_df.empty:
        return df_user

    # Normalización de registros para comparación exacta
    def _norm_reg(v):
        try: return str(int(float(v)))
        except: return str(v).strip()

    template_df['register_key'] = template_df['register'].apply(_norm_reg)
    df_user['register_key'] = df_user['register'].apply(_norm_reg)

    # Identificar registros del usuario que NO están en la plantilla
    existing_regs = set(template_df['register_key'].unique())
    df_new_entries = df_user[~df_user['register_key'].isin(existing_regs)].copy()

    # Combinar: Plantilla primero, luego lo nuevo del usuario
    df_combined = pd.concat([template_df, df_new_entries], ignore_index=True)

    # Limpieza: eliminar la llave temporal y reordenar por registro
    df_combined.drop(columns=['register_key'], inplace=True)
    df_combined = df_combined.sort_values(by='register').reset_index(drop=True)
    
    # Re-generar IDs secuenciales para mantener consistencia
    df_combined['id'] = range(1, len(df_combined) + 1)
    
    return df_combined

# =====================================================
# FUNCIÓN PRINCIPAL
# =====================================================

def convert_excel_to_dataframe(file_bytes: bytes, df_plantilla: pd.DataFrame = None) -> Optional[pd.DataFrame]:
    """Procesa un archivo Excel (bytes) y devuelve un DataFrame procesado."""
    try:
        xls = pd.ExcelFile(BytesIO(file_bytes))
        logger.info(f"Archivo Excel leído con {len(xls.sheet_names)} hojas.")
    except Exception as e:
        logger.error(f"Error al abrir el archivo Excel: {e}", exc_info=True)
        return None

    processed_dfs: List[pd.DataFrame] = []

    for sheet_name in xls.sheet_names:
        try:
            logger.info(f"Procesando hoja: {sheet_name}")
            df = pd.read_excel(xls, sheet_name=sheet_name, header=0)
            if len(df) > 0:
                df = df.drop(df.index[0]).reset_index(drop=True)

            df.columns = df.columns.astype(str).str.strip()
            df.rename(columns=COLUMN_MAPPING, inplace=True, errors='ignore')
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            for col in ['category', 'name', 'description', 'attribute', 'groups']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()

            if 'register' in df.columns:
                df['register'] = df['register'].apply(register_to_decimal)

            if 'dimension' in df.columns:
                df = expand_dimension_to_rows_name_bits(df, default_bits=1)
                df.drop(columns=['dimension'], inplace=True, errors='ignore')

            if 'description' in df.columns:
                df['description'] = df['description'].astype(str).str.slice(0, 60)

            df = categorize_system(df)
            if df.empty:
                logger.warning(f"La hoja '{sheet_name}' no contiene categorías válidas, se omitirá.")
                continue

            df = apply_min_max(df)
            df = apply_rw_permissions(df)
            df = assign_tags(df)
            df = fix_duplicate_names(df)
            df = _apply_mask_logic(df)
            df = _apply_sampling_rules(df)

            if 'length' in df.columns:
                df['length'] = df['length'].apply(normalize_length)

            df['unit'] = df.get('unit', pd.Series("", index=df.index)).astype(str).replace({"nan": "", "None": "", "NaN": ""})
            df['offset'] = 0.0

            processed_dfs.append(df)

        except Exception as e:
            logger.error(f"Error procesando hoja {sheet_name}: {e}", exc_info=True)
            continue

    if not processed_dfs:
        df_usuario_raw = pd.DataFrame(columns=LIBRARY_COLUMNS)
    else:
        df_usuario_raw = pd.concat(processed_dfs, ignore_index=True)

    # 2. USA EL PARÁMETRO EN LUGAR DE CARGARLO AQUÍ
    if df_plantilla is not None:
        df_final = merge_with_template(df_usuario_raw, df_plantilla)
    else:
        df_final = df_usuario_raw

    # 3. Máscaras a eliminar (por name)
    masks_a_quitar = [
        #Filtado ALARMS
        "LIST_", "ALARM_NOLINK", "HORA_INICIO_", "MINUTO_INICIO_", "NUM_ALARMA", "LIST_ALARMS", "WARNING_", "NUM_", "ALARM_REG", "ALARM_PB",
        #Filtado ANALOG_INPUT
        "SONDAS_",
        #Filtado ANALOG_OUTPUT
        "AO_OUT", "SALIDA_ANALOG_",
        #Filtrado COMMAND
        "KB_ONOFF", "RESET_DATALOG_"
        #Filtrado CONFIG_PARAMETER
        "SALIDAS_ANALOG_", "PASSWORD_", "ENTRADAS_DIGITALES_", "POLARIDAD_", "FORCE_",
        #Filtrado DIGITAL_INPUT
        "DI_OUT",
        #Filtrado DIGITAL_OUTPUT
        "RELE_SALIDA_", "RELE_TEST_",
        #Filtrado STATUS
        "ENABLE_", "EXPORT_", "USB_", "TEST_", "LOAD_", "SAVE_", "PASSWORD_", "TIMER_", "SEL_", "STATUS_", "CURRENT_", "SET_", "LEER_", "BLACKOUT_", "EN_COMUNICAION_", "ST_CLOCK_", "SIMULADOR", "DEPURACION", "CICLO", "V-LANG", "V_ICXVAR", "SYS_BUZ",
        #Filtrado SYSTEM
        "VERSION_",
        #OTROS
        "EN_REG", "RESET_LOG", "EXPORT_LOG", "TIME_BETWEEN_"
    ]

    if "name" in df_final.columns:
        patron = "|".join(masks_a_quitar)
        filas_antes = len(df_final)

        df_final = df_final[
            ~df_final["name"].astype(str).str.contains(patron, na=False)
        ].copy()

        logger.info(
            f"Filtrado por name completado. "
            f"Eliminadas {filas_antes - len(df_final)} filas. "
            f"Quedan {len(df_final)}."
        )

    # 4. Finalización
    df_final = df_final[
        pd.to_numeric(df_final["register"], errors="coerce").notna()
    ].copy()
    df_final["view"] = "simple"
    df_final = finalize_dataframe(df_final)

    logger.info(f"Proceso completado. Filas finales: {len(df_final)}")
    return df_final

# =====================================================
# EJECUCIÓN POR LÍNEA DE COMANDO
# =====================================================
if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path
    import pandas as pd

    def load_template(excel_path: Path) -> pd.DataFrame:
        try:
            df_template = pd.read_excel(excel_path)
            return df_template
        except Exception as e:
            logger.error(f"Error cargando plantilla: {e}", exc_info=True)
            return pd.DataFrame()

    # 1. Definimos la ruta por defecto de la plantilla
    default_template_path = Path(BASE_DIR) / "Plantilla kiControl.xlsx"

    parser = argparse.ArgumentParser(
        description="Procesa un archivo Excel de variables y lo mezcla con la plantilla maestra."
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Ruta al archivo Excel del usuario (.xlsx)"
    )
    parser.add_argument(
        "--template", "-t",
        default=str(default_template_path),
        help="Ruta a la plantilla maestra (.xlsx)"
    )
    parser.add_argument(
        "--output", "-o", default="resultado_ipro.xlsx",
        help="Ruta del archivo Excel de salida"
    )
    parser.add_argument(
        "--preview", "-p", action="store_true",
        help="Muestra las primeras filas en consola"
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    template_path = Path(args.template)
    output_path = Path(args.output)

    # 1. Validaciones iniciales
    if not input_path.exists():
        logger.error(f"El archivo de entrada no existe: {input_path}")
        sys.exit(1)

    # 2. Cargar Plantilla (EXCEL, no CSV)
    logger.info(f"Cargando plantilla desde: {template_path}")
    #logger.info(f"BASE_DIR = {BASE_DIR}")
    #logger.info(f"Ruta final plantilla = {default_template_path}")
    df_plantilla = pd.DataFrame()
    if template_path.exists():
        df_plantilla = load_template(template_path)
        if df_plantilla.empty:
            logger.warning("La plantilla se cargó vacía. Continuando solo con input.")
        else:
            logger.info(f"Plantilla cargada: {len(df_plantilla)} registros.")
    else:
        logger.warning("Archivo de plantilla no encontrado. Continuando solo con input.")

    # 3. Procesar archivo mediante la función principal
    try:
        file_bytes = input_path.read_bytes()

        # Llamamos a la función que ya tiene toda la lógica de limpieza y merge
        df_final = convert_excel_to_dataframe(file_bytes, df_plantilla=df_plantilla)

        if df_final is not None and not df_final.empty:
            # Vista previa opcional
            if args.preview:
                print("\n--- VISTA PREVIA DEL RESULTADO ---")
                print(df_final.head(15).to_string(index=False))
                print("----------------------------------\n")

            # 4. Exportar resultado
            df_final.to_excel(output_path, index=False)
            logger.info(f"Archivo final exportado en: {output_path.resolve()}")
        else:
            logger.error("El proceso no generó datos válidos.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error crítico en la ejecución: {e}", exc_info=True)
        sys.exit(1)