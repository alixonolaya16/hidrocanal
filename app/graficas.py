"""Gráficas técnicas con Matplotlib.

Cada función recibe un :class:`~app.modelo.Resultado` y devuelve una
``Figure``. La interfaz muestra las figuras como PNG en memoria y la memoria
de cálculo inserta las mismas imágenes.
"""

import io

import matplotlib.style
import numpy as np
from matplotlib.figure import Figure

from app.geometria import poligonos_mojados

AGUA, CRITICO, NORMAL, FONDO = "#3b82c4", "#c0392b", "#1f6f43", "#4d4d4d"
ESTILO = "default"  # sections.py activa 'ggplot' al importarse; aquí se usa el estilo base


def figura_seccion(resultado):
    """Sección transversal con la lámina de agua en el tirante normal y el crítico."""
    seccion, yn = resultado.seccion, resultado.normal["y"]
    with matplotlib.style.context(ESTILO):
        fig = Figure(figsize=(7, 4.2), layout="constrained")
        ax = fig.add_subplot()
        for i, poligono in enumerate(poligonos_mojados(seccion.contorno, yn)):
            ax.fill(poligono[:, 0], poligono[:, 1], color=AGUA, alpha=0.45,
                    label=f"Agua, yn = {yn:.3f} m" if i == 0 else None)
        ax.plot(seccion.contorno[:, 0], seccion.contorno[:, 1], color=FONDO, lw=2, label="Contorno del canal")
        _linea_superficie(ax, seccion, yn, NORMAL, "-", "Tirante normal yn")
        if resultado.critico:
            yc = resultado.critico["y"]
            _linea_superficie(ax, seccion, yc, CRITICO, "--", f"Tirante crítico yc = {yc:.3f} m")
        ax.axhline(seccion.altura, color="0.6", ls=":", lw=1, label=f"Altura del canal H = {seccion.altura:.2f} m")
        ax.set(title=f"Sección transversal {seccion.tipo.lower()}", xlabel="Ancho y (m)", ylabel="Altura z (m)")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=8, frameon=False)
    return fig


def figura_energia(resultado):
    """Curva de energía específica E–y y curva de capacidad Q–y (Manning)."""
    tabla, datos = resultado.tabla, resultado.datos
    yn = resultado.normal["y"]
    with matplotlib.style.context(ESTILO):
        fig = Figure(figsize=(8, 4.2), layout="constrained")
        ax_e, ax_q = fig.subplots(1, 2, sharey=True)

        visible = tabla["E"] <= 3 * tabla["y"].max()
        ax_e.plot(tabla["E"][visible], tabla["y"][visible], color=AGUA, lw=2, label=f"E(y), Q = {datos.Q:g} m³/s")
        ax_e.plot([0, tabla["y"].max()], [0, tabla["y"].max()], color="0.6", ls=":", label="E = y")
        ax_e.plot(resultado.normal["E"], yn, "o", color=NORMAL, label=f"Normal: E = {resultado.normal['E']:.3f} m")
        if resultado.critico:
            c = resultado.critico
            ax_e.plot(c["E"], c["y"], "s", color=CRITICO, label=f"Crítico: Emín = {c['E']:.3f} m")
        ax_e.set(title="Energía específica", xlabel="E (m)", ylabel="Tirante y (m)", xlim=(0, None), ylim=(0, None))

        ax_q.plot(tabla["Q_manning"], tabla["y"], color=AGUA, lw=2, label="Capacidad de Manning")
        ax_q.axvline(datos.Q, color="0.4", ls="--", lw=1, label=f"Q de diseño = {datos.Q:g} m³/s")
        ax_q.plot(datos.Q, yn, "o", color=NORMAL, label=f"yn = {yn:.3f} m")
        ax_q.set(title="Curva de caudal (Manning)", xlabel="Q (m³/s)", xlim=(0, None))

        for ax in (ax_e, ax_q):
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8, loc="lower right")
    return fig


def figura_perfil(resultado):
    """Perfil longitudinal de la curva de remanso (cotas respecto al fondo en x = L)."""
    perfil, datos = resultado.perfil, resultado.datos
    x, y = perfil["x"], perfil["y"]
    L, S0 = datos.longitud, datos.S0
    x_tramo = np.array([0.0, L])
    fondo, fondo_tramo = S0 * (L - x), S0 * (L - x_tramo)
    with matplotlib.style.context(ESTILO):
        fig = Figure(figsize=(8, 4), layout="constrained")
        ax = fig.add_subplot()
        ax.fill_between(x, fondo, fondo + y, color=AGUA, alpha=0.35)
        ax.plot(x, fondo + y, color=AGUA, lw=2, label=f"Superficie del agua (perfil {perfil['tipo']})")
        ax.plot(x_tramo, fondo_tramo, color=FONDO, lw=2.5, label=f"Fondo, S0 = {S0:g}")
        ax.plot(x_tramo, fondo_tramo + resultado.normal["y"], color=NORMAL, ls="-.", lw=1.2, label="Tirante normal")
        if resultado.critico:
            ax.plot(x_tramo, fondo_tramo + resultado.critico["y"], color=CRITICO, ls="--", lw=1.2, label="Tirante crítico")
        ax.plot(x_tramo, fondo_tramo + resultado.seccion.altura, color="0.6", ls=":", label="Borde del canal")
        x_control = L if perfil["control"] == "aguas abajo" else 0.0
        ax.plot(x_control, S0 * (L - x_control) + datos.y_control, "v", color="k", ms=8,
                label=f"Control ({perfil['control']}), y = {datos.y_control:g} m")
        ax.set(title=f"Curva de remanso {perfil['tipo']}", xlabel="Distancia x (m, sentido del flujo →)",
               ylabel="Cota (m)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False)
    return fig


def figuras(resultado):
    """Diccionario con todas las figuras del resultado."""
    salida = {"seccion": figura_seccion(resultado), "energia": figura_energia(resultado)}
    if resultado.perfil is not None:
        salida["perfil"] = figura_perfil(resultado)
    return salida


def a_png(figura, dpi=130):
    """Convierte una figura en una imagen PNG (bytes)."""
    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", dpi=dpi)
    return buffer.getvalue()


def _linea_superficie(ax, seccion, y, color, estilo, etiqueta):
    """Dibuja la superficie libre de orilla a orilla para el tirante y."""
    for i, poligono in enumerate(poligonos_mojados(seccion.contorno, y)):
        extremos = poligono[[0, -1], 0]
        ax.plot(extremos, [y, y], color=color, ls=estilo, lw=1.6, label=etiqueta if i == 0 else None)
