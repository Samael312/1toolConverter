from io import BytesIO
from typing import List, Optional
import pandas as pd
import numpy as np
from nicegui import ui


# --- Procesamiento de datos ---

LIBRARY_COLUMNS = [
    "id", "register", "name", "description", "system_category", "category", "view",
    "sampling", "read", "write", "minvalue", "maxvalue", "unit", "offset",
    "addition", "mask", "value", "length", "general_icon", "alarm", "metadata",
    "l10n", "tags", "type", "parameter_write_byte_position", "mqtt", "json",
    "current_value", "current_error_status", "notes"
]

COLUMN_MAPPING = {
    'BMS Address': 'register',
    'Variable name': 'name',
    'Description': 'description',
    'Min': 'minvalue',
    'Max': 'maxvalue',
    'Category': 'category',
    'UOM': 'unit',
    'Bms_Ofs': 'offset',
    'Bms_Type': 'system_category',
}

uploaded_file_content: Optional[bytes] = None
processed_data: Optional[pd.DataFrame] = None


def process_html(html_content: bytes) -> Optional[pd.DataFrame]:
    html_io = BytesIO(html_content)
    try:
        list_of_dataframes: List[pd.DataFrame] = pd.read_html(html_io, header=0, flavor='bs4')
    except Exception as e:
        ui.notify(f"Error al procesar el archivo HTML: {e}", type='negative')
        return None

    if not list_of_dataframes or len(list_of_dataframes) < 2:
        ui.notify("No se encontraron tablas válidas para exportar.", type='warning')
        return None

    processed_dfs = []
    try:
        for df in list_of_dataframes[1:]:
            df.columns = df.columns.astype(str).str.strip()
            if not df.empty and not str(df.iloc[0, 0]).strip().isdigit():
                df = df.iloc[1:].copy()
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            access_col_name = next((n for n in ['Read/Write', 'Direction'] if n in df.columns), None)
            current_mapping = COLUMN_MAPPING.copy()
            if access_col_name:
                current_mapping[access_col_name] = 'access_type'
            df.rename(columns=current_mapping, inplace=True, errors='ignore')

            if 'access_type' in df.columns:
                df['read'] = np.where(df['access_type'].astype(str).str.contains('R', case=False), 4, 0)
                df['write'] = np.where(df['access_type'].astype(str).str.contains('W', case=False), 4, 0)
                df.drop(columns=['access_type'], inplace=True, errors='ignore')
            else:
                df['read'], df['write'] = 0, 0

            if 'offset' in df.columns:
                df['offset'] = pd.to_numeric(df['offset'].astype(str).str.strip()
                                             .replace(['', '---', 'nan'], np.nan), errors='coerce').fillna(0.0)
            if 'unit' in df.columns:
                df['unit'] = df['unit'].astype(str).str.strip().replace(['0', '---', None], np.nan).fillna(' ')
            if 'category' in df.columns:
                df['category'] = df['category'].astype(str).str.upper().str.strip()
                df.loc[df['category'] == 'ALARMS', 'system_category'] = 'ALARM'
            if 'system_category' in df.columns:
                df['system_category'] = df['system_category'].astype(str).str.upper().str.strip()
                conditions = {
                    'ANALOG': {'read': 3, 'write': 16, 'sampling': 60},
                    'INTEGER': {'read': 3, 'write': 16, 'sampling': 60},
                    'DIGITAL': {'read': 1, 'write': 5, 'sampling': 60},
                    'ALARM': {'read': 4, 'write': 0, 'sampling': 30},
                }
                for key, vals in conditions.items():
                    for col, val in vals.items():
                        df.loc[df['system_category'] == key, col] = val

            for col in ['minvalue', 'maxvalue']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.strip()
                                            .replace(['', '---', 'nan'], np.nan), errors='coerce')

            df['length'] = '16bit'
            if 'minvalue' in df.columns and 'maxvalue' in df.columns:
                df.loc[(df['minvalue'] < 0) | (df['maxvalue'] < 0), 'length'] = 's16'

            processed_dfs.append(df)

        final_df = pd.concat(processed_dfs, ignore_index=True)
        final_df["id"] = range(1, len(final_df) + 1)
        final_df["view"] = "simple"

        defaults = {
            "addition": 0, "mask": 0, "value": 0,
            "alarm": """ {"severity":"none"} """,
            "metadata": "[]",
            "l10n": '{"_type":"l10n","default_lang":"en_US","translations":{"en_US":{"name":null,"_type":"languages","description":null}}}',
            "tags": "[]", "type": "modbus"
        }
        for c, v in defaults.items():
            if c not in final_df.columns:
                final_df[c] = v

        return final_df.reindex(columns=LIBRARY_COLUMNS)

    except Exception as e:
        ui.notify(f"Error durante el procesamiento: {e}", type='negative')
        return None


# --- Interfaz con NiceGUI ---

def handle_upload(e):
    global uploaded_file_content
    uploaded_file_content = e.content.read()
    process_button.enable()
    show_table_button.disable()
    download_button.disable()
    table_card.visible = False
    ui.notify(f"Archivo '{e.name}' cargado.", type='info')


def process_file():
    global processed_data
    if uploaded_file_content is None:
        ui.notify("No hay archivo para procesar.", type='negative')
        return
    df = process_html(uploaded_file_content)
    if df is not None and not df.empty:
        processed_data = df
        show_table_button.enable()
        download_button.enable()
        ui.notify(f"{len(df)} parámetros procesados.", type='positive')
    else:
        processed_data = None
        show_table_button.disable()
        download_button.disable()


def display_table():
    if processed_data is None:
        ui.notify("No hay datos procesados.", type='warning')
        return
    cols = ["id", "register", "name", "description", "system_category",
            "read", "write", "offset", "unit", "length"]
    table.columns = [{'name': c, 'label': c.replace('_', ' ').title(), 'field': c, 'sortable': True} for c in cols]
    table.rows = processed_data.replace({np.nan: ''}).to_dict('records')
    table_card.visible = True


def download_excel():
    if processed_data is None or processed_data.empty:
        ui.notify("No hay datos para exportar.", type='warning')
        return
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        processed_data.to_excel(writer, sheet_name="Parametros_Unificados", index=False)
    ui.download(
        content=output.getvalue(),
        filename='parametros_convertidos.xlsx',
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    ui.notify("Descarga iniciada.", type='info')


# --- UI ---

ui.dark_mode().set_value(True)

with ui.header().classes('items-center justify-between'):
    ui.label('Conversor HTML a Parámetros').classes('text-xl font-bold')

with ui.column().classes('w-full p-4 md:p-8 items-center gap-8'):

    with ui.card().classes('w-full max-w-2xl'):
        ui.label('1. Cargar Archivo HTML').classes('text-lg font-bold')
        ui.separator()
        upload = ui.upload(label='Seleccionar o arrastrar archivo HTML', auto_upload=True, max_files=1).props('accept=".html"').classes('w-full')
        upload.on_upload(handle_upload)

    with ui.card().classes('w-full max-w-2xl'):
        ui.label('2. Procesar el Archivo').classes('text-lg font-bold')
        ui.separator()
        process_button = ui.button('Procesar Archivo', on_click=process_file, icon='play_for_work').disable()

    with ui.card().classes('w-full max-w-2xl'):
        ui.label('3. Visualizar y Descargar Resultados').classes('text-lg font-bold')
        ui.separator()
        with ui.row():
            show_table_button = ui.button('Mostrar en Tabla', on_click=display_table, icon='visibility').disable()
            download_button = ui.button('Descargar Excel', on_click=download_excel, icon='download').props('color=primary').disable()

    with ui.card().classes('w-full max-w-6xl') as table_card:
        table = ui.table(columns=[], rows=[], row_key='id').classes('w-full h-96').props('flat bordered dense')
        table_card.visible = False


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title="Conversor HTML a Excel", reload=True)
