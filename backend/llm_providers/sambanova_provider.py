"""
SambaNova provider implementation
"""
from typing import Dict, Any, List
import json
import openai
from .base import LLMProvider, LLMConfig


class SambaNovaProvider(LLMProvider):
    """SambaNova provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            client = openai.OpenAI(
                api_key=config.api_key,
                base_url="https://api.sambanova.ai/v1"
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
            raise Exception(f"SambaNova API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        try:
            client = openai.OpenAI(
                api_key=config.api_key,
                base_url="https://api.sambanova.ai/v1"
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
            raise Exception(f"SambaNova API parse error: {e}")

