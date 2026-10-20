"""Detecta claves, contraseñas, tokens y tarjetas para no guardarlos nunca en datos/."""
import re
import unicodedata

# ponytail: no detecta contraseñas sueltas sin etiqueta ni cadenas aleatorias genéricas (por entropía); con la duda
# rechaza, así que hay falsos positivos como "la clave del éxito es...". Añadir entropía si hace falta.
TOKEN = "una clave de API o un token"
# ponytail: con "_" repetido el coste es cuadrático; quien llama limita la longitud (notas 2000).
# (?<![^\W_]) y (?:_\w*)? aceptan "_" pegado a la etiqueta: DB_PASSWORD=..., secret_key=...
ETIQUETA = (r"(?<![^\W_])(?:contraseñas?|contrasenas?|password|passwd|pwd|clave|pin|token|secreto|secret|"
            r"api[ _-]?key|cvv|cvc)(?:_\w*)?\b(?:[ \t]+[^\s:=]+){0,5}?[ \t]*(?:[:=]|\b(?:es|era|is)\b)[ \t]*\S")
PATRONES = (
    ("una clave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (TOKEN, re.compile(r"\bsk-(?:ant|or|proj)-[A-Za-z0-9_\-]{8,}")),
    (TOKEN, re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    (TOKEN, re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}")),
    (TOKEN, re.compile(r"\bya29\.[0-9A-Za-z_\-]{10,}")),
    (TOKEN, re.compile(r"\b1//0[0-9A-Za-z_\-]{10,}")),
    (TOKEN, re.compile(r"\bGOCSPX-[0-9A-Za-z_\-]{10,}")),
    (TOKEN, re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    (TOKEN, re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (TOKEN, re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{10,}")),
    (TOKEN, re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.")),  # JWT
    (TOKEN, re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=\-]{8,}", re.IGNORECASE)),
    ("una contraseña", re.compile(ETIQUETA, re.IGNORECASE)),
)
TARJETA = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_valido(digitos: str) -> bool:
    suma = 0
    for i, c in enumerate(reversed(digitos)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        suma += n
    return suma % 10 == 0


def detectar(texto: str) -> str | None:
    t = unicodedata.normalize("NFKC", texto)  # dígitos de ancho completo, ligaduras, etc.
    for tipo, patron in PATRONES:
        if patron.search(t):
            return tipo
    for m in TARJETA.finditer(t):
        d = re.sub(r"\D", "", m.group())
        if 13 <= len(d) <= 19 and luhn_valido(d):
            return "un número de tarjeta"
    return None


def rechazo(tipo: str) -> str:
    # Nunca incluye el texto analizado: el mensaje llega al modelo y a la terminal.
    return (f"no lo guardo porque parece contener {tipo}; las claves, contraseñas y números de tarjeta "
            "no se guardan (usa un gestor de contraseñas).")
