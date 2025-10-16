from nicegui import ui
import pandas as pd
import uuid

# Estado global (frontend-only)
df_data = pd.DataFrame()
table = None
classification_options = [
    'ANALOG_INPUT', 'DIGITAL_INPUT', 'ANALOG_OUTPUT', 'DIGITAL_OUTPUT',
    'COMMAND', 'SET_POINT', 'ALARM', 'CONFIG_PARAMETER'
]

# Columnas por defecto que mostrará la UI (minimales)
DISPLAY_COLUMNS = ['register', 'name', 'description', 'system_category', 'read', 'write', 'sampling', '_id']


@ui.page('/')
def main_page():
    global table

    # Ensure responsive and contained table view
    ui.add_head_html('<style>.nicegui-table { max-height: 70vh; overflow: auto; }</style>')

    with ui.header().classes('items-center justify-between bg-blue-600 text-white'):
        ui.label('Frontend: Clasificador de Variables (NiceGUI)').classes('text-xl font-medium')

    with ui.column().classes('w-full items-center gap-4 p-4'):

        with ui.row().classes('items-center gap-6 justify-center w-full'):
            ui.label('1. Carga de Datos:').classes('text-lg font-bold text-gray-700')
            ui.upload(
                label='Seleccionar archivo (no procesado)',
                auto_upload=True,
                on_upload=handle_upload,
                max_file_size=10_000_000
            ).classes('w-60 shadow-lg')

            # Botón para llenar datos de ejemplo (frontend-only)
            ui.button(
                'Llenar datos de ejemplo', 
                on_click=fill_sample_data,
                icon='data_object'
            ).classes('w-48 bg-green-500 hover:bg-green-600 text-white shadow-lg')

        ui.separator().classes('w-full')

        ui.label('2. Tabla editable (Clasificación)').classes('text-lg font-bold text-gray-700')

        with ui.card().classes('w-full max-w-7xl shadow-xl'):
            ui.label('Edita las celdas directamente. La columna "System Category" usa un desplegable.').classes('text-gray-600 mb-2')
            
            # Crear aggrid vacío y guardar referencia
            table_local = ui.aggrid({
                'columnDefs': [{'headerName': 'Carga datos de ejemplo', 'field': 'info'}],
                'rowData': [],
                'rowSelection': 'multiple',
                'defaultColDef': {'resizable': True, 'sortable': True, 'filter': True, 'editable': True} # Default editable set to true
            }).classes('nicegui-table')
            globals()['table'] = table_local

            with ui.row().classes('mt-4 gap-3 justify-start w-full'):
                ui.button('Añadir fila', on_click=add_empty_row, icon='add').classes('w-36 bg-blue-500 hover:bg-blue-600')
                ui.button('Borrar filas', on_click=delete_selected_rows, icon='delete').classes('w-48 bg-red-500 hover:bg-red-600')
                ui.button('Exportar (simulado)', on_click=export_simulated, icon='download').classes('w-48 bg-indigo-500 hover:bg-indigo-600')

        ui.separator().classes('w-full')

        ui.label('3. Notas').classes('text-lg font-bold text-gray-700')
        ui.markdown('''
- Esta vista es **frontend-only** (sin conexión a base de datos).
- **Importante:** Utiliza el botón **"Llenar datos de ejemplo"** para inicializar la tabla y probar la edición.
- El botón **"Exportar (simulado)"** vuelca los datos actuales de la tabla a la consola del servidor.
''').classes('text-sm text-gray-600 w-full max-w-7xl p-2 rounded-lg bg-gray-100')


async def handle_upload(e):
    """Maneja la subida del archivo pero NO lo procesa ni parsea."""
    fname = getattr(e, 'filename', '<sin nombre>')
    fsize = getattr(e, 'size', 'desconocido')
    
    # Simple size calculation for notification
    fsize_display = f"{fsize} bytes" if isinstance(fsize, int) else "tamaño desconocido"

    ui.notify(f'Archivo subido: {fname} ({fsize_display}). Atención: No se procesa automáticamente en esta demo.', 
              duration=5, type='info')


def make_empty_df():
    """Crea un DataFrame vacío con las columnas esperadas."""
    cols = DISPLAY_COLUMNS.copy()
    df = pd.DataFrame(columns=cols)
    return df


def sample_dataframe():
    """Datos de ejemplo frontend-only."""
    data = {
        'register': [40001, 40002, 40003, 40004, 40005],
        'name': ['Temp_1', 'Press_2', 'Flow_3', 'Valve_4', 'Motor_CMD'],
        'description': ['Sensor de temperatura del proceso', 'Sensor de presión de la línea', 'Caudalímetro principal', 'Válvula de salida del tanque', 'Comando de arranque de motor'],
        'system_category': ['ANALOG_INPUT', 'ANALOG_INPUT', 'ANALOG_INPUT', 'DIGITAL_OUTPUT', 'COMMAND'],
        'read': [True, True, True, False, False],
        'write': [False, False, False, True, True],
        'sampling': [1.0, 0.5, 0.2, 0.1, 0.0],
    }
    df = pd.DataFrame(data)
    df['_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df


async def fill_sample_data():
    """Puebla la UI con datos de ejemplo (frontend-only)."""
    global df_data
    df_data = sample_dataframe()
    await update_table()
    ui.notify('Datos de ejemplo cargados en la tabla.', type='positive', icon='check')


async def update_table():
    """Actualiza la tabla aggrid desde df_data."""
    global table, df_data

    if table is None:
        print('Tabla no inicializada.')
        return

    if df_data is None or df_data.empty:
        # Update options dictionary directly and call update()
        table.options['columnDefs'] = [{'headerName': 'Sin datos', 'field': 'none'}]
        table.options['rowData'] = []
        table.update()
        return

    display_columns = [c for c in DISPLAY_COLUMNS if c in df_data.columns]

    column_defs = []
    for col in display_columns:
        col_def = {'headerName': col.replace('_', ' ').title(), 'field': col, 'sortable': True, 'filter': True}
        
        if col == '_id':
            col_def.update({'hide': True, 'editable': False})
        elif col == 'system_category':
            col_def.update({
                'editable': True,
                'cellEditor': 'agSelectCellEditor',
                'cellEditorParams': {'values': classification_options},
                'minWidth': 180
            })
        elif col in ['register', 'name', 'description']:
            col_def.update({'editable': True, 'minWidth': 140})
        elif col == 'sampling':
             col_def.update({'editable': True, 'minWidth': 100, 'type': 'numericColumn'})
        elif col in ['read', 'write']:
            col_def.update({
                'editable': True, 
                'cellEditor': 'agSelectCellEditor',
                'cellEditorParams': {'values': [True, False]}, 
                'minWidth': 100
            })
        
        # Ensure default editable is respected unless explicitly set otherwise
        if col != '_id':
             col_def.setdefault('editable', True)

        column_defs.append(col_def)

    row_data = df_data.to_dict('records')
    
    # FIX: Modify the options dictionary directly and call update()
    table.options['columnDefs'] = column_defs
    table.options['rowData'] = row_data
    table.update() # Send the updates to the client


async def add_empty_row():
    """Añade una fila vacía editable."""
    global df_data
    if df_data is None or df_data.empty:
        df_data = make_empty_df()

    # Create a new row dictionary with default values for appropriate types
    new_row = {
        'register': 0, 
        'name': 'NEW_VAR', 
        'description': '', 
        'system_category': classification_options[0],
        'read': True,
        'write': False,
        'sampling': 1.0,
        '_id': str(uuid.uuid4())
    }
    
    # Ensure the new row only contains keys present in the DataFrame columns
    new_row = {k: v for k, v in new_row.items() if k in df_data.columns}

    df_data = pd.concat([df_data, pd.DataFrame([new_row])], ignore_index=True)
    await update_table()
    ui.notify('Fila añadida (edita los campos en la tabla).', duration=2, type='info')


async def delete_selected_rows():
    """Borra las filas seleccionadas en la ag-Grid (frontend-only)."""
    global df_data, table
    if table is None:
        ui.notify('La tabla no está inicializada.', type='warning')
        return

    # Fetching the current selection from the grid
    selected = await table.get_selected_rows()
    if not selected:
        ui.notify('No hay filas seleccionadas para borrar.', type='warning')
        return

    ids_to_remove = [row.get('_id') for row in selected if row.get('_id') is not None]
    
    if not ids_to_remove:
        # This handles cases where selection might be active but the ID column is missing/corrupted
        ui.notify('Error: Las filas seleccionadas no contienen identificadores internos.', type='negative')
        return

    # Update the global DataFrame
    initial_count = len(df_data)
    df_data = df_data[~df_data['_id'].isin(ids_to_remove)].reset_index(drop=True)
    deleted_count = initial_count - len(df_data)
    
    await update_table()
    ui.notify(f'Borradas {deleted_count} filas seleccionadas.', type='positive', icon='delete_forever')


async def export_simulated():
    """Simula la exportación, obtiene los datos editados y los imprime en consola."""
    global table
    if table is None:
        ui.notify('La tabla no está inicializada.', type='warning')
        return

    # get_rows() retrieves the current state of the grid data, including edits
    edited_rows = await table.get_rows()
    if not edited_rows:
        ui.notify('No hay datos para exportar.', type='warning')
        return

    df_final = pd.DataFrame(edited_rows)
    # Drop the internal '_id' column before printing/exporting
    if '_id' in df_final.columns:
        df_final = df_final.drop(columns=['_id'])

    print('\n' + '='*20 + ' EXPORT SIMULADO: Contenido Final ' + '='*20)
    # Print clean output without pandas index
    print(df_final.to_string(index=False))
    print('='*70 + '\n')
    
    ui.notify('Exportación simulada completada. Revisa la consola del servidor.', type='positive', duration=4, icon='done_all')


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Frontend: Clasificador (NiceGUI)', reload=True)
