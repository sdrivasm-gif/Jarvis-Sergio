"""Envía un correo desde Gmail a una sola dirección. Siempre pide confirmación."""
from jarvis.integrations import correo, google

NOMBRE = "correo_enviar"
DESCRIPCION = "Envía un correo desde el Gmail del usuario a UNA sola dirección. Requiere confirmación."
ESQUEMA = {"type": "object",
           "properties": {"para": {"type": "string", "description": "Una sola dirección, p. ej. ana@example.com."},
                          "asunto": {"type": "string", "description": "Asunto, en una línea."},
                          "cuerpo": {"type": "string", "description": "Texto del correo."}},
           "required": ["para", "asunto", "cuerpo"]}
requiere_confirmacion = True  # envía un mensaje en nombre del usuario


def ejecutar(para: str, asunto: str, cuerpo: str) -> str:
    # ponytail: un solo destinatario, sin CC, adjuntos ni respuestas en hilo.
    para = para.strip()
    if not google.CORREO_VALIDO.fullmatch(para):
        return f"Error: la dirección '{para}' no es válida; pon un solo correo, como ana@example.com."
    if "\n" in asunto or "\r" in asunto:
        return "Error: el asunto no puede tener saltos de línea."
    asunto = asunto.strip()
    try:
        correo.obtener_cliente().enviar(para, asunto, cuerpo)
    except google.ErrorIntegracion as e:
        return f"Error: {e}"
    return f"Correo enviado a {para}: '{asunto}'."
