"""
Anthropic Claude provider implementation
"""
from typing import Dict, Any, List
import json
import anthropic
from .base import LLMProvider, LLMConfig


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
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

