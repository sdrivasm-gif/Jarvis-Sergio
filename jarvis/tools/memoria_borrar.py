"""Borra UN recuerdo por id y texto exacto. Siempre pide confirmación."""
from jarvis import memoria

NOMBRE = "memoria_borrar"
DESCRIPCION = ("Borra UN recuerdo de la memoria. Pide su id y su texto exacto, tal como los da memoria (listar o buscar). "
               "Requiere confirmación.")
ESQUEMA = {"type": "object",
           "properties": {"id_recuerdo": {"type": "integer", "description": "Id del recuerdo."},
                          "texto": {"type": "string",
                                    "description": "Texto del recuerdo tal como lo da memoria, para que el señor vea qué se borra."}},
           "required": ["id_recuerdo", "texto"]}
requiere_confirmacion = True  # borra datos del usuario


def ejecutar(id_recuerdo: int, texto: str) -> str:
    try:
        n = int(id_recuerdo)
    except (TypeError, ValueError):
        return f"Error: el id '{id_recuerdo}' no es válido."
    try:
        r = memoria.borrar(n, texto)
    except ValueError as e:
        return f"Error: {e}"
    return f"Recuerdo borrado (id {r['id']}): {r['texto']}"
