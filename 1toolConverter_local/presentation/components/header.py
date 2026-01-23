from nicegui import ui

def create_header():
    """Renderiza el header de la aplicación."""
    with ui.header().classes('bg-slate-800 text-white shadow-md q-py-sm items-center justify-between'):
        with ui.row().classes('items-center gap-3 q-pl-md'):
            ui.icon('library_books', size='md').classes('text-blue-400')
            with ui.column().classes('gap-0'):
                ui.label('Creador de Librerías').classes('text-xl font-bold tracking-tight')
                ui.label('Herramienta de conversión y gestión').classes('text-xs text-slate-400')
        ui.label('v1.0').classes('q-pr-md text-slate-500 text-xs')