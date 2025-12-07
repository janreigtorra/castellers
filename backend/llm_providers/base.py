"""
Base classes for LLM providers
"""
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM providers"""
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0
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

