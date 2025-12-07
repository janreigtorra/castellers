"""
Google Gemini provider implementation
"""
from typing import Dict, Any, List
import json
import re
import google.generativeai as genai
from .base import LLMProvider, LLMConfig


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation"""
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
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

