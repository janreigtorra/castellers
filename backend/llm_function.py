"""
llm_function.py
Modular LLM function supporting multiple providers and models for cost-effective production deployment.
Supports OpenAI, Anthropic, Ollama, Hugging Face, and other providers with Catalan language support.
"""

import os
from this import d
from typing import Dict, Any, Optional, Union, List
from dotenv import load_dotenv

# Import providers from llm_providers package
from llm_providers import (
    LLMConfig,
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    GroqProvider,
    GeminiProvider,
    DeepSeekProvider,
    CerebrasProvider,
    SambaNovaProvider
)

# Import utility dictionaries
from util_dics import AVAILABLE_PROVIDERS

# Load environment variables
load_dotenv()

class LLMManager:
    """Manager for different LLM providers"""
    
    def __init__(self):
        self.providers = {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "ollama": OllamaProvider(),
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "deepseek": DeepSeekProvider(),
            "cerebras": CerebrasProvider(),
            "sambanova": SambaNovaProvider()
        }
    
    def get_provider(self, provider_name: str) -> LLMProvider:
        """Get provider by name"""
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not supported. Available: {list(self.providers.keys())}")
        return self.providers[provider_name]

# Global manager instance
llm_manager = LLMManager()

def list_available_providers() -> Dict[str, Dict[str, Any]]:
    """List all available providers and their models"""
    return AVAILABLE_PROVIDERS.copy()

def list_provider_models(provider: str) -> List[str]:
    """List models available for a specific provider"""
    if provider not in AVAILABLE_PROVIDERS:
        raise ValueError(f"Provider '{provider}' not found. Available: {list(AVAILABLE_PROVIDERS.keys())}")
    return AVAILABLE_PROVIDERS[provider]["models"]

def llm_call(
    prompt: str, 
    model: str,
    response_format=None,
    system_message: str = "Ets Xiquet, un expert en el món casteller. Respon sempre en català.",
    custom_config: Optional[LLMConfig] = None
) -> Union[str, Any]:
    """
    Modular LLM call function supporting multiple providers and models.
    
    Args:
        prompt: The user prompt
        model: Provider:model format (e.g., "groq:llama-3.1-70b-versatile") or legacy model name
        response_format: Pydantic model for structured output (optional)
        system_message: System message for the LLM
        custom_config: Custom LLMConfig for advanced usage
    
    Returns:
        Generated response (string or parsed object)
    """
    from datetime import datetime
    
    llm_start = datetime.now()
    
    # Parse model parameter
    if ":" in model:
        # Provider:model format
        provider_name, model_name = model.split(":", 1)
        api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
        config = LLMConfig(
            provider=provider_name,
            model=model_name,
            api_key=api_key
        )
    else:
        raise ValueError(f"Unknown model '{model}'. Use provider:model format (e.g., 'groq:llama-3.1-70b-versatile')")
    
    # Validate API key
    if not config.api_key and config.provider not in ["ollama"]:
        raise ValueError(f"API key not found for provider '{config.provider}'. Set {config.provider.upper()}_API_KEY environment variable.")
    
    # Prepare messages
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    
    # Get provider and generate response
    provider = llm_manager.get_provider(config.provider)
    
    try:
        api_start = datetime.now()
        if response_format:
            result = provider.parse(messages, config, response_format)
        else:
            result = provider.generate(messages, config, response_format)
        api_time = (datetime.now() - api_start).total_seconds() * 1000
        
        total_time = (datetime.now() - llm_start).total_seconds() * 1000
        print(f"[TIMING] LLM API call ({config.provider}:{config.model}): {api_time:.2f}ms (total: {total_time:.2f}ms)")
        
        return result
    except Exception as e:
        raise Exception(f"LLM call failed with {config.provider}:{config.model}: {e}")

# Example usage and testing
if __name__ == "__main__":
    # Test different models
    test_prompt = "Explica què és un castell de 3 pisos"
    
    print("Available providers:")
    for name, config in list_available_providers().items():
        print(f"- {name}: {config['description']}")
    
    print("\nTesting models...")
    
    