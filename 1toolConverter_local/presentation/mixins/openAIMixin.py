import asyncio
import os
from openai import AsyncOpenAI
from nicegui import ui
import pandas as pd
from dotenv import load_dotenv
from backend.General.logic import validate_description_text

load_dotenv()

class OpenAIMixin:
    """
    Maneja la lógica de corrección y rellenado usando OpenAI.
    """

    def _get_openai_client(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            ui.notify(" Falta la API Key (Configure .env)", type='negative')
            return None
        return AsyncOpenAI(api_key=api_key)

    async def _process_batch_ai(self, rows_to_process, system_prompt, user_prompt_template, field_name='description', source_column=None):
        """
        Versión Estética con Porcentaje Correcto (0-100%).
        """
        client = self._get_openai_client()
        if not client: return

        total = len(rows_to_process)
        count = 0

        # --- 1. SETUP UI (Diseño Moderno) ---
        loading_dialog = ui.dialog().props('persistent backdrop-filter="blur(4px)"')
        
        with loading_dialog, ui.card().classes('w-96 shadow-2xl rounded-2xl items-center p-6 bg-white'):
            # Icono animado o destacado
            ui.icon('auto_awesome', size='3em', color='blue-9').classes('q-mb-sm')
            
            ui.label("Procesando...").classes("text-xl font-bold text-gray-800")
            ui.label("Por favor espera, no cierres esta ventana.").classes("text-xs text-gray-400 q-mb-md")
            
            # Contenedor de la barra y porcentajes
            with ui.column().classes('w-full q-my-md'):
                # Fila con etiquetas encima de la barra
                with ui.row().classes('w-full justify-between items-end q-mb-xs'):
                    status_label = ui.label("Iniciando...").classes("text-xs text-gray-500 font-medium")
                    percent_label = ui.label("0%").classes("text-sm font-bold text-blue-9")

                # Barra de progreso
                progress_bar = ui.linear_progress(value=0).props(
                    'size="10px" rounded color="blue-9" track-color="blue-2"'
                )
            
            # Spinner pequeño abajo
            ui.spinner('dots', size='lg', color='blue-7')

        loading_dialog.open()
        await asyncio.sleep(0.1)

        # --- 2. BUCLE ---
        for index, row in rows_to_process.iterrows():
            row_id = str(row['id'])
            
            col_to_read = source_column if source_column else field_name
            input_val = row.get(col_to_read, '')
            
            # Saltamos vacíos pero actualizamos contador para que la barra avance
            if not input_val or pd.isna(input_val):
                count += 1
                # Actualizar barra incluso si saltamos
                pct = count / total
                progress_bar.value = pct
                percent_label.text = f"{int(pct * 100)}%"
                continue

            prompt = user_prompt_template.format(val=input_val)

            try:
                # LLAMADA API
                response = await client.chat.completions.create(
                    model="gpt-4o-mini", 
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=80,
                    temperature=0.3
                )
                
                # PROCESAR
                raw_new_val = response.choices[0].message.content.strip()
                new_val = raw_new_val.strip('"').strip("'")
                if len(new_val) > 60: new_val = new_val[:60]
                
                print(f"ID {row_id} | '{input_val}' -> '{new_val}'")

                # GUARDAR
                mask = self.processed_data['id'].astype(str) == row_id
                if mask.any():
                    self.processed_data.loc[mask, field_name] = new_val
                    if self.grouped_data is not None:
                         mask_g = self.grouped_data['id'].astype(str) == row_id
                         self.grouped_data.loc[mask_g, field_name] = new_val

                    # VALIDAR
                    validation_result = validate_description_text(new_val)
                    flag = 0 if (validation_result is True) else 1
                    
                    self.processed_data.loc[mask, 'error_flag'] = flag
                    if self.grouped_data is not None:
                        mask_g = self.grouped_data['id'].astype(str) == row_id
                        self.grouped_data.loc[mask_g, 'error_flag'] = flag

                # --- 3. ACTUALIZAR UI ---
                count += 1
                percentage = count / total  # Esto da 0.0 a 1.0 (necesario para la barra)
                
                # Actualizamos barra (0.0 - 1.0)
                progress_bar.value = percentage
                
                # Actualizamos texto (0 - 100)
                percent_label.text = f"{int(percentage * 100)}%"
                
                # Actualizamos estado
                status_label.text = f"Procesando: {count} / {total}"
                
                if count % 2 == 0:
                    self.refresh_table_view()
                    await asyncio.sleep(0.01)

            except Exception as e:
                print(f"Error IA en fila {row_id}: {e}")
                count += 1
                continue

        # FIN
        loading_dialog.close()
        self.update_error_counter()
        self.refresh_table_view()
        if hasattr(self, 'update_group_table'):
            self.update_group_table()
            
        ui.notify(f" Completado: {count} filas procesadas.", type='positive')
    
    async def ai_fix_errors(self):
        if self.processed_data is None: return
        rows_with_errors = self.processed_data[self.processed_data['error_flag'] == 1]
        
        if rows_with_errors.empty:
            ui.notify(" No hay errores pendientes.", type='positive')
            return

        system_prompt = (
            "Eres un experto en limpieza de datos. "
            "Corrige la descripción técnica. "
            "REGLAS: Máx 50 caracteres. Solo A-Z, 0-9 y . , ; : _ - / ( ) "
            "Devuelve SOLO el texto limpio."
        )
        # Solo usamos {val}
        user_template = "CORREGIR: '{val}'"
        
        await self._process_batch_ai(rows_with_errors, system_prompt, user_template)

    # --- FEATURE #4: RELLENAR VACÍOS (Modificada) ---
    async def ai_fill_empty(self):
        """
        Busca descripciones vacías y las genera usando el campo 'Name'.
        """
        if self.processed_data is None: return

        # 1. Filtramos donde 'description' está vacía
        mask = (self.processed_data['description'].isna()) | (self.processed_data['description'] == '')
        empty_rows = self.processed_data[mask]
        
        if empty_rows.empty:
            ui.notify("No hay celdas vacías para rellenar.", type='warning')
            return

        # 2. Verificamos que exista la columna 'Name' (o como se llame en tu Excel)
        source_col = 'name' 
        if source_col not in self.processed_data.columns:
            ui.notify(f"Error: No encuentro la columna '{source_col}' para basarme.", type='negative')
            return

        # 3. Prompt específico para generar desde cero
        system_prompt = (
            "Eres un experto técnico en empresa Industrias de Tecnologías Aplicadas de Refrigeración y Conservación. "
            "Tu tarea: Generar una descripción técnica concisa (máx 60 chars) basada en el NOMBRE del producto. "
            "Reglas: "
            "1. Usa abreviaturas estándar si es largo. "
            "2. Prioriza: ¿Que es? o ¿Para que sirve?. "
            "3. Elimina palabras como 'Oferta', 'Nuevo'. "
            "Devuelve SOLO la descripción."
        )
        
        user_template = "Descripción: '{val}'"
        
        # 4. Llamamos pasando source_column='Name'
        await self._process_batch_ai(
            rows_to_process=empty_rows, 
            system_prompt=system_prompt, 
            user_prompt_template=user_template,
            field_name='description',   # Donde escribimos
            source_column=source_col    # De donde leemos (Name)
        )