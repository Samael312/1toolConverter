from nicegui import ui

def create_header():
    """Renderiza el header de la aplicación."""
    with ui.header().classes('bg-slate-800 text-white shadow-md q-py-sm items-center justify-between'):
        with ui.row().classes('items-center gap-3 q-pl-md'):
            ui.image('/logo/ki_fav.png').classes('w-8 h-8')
            with ui.column().classes('gap-0'):
                ui.label('kiCreator').classes('text-xl font-bold tracking-tight')
                ui.label('Herramienta de creación de librerías').classes('text-xs text-slate-400')
        #ui.label('v1.0').classes('q-pr-md text-slate-500 text-xs')