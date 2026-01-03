"""LLM client configuration and factory."""

from typing import Optional

from langchain_core.language_models import BaseChatModel

from ..config.settings import settings


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """
    Get an LLM instance based on configuration.

    Args:
        provider: Override the default provider ("anthropic" or "openai")
        model: Override the default model name
        temperature: Override the default temperature

    Returns:
        A configured LLM instance
    """
    provider = provider or settings.llm_provider
    model = model or settings.llm_model
    temperature = temperature if temperature is not None else settings.llm_temperature

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=settings.anthropic_api_key,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_structured_llm(
    output_schema: type,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """
    Get an LLM configured for structured output.

    Args:
        output_schema: Pydantic model or TypedDict for structured output
        provider: Override the default provider
        model: Override the default model name

    Returns:
        An LLM configured with structured output
    """
    llm = get_llm(provider=provider, model=model, temperature=0.3)
    return llm.with_structured_output(output_schema)
