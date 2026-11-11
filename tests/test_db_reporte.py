"""Pruebas de la persistencia (SQLite) y de la memoria de cálculo (docxtpl)."""

import pytest
from docx import Document

from app import db
from app.modelo import DatosEntrada, analizar
from app.reporte import generar_memoria

CANAL = DatosEntrada(tipo="Trapezoidal", b=1.5, m=1.5, H=1.5, Q=2.5, n=0.015, S0=0.0008)


@pytest.fixture
def conexion(tmp_path):
    con = db.conectar(tmp_path / "prueba.db")
    yield con
    con.close()


def test_la_base_se_crea_sola_y_guarda_y_reabre(conexion):
    proyecto = db.crear_proyecto(conexion, "Distrito de riego", "Funza", "A. Olaya")
    resultado = analizar(CANAL)
    calculo_id = db.guardar_calculo(conexion, proyecto, "Canal principal", resultado)

    fila = db.obtener_calculo(conexion, calculo_id)
    assert fila["proyecto"] == "Distrito de riego"
    assert fila["yn"] == pytest.approx(resultado.normal["y"])
    # Las entradas guardadas reproducen el mismo cálculo
    reabierto = analizar(DatosEntrada.desde_dict(fila["entradas"]))
    assert reabierto.normal["y"] == pytest.approx(resultado.normal["y"])


def test_buscar_filtrar_y_ordenar(conexion):
    p1 = db.crear_proyecto(conexion, "Riego norte")
    p2 = db.crear_proyecto(conexion, "Drenaje sur")
    db.guardar_calculo(conexion, p1, "Canal A", analizar(CANAL))
    db.guardar_calculo(conexion, p1, "Canal B", analizar(DatosEntrada(**{**CANAL.a_dict(), "Q": 4.0})))
    db.guardar_calculo(conexion, p2, "Colector", analizar(DatosEntrada(**{**CANAL.a_dict(), "v_min": 2.0})))

    assert len(db.buscar_calculos(conexion, "canal")) == 2
    assert len(db.buscar_calculos(conexion, "sur")) == 1             # busca también por proyecto
    assert len(db.buscar_calculos(conexion, proyecto_id=p1)) == 2
    assert [f["nombre"] for f in db.buscar_calculos(conexion, estado="No cumple")] == ["Colector"]
    assert db.buscar_calculos(conexion, orden="Mayor caudal")[0]["nombre"] == "Canal B"


def test_consultas_parametrizadas_evitan_inyeccion(conexion):
    proyecto = db.crear_proyecto(conexion, "Proyecto")
    db.guardar_calculo(conexion, proyecto, "Canal", analizar(CANAL))
    assert db.buscar_calculos(conexion, "x' OR '1'='1") == []


def test_eliminar_proyecto_borra_sus_calculos_en_cascada(conexion):
    proyecto = db.crear_proyecto(conexion, "Temporal")
    calculo_id = db.guardar_calculo(conexion, proyecto, "Canal", analizar(CANAL))
    db.eliminar_proyecto(conexion, proyecto)
    assert db.obtener_calculo(conexion, calculo_id) is None
    assert db.listar_proyectos(conexion) == []


def test_memoria_con_tablas_grafica_y_conclusion(tmp_path):
    datos = DatosEntrada(**{**CANAL.a_dict(), "remanso": True, "y_control": 1.25, "longitud": 1500})
    resultado = analizar(datos)
    ruta = generar_memoria(resultado, {"nombre": "Distrito de riego", "ubicacion": "Funza", "responsable": "A. Rincón"},
                           {"nombre": "Canal principal"}, tmp_path / "memoria.docx")

    documento = Document(ruta)
    texto = "\n".join(p.text for p in documento.paragraphs)
    assert "Distrito de riego" in documento.tables[0].cell(0, 1).text
    assert "CUMPLE" in texto and "M1" in texto
    assert f"{resultado.normal['y']:.4f}" in documento.tables[2].cell(1, 2).text   # tabla de resultados
    assert len(documento.tables[3].rows) == 13                                      # encabezado + 12 tirantes
    assert len(documento.inline_shapes) == 3                                        # sección, energía y remanso
    assert "{{" not in texto and "{%" not in texto
