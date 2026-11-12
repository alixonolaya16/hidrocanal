"""Ventana principal: navegación entre las vistas Cálculo e Historial."""

import flet as ft

from app import db
from app.modelo import DatosEntrada
from app.ui.comunes import avisar
from app.ui.vista_calculo import VistaCalculo
from app.ui.vista_historial import VistaHistorial


class Aplicacion:
    """Coordina las vistas y la conexión a la base de datos."""

    def __init__(self, page: ft.Page, ruta_bd=db.RUTA_BD):
        self.page = page
        self.conexion = db.conectar(ruta_bd)
        self.calculo = VistaCalculo(self)
        self.historial = VistaHistorial(self)
        self.contenido = ft.Container(expand=True, content=self.calculo.control)
        self.navegacion = ft.NavigationRail(
            selected_index=0, label_type=ft.NavigationRailLabelType.ALL, min_width=90,
            leading=ft.Column([ft.Icon(ft.Icons.WATER, size=34, color=ft.Colors.BLUE_800),
                               ft.Text("HidroCanal", weight=ft.FontWeight.BOLD)],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.CALCULATE, label="Cálculo"),
                ft.NavigationRailDestination(icon=ft.Icons.HISTORY, label="Historial"),
            ],
            on_change=self._navegar,
        )

    def construir(self):
        self.page.title = "HidroCanal · Flujo uniforme en canales"
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.window.width, self.page.window.height = 1400, 900
        self.page.window.min_width, self.page.window.min_height = 1000, 650
        self.page.add(ft.Row([self.navegacion, ft.VerticalDivider(width=1), self.contenido], expand=True, spacing=0))
        self.refrescar_proyectos()

    def mostrar_vista(self, indice):
        self.navegacion.selected_index = indice
        self.contenido.content = (self.calculo, self.historial)[indice].control
        if indice == 1:
            self.historial.refrescar()
        self.page.update()

    def refrescar_proyectos(self):
        """Actualiza la lista de proyectos en ambas vistas y la tabla del historial."""
        proyectos = db.listar_proyectos(self.conexion)
        self.calculo.actualizar_proyectos(proyectos)
        self.historial.actualizar_proyectos(proyectos)
        self.historial.refrescar()

    def abrir_calculo(self, calculo):
        """Carga un cálculo guardado en la vista Cálculo y lo recalcula."""
        self.calculo.cargar_entradas(DatosEntrada.desde_dict(calculo["entradas"]), calculo["proyecto_id"], calculo["nombre"])
        self.mostrar_vista(0)
        if self.calculo.calcular() is not None:
            avisar(self.page, f"Cálculo '{calculo['nombre']}' (id {calculo['id']}) reabierto.")
            self.page.update()

    def _navegar(self, e):
        self.mostrar_vista(e.control.selected_index)


def main(page: ft.Page):
    Aplicacion(page).construir()
