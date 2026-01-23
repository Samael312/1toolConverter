
import logging
from nicegui import ui

logger = logging.getLogger(__name__)

def create_main_table(columns, pagination, on_pagination_change):
    """Crea la tabla principal con sus configuraciones base."""
    table = ui.table(
        columns=columns,
        rows=[],
        row_key='id',
        selection='multiple',
        pagination=pagination,
        on_pagination_change=on_pagination_change,
    ).classes('w-full').props('flat dense')
    
    return table

def inject_table_slots(table, event_handler_validation, event_handler_estado, event_handler_view):
    """Inyecta los slots HTML y CSS complejos a la tabla."""
    
    # Slot Estado (Chips de colores)
    table.add_slot('body-cell-estado', '''
    <q-td key="estado" :props="props">
        <q-select v-model="props.row.system_category" dense borderless emit-value map-options
            :options="['ALARM', 'SET_POINT', 'CONFIG_PARAMETER', 'COMMAND', 'ANALOG_INPUT', 'STATUS', 'SYSTEM']"
            @update:model-value="$parent.$emit('estado-change', props.row)">
            <template v-slot:selected-item="scope">
                <q-chip dense :style="{backgroundColor: '#94a3b8', color: 'white'}"> 
                    {{ props.row.system_category }} 
                </q-chip>
            </template>
        </q-select>
    </q-td>
    ''')
    table.on('estado-change', event_handler_estado)

    # Slot View (Badges)
    table.add_slot('body-cell-view', '''
    <q-td key="view" :props="props">
        <q-select v-model="props.row.view" dense borderless emit-value map-options
            :options="['basic', 'simple', 'primary']"
            @update:model-value="$parent.$emit('view-change', props.row)">
             <template v-slot:selected-item="scope">
                <q-badge color="blue">{{ props.row.view }}</q-badge>
            </template>
        </q-select>
    </q-td>
    ''')
    table.on('view-change', event_handler_view)
    
def add_editable_slot(self, field_name: str, label: str, input_type: str = "text", max_length: int = 150, 
                          style_overrides: dict | str | None = None, input_style: str = "width: auto; min-width: 1ch;", 
                          validator=None, placeholder: str | None = None):
        # ... (LÓGICA INTACTA, SOLO AJUSTES VISUALES EN HTML)
        event_name = f"{field_name}-change"
        slot_name = f"body-cell-{field_name}"

        if isinstance(style_overrides, dict):
            style_str = "; ".join(f"{k}: {v}" for k, v in style_overrides.items())
        elif isinstance(style_overrides, str):
            style_str = style_overrides
        else:
            style_str = "width: 100%;"

        placeholder_text = placeholder or ""
        slot_html = f"""
        <q-td :props="props">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <q-input dense outlined bg-color="white" type="{input_type}" v-model="props.row.{field_name}"
              placeholder="{placeholder_text}" maxlength="{max_length}" style="{style_str}" input-style="{input_style}" />
            <q-btn dense flat round size="sm" 
              :icon="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? 'check_circle' : 'cancel'" 
              :color="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? 'positive' : 'negative'" 
              @click="props.row.description && props.row.description.length <= 60 && /^[a-zA-Z0-9\s\.,;:_\-/=%°CñÑáéíóúÁÉÍÓÚ()]*$/.test(props.row.description) ? $parent.$emit('{event_name}', props.row) :$parent.$emit('openError', props.row)"
            />
          </div>
        </q-td>
        """
        self.table.add_slot(slot_name, slot_html)

        def wrapped_handler(e, fn=field_name, lbl=label):
            self.toggle_error_filter(e)
            self.update_error_counter()
            if validator:
                args = getattr(e, 'args', e)
                row = args if isinstance(args, dict) else args[0]
                val = row.get(fn)
                result = validator(val)
                if result is False: ui.notify(f"Valor inválido para {lbl}", type='warning'); return
                elif isinstance(result, str): ui.notify(result, type='warning'); return
            self.handle_field_change(e, fn, lbl)

        self.table.on(event_name, wrapped_handler)

        logger.info(f"✅ Slot editable '{field_name}' registrado (tipo={input_type})")


