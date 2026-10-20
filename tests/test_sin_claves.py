"""Busca patrones de claves en el repositorio. Nunca abre .env ni imprime el valor encontrado."""
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTE_ARCHIVO = Path(__file__).resolve()
CARPETAS_EXCLUIDAS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "datos", "graphify-out"}
MAX_BYTES = 1_000_000
# ponytail: no hay patrón genérico de password = "..." (daría falsos positivos); añadirlo si hace falta.
PATRONES = {
    "anthropic": r"\bsk-ant-[A-Za-z0-9_\-]{20,}",
    "openrouter": r"\bsk-or-[A-Za-z0-9_\-]{20,}",
    "openai": r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}",
    "google_api": r"\bAIza[0-9A-Za-z_\-]{35}",
    "google_oauth": r"\bya29\.[0-9A-Za-z_\-]{20,}",
    "google_refresh": r"\b1//0[0-9A-Za-z_\-]{20,}",
    "google_secreto": r"\bGOCSPX-[0-9A-Za-z_\-]{20,}",
    "github": r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})",
    "aws": r"\bAKIA[0-9A-Z]{16}\b",
    "slack": r"\bxox[abprs]-[0-9A-Za-z\-]{10,}",
    "clave_privada": r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
}
# Armados por trozos para que ningún escáner vea una clave literal.
EJEMPLOS = {
    "anthropic": "sk-" + "ant-" + "a1" * 15, "openrouter": "sk-" + "or-v1-" + "b2" * 16,
    "openai": "sk-" + "proj-" + "c3" * 12, "google_api": "AI" + "za" + "d" * 35,
    "google_oauth": "ya" + "29." + "e" * 30, "google_refresh": "1/" + "/0" + "f" * 30,
    "google_secreto": "GOC" + "SPX-" + "g" * 24, "github": "gh" + "p_" + "h" * 36,
    "aws": "AK" + "IA" + "A" * 16, "slack": "xo" + "xb-" + "1" * 12,
    "clave_privada": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
}


def es_env_privado(nombre: str) -> bool:
    n = nombre.casefold()
    return n == ".envrc" or n.endswith(".env") or (n.startswith(".env.") and n != ".env.example")


def archivos_a_revisar(raiz: Path) -> list[Path]:
    encontrados = []
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [d for d in subcarpetas if d not in CARPETAS_EXCLUIDAS and not d.endswith(".egg-info")]
        for nombre in archivos:
            ruta = Path(carpeta, nombre)
            if es_env_privado(nombre) or ruta.resolve() == ESTE_ARCHIVO:
                continue
            if ruta.stat().st_size <= MAX_BYTES:
                encontrados.append(ruta)
    return encontrados


def buscar_claves(texto: str) -> list[str]:
    return [nombre for nombre, patron in PATRONES.items() if re.search(patron, texto)]


def hallazgos(raiz: Path) -> list[str]:
    salida = []
    for ruta in archivos_a_revisar(raiz):
        texto = ruta.read_bytes().decode("utf-8", "ignore")
        for n, linea in enumerate(texto.splitlines(), 1):
            for patron in buscar_claves(linea):
                salida.append(f"{ruta.relative_to(raiz)}:{n}:{patron}")
    return salida


def test_patrones_detectan_ejemplos():
    for nombre, valor in EJEMPLOS.items():
        assert nombre in buscar_claves(f"clave = '{valor}'")


def test_textos_inocentes_no_disparan():
    for texto in ("desk-top", "sk-falsa", "ya29", "tok-falso", "Bearer tok-falso", "AIza corta",
                  "-----BEGIN PUBLIC KEY-----"):
        assert buscar_claves(texto) == []


def test_no_lee_env_ni_carpetas_excluidas(tmp_path):
    clave = EJEMPLOS["anthropic"]
    for ruta in (".env", ".env.local", ".envrc", "produccion.env", ".git/config", ".venv/x.py", "datos/notas.txt",
                 "sub/config.py", ".env.example"):
        destino = tmp_path / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(clave, encoding="utf-8")
    assert {p.name for p in archivos_a_revisar(tmp_path)} == {"config.py", ".env.example"}
    encontrados = hallazgos(tmp_path)
    assert sorted(encontrados) == sorted([f"{Path('sub', 'config.py')}:1:anthropic", ".env.example:1:anthropic"])
    assert not any(clave in h for h in encontrados)


def test_repositorio_sin_claves():
    h = hallazgos(RAIZ)
    assert h == [], "Posibles claves (archivo:línea:patrón): " + ", ".join(h)
    revisados = archivos_a_revisar(RAIZ)
    assert ESTE_ARCHIVO not in revisados
    assert RAIZ / ".env" not in revisados
