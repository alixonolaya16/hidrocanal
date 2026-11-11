"""Pruebas del modelo hidráulico contra casos resueltos a mano y de la literatura."""

import math

import numpy as np
import pytest
from scipy.integrate import cumulative_trapezoid

from app.geometria import ErrorDatos, area_y_centroide, crear_seccion, leer_coordenadas, perimetro_y_ancho
from app.modelo import G, DatosEntrada, analizar, propiedades, tipo_perfil

PIE = 0.3048  # m


def test_caso_literatura_chow_tirante_normal():
    """Chow (1959), cap. 6: b = 20 ft, talud 2:1, S0 = 0.0016, n = 0.025,
    Q = 400 ft³/s  →  yn = 3.36 ft (Chow usa 1.49 en lugar de 1/0.3048^(1/3))."""
    datos = DatosEntrada(tipo="Trapezoidal", b=20 * PIE, m=2, H=10 * PIE,
                         Q=400 * PIE**3, n=0.025, S0=0.0016)
    resultado = analizar(datos)
    assert resultado.normal["y"] / PIE == pytest.approx(3.36, abs=0.01)


def test_caso_a_mano_trapecio():
    """Caso del README resuelto a mano: b = 1.5 m, m = 1.5, n = 0.015,
    S0 = 0.0008, Q = 2.5 m³/s  →  yn = 0.7935 m, A = 2.1346 m², P = 4.3609 m."""
    datos = DatosEntrada(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008)
    normal = analizar(datos).normal
    y = normal["y"]
    assert y == pytest.approx(0.7935, abs=5e-4)
    assert normal["A"] == pytest.approx((1.5 + 1.5 * y) * y)
    assert normal["P"] == pytest.approx(1.5 + 2 * y * math.sqrt(1 + 1.5**2))
    # Manning se cumple en el tirante encontrado
    q_manning = normal["A"] * normal["R"] ** (2 / 3) * math.sqrt(0.0008) / 0.015
    assert q_manning == pytest.approx(2.5, rel=1e-8)


def test_tirante_critico_rectangular_formula_cerrada():
    """yc = (q² / g)^(1/3) con q = Q / b."""
    datos = DatosEntrada(tipo="Rectangular", b=2.0, H=2.0, Q=3.0, n=0.013, S0=0.001)
    resultado = analizar(datos)
    assert resultado.critico["y"] == pytest.approx((1.5**2 / G) ** (1 / 3), rel=1e-8)
    assert resultado.critico["Fr"] == pytest.approx(1.0, rel=1e-6)


def test_tirante_critico_triangular_formula_cerrada():
    """yc = (2 Q² / (g m²))^(1/5)."""
    datos = DatosEntrada(tipo="Triangular", m=1.5, H=2.0, Q=1.2, n=0.013, S0=0.001)
    yc = analizar(datos).critico["y"]
    assert yc == pytest.approx((2 * 1.2**2 / (G * 1.5**2)) ** 0.2, rel=1e-7)


def test_fuerza_especifica_minima_en_el_tirante_critico():
    """dM/dy = 0 en yc: el centroide de PySection da M = Q²/(gA) + A·ȳ."""
    datos = DatosEntrada(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008)
    resultado = analizar(datos)
    yc = resultado.critico["y"]
    m_critico = resultado.critico["M"]
    for y in (0.9 * yc, 1.1 * yc):
        assert propiedades(resultado.seccion, y, 2.5, 0.015)["M"] > m_critico
    # Rectángulo: el centroide del agua está a la mitad del tirante
    rect = analizar(DatosEntrada(tipo="Rectangular", b=2.0, H=2.0, Q=3.0, n=0.013, S0=0.001))
    assert rect.normal["ybar"] == pytest.approx(rect.normal["y"] / 2)


def test_circulo_medio_lleno_con_pysection():
    """Medio círculo: A = πD²/8 y centroide a 4r/(3π) bajo el diámetro."""
    seccion = crear_seccion("Circular", D=1.0)
    A, zc = area_y_centroide(seccion, 0.5)
    P, T = perimetro_y_ancho(seccion.contorno, 0.5)
    assert A == pytest.approx(math.pi / 8, rel=1e-4)       # polígono de 360 lados
    assert zc == pytest.approx(0.5 - 4 * 0.5 / (3 * math.pi), rel=1e-4)
    assert P[0] == pytest.approx(math.pi / 2, rel=1e-4)
    assert T[0] == pytest.approx(1.0)


def test_area_pysection_igual_a_integral_del_ancho_superficial():
    """Verificación independiente: A(y) = ∫ T dy (NumPy/SciPy) vs. PySection."""
    seccion = crear_seccion("Natural", coordenadas=[(0, 3), (2, 1.2), (4, 0.4), (6, 0), (8, 0.5), (11, 1), (14, 3.2)])
    y = np.linspace(0, 2.5, 5001)
    area_integrada = cumulative_trapezoid(perimetro_y_ancho(seccion.contorno, y)[1], y, initial=0)
    for tirante in (0.3, 1.0, 2.2):
        assert area_y_centroide(seccion, tirante)[0] == pytest.approx(np.interp(tirante, y, area_integrada), rel=1e-4)


def test_caudal_mayor_que_la_capacidad():
    datos = DatosEntrada(tipo="Circular", D=1.0, Q=5.0, n=0.013, S0=0.002)
    with pytest.raises(ErrorDatos, match="capacidad") as error:
        analizar(datos)
    assert error.value.campo == "Q"


@pytest.mark.parametrize("cambios, campo", [
    ({"Q": 0}, "Q"),
    ({"n": 0.5}, "n"),
    ({"S0": -0.001}, "S0"),
    ({"b": -1}, "b"),
    ({"remanso": True, "y_control": None, "longitud": 100}, "y_control"),
])
def test_datos_invalidos(cambios, campo):
    base = dict(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008)
    with pytest.raises(ErrorDatos) as error:
        analizar(DatosEntrada(**{**base, **cambios}))
    assert error.value.campo == campo


def test_coordenadas_naturales():
    assert leer_coordenadas("0 3\n2;1.2\n4,0.4") == [(0, 3), (2, 1.2), (4, 0.4)]
    with pytest.raises(ErrorDatos):
        leer_coordenadas("0 3\nabc")
    with pytest.raises(ErrorDatos, match="crecientes"):
        crear_seccion("Natural", coordenadas=[(0, 2), (3, 0), (1, 2)])


def test_curva_de_remanso_m1_tiende_al_tirante_normal():
    """Pendiente suave con control alto aguas abajo: perfil M1 que decrece
    hacia aguas arriba y se acerca asintóticamente a yn."""
    datos = DatosEntrada(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008,
                         remanso=True, y_control=1.25, longitud=3000)
    resultado = analizar(datos)
    perfil = resultado.perfil
    assert perfil["tipo"] == "M1"
    assert perfil["y"][-1] == pytest.approx(1.25)
    assert np.all(np.diff(perfil["y"]) >= 0)
    assert perfil["y"][0] == pytest.approx(resultado.normal["y"], abs=0.01)


def test_clasificacion_de_perfiles():
    assert tipo_perfil(1.5, yn=1.0, yc=0.6) == "M1"
    assert tipo_perfil(0.8, yn=1.0, yc=0.6) == "M2"
    assert tipo_perfil(0.4, yn=1.0, yc=0.6) == "M3"
    assert tipo_perfil(0.2, yn=0.4, yc=0.6) == "S3"


def test_chequeos_cumple_y_no_cumple():
    base = dict(tipo="Rectangular", b=2.0, H=1.5, Q=3.0, n=0.013, S0=0.001)
    assert analizar(DatosEntrada(**base)).cumple
    lento = analizar(DatosEntrada(**{**base, "v_min": 2.0}))
    assert not lento.cumple
    assert [c["cumple"] for c in lento.chequeos][1] is False
