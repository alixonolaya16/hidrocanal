"""HidroCanal: flujo uniforme en canales abiertos.

Matplotlib se configura con el backend "Agg" (dibuja en memoria) antes de que
cualquier módulo importe pyplot; así las gráficas se generan sin abrir
ventanas, tanto en la aplicación Flet como en las pruebas.
"""

import matplotlib

matplotlib.use("Agg")
