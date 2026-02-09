import asyncio
import os
import re
import pandas as pd
from nicegui import ui
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Tu Regex definida
ALLOWED_CHARS_REGEX = r"[^a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]"
load_dotenv()

class OpenAIMixin:
    
    def _get_openai_client(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            ui.notify("Falta la API Key", type='negative')
            return None
        return AsyncOpenAI(api_key=api_key)

    async def _call_openai_simple(self, client, system_msg, user_msg):
        """Helper simple para una llamada a OpenAI"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=20,
                temperature=0.3
            )
            return response.choices[0].message.content.strip().strip('"').strip("'")
        except Exception as e:
            print(f"Error OpenAI: {e}")
            return None

    def _validate_chars(self, text):
        """Valida si el texto cumple con los caracteres permitidos"""
        if not text: return False
        cleaned = re.sub(ALLOWED_CHARS_REGEX, "", text)
        # Si al limpiar queda igual que el original, es válido.
        # También verificamos que no sea una cadena vacía después de limpiar.
        return cleaned == text and len(cleaned) > 0

    async def ai_fix_errors(self):
        """
        Lógica inteligente: 
        1. Intenta limpiar/parafrasear la descripción.
        2. Si falla o queda vacía, genera una nueva basada en el NOMBRE.
        """
        if self.processed_data is None: return
        
        # Filtramos filas con error (flag == 1)
        rows_to_process = self.processed_data[self.processed_data['error_flag'] == 1]
        
        if rows_to_process.empty:
            ui.notify("No hay errores pendientes.", type='positive')
            return

        client = self._get_openai_client()
        if not client: return

        total = len(rows_to_process)
        count = 0

        # --- UI SETUP ---
        loading_dialog = ui.dialog().props('persistent backdrop-filter="blur(4px)"')
        with loading_dialog, ui.card().classes('w-96 items-center p-6'):
            ui.label("Corrección Inteligente IA").classes("text-xl font-bold")
            status_label = ui.label("Iniciando...")
            progress_bar = ui.linear_progress(value=0).props('color="blue-9"')
            ui.spinner('dots', size='lg')
        
        loading_dialog.open()
        await asyncio.sleep(0.1)

        # --- PROMPTS ---
        
        # PROMPT 1: Limpieza
        system_clean = (
            "Eres un técnico experto. Extrae y limpia descripciones. "
            "REGLA DE ORO: Máximo 55 caracteres. Es un límite estricto de espacio. "
            "INSTRUCCIONES: "
            "1. Usa estilo telegrama: omite artículos (el, la, los) y usa abreviaturas. "
            "2. Ejemplo: 'Control de ventiladores' -> 'Ctrl ventiladores'. "
            "3. Usa SOLO: a-z, 0-9 y . , ; : _ - / = % ° ( ) "
            "4. Si es INVALIDO devuelve esa palabra."
        )

        # PROMPT 2: Generación
        system_generate = (
            "Genera una descripción técnica de MÁXIMO 55 CARACTERES. "
            "Sé ultra conciso. Usa abreviaturas (Temp, Ctrl, Comp, Vel, Act). "
            "Usa SOLO: a-z, 0-9 y . , ; : _ - / = % ° ( )"
        )

        # --- BUCLE DE PROCESAMIENTO ---
        for index, row in rows_to_process.iterrows():
            row_id = str(row['id'])
            original_desc = str(row.get('description', ''))
            row_name = str(row.get('name', '')) # Necesario para el fallback

            new_val = ""
            origin = "Fixed"

            # INTENTO 1: Corregir la descripción existente
            prompt_user = f"LIMPIAR: '{original_desc}'"
            cleaned_text = await self._call_openai_simple(client, system_clean, prompt_user)

            # Validamos longitud y caracteres
            is_valid = False
            if cleaned_text and cleaned_text != "INVALIDO":
                # Si la IA se pasó por poco, la truncamos nosotros
                if len(cleaned_text) > 55:
                    cleaned_text = cleaned_text[:55].strip()
                    
                if self._validate_chars(cleaned_text):
                    new_val = cleaned_text
                    is_valid = True
            
            # INTENTO 2 (FALLBACK): Si falló lo anterior, usamos el NOMBRE
            if not is_valid:
                print(f"ID {row_id} | Falló limpieza de '{original_desc}'. Intentando generar desde Name: '{row_name}'")
                prompt_user_gen = f"Generar descripción para: '{row_name}'"
                generated_text = await self._call_openai_simple(client, system_generate, prompt_user_gen)
                
                # Validamos de nuevo (incluso lo generado por IA puede tener alucinaciones)
                if self._validate_chars(generated_text):
                    new_val = generated_text
                    origin = "Generated"
                else:
                    # Si falla todo, dejamos un placeholder seguro
                    new_val = "Revisar Manualmente"
            
            # --- GUARDADO ---
            print(f"ID {row_id} | Final ({origin}): '{new_val}'")
            
            mask = self.processed_data['id'].astype(str) == row_id
            if mask.any():
                self.processed_data.loc[mask, 'description'] = new_val
                # Validamos formalmente para quitar el flag de error
                # Como ya pasó el _validate_chars, sabemos que es True, 
                # a menos que sea "Revisar Manualmente" que fallará el regex si no admites espacios
                if self._validate_chars(new_val):
                     self.processed_data.loc[mask, 'error_flag'] = 0
                
                if self.grouped_data is not None:
                     mask_g = self.grouped_data['id'].astype(str) == row_id
                     self.grouped_data.loc[mask_g, 'description'] = new_val
                     if self._validate_chars(new_val):
                        self.grouped_data.loc[mask_g, 'error_flag'] = 0

            # --- UI UPDATE ---
            count += 1
            pct = count / total
            progress_bar.value = pct
            status_label.text = f"Procesando: {count}/{total}"
            if count % 2 == 0: await asyncio.sleep(0.01)

        loading_dialog.close()
        self.update_error_counter()
        self.refresh_table_view()
        if hasattr(self, 'update_group_table'): self.update_group_table()
        ui.notify(f"Proceso finalizado. {count} filas revisadas.", type='positive')

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
            "Tu tarea: Generar una descripción técnica concisa basada en el NOMBRE del producto. "
            "Reglas: "
            "1. Usa abreviaturas estándar si es largo. "
            "2. Prioriza: ¿Que es? o ¿Para que sirve?. "
            "3. Elimina palabras como 'Oferta', 'Nuevo'. "
            "Devuelve SOLO la descripción."
            "Usa SOLO letras, números y: . , ; : _ - / = % ° ( ) "
            "Máximo 55 caracteres."
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