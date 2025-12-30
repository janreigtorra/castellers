"""
SambaNova provider implementation
"""
from typing import Dict, Any, List
import json
import openai
from .base import LLMProvider, LLMConfig


class SambaNovaProvider(LLMProvider):
    """SambaNova provider implementation"""
    
    # Store last usage for token counting
    last_usage = None
    
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
            client = openai.OpenAI(
                api_key=config.api_key,
                base_url="https://api.sambanova.ai/v1"
            )
            
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
            
            response = client.chat.completions.create(**kwargs)
            
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

