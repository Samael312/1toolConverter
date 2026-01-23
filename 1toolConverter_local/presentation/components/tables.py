
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
    

