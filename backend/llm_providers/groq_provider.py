"""
Groq provider implementation (very fast and cheap)
"""
from typing import Dict, Any, List
import json
import re
from groq import Groq
from .base import LLMProvider, LLMConfig


class GroqProvider(LLMProvider):
    """Groq provider implementation (very fast and cheap)"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
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

