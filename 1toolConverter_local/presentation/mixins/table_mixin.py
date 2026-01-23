from nicegui import ui
import logging

logger = logging.getLogger(__name__)

class TableMixin:
    """
    Contiene la lógica compleja para inyectar slots editables que 
    interactúan con el estado de la aplicación (self).
    """

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

