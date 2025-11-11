import sys
import logging
from pathlib import Path
from io import BytesIO
import pandas as pd
import pdfplumber
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

COLUMN_MAPPING_PDF = {
    "DIRECCION": "register",
    "DIRECCIÓN": "register",
    "Nombre": "name",
    "Longitud Word Dato": "length",
    "Longitud\nWord Dato": "length",
    "Valores": "description"
}

DEFAULT_VALUES = {
    "system_category": "DEFAULT",
    "category": "DEFAULT",
    "view": "basic",
    "sampling": 0,
    "read": "",
    "write": "",
    "minvalue": 0,
    "maxvalue": 0,
    "unit": "",
    "offset": 0,
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
# Función para aplicar modos de lectura/escritura
# ====================================================
def apply_read_write_flags(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Analizando modos de LECTURA/ESCRITURA en columna 'register'...")

    if "register" not in df.columns:
        return df

    df = df.reset_index(drop=True)
    if "write" not in df.columns:
        df["write"] = ""
    if "read" not in df.columns:
        df["read"] = ""

    current_mode = None
    to_drop = set()
    n = len(df)

    i = 0
    while i < n:
        reg_raw = str(df.at[i, "register"]).strip()
        reg_upper = reg_raw.upper()

        # Si es texto, puede indicar modo o encabezado
        if reg_raw and not reg_raw.isdigit():
            # Detectar modo
            if "ESCRITURA" in reg_upper:
                current_mode = "write"
                logger.info(f"Modo ESCRITURA detectado en fila {i}.")
                to_drop.add(i)
            elif "LECTURA" in reg_upper:
                current_mode = "read"
                logger.info(f"Modo LECTURA detectado en fila {i}.")
                to_drop.add(i)
            else:
                logger.info(f"Encabezado no modo detectado en fila {i}: '{reg_raw}' (modo actual: {current_mode}).")

            # Si la siguiente fila también tiene texto, eliminarla
            if i + 1 < n:
                next_reg = str(df.at[i + 1, "register"]).strip()
                if next_reg and not next_reg.isdigit():
                    to_drop.add(i + 1)
                    logger.info(f"Fila {i+1} marcada para eliminación (texto consecutivo: '{next_reg}').")

            i += 1
            continue

        # Aplicar el modo actual
        if current_mode == "write":
            df.at[i, "write"] = "W"
        elif current_mode == "read":
            df.at[i, "read"] = "R"

        i += 1

    if to_drop:
        logger.info(f"Eliminando {len(to_drop)} filas de encabezado (modos y texto consecutivo): {sorted(to_drop)}")
        df = df.drop(index=sorted(list(to_drop))).reset_index(drop=True)

    total_w = (df["write"] == "W").sum()
    total_r = (df["read"] == "R").sum()
    logger.info(f"✅ Aplicadas {total_w} 'W' y {total_r} 'R' correctamente.")

    return df


# ====================================================
# Propagar categorías por duplicados
# ====================================================
def propagate_context(df: pd.DataFrame) -> pd.DataFrame:
    """
    Propaga categorías basadas en duplicados de 'register'.

    - Cuando un 'register' se repite, la primera ocurrencia define la categoría (usando 'name').
    - Esa fila se elimina después de propagar la categoría,
      excepto si el 'name' comienza por 'AL'.
    """
    logger.info("Propagando categorías basadas en duplicados de 'register'...")

    df["register"] = df["register"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).str.strip()

    seen_registers = set()
    first_names = {}
    current_category = "DEFAULT"
    categories = []
    first_duplicate_indexes = []

    for idx, row in df.iterrows():
        reg = row.get("register", "").strip()
        name = row.get("name", "").strip()

        if not reg:
            categories.append(current_category)
            continue

        # Primera aparición de un registro
        if reg not in seen_registers:
            seen_registers.add(reg)
            first_names[reg] = name.replace(" ", "_")
            categories.append(current_category)
            continue

        # Duplicado → Propagar categoría usando el nombre de la primera aparición
        current_category = first_names[reg]
        first_index = df.index[df["register"] == reg][0]

        # Eliminar encabezado si no empieza por AL
        header_name = str(df.at[first_index, "name"]).strip()
        if not header_name.upper().startswith("AL"):
            if first_index not in first_duplicate_indexes:
                first_duplicate_indexes.append(first_index)
                logger.info(f"🗑️ Eliminando encabezado de grupo '{header_name}' en fila {first_index}")
        else:
            logger.info(f"⚠️ Encabezado '{header_name}' conservado (comienza por 'AL')")

        categories.append(current_category)

    df["category"] = categories

    # Eliminar encabezados de grupo que no sean AL...
    if first_duplicate_indexes:
        df = df.drop(index=first_duplicate_indexes).reset_index(drop=True)
        logger.info(f"Eliminadas {len(first_duplicate_indexes)} filas de encabezado de grupo (no AL).")

    return df



# ====================================================
# Propagar categoría por 'register' vacío
# ====================================================
def propagate_empty_register_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Si 'register' está vacío:
    - El valor de 'name' en esa fila define una nueva categoría activa.
    - Las siguientes filas heredan esa categoría hasta que aparezca otro vacío.
    - Finalmente, se eliminan las filas donde 'register' estaba vacío,
      excepto si el 'name' comienza por 'AL' (por ejemplo: 'ALARMAS').
    """
    logger.info("Propagando categorías basadas en filas con 'register' vacío y eliminando encabezados...")

    df = df.reset_index(drop=True)
    current_category = None
    empty_rows = []

    for i in range(len(df)):
        reg = str(df.at[i, "register"]).strip()
        name = str(df.at[i, "name"]).strip()

        # Si el registro está vacío, define nueva categoría
        if reg == "" or reg.lower() in ["nan", "none"]:
            if name:
                current_category = name.replace(" ", "_")
                logger.info(f"➡️ Nueva categoría detectada por vacío en fila {i}: '{current_category}'")

                
                empty_rows.append(i)

        # Aplicar categoría actual
        if current_category:
            df.at[i, "category"] = current_category

    # Eliminar las filas vacías (excepto encabezados tipo 'AL...')
    if empty_rows:
        logger.info(f"🗑️ Eliminando {len(empty_rows)} filas con 'register' vacío (no AL): {empty_rows}")
        df = df.drop(index=empty_rows).reset_index(drop=True)

    logger.info("✅ Categorías propagadas y filas vacías eliminadas correctamente.")
    return df


# ====================================================
# Ajustar system_category según "AL"
# ====================================================
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def adjust_system_category(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Ajustando 'system_category' según categorías tipo 'AL'...")
    if "system_category" not in df.columns:
        df["system_category"] = "DEFAULT"

    # --- 1️⃣ Detectar y marcar alarmas ---
    mask_alarm = df["category"].astype(str).str.upper().str.startswith("AL", na=False)
    total_alarms = mask_alarm.sum()
    df.loc[mask_alarm, "system_category"] = "ALARM"
    logger.info(f"{total_alarms} filas marcadas como ALARM en 'system_category'.")

    # --- 1️⃣ Detectar y marcar command ---
    mask_command = df["name"].astype(str).str.upper().str.startswith(("CONTROL", "RESET"), na=False)
    total_com = mask_command.sum()
    df.loc[mask_command, "system_category"] = "COMMAND"
    logger.info(f"{total_com} filas marcadas como COMMAND en 'system_category'.")

    # --- 1️⃣ Detectar y marcar config_parammeter ---
    mask_pa = df["name"].astype(str).str.upper().str.startswith(("P_", "NIVEL", "RESERVA","TPO", "AJUSTE", "OFFSET"), na=False)
    total_pa = mask_pa.sum()
    df.loc[mask_pa, "system_category"] = "CONFIG_PARAMETER"
    logger.info(f"{total_pa} filas marcadas como CONFIG_PARAMMETER en 'system_category'.")

    # --- 1️⃣ Detectar y marcar set_point ---
    mask_sp = df["name"].astype(str).str.upper().str.startswith("SP", na=False)
    mas_cg= df["name"].astype(str).str.upper().str.startswith("CONSIGNA", na=False)
    total_SP = mask_sp.sum() + mas_cg.sum()
    df.loc[mask_sp, "system_category"] = "SET_POINT"
    df.loc[mas_cg, "system_category"] = "SET_POINT"
    logger.info(f"{total_SP} filas marcadas como SET_POINT en 'system_category'.")

    # --- 2️⃣ Ajustar otras categorías ---
    if 'category' in df.columns:
        # Limpiar texto de la columna category
        df['category'] = df['category'].astype(str).str.upper().str.strip()

        # Mapeo de categorías
        mapping = {
            'ANALOGICAS': 'ANALOG_OUTPUT',
            'CONTROL_EQUIPOS': 'DIGITAL_OUTPUT',
            'ESTADO_EQUIPOS': 'STATUS',
        }

        # Reemplazo basado en category
        mask_sys = df['category'].isin(mapping.keys())
        total_sys = mask_sys.sum()
        df.loc[mask_sys, 'system_category'] = df.loc[mask_sys, 'category'].map(mapping)

        # Eliminar valores no válidos
        df = df[~df['system_category'].isin(['NONE', '', 'NAN', None])].copy()

        logger.info(f"{total_sys} filas ajustadas en 'system_category'.")

    return df

def _apply_view_rules(df: pd.DataFrame) -> pd.DataFrame:
    df.loc[df['system_category'] == 'STATUS', 'view'] = 'basic'
    df.loc[df['system_category'] == 'ALARM', 'view'] = 'simple'
    view = {
        'ALARM': 'simple',
        'SET_POINT': "simple",
        'DEFAULT': "simple",
        'COMMAND': "simple",
        'STATUS': "basic",
        'DIGITAL_OUTPUT': "simple",
        'CONFIG_PARAMETER': "simple",
        'SYSTEM': 'simple'
    }
    df['view'] = df['system_category'].map(view).fillna('simple')
    return df

def _apply_length_rules(df: pd.DataFrame) -> pd.DataFrame:
    length = {
        'ALARM': '1bit',
        'SET_POINT': "f32cdab",
        'DEFAULT': "s16",
        'COMMAND': "1bit",
        'STATUS': "f32cdab",
        'DIGITAL_OUTPUT':"f32cdab",
        'CONFIG_PARAMETER': "f32cdab",
        'SYSTEM': 's16'
    }
    df['length'] = df['system_category'].map(length).fillna('s16')
    return df

def _apply_sampling_rules(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {"ALARM": 30, "SET_POINT": 300, "DEFAULT": 0, "COMMAND": 0, "STATUS": 60, "SYSTEM": 0, "CONFIG_PARAMETER":0}
    df["sampling"] = df["system_category"].map(mapping).fillna(0)

     # Agregar sufijo solo a duplicados (primer valor tiene índice 0)
    if "system_category" in df.columns:
        system_type = df['system_category'].astype(str).str.upper().str.strip()
        df["tags"] = np.where(system_type.isin(["SYSTEM"]), '["library_identifier"]', "[]")
    
    if "name" in df.columns:
        # Eliminar espacios y asegurar tipo string
        df["name"] = df["name"].astype(str).str.strip()
        
        # Contar repeticiones
        duplicates = df.groupby("name").cumcount()
        
        # Agregar sufijo solo a duplicados (primer valor tiene índice 0)
        df["name"] = np.where(
            duplicates == 0,
            df["name"],
            df["name"] + "_" + (duplicates + 1).astype(str)
        )
    
    return df

def _apply_mask_logic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna máscaras (mask) a filas donde 'length' contiene 'BIT'.
    
    Regla:
        Cada fila marcada como 'BIT' recibe una máscara binaria secuencial:
        0x1, 0x2, 0x4, ..., 0x8000
        Si hay más de 16 filas 'BIT', reinicia el conteo desde 0x1.
    """
    logger.info("=== Iniciando proceso de asignación de máscaras por 'length' = BIT ===")
    df["mask"] = "0x0"
    df = df.copy()

    # Validar columnas
    if "length" not in df.columns:
        logger.warning("No se encontró la columna 'length'. No se aplicarán máscaras.")
        return df

    # Asegurar que exista la columna mask
    if "mask" not in df.columns:
        df["mask"] = np.nan

    # Normalizar la columna length
    df["length"] = df["length"].astype(str).str.upper().str.strip()

    # Filas con 'BIT'
    mask_bit = df["length"].str.contains("BIT", na=False)
    total_bits = mask_bit.sum()

    if total_bits == 0:
        logger.info("No se encontraron filas con 'length' = BIT. No se asignaron máscaras.")
        return df

    logger.info(f"Total de filas 'BIT' detectadas: {total_bits}")

    # Generar máscaras 0x1, 0x2, 0x4, ..., 0x8000 (reinicia cada 16)
    masks = [f"0x{1 << (i % 16):X}" for i in range(total_bits)]

    # Asignar las máscaras a las filas correspondientes
    df.loc[mask_bit, "mask"] = masks

    logger.info(f"✅ Máscaras asignadas a {total_bits} filas con 'length' = BIT")
    logger.info("=== Finalizado proceso de asignación de máscaras ===")

    return df


def _process_access_permissions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajusta los permisos de lectura y escritura según 'access_type' y 'system_category'.
    Valores por defecto:
      read = 0 (sin lectura)
      write = 0 (sin escritura)
    """

    # Asegurar columnas
    if "read" not in df.columns:
        df["read"] = 0
    if "write" not in df.columns:
        df["write"] = 0
    df.columns = df.columns.astype(str).str.strip()

    # === 1️⃣ Reglas basadas en 'access_type' ===
    if "access_type" in df.columns:
        access = df["access_type"].astype(str).str.upper().str.strip()

        df.loc[access == "R", "read"] = 4
        df.loc[access == "W", "write"] = 6
        df.loc[access == "R/W", ["read", "write"]] = [4, 6]

        df.drop(columns=["access_type"], inplace=True, errors="ignore")

    # === 2️⃣ Reglas adicionales según 'system_category' ===
    if "system_category" in df.columns:
        system_type = df["system_category"].astype(str).str.upper().str.strip()

        df.loc[system_type == "ALARM", "read"] = 1
        df.loc[system_type == "STATUS", "read"] = 4
        df.loc[system_type == "COMMAND", ["read", "write"]] = [0, 6]
        df.loc[system_type == "DIGITAL_OUTPUT", ["read", "write"]] = [1, 5]
        df.loc[system_type == "SET_POINT", ["read", "write"]] = [3, 6]
        df.loc[system_type == "CONFIG_PARAMETER", ["read", "write"]] = [1, 5]
        df.loc[system_type == "ANALOG_OUTPUT", "read"] = 3
        df.loc[system_type == "SYSTEM", ["read", "write"]] = [3, 0]

    # === 3️⃣ Limpieza y conversión segura ===
    for col in ["read", "write"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    logger.info("✅ Permisos de acceso procesados correctamente.")
    return df

def _apply_range_rules(df: pd.DataFrame) -> pd.DataFrame:
    
    # --- 0️⃣ Validación general ---
    if "system_category" in df.columns:
        system_type = df["system_category"].astype(str).str.upper().str.strip()

        # Corrige: comparación múltiple debe hacerse con isin()
        mask_digital = system_type.isin(["DIGITAL_OUTPUT", "STATUS"])
        df.loc[mask_digital, ["minvalue", "maxvalue"]] = [0, 1]

    # --- 1️⃣ Detectar y marcar alarmas ---
    mask_alarm = df["category"].astype(str).str.upper().str.startswith("AL", na=False)
    total_alarms = mask_alarm.sum()
    df.loc[mask_alarm, ["minvalue", "maxvalue"]] = [0, 1]

    # --- 2️⃣ Detectar y marcar command ---
    mask_command = df["name"].astype(str).str.upper().str.startswith(("CONTROL", "RESET"), na=False)
    total_com = mask_command.sum()
    df.loc[mask_command, ["minvalue", "maxvalue"]] = [0, 1]

    # --- 3️⃣ Detectar y marcar ANALOG_OUTPUT ---
    mask_analog_output = df["system_category"].astype(str).str.upper().eq("ANALOG_OUTPUT")

    # Si empieza con TEMP → [-270, 270]
    mask_temp = mask_analog_output & df["name"].astype(str).str.upper().str.startswith("TEMP", na=False)
    df.loc[mask_temp, ["minvalue", "maxvalue"]] = [-270, 270]

    # Si es ANALOG_OUTPUT pero no empieza con TEMP → [0, 9999]
    mask_analog_other = mask_analog_output & ~df["name"].astype(str).str.upper().str.startswith("TEMP", na=False)
    df.loc[mask_analog_other, ["minvalue", "maxvalue"]] = [0, 9999]

    # --- 4️⃣ Detectar y marcar CONFIG_PARAMETER ---
    mask_pa = df["system_category"].astype(str).str.upper().eq("CONFIG_PARAMETER")

    # NIVEL → [0, 100]
    mask_ni = mask_pa & df["name"].astype(str).str.upper().str.startswith("NIVEL", na=False)
    df.loc[mask_ni, ["minvalue", "maxvalue"]] = [0, 100]

    # P_, RESERVA, TPO, AJUSTE, OFFSET → [0, 9999]
    mask_p_re_tpo = mask_pa & df["name"].astype(str).str.upper().str.startswith(
        ("P_", "RESERVA", "TPO", "AJUSTE", "OFFSET"), na=False
    )
    df.loc[mask_p_re_tpo, ["minvalue", "maxvalue"]] = [0, 9999]

    # --- 5️⃣ Detectar y marcar set_point ---
    mask_sp = df["name"].astype(str).str.upper().str.startswith("SP", na=False)
    mask_cg = df["name"].astype(str).str.upper().str.startswith("CONSIGNA", na=False)
    total_SP = mask_sp.sum() + mask_cg.sum()
    df.loc[mask_sp | mask_cg, ["minvalue", "maxvalue"]] = [0, 9999]

    return df

def _apply_unit_rules(df: pd.DataFrame) -> pd.DataFrame:
    
    # --- 0️⃣ Validación general ---
    if "system_category" not in df.columns or "name" not in df.columns:
        return df

    system_type = df["system_category"].astype(str).str.upper().str.strip()
    name_upper = df["name"].astype(str).str.upper().str.strip()

    # --- 1️⃣ Detectar y marcar ANALOG_OUTPUT ---
    mask_analog_output = system_type.eq("ANALOG_OUTPUT")

    # --- 2️⃣ Asignar unidades según el tipo ---
    # PRESION → bar
    mask_presion = mask_analog_output & name_upper.str.contains("PRESION", na=False)
    df.loc[mask_presion, "unit"] = "bar"

    # TEMP → ºC
    mask_temp = mask_analog_output & name_upper.str.contains("TEMP", na=False)
    df.loc[mask_temp, "unit"] = "ºC"

    # CAUDALIMETRO → m3/s
    mask_caudal = mask_analog_output & name_upper.str.contains("CAUDALIMETRO", na=False)
    df.loc[mask_caudal, "unit"] = "m3/s"

    return df

# ====================================================
# Función principal
# ====================================================
def process_pdf(pdf_content: bytes) -> pd.DataFrame:
    logger.info("Procesando archivo PDF con backend Cefa...")
    pdf_io = BytesIO(pdf_content)
    tablas = []

    with pdfplumber.open(pdf_io) as pdf:
        for pagina in pdf.pages:
            for tabla in pagina.extract_tables():
                df = pd.DataFrame(tabla)
                if not df.empty:
                    tablas.append(df)

    if not tablas:
        logger.warning("No se encontraron tablas válidas en el PDF.")
        return pd.DataFrame(columns=LIBRARY_COLUMNS)

    df = pd.concat(tablas, ignore_index=True)
    logger.info(f"Concatenadas {len(tablas)} tablas con {len(df)} filas totales.")

    raw_headers = list(df.iloc[0])
    clean_headers = [(h if h is not None else "").strip() for h in raw_headers]
    seen = {}
    final_headers = []
    for h in clean_headers:
        if h not in seen:
            seen[h] = 0
            final_headers.append(h)
        else:
            seen[h] += 1
            final_headers.append(f"{h}_{seen[h]}")

    df.columns = final_headers
    df = df.drop(index=[0], errors="ignore").reset_index(drop=True)
    df = df.rename(columns=COLUMN_MAPPING_PDF)

    for col in ["minvalue", "maxvalue", "offset"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["register", "name", "description", "unit"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = apply_read_write_flags(df)
    df = propagate_context(df)
    df = propagate_empty_register_category(df)
    df = adjust_system_category(df)
    df = _apply_view_rules(df)
    df = _apply_sampling_rules(df)
    df = _process_access_permissions(df)
    df = _apply_range_rules(df)
    df = _apply_unit_rules(df)
    df = _apply_mask_logic(df)
    df= _apply_length_rules(df)

    for col in LIBRARY_COLUMNS:
        if col not in df.columns:
            df[col] = DEFAULT_VALUES.get(col, "")

    df["id"] = range(1, len(df) + 1)
    df = df.reindex(columns=LIBRARY_COLUMNS)

    # ======= Debug detallado para columna 'register' =======
    if "register" in df.columns:
        logger.info(f"✅ Columna 'register' encontrada.")
        logger.info(f"Tipo de 'register': {df['register'].dtype}")
        logger.info(f"Primeros 10 valores: {df['register'].head(10).tolist()}")
        logger.info(f"Valores únicos (máx 20): {df['register'].unique()[:20]}")
        logger.info(f"Cantidad de valores nulos: {df['register'].isna().sum()}")
    else:
        logger.warning("⚠️ La columna 'register' NO existe después del renombrado")

    logger.info(f"Procesamiento completado: {len(df)} filas finales.")
    return df


# ====================================================
# Script ejecutable
# ====================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python cefa.py <archivo.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"❌ El archivo {pdf_path} no existe.")
        sys.exit(1)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    df = process_pdf(pdf_bytes)

    if df is None or df.empty:
        print("⚠️ No se extrajo ninguna tabla del PDF.")
        sys.exit(0)

    print("\n✅ Primeras filas del DataFrame:")
    print(df.head())

    excel_path = pdf_path.with_suffix(".xlsx")
    df.to_excel(excel_path, index=False, engine="openpyxl")
    print(f"\n📘 Datos exportados a Excel: {excel_path}")
