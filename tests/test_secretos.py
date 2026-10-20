from jarvis import secretos
from jarvis.secretos import TOKEN, detectar, luhn_valido, rechazo

# Armados por trozos para que test_sin_claves no vea una clave literal.
EJEMPLOS = {"anthropic": "sk-" + "ant-" + "a1" * 15, "openrouter": "sk-" + "or-v1-" + "b2" * 16,
            "openai": "sk-" + "proj-" + "c3" * 12, "google_api": "AI" + "za" + "d" * 35,
            "google_oauth": "ya" + "29." + "e" * 30, "google_refresh": "1/" + "/0" + "f" * 30,
            "google_secreto": "GOC" + "SPX-" + "g" * 24, "github": "gh" + "p_" + "h" * 36,
            "aws": "AK" + "IA" + "A" * 16, "slack": "xo" + "xb-" + "1" * 12,
            "jwt": "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0" + ".firma",
            "bearer": "Authorization: Bear" + "er " + "x9" * 10}
PEM = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"


def test_detecta_claves_y_tokens():
    for nombre, valor in EJEMPLOS.items():
        assert detectar(f"guarda esto: {valor}") == TOKEN, nombre
    assert detectar(PEM + "\nMIIE...") == "una clave privada"


def test_detecta_contrasenas():
    for texto in ("mi contraseña: hunter2", "La clave del wifi es Perro123", "password=abc123",
                  "el PIN de la tarjeta es 4821", "Mi contrasena es gatito"):
        assert detectar(texto) == "una contraseña", texto


def test_detecta_tarjetas_con_luhn():
    for texto in ("4111 1111 1111 1111", "4111-1111-1111-1111", "mi tarjeta 5555555555554444",
                  "Amex 3782 822463 10005", "４１１１１１１１１１１１１１１１"):
        assert detectar(texto) == "un número de tarjeta", texto


def test_textos_normales_no_disparan():
    for texto in ("prefiere el café sin azúcar", "su teléfono es 987 654 321", "pedido 1234567890123",
                  "4111 1111 1111 1112", "reunión el 2026-10-20 a las 17:00",
                  "cambiar la contraseña del banco el lunes", "la clave del éxito", "desk-top", "sk-corta",
                  "Bearer"):
        assert detectar(texto) is None, texto


def test_luhn():
    assert luhn_valido("4111111111111111") and luhn_valido("79927398713")
    assert not luhn_valido("4111111111111112")


def test_rechazo_exacto():
    assert rechazo("una contraseña") == (
        "no lo guardo porque parece contener una contraseña; las claves, contraseñas y números de tarjeta "
        "no se guardan (usa un gestor de contraseñas).")
    assert secretos.TOKEN == "una clave de API o un token"


def test_detecta_variables_y_etiquetas_largas():
    # Armados por trozos para que ningún escáner vea una asignación literal.
    for texto in ("DB_" + "PASSWORD=" + "hunter2", "GOOGLE_CLIENT_" + "SECRET=" + "abc123xyz", "MY_" + "TOKEN=" + "abc",
                  "secret" + "_key=" + "abcdef", "user_" + "password: " + "x",
                  "la contraseña de mi correo personal es Perro123"):
        assert detectar(texto) == "una contraseña", texto


def test_palabras_parecidas_no_disparan():
    for texto in ("pinguino es lindo", "el pino es alto", "tokenizar es fácil", "el clavel es rojo",
                  "la clave del éxito", "secretaria de Ana", "pinta la pared", "mi_pinza es azul"):
        assert detectar(texto) is None, texto


def test_sin_redos_con_entradas_largas():
    import time
    for texto in ("clave " + "a " * 20000, "password" + " x" * 20000, "_" * 20000 + "token", "pin" * 20000,
                  "clave " + "a" * 20000, "1 " * 20000):
        inicio = time.perf_counter()
        detectar(texto)
        assert time.perf_counter() - inicio < 1, texto[:20]


def test_tope_de_tiempo_con_el_maximo_que_dejan_pasar():
    # Con "_" repetido el coste es cuadrático; notas (2000), memoria (500) y recordatorios (300) acotan la entrada.
    import time
    for texto in (("pin_" * 500)[:2000], ("token_" * 334)[:2000]):
        inicio = time.perf_counter()
        detectar(texto)
        assert time.perf_counter() - inicio < 0.5, texto[:10]
