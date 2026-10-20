import jarvis.__main__ as principal


def test_main_sin_clave_devuelve_1_sin_tocar_la_red(monkeypatch, capsys):
    for variable in ("JARVIS_PROVIDER", "JARVIS_MODEL", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "claude")  # el proveedor por defecto (claude-cli) no pide clave
    monkeypatch.setattr(principal, "load_dotenv", lambda: None)  # no se lee el .env real

    def prohibido(*args, **kwargs):
        raise AssertionError("no debía crear el cliente ni conversar")

    monkeypatch.setattr(principal, "crear_cliente", prohibido)
    monkeypatch.setattr(principal, "conversar", prohibido)

    assert principal.main() == 1
    salida = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in salida.err
    assert salida.out == ""
