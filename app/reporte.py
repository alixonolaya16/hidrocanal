"""Memoria de cálculo en Word con docxtpl a partir de ``plantillas/memoria.docx``."""

import io
import re
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage

from app.graficas import a_png, figuras

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLA = RAIZ / "plantillas" / "memoria.docx"
CARPETA_REPORTES = RAIZ / "reportes"
FILAS_TABLA = 12

DESCRIPCION_GEOMETRIA = {
    "b": ("Ancho de fondo", "b", "m"),
    "m": ("Talud (horizontal : vertical)", "m", "H:V"),
    "H": ("Altura del canal", "H", "m"),
    "D": ("Diámetro", "D", "m"),
}


def generar_memoria(resultado, proyecto, calculo, ruta_salida=None):
    """Genera la memoria .docx y devuelve su ruta.

    ``proyecto``: dict con nombre, ubicacion y responsable.
    ``calculo``: dict con nombre y, si ya está guardado, id y fecha.
    """
    plantilla = DocxTemplate(PLANTILLA)
    contexto = contexto_memoria(resultado, proyecto, calculo)
    contexto.update({
        f"fig_{clave}": InlineImage(plantilla, io.BytesIO(a_png(figura, dpi=200)), width=Mm(160))
        for clave, figura in figuras(resultado).items()
    })
    plantilla.render(contexto)

    if ruta_salida is None:
        CARPETA_REPORTES.mkdir(exist_ok=True)
        ruta_salida = CARPETA_REPORTES / f"memoria_{_nombre_archivo(calculo['nombre'])}.docx"
    plantilla.save(ruta_salida)
    return Path(ruta_salida)


def contexto_memoria(resultado, proyecto, calculo):
    """Variables de la plantilla (sin imágenes)."""
    d, normal, critico = resultado.datos, resultado.normal, resultado.critico
    return {
        "proyecto": proyecto,
        "calculo": calculo,
        "fecha_emision": date.today().isoformat(),
        "tipo_seccion": d.tipo.lower(),
        "entradas": _entradas(resultado),
        "coordenadas": [{"i": i, "y": f"{y:.3f}", "z": f"{z:.3f}"}
                        for i, (y, z) in enumerate(resultado.seccion.contorno, start=1)] if d.tipo == "Natural" else [],
        "resultados": _resultados(normal, critico),
        "tabla": _tabla_hidraulica(resultado.tabla),
        "chequeos": [{**c, "valor": f"{c['valor']:.3f} {c['unidad']}".strip(),
                      "estado": "CUMPLE" if c["cumple"] else "NO CUMPLE"} for c in resultado.chequeos],
        "cumple": resultado.cumple,
        "caudal": f"{d.Q:g}",
        "incumplidos": [c["criterio"].lower() for c in resultado.chequeos if not c["cumple"]],
        "yn": f"{normal['y']:.3f}", "yc": f"{critico['y']:.3f}" if critico else "—",
        "V": f"{normal['V']:.3f}", "Fr": f"{normal['Fr']:.3f}",
        "regimen": normal["regimen"].lower(), "pendiente": resultado.pendiente.lower(),
        "remanso": resultado.perfil is not None,
        "perfil": _perfil(resultado) if resultado.perfil is not None else {},
        "advertencias": resultado.advertencias,
    }


def _entradas(resultado):
    d = resultado.datos
    filas = [
        {"descripcion": "Tipo de sección", "simbolo": "—", "valor": d.tipo, "unidad": "—"},
    ]
    for clave, valor in resultado.seccion.parametros.items():
        if clave in DESCRIPCION_GEOMETRIA:
            descripcion, simbolo, unidad = DESCRIPCION_GEOMETRIA[clave]
            filas.append({"descripcion": descripcion, "simbolo": simbolo, "valor": f"{valor:g}", "unidad": unidad})
    filas += [
        {"descripcion": "Caudal de diseño", "simbolo": "Q", "valor": f"{d.Q:g}", "unidad": "m³/s"},
        {"descripcion": "Coeficiente de rugosidad de Manning", "simbolo": "n", "valor": f"{d.n:g}", "unidad": "s/m^(1/3)"},
        {"descripcion": "Pendiente longitudinal", "simbolo": "S0", "valor": f"{d.S0:g}", "unidad": "m/m"},
        {"descripcion": "Velocidad mínima permitida", "simbolo": "Vmín", "valor": f"{d.v_min:g}", "unidad": "m/s"},
        {"descripcion": "Velocidad máxima permitida", "simbolo": "Vmáx", "valor": f"{d.v_max:g}", "unidad": "m/s"},
        {"descripcion": "Borde libre mínimo", "simbolo": "BL", "valor": f"{d.borde_libre:g}", "unidad": "m"},
    ]
    if d.remanso:
        filas += [
            {"descripcion": "Tirante en la sección de control", "simbolo": "y0", "valor": f"{d.y_control:g}", "unidad": "m"},
            {"descripcion": "Longitud del tramo", "simbolo": "L", "valor": f"{d.longitud:g}", "unidad": "m"},
        ]
    return filas


def _resultados(normal, critico):
    filas = [
        ("Tirante", "y", "y", "m", 4),
        ("Área mojada", "A", "A", "m²", 4),
        ("Perímetro mojado", "P", "P", "m", 4),
        ("Radio hidráulico", "R", "R", "m", 4),
        ("Ancho superficial", "T", "T", "m", 4),
        ("Velocidad media", "V", "V", "m/s", 4),
        ("Número de Froude", "Fr", "Fr", "—", 4),
        ("Energía específica", "E", "E", "m", 4),
        ("Fuerza específica", "M", "M", "m³", 4),
        ("Profundidad del centroide", "ȳ", "ybar", "m", 4),
        ("Pendiente de fricción", "Sf", "Sf", "m/m", 6),
    ]
    return [{
        "descripcion": descripcion, "simbolo": simbolo, "unidad": unidad,
        "normal": f"{normal[clave]:.{dec}f}",
        "critico": f"{critico[clave]:.{dec}f}" if critico else "—",
    } for descripcion, simbolo, clave, unidad, dec in filas]


def _tabla_hidraulica(tabla):
    """FILAS_TABLA tirantes repartidos entre el 10 % y el 100 % de la altura."""
    ultimo = len(tabla["y"]) - 1
    indices = np.linspace(ultimo // 10, ultimo, FILAS_TABLA).round().astype(int)
    return [{
        "y": f"{tabla['y'][i]:.3f}", "A": f"{tabla['A'][i]:.4f}", "P": f"{tabla['P'][i]:.3f}",
        "R": f"{tabla['R'][i]:.4f}", "T": f"{tabla['T'][i]:.3f}", "V": f"{tabla['V'][i]:.3f}",
        "Fr": f"{tabla['Fr'][i]:.3f}", "E": f"{tabla['E'][i]:.3f}", "Q": f"{tabla['Q_manning'][i]:.3f}",
    } for i in indices]


def _perfil(resultado):
    perfil = resultado.perfil
    x, y = perfil["x"], perfil["y"]
    indices = np.linspace(0, len(x) - 1, min(10, len(x))).round().astype(int)
    return {
        "tipo": perfil["tipo"], "control": perfil["control"],
        "longitud": f"{x[-1] - x[0]:.1f}", "y_max": f"{perfil['y_max']:.3f}",
        "puntos": [{"x": f"{x[i]:.1f}", "y": f"{y[i]:.3f}"} for i in indices],
    }


def _nombre_archivo(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_-]+", "_", texto.strip()).strip("_") or "calculo"
