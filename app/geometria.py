"""Geometría de la sección transversal del canal.

La sección se describe con su **contorno**: la línea del fondo y las paredes,
recorrida de la orilla izquierda a la derecha, con coordenadas (y, z) en metros
(y horizontal, z vertical, z = 0 en el punto más bajo). Es la misma convención
de ejes de PySection.

Para un tirante y, la parte del contorno que queda bajo la lámina de agua,
cerrada por la superficie libre, forma el polígono de la **sección mojada**.
Su área y su centroide los calcula PySection; el perímetro mojado y el ancho
superficial se calculan con NumPy, vectorizados para muchos tirantes a la vez.
"""

from dataclasses import dataclass, field

import numpy as np

from app.pysections.sections import _SinglePolygonSection

TIPOS = ("Rectangular", "Trapezoidal", "Triangular", "Circular", "Natural")
LADOS_CIRCULO = 360  # PySection trabaja con polígonos: el círculo se aproxima


class ErrorDatos(ValueError):
    """Dato de entrada inválido. ``campo`` indica qué dato lo produjo."""

    def __init__(self, campo, mensaje):
        super().__init__(mensaje)
        self.campo = campo


@dataclass
class Seccion:
    """Sección transversal definida por su contorno."""

    tipo: str
    contorno: np.ndarray        # (n, 2): puntos (y, z) de orilla izquierda a derecha
    altura: float               # profundidad máxima antes de desbordar (m)
    parametros: dict = field(default_factory=dict)


class PoligonoMojado(_SinglePolygonSection):
    """Sección mojada como polígono de PySection (sin modificar la biblioteca)."""

    def __init__(self, vertices):
        self._vertices = vertices
        super().__init__()

    def _calculate_points(self):
        return self._vertices


# ---------------------------------------------------------------------------
# Construcción de secciones
# ---------------------------------------------------------------------------

def crear_seccion(tipo, b=None, m=None, H=None, D=None, coordenadas=None):
    """Crea la sección del tipo indicado validando sus dimensiones (m)."""
    if tipo == "Rectangular":
        b, H = _positivo("b", b), _positivo("H", H)
        puntos = [(-b / 2, H), (-b / 2, 0), (b / 2, 0), (b / 2, H)]
        return Seccion(tipo, np.array(puntos, float), H, {"b": b, "H": H})
    if tipo == "Trapezoidal":
        b, m, H = _positivo("b", b), _no_negativo("m", m), _positivo("H", H)
        puntos = [(-b / 2 - m * H, H), (-b / 2, 0), (b / 2, 0), (b / 2 + m * H, H)]
        return Seccion(tipo, np.array(puntos, float), H, {"b": b, "m": m, "H": H})
    if tipo == "Triangular":
        m, H = _positivo("m", m), _positivo("H", H)
        puntos = [(-m * H, H), (0, 0), (m * H, H)]
        return Seccion(tipo, np.array(puntos, float), H, {"m": m, "H": H})
    if tipo == "Circular":
        D = _positivo("D", D)
        # Desde la clave (arriba), bajando por la izquierda y subiendo por la derecha
        theta = np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, LADOS_CIRCULO + 1)
        puntos = np.column_stack([D / 2 * np.cos(theta), D / 2 + D / 2 * np.sin(theta)])
        puntos[[0, -1]] = (0.0, D)  # elimina el error de redondeo en la clave
        return Seccion(tipo, puntos, D, {"D": D})
    if tipo == "Natural":
        puntos = _validar_natural(coordenadas)
        altura = float(min(puntos[0, 1], puntos[-1, 1]))
        return Seccion(tipo, puntos, altura, {"coordenadas": puntos.tolist()})
    raise ErrorDatos("tipo", f"Tipo de sección desconocido: {tipo}")


def leer_coordenadas(texto):
    """Convierte texto con una pareja 'y z' por línea en una lista de puntos.

    Separadores aceptados: espacio, tabulación, punto y coma o una sola coma.
    El decimal se escribe con punto.
    """
    puntos = []
    for numero, linea in enumerate(texto.strip().splitlines(), start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = linea.replace(";", " ").replace("\t", " ").split()
        if len(partes) == 1 and linea.count(",") == 1:
            partes = linea.split(",")
        try:
            y, z = (float(p) for p in partes)
        except ValueError:
            raise ErrorDatos(
                "coordenadas", f"Línea {numero}: escriba dos números 'y z' (se leyó '{linea}')."
            ) from None
        puntos.append((y, z))
    return puntos


# ---------------------------------------------------------------------------
# Propiedades de la sección mojada
# ---------------------------------------------------------------------------

def poligonos_mojados(contorno, y):
    """Polígonos de agua para el tirante ``y`` (uno por cada tramo sumergido).

    Recorre el contorno y conserva los puntos bajo la lámina, agregando las
    intersecciones con la superficie libre al entrar y salir del agua.
    """
    poligonos, actual = [], None
    for (y1, z1), (y2, z2) in zip(contorno[:-1], contorno[1:]):
        dentro1, dentro2 = z1 < y, z2 < y
        if dentro1 and actual is None:
            actual = [(y1, z1)]
        if dentro1 != dentro2:
            t = (y - z1) / (z2 - z1)
            corte = (y1 + t * (y2 - y1), y)
            if dentro2:
                actual = [corte]
            else:
                actual.append(corte)
                poligonos.append(np.array(actual))
                actual = None
        if dentro2 and actual is not None:
            actual.append((y2, z2))
    return [p for p in poligonos if len(p) >= 3]


def area_y_centroide(seccion, y):
    """Área mojada (m²) y altura del centroide sobre el fondo (m), con PySection."""
    area_total, momento = 0.0, 0.0
    for poligono in poligonos_mojados(seccion.contorno, y):
        parte = PoligonoMojado(_antihorario(poligono))
        area_total += parte.area
        momento += parte.area * parte.z
    if area_total <= 0:
        return 0.0, 0.0
    return area_total, momento / area_total


def perimetro_y_ancho(contorno, tirantes):
    """Perímetro mojado P y ancho superficial T para un arreglo de tirantes.

    Cálculo vectorizado: para cada lado del contorno y cada tirante se obtiene
    la fracción del lado que queda bajo el agua (matriz tirantes x lados).
    P suma la longitud sumergida; T suma la proyección horizontal con signo,
    que en cada tramo sumergido es la distancia entre orillas.
    """
    tirantes = np.atleast_1d(np.asarray(tirantes, float))[:, None]
    p1, p2 = contorno[:-1], contorno[1:]
    z_bajo = np.minimum(p1[:, 1], p2[:, 1])
    z_alto = np.maximum(p1[:, 1], p2[:, 1])
    dz = z_alto - z_bajo

    horizontal = dz == 0
    fraccion = np.clip((tirantes - z_bajo) / np.where(horizontal, 1.0, dz), 0.0, 1.0)
    fraccion = np.where(horizontal, (z_bajo < tirantes).astype(float), fraccion)

    longitud = np.hypot(p2[:, 0] - p1[:, 0], p2[:, 1] - p1[:, 1])
    P = (fraccion * longitud).sum(axis=1)
    T = (fraccion * (p2[:, 0] - p1[:, 0])).sum(axis=1)
    return P, T


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

def _positivo(campo, valor):
    if valor is None or not np.isfinite(valor) or valor <= 0:
        raise ErrorDatos(campo, f"'{campo}' debe ser un número mayor que cero.")
    return float(valor)


def _no_negativo(campo, valor):
    if valor is None or not np.isfinite(valor) or valor < 0:
        raise ErrorDatos(campo, f"'{campo}' debe ser un número mayor o igual que cero.")
    return float(valor)


def _validar_natural(coordenadas):
    """Valida una sección natural y traslada el punto más bajo a z = 0."""
    if not coordenadas or len(coordenadas) < 3:
        raise ErrorDatos("coordenadas", "Ingrese al menos 3 puntos (y z) del levantamiento.")
    puntos = np.array(coordenadas, float)
    if not np.isfinite(puntos).all():
        raise ErrorDatos("coordenadas", "Hay coordenadas que no son números finitos.")
    pasos = np.diff(puntos, axis=0)
    if np.any(pasos[:, 0] < 0):
        raise ErrorDatos("coordenadas", "Las abscisas y deben ir de la orilla izquierda a la derecha (crecientes).")
    if np.any(np.all(pasos == 0, axis=1)):
        raise ErrorDatos("coordenadas", "Hay puntos repetidos seguidos.")
    puntos[:, 1] -= puntos[:, 1].min()
    if min(puntos[0, 1], puntos[-1, 1]) <= 0:
        raise ErrorDatos("coordenadas", "Las orillas (primer y último punto) deben estar por encima del fondo.")
    return puntos


def _antihorario(poligono):
    """PySection da áreas negativas en sentido horario: se garantiza el antihorario."""
    y, z = poligono[:, 0], poligono[:, 1]
    area_con_signo = 0.5 * np.sum(y * np.roll(z, -1) - np.roll(y, -1) * z)
    return poligono if area_con_signo > 0 else poligono[::-1].copy()
