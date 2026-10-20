import pytest

from jarvis.config import ErrorConfig, cargar_config
from jarvis.llm.openrouter import MODELO_OPENROUTER_POR_DEFECTO


def test_claude_cli_es_el_proveedor_por_defecto_y_no_pide_clave():
    config = cargar_config({})
    assert config.proveedor == "claude-cli"
    assert config.modelo == "sonnet"
    assert config.esfuerzo == "medium"
    assert config.clave == ""


def test_claude_cli_modelo_y_esfuerzo_configurables():
    config = cargar_config({"JARVIS_MODEL": "opus", "JARVIS_EFFORT": "high"})
    assert (config.modelo, config.esfuerzo) == ("opus", "high")


def test_llm_provider_elige_proveedor_y_manda_sobre_jarvis_provider():
    config = cargar_config({"LLM_PROVIDER": "claude-cli", "JARVIS_PROVIDER": "openrouter"})
    assert config.proveedor == "claude-cli"


def test_claude_con_clave():
    config = cargar_config({"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "falsa"})
    assert config.proveedor == "claude"
    assert config.modelo == "claude-sonnet-5-5"
    assert config.clave == "falsa"


def test_sin_clave_nombra_variable_y_env():
    with pytest.raises(ErrorConfig) as error:
        cargar_config({"LLM_PROVIDER": "claude"})
    assert "ANTHROPIC_API_KEY" in str(error.value)
    assert ".env" in str(error.value)


def test_openrouter_sin_clave():
    with pytest.raises(ErrorConfig) as error:
        cargar_config({"JARVIS_PROVIDER": "openrouter", "ANTHROPIC_API_KEY": "falsa"})
    assert "OPENROUTER_API_KEY" in str(error.value)
    assert "falsa" not in str(error.value)


def test_openrouter_modelo_por_defecto():
    config = cargar_config({"JARVIS_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "falsa"})
    assert config.proveedor == "openrouter"
    assert config.modelo == MODELO_OPENROUTER_POR_DEFECTO


def test_proveedor_desconocido():
    with pytest.raises(ErrorConfig):
        cargar_config({"JARVIS_PROVIDER": "otro", "ANTHROPIC_API_KEY": "falsa"})


def test_repr_no_muestra_la_clave():
    assert "falsa" not in repr(cargar_config({"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "falsa"}))


def test_jarvis_model_sustituye_al_defecto():
    config = cargar_config({"LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "falsa", "JARVIS_MODEL": "otro-modelo"})
    assert config.modelo == "otro-modelo"
