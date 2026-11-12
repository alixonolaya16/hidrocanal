"""Vista "Historial": buscar, reabrir, comparar y eliminar cálculos guardados."""

import flet as ft

from app import db
from app.modelo import DatosEntrada, analizar
from app.reporte import generar_memoria
from app.ui.comunes import avisar, confirmar, dialogo_memoria, estado, fila, seguro, tabla, titulo

TODOS = "todos"


class VistaHistorial:
    """Tabla de cálculos guardados con filtros y acciones por fila."""

    def __init__(self, app):
        self.app, self.page = app, app.page
        self.seleccionados = set()
        evento = seguro(self.page)

        self.buscar = ft.TextField(label="Buscar por cálculo o proyecto", prefix_icon=ft.Icons.SEARCH, width=300,
                                   dense=True, on_change=evento(self.refrescar))
        self.filtro_proyecto = ft.Dropdown(label="Proyecto", width=230, dense=True, value=TODOS,
                                           on_select=evento(self.refrescar))
        self.filtro_estado = ft.Dropdown(label="Estado", width=150, dense=True, value="Todos",
                                         options=[ft.DropdownOption(key=k, text=k) for k in db.ESTADOS],
                                         on_select=evento(self.refrescar))
        self.orden = ft.Dropdown(label="Ordenar por", width=190, dense=True, value="Más recientes",
                                 options=[ft.DropdownOption(key=k, text=k) for k in db.ORDENES],
                                 on_select=evento(self.refrescar))
        self.boton_comparar = ft.Button("Comparar seleccionados", icon=ft.Icons.COMPARE_ARROWS, disabled=True,
                                        on_click=evento(self.comparar))
        self.boton_eliminar_proyecto = ft.Button("Eliminar proyecto", icon=ft.Icons.DELETE_FOREVER, disabled=True,
                                                 on_click=evento(self.eliminar_proyecto))
        self.contador = ft.Text(color=ft.Colors.GREY_700)
        self.tabla = tabla(["", "Id", "Fecha", "Proyecto", "Cálculo", "Sección", "Q (m³/s)", "yn (m)", "V (m/s)",
                            "Fr", "Diseño", "Acciones"], numericas=("Id", "Q (m³/s)", "yn (m)", "V (m/s)", "Fr"))
        self.vacio = ft.Text("No hay cálculos que coincidan con la búsqueda.", italic=True, color=ft.Colors.GREY_700)

        self.control = ft.Container(expand=True, padding=ft.Padding.all(16), content=ft.Column(
            expand=True, scroll=ft.ScrollMode.AUTO, spacing=12, controls=[
                ft.Text("Historial de cálculos", size=22, weight=ft.FontWeight.BOLD),
                ft.Row([self.buscar, self.filtro_proyecto, self.filtro_estado, self.orden], wrap=True),
                ft.Row([self.boton_comparar, self.boton_eliminar_proyecto, self.contador], wrap=True),
                ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO),
                self.vacio,
            ]))

    # ------------------------------------------------------------------ datos

    def actualizar_proyectos(self, proyectos):
        self.filtro_proyecto.options = [ft.DropdownOption(key=TODOS, text="Todos los proyectos")] + [
            ft.DropdownOption(key=str(p["id"]), text=f"{p['nombre']} ({p['num_calculos']})") for p in proyectos]
        if self.filtro_proyecto.value not in {o.key for o in self.filtro_proyecto.options}:
            self.filtro_proyecto.value = TODOS

    def refrescar(self, e=None):
        proyecto = None if self.filtro_proyecto.value in (None, TODOS) else int(self.filtro_proyecto.value)
        filas = db.buscar_calculos(self.app.conexion, self.buscar.value or "", proyecto,
                                   self.filtro_estado.value, self.orden.value)
        visibles = {f["id"] for f in filas}
        self.seleccionados &= visibles
        self.tabla.rows = [self._fila(f) for f in filas]
        self.vacio.visible = not filas
        self.contador.value = f"{len(filas)} cálculo(s)"
        self.boton_eliminar_proyecto.disabled = proyecto is None
        self._actualizar_comparar()
        self.page.update()

    def _fila(self, f):
        evento = seguro(self.page)
        casilla = ft.Checkbox(value=f["id"] in self.seleccionados, data=f["id"], on_change=evento(self._seleccionar))
        acciones = ft.Row(spacing=0, controls=[
            ft.IconButton(ft.Icons.OPEN_IN_NEW, tooltip="Reabrir en Cálculo", data=f["id"], on_click=evento(self.reabrir)),
            ft.IconButton(ft.Icons.DESCRIPTION, tooltip="Generar memoria .docx", data=f["id"], on_click=evento(self.memoria)),
            ft.IconButton(ft.Icons.DELETE, tooltip="Eliminar", icon_color=ft.Colors.RED_400, data=f["id"],
                          on_click=evento(self.eliminar)),
        ])
        return fila(casilla, f["id"], f["fecha"][:16], f["proyecto"], f["nombre"], f["tipo_seccion"], f"{f['Q']:.3f}",
                    f"{f['yn']:.3f}", f"{f['V']:.3f}", f"{f['Fr']:.3f}", estado(bool(f["cumple"])), acciones)

    # ------------------------------------------------------------------ acciones

    def reabrir(self, e):
        calculo = db.obtener_calculo(self.app.conexion, e.control.data)
        self.app.abrir_calculo(calculo)

    def memoria(self, e):
        calculo = db.obtener_calculo(self.app.conexion, e.control.data)
        resultado = analizar(DatosEntrada.desde_dict(calculo["entradas"]))
        proyecto = dict(db.obtener_proyecto(self.app.conexion, calculo["proyecto_id"]))
        ruta = generar_memoria(resultado, proyecto,
                               {"nombre": calculo["nombre"], "id": calculo["id"], "fecha": calculo["fecha"]})
        dialogo_memoria(self.page, ruta)

    def eliminar(self, e):
        calculo_id = e.control.data
        calculo = db.obtener_calculo(self.app.conexion, calculo_id)

        def borrar():
            db.eliminar_calculo(self.app.conexion, calculo_id)
            self.app.refrescar_proyectos()
            avisar(self.page, f"Cálculo {calculo_id} eliminado.")

        confirmar(self.page, "Eliminar cálculo",
                  f"¿Eliminar '{calculo['nombre']}' (id {calculo_id}) del proyecto '{calculo['proyecto']}'? "
                  "Esta acción no se puede deshacer.", borrar)

    def eliminar_proyecto(self, e):
        proyecto_id = int(self.filtro_proyecto.value)
        proyecto = db.obtener_proyecto(self.app.conexion, proyecto_id)

        def borrar():
            db.eliminar_proyecto(self.app.conexion, proyecto_id)
            self.filtro_proyecto.value = TODOS
            self.app.refrescar_proyectos()
            avisar(self.page, f"Proyecto '{proyecto['nombre']}' eliminado.")

        confirmar(self.page, "Eliminar proyecto",
                  f"¿Eliminar el proyecto '{proyecto['nombre']}' y TODOS sus cálculos? "
                  "Esta acción no se puede deshacer.", borrar)

    def comparar(self, e):
        calculos = [db.obtener_calculo(self.app.conexion, i) for i in sorted(self.seleccionados)]
        filas = [
            ("Proyecto", lambda c: c["proyecto"]), ("Sección", lambda c: c["tipo_seccion"]),
            ("Q (m³/s)", lambda c: f"{c['Q']:.3f}"), ("n", lambda c: f"{c['n']:.4f}"), ("S0 (m/m)", lambda c: f"{c['S0']:g}"),
            ("yn (m)", lambda c: f"{c['yn']:.3f}"), ("yc (m)", lambda c: f"{c['yc']:.3f}" if c["yc"] else "—"),
            ("V (m/s)", lambda c: f"{c['V']:.3f}"), ("Fr", lambda c: f"{c['Fr']:.3f}"), ("Régimen", lambda c: c["regimen"]),
            ("Diseño", lambda c: "CUMPLE" if c["cumple"] else "NO CUMPLE"),
        ]
        comparacion = tabla(["Propiedad"] + [f"{c['nombre']} (id {c['id']})" for c in calculos])
        comparacion.rows = [fila(nombre, *(valor(c) for c in calculos)) for nombre, valor in filas]
        self.page.show_dialog(ft.AlertDialog(
            title=titulo("Comparación de cálculos", ft.Icons.COMPARE_ARROWS),
            content=ft.Row([comparacion], scroll=ft.ScrollMode.AUTO, width=760),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())],
        ))

    def _seleccionar(self, e):
        if e.control.value:
            self.seleccionados.add(e.control.data)
        else:
            self.seleccionados.discard(e.control.data)
        self._actualizar_comparar()
        self.page.update()

    def _actualizar_comparar(self):
        self.boton_comparar.disabled = len(self.seleccionados) < 2
        self.boton_comparar.content = f"Comparar seleccionados ({len(self.seleccionados)})"
