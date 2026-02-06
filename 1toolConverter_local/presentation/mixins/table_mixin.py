from nicegui import ui
import logging

logger = logging.getLogger(__name__)

class TableMixin:
    """
    Contiene la lógica compleja para inyectar slots editables que 
    interactúan con el estado de la aplicación (self).
    """

    def add_editable_slot(self, field_name: str, label: str, input_type: str = "text", max_length: int = 60, 
                          style_overrides: dict | str | None = None, input_style: str = "width: auto; min-width: 1ch;", 
                          validator=None, placeholder: str | None = None):
        
        event_name = f"{field_name}-change"
        sync_event = f"{field_name}-sync"
        slot_name = f"body-cell-{field_name}"

        if isinstance(style_overrides, dict):
            style_str = "; ".join(f"{k}: {v}" for k, v in style_overrides.items())
        elif isinstance(style_overrides, str):
            style_str = style_overrides
        else:
            style_str = "width: 100%;"
        
        placeholder_text = placeholder or ""

        # Definimos el JS para validar (Lo hacemos reutilizable para que el HTML sea legible)
        # CAMBIO 1: Usamos String() para asegurar que los números (3, 16, 0) tengan .length y pasen el regex
        js_validation = (
            f"props.row.{field_name} !== null && "
            f"String(props.row.{field_name}).length > 0 && "
            f"String(props.row.{field_name}).length <= 60 && "
            f"/^[a-zA-Z0-9\\s\\.,;:_\\-/=%°CñÑáéíóúÁÉÍÓÚ()]*$/.test(String(props.row.{field_name}))"
        )

        slot_html = f"""
        <q-td :props="props">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            
            <q-input dense outlined bg-color="white" type="{input_type}" 
              v-model="props.row.{field_name}"
              placeholder="{placeholder_text}" 
              maxlength="{max_length}" 
              style="{style_str}" 
              input-style="{input_style}"
              debounce="1000"
              @update:model-value="(val) => $parent.$emit('{sync_event}', {{id: props.row.id, val: val}})"
            />
            
            <div style="display: flex; justify-content: center;">

                <div v-if="!props.row.error_flag || props.row.error_flag == 0">
                    <q-icon name="check_circle" color="positive" size="sm">
                        <q-tooltip>Datos correctos y guardados</q-tooltip>
                    </q-icon>
                </div>

                <div v-else>
                    
                    <q-btn v-if="{js_validation}"
                        dense flat round size="sm" 
                        icon="check_circle" 
                        color="warning" 
                        disable
                    >
                        <q-tooltip class="bg-orange text-black">
                            Para guardar los cambios usar el boton "Guardar Cambios".
                        </q-tooltip>
                    </q-btn>

                    <q-btn v-else
                        dense flat round size="sm"
                        icon="cancel" 
                        color="negative"
                        @click="$parent.$emit('openError', props.row)"
                    >
                        <q-tooltip class="bg-red">Haga clic para ver errores</q-tooltip>
                    </q-btn>
                </div>

            </div>
          </div>
        </q-td>
        """
        self.table.add_slot(slot_name, slot_html)

        # --- Handlers (Sin cambios en la lógica Python) ---
        def wrapped_handler(e, fn=field_name, lbl=label):
            if validator:
                args = getattr(e, 'args', e)
                row = args if isinstance(args, dict) else args[0]
                val = row.get(fn)
                result = validator(val)
                if result is False: ui.notify(f"Valor inválido para {lbl}", type='warning'); return
                elif isinstance(result, str): ui.notify(result, type='warning'); return
            
            self.handle_field_change(e, fn, lbl)

        def sync_handler(e):
            try:
                args = e.args if isinstance(e.args, dict) else e.args[0]
                r_id = str(args.get('id'))
                val = args.get('val')
                for row in self.table.rows:
                    if str(row.get('id')) == r_id:
                        row[field_name] = val
                        break
            except Exception:
                pass 

        self.table.on(event_name, wrapped_handler)
        self.table.on(sync_event, sync_handler)