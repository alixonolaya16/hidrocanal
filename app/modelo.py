"""Modelo hidráulico de flujo en canales abiertos (sin interfaz gráfica).

Ecuaciones (Chow, 1959; unidades SI, g = 9.81 m/s²):

* Manning:            Q = (1/n) · A · R^(2/3) · S0^(1/2),   R = A / P
* Flujo crítico:      Q² · T / (g · A³) = 1
* Número de Froude:   Fr = V / √(g · A / T)
* Energía específica: E = y + V² / (2g)
* Fuerza específica:  M = Q² / (g · A) + A · ȳ   (ȳ: profundidad del centroide)
* Flujo gradualmente variado (curva de remanso):
                      dy/dx = (S0 − Sf) / (1 − Fr²),   Sf = (n·V)² / R^(4/3)

Métodos numéricos:

* Tabla hidráulica en una malla de tirantes (NumPy vectorizado).
* Tirante normal y crítico: raíces con ``scipy.optimize.brentq``, acotadas con
  la tabla hidráulica (la función cambia de signo una sola vez en el intervalo).
* Curva de remanso: ``scipy.integrate.solve_ivp`` (RK45) sobre interpolantes
  monótonos ``scipy.interpolate.PchipInterpolator`` de A, P y T.
"""

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from app.geometria import ErrorDatos, area_y_centroide, crear_seccion, perimetro_y_ancho

G = 9.81                 # aceleración de la gravedad (m/s²)
PUNTOS_TABLA = 200       # tirantes de la tabla hidráulica
FR_INESTABLE = (0.8, 1.2)  # flujo cercano al crítico: superficie ondulada e inestable


@dataclass
class DatosEntrada:
    """Datos del cálculo, tal como se guardan en la base de datos (JSON)."""

    tipo: str = "Trapezoidal"
    b: float | None = None          # ancho de fondo (m)
    m: float | None = None          # talud (horizontal : vertical)
    H: float | None = None          # altura del canal (m)
    D: float | None = None          # diámetro (m)
    coordenadas: list = field(default_factory=list)  # sección natural [(y, z), ...] (m)
    Q: float = 0.0                  # caudal de diseño (m³/s)
    n: float = 0.0                  # coeficiente de rugosidad de Manning (s/m^(1/3))
    S0: float = 0.0                 # pendiente longitudinal del fondo (m/m)
    v_min: float = 0.6              # velocidad mínima permitida (m/s)
    v_max: float = 3.0              # velocidad máxima permitida (m/s)
    borde_libre: float = 0.3        # borde libre mínimo (m)
    remanso: bool = False           # calcular la curva de remanso
    y_control: float | None = None  # tirante en la sección de control (m)
    longitud: float | None = None   # longitud del tramo (m)

    def a_dict(self):
        return asdict(self)

    @classmethod
    def desde_dict(cls, datos):
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})


@dataclass
class Resultado:
    """Resultados del análisis."""

    datos: DatosEntrada
    seccion: object
    tabla: dict          # arreglos de la tabla hidráulica
    normal: dict         # propiedades en el tirante normal
    critico: dict | None  # propiedades en el tirante crítico (None si no existe)
    pendiente: str       # suave, empinada o crítica
    chequeos: list       # [{criterio, valor, limite, cumple}]
    perfil: dict | None  # curva de remanso
    advertencias: list

    @property
    def cumple(self):
        return all(c["cumple"] for c in self.chequeos)


# ---------------------------------------------------------------------------
# Análisis completo
# ---------------------------------------------------------------------------

def analizar(datos: DatosEntrada) -> Resultado:
    """Ejecuta todo el cálculo y devuelve un :class:`Resultado`."""
    _validar_hidraulica(datos)
    seccion = crear_seccion(datos.tipo, datos.b, datos.m, datos.H, datos.D, datos.coordenadas)
    tabla = tabla_hidraulica(seccion, datos.Q, datos.n, datos.S0)
    advertencias = []

    yn = tirante_normal(seccion, tabla, datos.Q, datos.n, datos.S0)
    normal = propiedades(seccion, yn, datos.Q, datos.n)

    yc = tirante_critico(seccion, tabla, datos.Q)
    critico = propiedades(seccion, yc, datos.Q, datos.n) if yc is not None else None
    if yc is None:
        advertencias.append("El tirante crítico supera la altura de la sección.")

    pendiente = clasificar_pendiente(yn, yc)
    perfil = None
    if datos.remanso:
        perfil = curva_remanso(seccion, tabla, datos, yn, yc)
        advertencias.extend(perfil["advertencias"])

    chequeos = chequear(datos, seccion, normal, perfil)
    return Resultado(datos, seccion, tabla, normal, critico, pendiente, chequeos, perfil, advertencias)


def tabla_hidraulica(seccion, Q, n, S0, puntos=PUNTOS_TABLA):
    """Propiedades hidráulicas en una malla de tirantes, de 0 a la altura del canal.

    A y el centroide se obtienen con PySection, que analiza un polígono a la vez
    (por eso hay un ciclo sobre los tirantes). Todo lo demás se calcula de forma
    vectorizada sobre los arreglos.
    """
    y = np.linspace(seccion.altura / puntos, seccion.altura, puntos)
    A = np.array([area_y_centroide(seccion, yi)[0] for yi in y])
    P, T = perimetro_y_ancho(seccion.contorno, y)

    R = A / P
    V = Q / A
    con_ancho = T > 1e-9
    Fr = np.where(con_ancho, V / np.sqrt(G * A / np.where(con_ancho, T, 1.0)), 0.0)
    return {
        "y": y, "A": A, "P": P, "T": T, "R": R, "V": V, "Fr": Fr,
        "E": y + V**2 / (2 * G),                       # energía específica
        "Q_manning": A * R ** (2 / 3) * np.sqrt(S0) / n,  # capacidad para cada tirante
    }


def propiedades(seccion, y, Q, n):
    """Propiedades hidráulicas en un tirante (área y centroide con PySection)."""
    A, zc = area_y_centroide(seccion, y)
    P, T = (float(v[0]) for v in perimetro_y_ancho(seccion.contorno, y))
    R, V = A / P, Q / A
    Fr = V / np.sqrt(G * A / T) if T > 0 else 0.0
    return {
        "y": y, "A": A, "P": P, "T": T, "R": R, "V": V, "Fr": Fr,
        "E": y + V**2 / (2 * G),
        "Sf": (n * V) ** 2 / R ** (4 / 3),
        "ybar": y - zc,                 # profundidad del centroide bajo la superficie
        "M": Q**2 / (G * A) + A * (y - zc),  # fuerza específica (usa el centroide de PySection)
        "regimen": regimen(Fr),
    }


# ---------------------------------------------------------------------------
# Tirantes normal y crítico (scipy.optimize.brentq)
# ---------------------------------------------------------------------------

def tirante_normal(seccion, tabla, Q, n, S0):
    """Tirante para el cual la ecuación de Manning da el caudal de diseño."""
    def residuo(y):
        A, _ = area_y_centroide(seccion, y)
        P = perimetro_y_ancho(seccion.contorno, y)[0][0]
        return A * (A / P) ** (2 / 3) * np.sqrt(S0) / n - Q

    # Para y → 0 la capacidad de Manning tiende a 0: el residuo empieza negativo
    intervalo = _primer_cambio_de_signo(tabla["y"], tabla["Q_manning"] - Q, signo_en_cero=-1)
    if intervalo is None:
        capacidad = tabla["Q_manning"].max()
        raise ErrorDatos("Q", f"El caudal supera la capacidad de la sección ({capacidad:.3f} m³/s).")
    return brentq(residuo, *intervalo, xtol=1e-10)


def tirante_critico(seccion, tabla, Q):
    """Tirante para el cual Q²·T/(g·A³) = 1 (energía específica mínima)."""
    def residuo(y):
        A, _ = area_y_centroide(seccion, y)
        T = perimetro_y_ancho(seccion.contorno, y)[1][0]
        return Q**2 * T / (G * A**3) - 1

    # Para y → 0 el número de Froude tiende a infinito: el residuo empieza positivo
    intervalo = _primer_cambio_de_signo(tabla["y"], tabla["Fr"] ** 2 - 1, signo_en_cero=1)
    if intervalo is None:
        return None
    return brentq(residuo, *intervalo, xtol=1e-10)


def _primer_cambio_de_signo(y, f, signo_en_cero):
    """Primer intervalo [y_i, y_i+1] donde f cambia de signo, empezando cerca de y = 0.

    ``signo_en_cero`` es el signo conocido de f cuando el tirante tiende a cero;
    así se detecta también una raíz menor que el primer tirante de la tabla.
    """
    y_ext = np.concatenate([[y[0] * 1e-3], y])
    signo = np.sign(np.concatenate([[signo_en_cero], f]))
    indices = np.flatnonzero(signo[1:] != signo[:-1])
    if indices.size == 0:
        return None
    i = indices[0]
    return y_ext[i], y_ext[i + 1]


def regimen(Fr):
    if Fr < 0.99:
        return "Subcrítico"
    if Fr > 1.01:
        return "Supercrítico"
    return "Crítico"


def clasificar_pendiente(yn, yc):
    if yc is None or yn > 1.01 * yc:
        return "Suave"
    if yn < 0.99 * yc:
        return "Empinada"
    return "Crítica"


# ---------------------------------------------------------------------------
# Curva de remanso (scipy.integrate.solve_ivp)
# ---------------------------------------------------------------------------

def curva_remanso(seccion, tabla, datos, yn, yc):
    """Perfil de flujo gradualmente variado desde la sección de control.

    Flujo subcrítico (control mayor que yc): el control está aguas abajo y se
    integra hacia aguas arriba. Flujo supercrítico: el control está aguas arriba
    y se integra hacia aguas abajo. La integración se detiene si el perfil llega
    al tirante crítico (resalto o caída) o a la altura del canal (desborde).
    """
    y0, L = datos.y_control, datos.longitud
    Q, n, S0 = datos.Q, datos.n, datos.S0
    if y0 >= seccion.altura:
        raise ErrorDatos("y_control", f"El tirante de control debe ser menor que la altura del canal ({seccion.altura:.3f} m).")
    subcritico = yc is None or y0 > yc
    A, P, T = (PchipInterpolator(tabla["y"], tabla[k]) for k in ("A", "P", "T"))

    def pendiente_superficie(x, y):
        yy = y[0]
        a, p, t = A(yy), P(yy), T(yy)
        Sf = (n * Q) ** 2 * p ** (4 / 3) / a ** (10 / 3)
        return [(S0 - Sf) / (1 - Q**2 * t / (G * a**3))]

    def llega_al_critico(x, y):
        # 1 − Fr² se acerca a 0 desde arriba (subcrítico) o desde abajo (supercrítico)
        margen = 0.02 if subcritico else -0.02
        return 1 - Q**2 * T(y[0]) / (G * A(y[0]) ** 3) - margen

    def desborda(x, y):
        return seccion.altura - y[0]

    for evento in (llega_al_critico, desborda):
        evento.terminal = True

    tramo = (L, 0.0) if subcritico else (0.0, L)
    sol = solve_ivp(pendiente_superficie, tramo, [y0], events=(llega_al_critico, desborda),
                    max_step=L / 200, rtol=1e-8, atol=1e-10)

    x, y = sol.t, sol.y[0]
    if subcritico:
        x, y = x[::-1], y[::-1]

    advertencias = []
    if sol.t_events[0].size:
        advertencias.append(f"El perfil alcanza el tirante crítico en x = {sol.t_events[0][0]:.1f} m (resalto o caída).")
    if sol.t_events[1].size:
        advertencias.append(f"El agua desborda el canal en x = {sol.t_events[1][0]:.1f} m.")

    return {
        "x": x, "y": y, "tipo": tipo_perfil(y0, yn, yc),
        "control": "aguas abajo" if subcritico else "aguas arriba",
        "y_max": float(y.max()), "advertencias": advertencias,
    }


def tipo_perfil(y0, yn, yc):
    """Clasificación de Chow: letra según la pendiente y zona (1, 2, 3) según y0."""
    letra = {"Suave": "M", "Empinada": "S", "Crítica": "C"}[clasificar_pendiente(yn, yc)]
    alto, bajo = max(yn, yc or 0), min(yn, yc or 0)
    zona = 1 if y0 > alto else (2 if y0 > bajo else 3)
    return f"{letra}{zona}"


# ---------------------------------------------------------------------------
# Chequeos de diseño
# ---------------------------------------------------------------------------

def chequear(datos, seccion, normal, perfil):
    """Compara los resultados con los criterios de diseño (cumple / no cumple)."""
    borde_libre = seccion.altura - normal["y"]
    fr = normal["Fr"]
    chequeos = [
        _chequeo("Borde libre", borde_libre, f"≥ {datos.borde_libre:.2f} m", borde_libre >= datos.borde_libre, "m"),
        _chequeo("Velocidad mínima (sedimentación)", normal["V"], f"≥ {datos.v_min:.2f} m/s", normal["V"] >= datos.v_min, "m/s"),
        _chequeo("Velocidad máxima (erosión)", normal["V"], f"≤ {datos.v_max:.2f} m/s", normal["V"] <= datos.v_max, "m/s"),
        _chequeo("Flujo estable (Fr fuera de 0.8–1.2)", fr, "Fr < 0.8 o Fr > 1.2",
                 not FR_INESTABLE[0] <= fr <= FR_INESTABLE[1], ""),
    ]
    if perfil is not None:
        chequeos.append(_chequeo("Remanso sin desborde", perfil["y_max"], f"≤ {seccion.altura:.2f} m",
                                 perfil["y_max"] < seccion.altura, "m"))
    return chequeos


def _chequeo(criterio, valor, limite, cumple, unidad):
    return {"criterio": criterio, "valor": float(valor), "unidad": unidad, "limite": limite, "cumple": bool(cumple)}


def _validar_hidraulica(d):
    reglas = [
        ("Q", d.Q, d.Q is not None and d.Q > 0, "El caudal Q debe ser mayor que cero."),
        ("n", d.n, d.n is not None and 0.005 <= d.n <= 0.2, "El coeficiente n debe estar entre 0.005 y 0.2."),
        ("S0", d.S0, d.S0 is not None and 0 < d.S0 < 1, "La pendiente S0 debe estar entre 0 y 1 (m/m)."),
        ("v_min", d.v_min, d.v_min is not None and d.v_min >= 0, "La velocidad mínima no puede ser negativa."),
        ("v_max", d.v_max, d.v_max is not None and d.v_max > (d.v_min or 0), "La velocidad máxima debe ser mayor que la mínima."),
        ("borde_libre", d.borde_libre, d.borde_libre is not None and d.borde_libre >= 0, "El borde libre no puede ser negativo."),
    ]
    if d.remanso:
        reglas += [
            ("y_control", d.y_control, d.y_control is not None and d.y_control > 0, "El tirante de control debe ser mayor que cero."),
            ("longitud", d.longitud, d.longitud is not None and d.longitud > 0, "La longitud del tramo debe ser mayor que cero."),
        ]
    for campo, _, valido, mensaje in reglas:
        if not valido:
            raise ErrorDatos(campo, mensaje)
