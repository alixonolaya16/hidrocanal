"""Acceso a datos con SQLite. Todo el SQL de la aplicación está en este módulo.

Esquema:
    proyectos (id, nombre, ubicacion, responsable, creado)
    calculos  (id, proyecto_id → proyectos.id, fecha, nombre, tipo_seccion,
               entradas JSON, Q, n, S0, yn, yc, V, Fr, regimen, cumple)

Las entradas completas se guardan como JSON para volver a abrir el cálculo;
los resultados principales van en columnas propias para listar, buscar,
ordenar y comparar. Todas las consultas usan parámetros ``?``.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

RUTA_BD = Path(__file__).resolve().parents[1] / "datos" / "hidrocanal.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS proyectos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    ubicacion   TEXT NOT NULL DEFAULT '',
    responsable TEXT NOT NULL DEFAULT '',
    creado      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calculos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id  INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    fecha        TEXT NOT NULL,
    nombre       TEXT NOT NULL,
    tipo_seccion TEXT NOT NULL,
    entradas     TEXT NOT NULL,
    Q REAL NOT NULL, n REAL NOT NULL, S0 REAL NOT NULL,
    yn REAL NOT NULL, yc REAL, V REAL NOT NULL, Fr REAL NOT NULL,
    regimen      TEXT NOT NULL,
    cumple       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calculos_proyecto ON calculos(proyecto_id);
"""

# ORDER BY no admite "?": el orden se elige de este diccionario cerrado
ORDENES = {
    "Más recientes": "c.id DESC",
    "Más antiguos": "c.id ASC",
    "Mayor caudal": "c.Q DESC",
    "Mayor velocidad": "c.V DESC",
    "Nombre (A-Z)": "c.nombre COLLATE NOCASE ASC",
}
ESTADOS = {"Todos": None, "Cumple": 1, "No cumple": 0}


def conectar(ruta=RUTA_BD):
    """Abre la base de datos y crea las tablas la primera vez."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")  # SQLite no las activa por defecto
    conexion.executescript(ESQUEMA)
    return conexion


def _ahora():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


# --- Proyectos ---------------------------------------------------------------

def crear_proyecto(conexion, nombre, ubicacion="", responsable=""):
    with conexion:
        cursor = conexion.execute(
            "INSERT INTO proyectos (nombre, ubicacion, responsable, creado) VALUES (?, ?, ?, ?)",
            (nombre.strip(), ubicacion.strip(), responsable.strip(), _ahora()),
        )
    return cursor.lastrowid


def listar_proyectos(conexion):
    return conexion.execute(
        """SELECT p.*, COUNT(c.id) AS num_calculos
           FROM proyectos p LEFT JOIN calculos c ON c.proyecto_id = p.id
           GROUP BY p.id ORDER BY p.nombre COLLATE NOCASE"""
    ).fetchall()


def obtener_proyecto(conexion, proyecto_id):
    return conexion.execute("SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()


def eliminar_proyecto(conexion, proyecto_id):
    """Elimina el proyecto y, por la llave foránea en cascada, sus cálculos."""
    with conexion:
        conexion.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))


# --- Cálculos ----------------------------------------------------------------

def guardar_calculo(conexion, proyecto_id, nombre, resultado):
    """Guarda las entradas (JSON) y el resumen de un :class:`Resultado`."""
    normal, critico = resultado.normal, resultado.critico
    with conexion:
        cursor = conexion.execute(
            """INSERT INTO calculos (proyecto_id, fecha, nombre, tipo_seccion, entradas,
                                     Q, n, S0, yn, yc, V, Fr, regimen, cumple)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (proyecto_id, _ahora(), nombre.strip(), resultado.datos.tipo,
             json.dumps(resultado.datos.a_dict()), resultado.datos.Q, resultado.datos.n,
             resultado.datos.S0, normal["y"], critico["y"] if critico else None,
             normal["V"], normal["Fr"], normal["regimen"], int(resultado.cumple)),
        )
    return cursor.lastrowid


def buscar_calculos(conexion, texto="", proyecto_id=None, estado="Todos", orden="Más recientes"):
    """Lista los cálculos que coinciden con el texto (nombre del cálculo o del
    proyecto), el proyecto y el estado de cumplimiento."""
    condiciones = ["(c.nombre LIKE ? OR p.nombre LIKE ?)"]
    parametros = [f"%{texto.strip()}%", f"%{texto.strip()}%"]
    if proyecto_id is not None:
        condiciones.append("c.proyecto_id = ?")
        parametros.append(proyecto_id)
    if ESTADOS[estado] is not None:
        condiciones.append("c.cumple = ?")
        parametros.append(ESTADOS[estado])
    consulta = (
        "SELECT c.*, p.nombre AS proyecto FROM calculos c "
        "JOIN proyectos p ON p.id = c.proyecto_id "
        f"WHERE {' AND '.join(condiciones)} ORDER BY {ORDENES[orden]}"
    )
    return conexion.execute(consulta, parametros).fetchall()


def obtener_calculo(conexion, calculo_id):
    """Fila del cálculo con sus entradas ya convertidas a diccionario."""
    fila = conexion.execute(
        "SELECT c.*, p.nombre AS proyecto FROM calculos c "
        "JOIN proyectos p ON p.id = c.proyecto_id WHERE c.id = ?",
        (calculo_id,),
    ).fetchone()
    if fila is None:
        return None
    return {**dict(fila), "entradas": json.loads(fila["entradas"])}


def eliminar_calculo(conexion, calculo_id):
    with conexion:
        conexion.execute("DELETE FROM calculos WHERE id = ?", (calculo_id,))
