"""
OpenAI provider implementation
"""
from typing import Dict, Any, List
from openai import OpenAI
from .base import LLMProvider, LLMConfig


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            client = OpenAI(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                # "temperature": config.temperature,
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
            client = OpenAI(api_key=config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "response_format": response_format,
                # "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            resp = client.chat.completions.parse(**kwargs)
            return resp.choices[0].message.parsed
            
        except Exception as e:
            raise Exception(f"OpenAI API parse error: {e}")

