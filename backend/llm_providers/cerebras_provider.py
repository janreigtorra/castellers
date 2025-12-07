"""
Cerebras provider implementation
"""
from typing import Dict, Any, List
import json
import re
from cerebras.cloud.sdk import Cerebras
from .base import LLMProvider, LLMConfig


class CerebrasProvider(LLMProvider):
    """Cerebras provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
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

