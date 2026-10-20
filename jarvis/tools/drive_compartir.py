"""Comparte un archivo de Google Drive con una persona. Siempre pide confirmación."""
from jarvis.integrations import drive, google

NOMBRE = "drive_compartir"
DESCRIPCION = ("Comparte un archivo de Google Drive (por su id, el que da drive_buscar) con una persona, "
               "como lector o editor; Google le avisa por correo. Requiere confirmación.")
ESQUEMA = {"type": "object",
           "properties": {"id_archivo": {"type": "string", "description": "Id del archivo, tal como lo da drive_buscar."},
                          "correo": {"type": "string", "description": "Correo de la persona."},
                          "rol": {"type": "string", "enum": ["lector", "editor"], "description": "lector por defecto."}},
           "required": ["id_archivo", "correo"]}
requiere_confirmacion = True  # da acceso a un archivo y envía un aviso por correo
ROLES = {"lector": "reader", "editor": "writer"}


def ejecutar(id_archivo: str, correo: str, rol: str = "lector") -> str:
    # ponytail: el usuario confirma el id, no el nombre del archivo; mostrar el nombre resuelto antes de confirmar.
    i = id_archivo.strip()
    if not google.ID_VALIDO.fullmatch(i):
        return f"Error: el id de archivo '{id_archivo}' no es válido."
    correo = correo.strip()
    if not google.CORREO_VALIDO.fullmatch(correo):
        return f"Error: la dirección '{correo}' no es válida; pon un solo correo, como ana@example.com."
    if rol not in ROLES:
        return f"Error: rol '{rol}' no válido; usa lector o editor."
    try:
        drive.obtener_cliente().compartir(i, correo, ROLES[rol])
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    return f"Compartí el archivo {i} con {correo} como {rol}."
