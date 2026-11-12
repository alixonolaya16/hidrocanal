"""Vista "Cálculo": formulario de entrada, resultados, chequeos y gráficas."""

import sqlite3

import flet as ft

from app import db
from app.geometria import TIPOS, ErrorDatos, leer_coordenadas
from app.graficas import a_png, figuras
from app.modelo import DatosEntrada, analizar
from app.reporte import generar_memoria
from app.ui.comunes import (ROJO, VERDE, avisar, campo_numero, dialogo_memoria, estado, fila, leer_numero,
                            seguro, tabla, titulo)

# Campos de geometría que usa cada tipo de sección
CAMPOS_POR_TIPO = {
    "Rectangular": ("b", "H"),
    "Trapezoidal": ("b", "m", "H"),
    "Triangular": ("m", "H"),
    "Circular": ("D",),
    "Natural": ("coordenadas",),
}
GEOMETRIA_INICIAL = {"b": "1.5", "m": "1.5", "H": "1.5", "D": "1.0"}  # al cambiar de tipo, si están vacíos
EJEMPLO_NATURAL = "0 3.0\n2 1.2\n4 0.4\n6 0.0\n8 0.5\n11 1.0\n14 3.2"
VALORES_INICIALES = DatosEntrada(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008,
                                 y_control=1.25, longitud=1500)


class VistaCalculo:
    """Formulario de entrada y panel de resultados."""

    def __init__(self, app):
        self.app, self.page = app, app.page
        self.resultado = None
        evento = seguro(self.page)

        # --- Datos generales ---
        self.proyecto = ft.Dropdown(label="Proyecto", expand=True, dense=True)
        self.nombre = ft.TextField(label="Nombre del cálculo", value="Canal principal K0+000", dense=True)
        self.tipo = ft.Dropdown(label="Tipo de sección", value="Trapezoidal", dense=True,
                                options=[ft.DropdownOption(key=t, text=t) for t in TIPOS],
                                on_select=evento(self._cambiar_tipo))

        # --- Geometría ---
        self.geometria = {
            "b": campo_numero("Ancho de fondo b", "m", ancho=170),
            "m": campo_numero("Talud m (H:V)", "H:V", ancho=170),
            "H": campo_numero("Altura del canal H", "m", ancho=170),
            "D": campo_numero("Diámetro D", "m", ancho=170),
            "coordenadas": ft.TextField(label="Coordenadas y z (m), una pareja por línea", multiline=True,
                                        min_lines=5, max_lines=8, value=EJEMPLO_NATURAL, dense=True,
                                        helper="Orilla izquierda a derecha, punto decimal."),
        }
        # --- Datos hidráulicos y criterios ---
        self.Q = campo_numero("Caudal Q", "m³/s", ancho=170)
        self.n = campo_numero("Manning n", "s·m^-1/3", ancho=170, ayuda="Concreto: 0.013 a 0.017")
        self.S0 = campo_numero("Pendiente S0", "m/m", ancho=170)
        self.v_min = campo_numero("V mínima", "m/s", ancho=112)
        self.v_max = campo_numero("V máxima", "m/s", ancho=112)
        self.borde_libre = campo_numero("Borde libre", "m", ancho=112)
        # --- Remanso ---
        self.remanso = ft.Switch(label="Calcular curva de remanso", on_change=evento(self._cambiar_remanso))
        self.y_control = campo_numero("Tirante de control", "m", ancho=170)
        self.longitud = campo_numero("Longitud del tramo", "m", ancho=170)

        self.formulario = ft.Container(
            width=390, padding=ft.Padding.all(12), bgcolor=ft.Colors.GREY_50,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=10, controls=[
                titulo("Datos generales", ft.Icons.FOLDER_OPEN),
                ft.Row([self.proyecto, ft.IconButton(ft.Icons.CREATE_NEW_FOLDER, tooltip="Nuevo proyecto",
                                                     on_click=evento(self._nuevo_proyecto))]),
                self.nombre,
                titulo("Sección transversal", ft.Icons.WATER),
                self.tipo,
                ft.Row([self.geometria["b"], self.geometria["m"]], wrap=True),
                ft.Row([self.geometria["H"], self.geometria["D"]], wrap=True),
                self.geometria["coordenadas"],
                titulo("Datos hidráulicos", ft.Icons.WATER_DROP),
                ft.Row([self.Q, self.n], wrap=True),
                self.S0,
                titulo("Criterios de diseño", ft.Icons.RULE),
                ft.Row([self.v_min, self.v_max, self.borde_libre], wrap=True, spacing=6),
                titulo("Flujo gradualmente variado", ft.Icons.SHOW_CHART),
                self.remanso,
                ft.Row([self.y_control, self.longitud], wrap=True),
                ft.Row(wrap=True, spacing=8, controls=[
                    ft.FilledButton("Calcular", icon=ft.Icons.CALCULATE, on_click=evento(self.calcular)),
                    ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=evento(self.guardar)),
                    ft.Button("Memoria .docx", icon=ft.Icons.DESCRIPTION, on_click=evento(self.memoria)),
                    ft.TextButton("Valores de ejemplo", icon=ft.Icons.RESTART_ALT, on_click=evento(self.restablecer)),
                ]),
            ]),
        )

        # --- Resultados ---
        self.mensaje_inicial = ft.Text("Ingrese los datos y presione Calcular.", italic=True, color=ft.Colors.GREY_700)
        self.tarjetas = ft.Row(wrap=True, spacing=8)
        self.tabla_resultados = tabla(["Propiedad", "Tirante normal", "Tirante crítico", "Unidad"],
                                      numericas=("Tirante normal", "Tirante crítico"))
        self.tabla_chequeos = tabla(["Criterio", "Valor", "Límite", "Estado"])
        self.advertencias = ft.Column(spacing=2)
        self.imagenes = {clave: ft.Image(src=b"", width=760, visible=False) for clave in ("seccion", "energia", "perfil")}
        self.panel_resultados = ft.Column(visible=False, spacing=12, controls=[
            self.tarjetas,
            titulo("Propiedades hidráulicas", ft.Icons.TABLE_CHART),
            ft.Row([self.tabla_resultados], scroll=ft.ScrollMode.AUTO),
            titulo("Chequeos de diseño", ft.Icons.FACT_CHECK),
            ft.Row([self.tabla_chequeos], scroll=ft.ScrollMode.AUTO),
            self.advertencias,
            titulo("Gráficas", ft.Icons.INSIGHTS),
            *self.imagenes.values(),
        ])
        self.control = ft.Row(expand=True, vertical_alignment=ft.CrossAxisAlignment.START, controls=[
            self.formulario,
            ft.Container(expand=True, padding=ft.Padding.all(16), content=ft.Column(
                scroll=ft.ScrollMode.AUTO, expand=True,
                controls=[ft.Text("Resultados", size=22, weight=ft.FontWeight.BOLD), self.mensaje_inicial,
                          self.panel_resultados])),
        ])
        self.cargar_entradas(VALORES_INICIALES)

    # ------------------------------------------------------------------ eventos

    def calcular(self, e=None):
        """Lee y valida el formulario, ejecuta el modelo y muestra los resultados.
        Devuelve el resultado, o None si hay datos inválidos."""
        self._limpiar_errores()
        try:
            datos = self._leer_formulario()
            self.resultado = analizar(datos)
        except ErrorDatos as error:
            self._campo(error.campo).error = str(error)
            self._ocultar_resultados()
            avisar(self.page, str(error), error=True)
        except ValueError:
            self._ocultar_resultados()
            avisar(self.page, "Revise los campos marcados en rojo.", error=True)
        else:
            self._mostrar(self.resultado)
        self.page.update()
        return self.resultado

    def guardar(self, e=None):
        if self.calcular() is None:
            return
        if not self.proyecto.value:
            self.proyecto.error_text = "Seleccione o cree un proyecto"
            avisar(self.page, "Seleccione un proyecto o cree uno con el botón de carpeta.", error=True)
        elif not self.nombre.value.strip():
            self.nombre.error = "Escriba un nombre"
            avisar(self.page, "Escriba el nombre del cálculo.", error=True)
        else:
            nuevo_id = db.guardar_calculo(self.app.conexion, int(self.proyecto.value), self.nombre.value, self.resultado)
            self.app.historial.refrescar()
            avisar(self.page, f"Cálculo guardado con id {nuevo_id}.")
        self.page.update()

    def memoria(self, e=None):
        if self.calcular() is None:
            return
        proyecto = db.obtener_proyecto(self.app.conexion, int(self.proyecto.value)) if self.proyecto.value else None
        datos_proyecto = dict(proyecto) if proyecto else {"nombre": "Sin proyecto", "ubicacion": "", "responsable": ""}
        ruta = generar_memoria(self.resultado, datos_proyecto, {"nombre": self.nombre.value.strip() or "Cálculo"})
        dialogo_memoria(self.page, ruta)

    def restablecer(self, e=None):
        self.cargar_entradas(VALORES_INICIALES)
        self.page.update()

    def cargar_entradas(self, datos, proyecto_id=None, nombre=None):
        """Llena el formulario con un :class:`DatosEntrada` (por ejemplo, uno guardado)."""
        self._limpiar_errores()
        self.tipo.value = datos.tipo
        for clave in ("b", "m", "H", "D"):
            valor = getattr(datos, clave)
            self.geometria[clave].value = "" if valor is None else f"{valor:g}"
        if datos.coordenadas:
            self.geometria["coordenadas"].value = "\n".join(f"{y:g} {z:g}" for y, z in datos.coordenadas)
        for campo, valor in ((self.Q, datos.Q), (self.n, datos.n), (self.S0, datos.S0), (self.v_min, datos.v_min),
                             (self.v_max, datos.v_max), (self.borde_libre, datos.borde_libre),
                             (self.y_control, datos.y_control), (self.longitud, datos.longitud)):
            campo.value = "" if valor is None else f"{valor:g}"
        self.remanso.value = datos.remanso
        if proyecto_id is not None:
            self.proyecto.value = str(proyecto_id)
        if nombre is not None:
            self.nombre.value = nombre
        self._cambiar_tipo()
        self._cambiar_remanso()

    def actualizar_proyectos(self, proyectos):
        self.proyecto.options = [ft.DropdownOption(key=str(p["id"]), text=p["nombre"]) for p in proyectos]
        if self.proyecto.value not in {str(p["id"]) for p in proyectos}:
            self.proyecto.value = str(proyectos[0]["id"]) if proyectos else None

    # ------------------------------------------------------------------ apoyo

    def _leer_formulario(self):
        """Construye DatosEntrada; marca todos los campos inválidos antes de fallar."""
        tipo = self.tipo.value
        valores, fallo = {}, False
        lecturas = [(clave, self.geometria[clave], True) for clave in CAMPOS_POR_TIPO[tipo] if clave != "coordenadas"]
        lecturas += [("Q", self.Q, True), ("n", self.n, True), ("S0", self.S0, True), ("v_min", self.v_min, True),
                     ("v_max", self.v_max, True), ("borde_libre", self.borde_libre, True)]
        if self.remanso.value:
            lecturas += [("y_control", self.y_control, True), ("longitud", self.longitud, True)]
        for clave, campo, obligatorio in lecturas:
            try:
                valores[clave] = leer_numero(campo, obligatorio)
            except ValueError:
                fallo = True
        if fallo:
            raise ValueError("datos inválidos")
        if tipo == "Natural":
            valores["coordenadas"] = leer_coordenadas(self.geometria["coordenadas"].value or "")
        return DatosEntrada(tipo=tipo, remanso=bool(self.remanso.value), **valores)

    def _mostrar(self, r):
        normal, critico = r.normal, r.critico
        self.mensaje_inicial.visible = False
        self.panel_resultados.visible = True
        self.tarjetas.controls = [
            _tarjeta("Tirante normal yn", f"{normal['y']:.3f} m"),
            _tarjeta("Tirante crítico yc", f"{critico['y']:.3f} m" if critico else "—"),
            _tarjeta("Velocidad V", f"{normal['V']:.3f} m/s"),
            _tarjeta("Froude Fr", f"{normal['Fr']:.3f}"),
            _tarjeta("Régimen", normal["regimen"]),
            _tarjeta("Pendiente", r.pendiente),
            _tarjeta("Diseño", "CUMPLE" if r.cumple else "NO CUMPLE", VERDE if r.cumple else ROJO),
        ]
        filas = [("Área mojada A", "A", "m²", 4), ("Perímetro mojado P", "P", "m", 4), ("Radio hidráulico R", "R", "m", 4),
                 ("Ancho superficial T", "T", "m", 4), ("Velocidad V", "V", "m/s", 4), ("Número de Froude", "Fr", "—", 4),
                 ("Energía específica E", "E", "m", 4), ("Fuerza específica M", "M", "m³", 4),
                 ("Pendiente de fricción Sf", "Sf", "m/m", 6)]
        self.tabla_resultados.rows = [
            fila(nombre, f"{normal[k]:.{d}f}", f"{critico[k]:.{d}f}" if critico else "—", u) for nombre, k, u, d in filas
        ]
        self.tabla_chequeos.rows = [
            fila(c["criterio"], f"{c['valor']:.3f} {c['unidad']}", c["limite"], estado(c["cumple"])) for c in r.chequeos
        ]
        avisos = list(r.advertencias)
        if r.perfil:
            avisos.insert(0, f"Curva de remanso {r.perfil['tipo']} con control {r.perfil['control']}.")
        self.advertencias.controls = [ft.Text(f"• {a}", color=ft.Colors.BLUE_GREY_700) for a in avisos]

        graficas = figuras(r)
        for clave, imagen in self.imagenes.items():
            imagen.visible = clave in graficas
            if imagen.visible:
                imagen.src = a_png(graficas[clave])

    def _ocultar_resultados(self):
        """Evita mostrar resultados que ya no corresponden a los datos del formulario."""
        self.resultado = None
        self.panel_resultados.visible = False
        self.mensaje_inicial.visible = True

    def _nuevo_proyecto(self, e=None):
        nombre = ft.TextField(label="Nombre del proyecto", autofocus=True)
        ubicacion = ft.TextField(label="Ubicación")
        responsable = ft.TextField(label="Responsable")

        def crear(e):
            if not nombre.value or not nombre.value.strip():
                nombre.error = "Escriba un nombre"
                self.page.update()
                return
            try:
                nuevo = db.crear_proyecto(self.app.conexion, nombre.value, ubicacion.value or "", responsable.value or "")
            except sqlite3.IntegrityError:
                nombre.error = "Ya existe un proyecto con ese nombre"
                self.page.update()
                return
            self.page.pop_dialog()
            self.app.refrescar_proyectos()
            self.proyecto.value, self.proyecto.error_text = str(nuevo), None
            avisar(self.page, f"Proyecto '{nombre.value.strip()}' creado.")
            self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Nuevo proyecto"),
            content=ft.Column([nombre, ubicacion, responsable], tight=True, width=380),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Crear", on_click=seguro(self.page)(crear))],
        ))

    def _cambiar_tipo(self, e=None):
        visibles = CAMPOS_POR_TIPO[self.tipo.value]
        for clave, campo in self.geometria.items():
            campo.visible = clave in visibles
            if campo.visible and not campo.value:
                campo.value = GEOMETRIA_INICIAL.get(clave, EJEMPLO_NATURAL)
        if e is not None:  # cambio hecho por el usuario: los resultados anteriores ya no aplican
            self._ocultar_resultados()
            self.page.update()

    def _cambiar_remanso(self, e=None):
        for campo in (self.y_control, self.longitud):
            campo.disabled = not self.remanso.value
        if e is not None:
            self.page.update()

    def _campo(self, clave):
        campos = {**self.geometria, "Q": self.Q, "n": self.n, "S0": self.S0, "v_min": self.v_min, "v_max": self.v_max,
                  "borde_libre": self.borde_libre, "y_control": self.y_control, "longitud": self.longitud}
        return campos.get(clave, self.Q)

    def _limpiar_errores(self):
        for campo in (*self.geometria.values(), self.Q, self.n, self.S0, self.v_min, self.v_max,
                      self.borde_libre, self.y_control, self.longitud, self.nombre):
            campo.error = None
        self.proyecto.error_text = None


def _tarjeta(etiqueta, valor, color=None):
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=ft.BorderRadius.all(8),
        bgcolor=ft.Colors.BLUE_GREY_50, width=150,
        content=ft.Column([ft.Text(etiqueta, size=11, color=ft.Colors.GREY_700),
                           ft.Text(valor, size=17, weight=ft.FontWeight.BOLD, color=color)], spacing=2, tight=True),
    )
