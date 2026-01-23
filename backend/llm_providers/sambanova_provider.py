"""
SambaNova provider implementation
"""
from typing import Dict, Any, List
import json
import time
import openai
from .base import LLMProvider, LLMConfig


class SambaNovaProvider(LLMProvider):
    """SambaNova provider implementation"""
    
    # Store last usage for token counting
    last_usage = None
    
    # Reusable client (avoid creating new connections each time)
    _client = None
    _client_api_key = None
    
    # Retry configuration
    MAX_RETRIES = 3
    BASE_DELAY = 2  # seconds
    
    @classmethod
    def _get_client(cls, api_key: str):
        """Get or create a reusable client"""
        if cls._client is None or cls._client_api_key != api_key:
            cls._client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.sambanova.ai/v1"
            )
            cls._client_api_key = api_key
        return cls._client
    
    def _call_with_retry(self, client, kwargs):
        """Execute API call with exponential backoff retry for rate limits"""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat.completions.create(**kwargs)
                return response
            except openai.RateLimitError as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_DELAY * (2 ** attempt)  # 2s, 4s, 8s
                    print(f"[SambaNova] Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{self.MAX_RETRIES})...")
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                raise
        
        raise last_error
    
    def generate(self, messages: List[Dict[str, str]], config: LLMConfig, response_format=None) -> str:
        try:
            client = self._get_client(config.api_key)
            
            kwargs = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            response = self._call_with_retry(client, kwargs)
            
            # Store token usage
            if hasattr(response, 'usage') and response.usage:
                SambaNovaProvider.last_usage = {
                    'input': getattr(response.usage, 'prompt_tokens', 0),
                    'output': getattr(response.usage, 'completion_tokens', 0)
                }
            else:
                SambaNovaProvider.last_usage = None
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"SambaNova API error: {e}")
    
    def parse(self, messages: List[Dict[str, str]], config: LLMConfig, response_format) -> Any:
        try:
            client = self._get_client(config.api_key)
            
            # Generate JSON schema from Pydantic model and inject into prompt
            # SambaNova doesn't support native structured outputs, so we need to guide the LLM
            if response_format and hasattr(response_format, 'model_json_schema'):
                schema = response_format.model_json_schema()
                # Simplify schema for LLM - remove $defs and inline the structure
                schema_str = self._simplify_schema_for_prompt(schema)
                
                # Inject schema instruction into the last user message
                modified_messages = messages.copy()
                if modified_messages and modified_messages[-1]["role"] == "user":
                    modified_messages[-1] = {
                        "role": "user",
                        "content": modified_messages[-1]["content"] + f"\n\nRESPON OBLIGATÒRIAMENT en format JSON seguint EXACTAMENT aquest esquema:\n{schema_str}\n\nNomés retorna el JSON, sense explicacions."
                    }
            else:
                modified_messages = messages
            
            kwargs = {
                "model": config.model,
                "messages": modified_messages,
                "response_format": {"type": "json_object"},
                "temperature": config.temperature,
                "timeout": config.timeout
            }
            
            if config.max_tokens:
                kwargs["max_tokens"] = config.max_tokens
            
            response = self._call_with_retry(client, kwargs)
            
            # Store token usage
            if hasattr(response, 'usage') and response.usage:
                SambaNovaProvider.last_usage = {
                    'input': getattr(response.usage, 'prompt_tokens', 0),
                    'output': getattr(response.usage, 'completion_tokens', 0)
                }
            else:
                SambaNovaProvider.last_usage = None
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            parsed = json.loads(response_text)
            
            # If we have a response_format, try to create an instance
            if response_format:
                try:
                    return response_format(**parsed)
                except Exception as e:
                    print(f"Warning: Could not create {response_format.__name__} instance: {e}")
                    print(f"Raw LLM response: {response_text[:500]}...")
                    return parsed
            return parsed
            
        except Exception as e:
            raise Exception(f"SambaNova API parse error: {e}")
    
    def _simplify_schema_for_prompt(self, schema: dict) -> str:
        """Convert Pydantic JSON schema to a simplified format for LLM prompts"""
        # Extract just the field definitions, ignoring $defs
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        simplified = {}
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "string")
            if field_type == "array":
                items_type = field_info.get("items", {}).get("type", "string")
                simplified[field_name] = f"[{items_type}]"
            else:
                simplified[field_name] = field_type
                
        return json.dumps(simplified, indent=2, ensure_ascii=False)

