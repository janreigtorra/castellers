"""
Ollama local provider implementation
"""
from typing import Dict, Any, List
import json
import requests
from .base import LLMProvider, LLMConfig


class OllamaProvider(LLMProvider):
    """Ollama local provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
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

