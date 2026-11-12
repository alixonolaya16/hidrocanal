"""Controles y utilidades compartidas por las vistas de la interfaz."""

import functools
import os
import subprocess
import sys
import traceback

import flet as ft

VERDE, ROJO, AZUL = ft.Colors.GREEN_700, ft.Colors.RED_700, ft.Colors.BLUE_800


def campo_numero(etiqueta, unidad, valor="", ancho=None, ayuda=None):
    """Campo de texto para un número, con su unidad al final."""
    return ft.TextField(
        label=etiqueta, suffix=unidad, value=str(valor), width=ancho, dense=True,
        keyboard_type=ft.KeyboardType.NUMBER, helper=ayuda,
    )


def leer_numero(campo, obligatorio=True):
    """Convierte el texto del campo en float. Si no es válido marca el campo
    con un mensaje de error y lanza ValueError."""
    texto = (campo.value or "").strip().replace(",", ".")
    if not texto:
        if obligatorio:
            campo.error = "Campo obligatorio"
            raise ValueError(campo.label)
        return None
    try:
        return float(texto)
    except ValueError:
        campo.error = "Número inválido"
        raise


def titulo(texto, icono=None):
    contenido = [ft.Text(texto, size=15, weight=ft.FontWeight.BOLD, color=AZUL)]
    if icono:
        contenido.insert(0, ft.Icon(icono, color=AZUL, size=20))
    return ft.Row(contenido, spacing=6)


def tabla(columnas, numericas=()):
    return ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, weight=ft.FontWeight.BOLD), numeric=c in numericas) for c in columnas],
        rows=[], column_spacing=18, data_row_min_height=32, data_row_max_height=40,
        heading_row_color=ft.Colors.BLUE_GREY_50,
        border=ft.Border.all(1, ft.Colors.BLUE_GREY_100), border_radius=ft.BorderRadius.all(6),
    )


def fila(*valores, color=None):
    return ft.DataRow(cells=[
        ft.DataCell(v if isinstance(v, ft.Control) else ft.Text(str(v), color=color)) for v in valores
    ])


def estado(cumple):
    """Texto CUMPLE / NO CUMPLE con icono y color."""
    return ft.Row([
        ft.Icon(ft.Icons.CHECK_CIRCLE if cumple else ft.Icons.CANCEL, color=VERDE if cumple else ROJO, size=18),
        ft.Text("CUMPLE" if cumple else "NO CUMPLE", color=VERDE if cumple else ROJO, weight=ft.FontWeight.BOLD),
    ], spacing=4, tight=True)


def avisar(page, mensaje, error=False):
    page.show_dialog(ft.SnackBar(
        ft.Text(mensaje, color=ft.Colors.WHITE), bgcolor=ROJO if error else ft.Colors.BLUE_GREY_800,
        duration=4000 if error else 2500,
    ))


def confirmar(page, titulo_dialogo, mensaje, al_aceptar, texto_aceptar="Eliminar"):
    """Diálogo de confirmación; ``al_aceptar`` se ejecuta solo si el usuario acepta."""
    def aceptar(e):
        page.pop_dialog()
        al_aceptar()

    page.show_dialog(ft.AlertDialog(
        modal=True, title=ft.Text(titulo_dialogo), content=ft.Text(mensaje),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(texto_aceptar, on_click=seguro(page)(aceptar), bgcolor=ROJO),
        ],
    ))


def dialogo_memoria(page, ruta):
    """Informa dónde quedó la memoria y permite abrirla."""
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Memoria de cálculo generada"),
        content=ft.Text(f"Se guardó en:\n{ruta}", selectable=True),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Abrir documento", icon=ft.Icons.OPEN_IN_NEW,
                            on_click=lambda e: (abrir_archivo(ruta), page.pop_dialog())),
        ],
    ))


def abrir_archivo(ruta):
    """Abre el archivo con el programa predeterminado del sistema operativo."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # noqa: S606 (solo existe en Windows)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)])
    except OSError:
        pass


def seguro(page):
    """Decorador para eventos: un error inesperado se informa con un mensaje
    y se registra en la consola, pero la aplicación no se cierra."""
    def decorador(funcion):
        @functools.wraps(funcion)
        def envoltura(*args, **kwargs):
            try:
                return funcion(*args, **kwargs)
            except Exception as error:  # noqa: BLE001 (última barrera de la interfaz)
                traceback.print_exc()
                avisar(page, f"Error inesperado: {error}", error=True)
                page.update()
        return envoltura
    return decorador
