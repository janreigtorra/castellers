"""
llm_function.py
Modular LLM function supporting multiple providers and models for cost-effective production deployment.
Supports OpenAI, Anthropic, Ollama, Hugging Face, and other providers with Catalan language support.
"""

import os
import json
from typing import Dict, Any, Optional, Union, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from dotenv import load_dotenv        
import re


# Load environment variables
load_dotenv()

@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 30

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        """Generate response from messages"""
        pass
    
    @abstractmethod
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        """Generate structured response from messages"""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "response_format": response_format,
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            resp = client.chat.completions.parse(**kwargs)
            return resp.choices[0].message.parsed
            
        except Exception as e:
            raise Exception(f"OpenAI API parse error: {e}")

class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=config.api_key)
            
            # Convert OpenAI format to Anthropic format
            system_msg = ""
            user_msg = ""
            
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                elif msg["role"] == "user":
                    user_msg = msg["content"]
            
            resp = client.messages.create(
                model=config.model,
                max_tokens=config.max_tokens or 1000,
                temperature=config.temperature,
                system=system_msg,
                messages=[{"role": "user", "content": user_msg}]
            )
            
            return resp.content[0].text.strip()
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        # Anthropic doesn't support structured output yet, fallback to generate
        response_text = self.generate(messages, config, response_format)
        try:
            # Try to parse JSON response
            return json.loads(response_text)
        except:
            return response_text

class OllamaProvider(LLMProvider):
    """Ollama local provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            import requests
            
            # Convert messages to Ollama format
            prompt = ""
            for msg in messages:
                if msg["role"] == "system":
                    prompt += f"System: {msg['content']}\n\n"
                elif msg["role"] == "user":
                    prompt += f"User: {msg['content']}\n\n"
            
            prompt += "Assistant:"
            
            url = f"{config.base_url or 'http://localhost:11434'}/api/generate"
            
            payload = {
                "model": config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.temperature,
                    "num_predict": config.max_tokens or 1000
                }
            }
            
            response = requests.post(url, json=payload, timeout=config.timeout)
            response.raise_for_status()
            
            result = response.json()
            return result["response"].strip()
            
        except Exception as e:
            raise Exception(f"Ollama API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        response_text = self.generate(messages, config, response_format)
        try:
            # Try to parse JSON response
            return json.loads(response_text)
        except:
            return response_text


class GroqProvider(LLMProvider):
    """Groq provider implementation (very fast and cheap)"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            from groq import Groq
            
            client = Groq(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Groq API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        # Groq doesn't support structured output yet, fallback to generate
        response_text = self.generate(messages, config, response_format)
        try:
            # Try to parse JSON response
            return json.loads(response_text)
        except:
            return response_text


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=config.api_key)
            model = genai.GenerativeModel(config.model)
            
            # Convert messages to Gemini format
            prompt_parts = []
            for msg in messages:
                if msg["role"] == "system":
                    prompt_parts.append(f"System: {msg['content']}")
                elif msg["role"] == "user":
                    prompt_parts.append(f"User: {msg['content']}")
                elif msg["role"] == "assistant":
                    prompt_parts.append(f"Assistant: {msg['content']}")
            
            prompt = "\n\n".join(prompt_parts)
            
            generation_config = genai.types.GenerationConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens or 1000,
            )
            
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            return response.text.strip()
            
        except Exception as e:
            raise Exception(f"Gemini API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        # Gemini doesn't support structured output yet, fallback to generate
        response_text = self.generate(messages, config, response_format)
        
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                # If we have a response_format, try to create an instance
                if response_format:
                    try:
                        return response_format(**parsed)
                    except Exception as e:
                        print(f"Warning: Could not create {response_format.__name__} instance: {e}")
                        return parsed
                return parsed
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse JSON: {e}")
                return response_text
        else:
            return response_text


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            import openai
            
            client = openai.OpenAI(
                api_key=config.api_key,
                base_url="https://api.deepseek.com"
            )
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"DeepSeek API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        try:
            import openai
            
            client = openai.OpenAI(
                api_key=config.api_key,
                base_url="https://api.deepseek.com"
            )
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            response = client.chat.completions.create(**kwargs)
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            parsed = json.loads(response_text)
            
            # If we have a response_format, try to create an instance
            if response_format:
                try:
                    return response_format(**parsed)
                except Exception as e:
                    print(f"Warning: Could not create {response_format.__name__} instance: {e}")
                    return parsed
            return parsed
            
        except Exception as e:
            raise Exception(f"DeepSeek API parse error: {e}")


class CerebrasProvider(LLMProvider):
    """Cerebras provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            from cerebras.cloud.sdk import Cerebras
            
            client = Cerebras(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "stream": False
            }
            
            if config.max_tokens:
                kwargs["max_completion_tokens"] = config.max_tokens
            
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Cerebras API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        try:
            from cerebras.cloud.sdk import Cerebras
            
            client = Cerebras(api_key=config.api_key)
            
            # Add JSON mode instruction to the system message
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] += "\n\nIMPORTANT: Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use <think> tags or any other formatting."
            else:
                messages.insert(0, {
                    "role": "system", 
                    "content": "Respond ONLY with valid JSON. Do not include any text before or after the JSON. Do not use <think> tags or any other formatting."
                })
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "stream": False
            }
            
            if config.max_tokens:
                kwargs["max_completion_tokens"] = config.max_tokens
            
            response = client.chat.completions.create(**kwargs)
            response_text = response.choices[0].message.content.strip()
            
            # Clean up the response - remove <think> tags and extract JSON
            import re
            
            # Remove <think> tags
            response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    parsed = json.loads(json_str)
                    
                    # If we have a response_format, try to create an instance
                    if response_format:
                        try:
                            return response_format(**parsed)
                        except Exception as e:
                            print(f"Warning: Could not create {response_format.__name__} instance: {e}")
                            return parsed
                    return parsed
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse JSON: {e}")
                    return response_text
            else:
                return response_text
            
        except Exception as e:
            raise Exception(f"Cerebras API parse error: {e}")

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
            "cerebras": CerebrasProvider()
        }
    
    def get_provider(self, provider_name: str) -> LLMProvider:
        """Get provider by name"""
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not supported. Available: {list(self.providers.keys())}")
        return self.providers[provider_name]

# Global manager instance
llm_manager = LLMManager()

# Available providers and their models
AVAILABLE_PROVIDERS = {
    "groq": {
        "description": "Very fast and cheap inference",
        "models": [
            "llama-3.1-8b-instant", 
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ]
    },
    "openai": {
        "description": "High quality, reliable",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo"
        ]
    },
    "anthropic": {
        "description": "High quality responses",
        "models": [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
    },
    "ollama": {
        "description": "Free local models",
        "models": [
            "llama3.1:8b",
            "llama3.1:70b",
            "mistral:7b",
            "codellama:7b"
        ]
    },
    "gemini": {
        "description": "Google's advanced AI models",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",  # best choice for production (30 RPM 1M TPM)
            "gemini-2.5-pro",
            "gemini-2.0-pro-exp",
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]
    },
    "deepseek": {
        "description": "Fast and cost-effective models",
        "models": [
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
            "deepseek-vl"
        ]
    },
    "cerebras": {
        "description": "High-performance large models",
        "models": [
            "gpt-oss-120b",
            "llama-4-maverick-17b-128e-instruct",
            "qwen-3-235b-a22b-instruct-2507",
            "qwen-3-32b"
        ]
    }
}

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
    model: str = "groq:llama-3.1-70b-versatile",
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
        # Legacy model name - convert to provider:model
        legacy_models = {
            "production_balanced": "openai:gpt-4o-mini",
            "production_cheap": "groq:llama-3.1-70b-versatile",
            "local_free": "ollama:llama3.1:8b",
            "high_quality": "anthropic:claude-3-haiku-20240307"
        }
        
        if model in legacy_models:
            provider_name, model_name = legacy_models[model].split(":", 1)
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
        if response_format:
            return provider.parse(messages, config, response_format)
        else:
            return provider.generate(messages, config, response_format)
    except Exception as e:
        raise Exception(f"LLM call failed with {config.provider}:{config.model}: {e}")

def estimate_cost(prompt: str, model: str = "groq:llama-3.1-70b-versatile") -> Dict[str, Any]:
    """Estimate cost for a prompt with a given model"""
    # Rough token estimation (4 characters per token)
    estimated_tokens = len(prompt) // 4
    
    # Cost estimates per 1k tokens (input)
    cost_estimates = {
        "groq": 0.00059,
        "openai": 0.00015,
        "anthropic": 0.00025,
        "ollama": 0.0,
        "gemini": 0.000075,  # Gemini 1.5 Flash pricing
        "deepseek": 0.00014,  # DeepSeek Chat pricing
        "cerebras": 0.0002  # Cerebras pricing (estimated)
    }
    
    if ":" in model:
        provider = model.split(":")[0]
        cost_per_1k = cost_estimates.get(provider, 0.0)
    else:
        cost_per_1k = 0.0
    
    estimated_cost = (estimated_tokens / 1000) * cost_per_1k
    
    return {
        "model": model,
        "estimated_tokens": estimated_tokens,
        "cost_per_1k_tokens": cost_per_1k,
        "estimated_cost": estimated_cost
    }

# Example usage and testing
if __name__ == "__main__":
    # Test different models
    test_prompt = "Explica què és un castell de 3 pisos"
    
    print("Available models:")
    for name, config in list_available_models().items():
        print(f"- {name}: {config['description']} (${config['cost_per_1k_tokens']}/1k tokens)")
    
    print("\nTesting models...")
    
    # Test with different models (uncomment to test)
    # try:
    #     response = llm_call(test_prompt, model="production_cheap")
    #     print(f"Groq response: {response[:100]}...")
    # except Exception as e:
    #     print(f"Groq error: {e}")
    
    # try:
    #     response = llm_call(test_prompt, model="local_free")
    #     print(f"Ollama response: {response[:100]}...")
    # except Exception as e:
    #     print(f"Ollama error: {e}")
    
    # Cost estimation
    print(f"\nCost estimation for prompt:")
    cost_info = estimate_cost(test_prompt, "production_balanced")
    print(f"Model: {cost_info['model']}")
    print(f"Estimated tokens: {cost_info['estimated_tokens']}")
    print(f"Estimated cost: ${cost_info['estimated_cost']:.6f}")
