"""
Xiquet package - Core agent and LLM functionality for the Casteller AI assistant.
"""

from .agent import Xiquet, xiquet_agent
from .llm_function import llm_call, is_guardrail_violation, list_available_providers, list_provider_models
from .llm_sql_v2 import LLMSQLGeneratorV2 as LLMSQLGenerator, get_sql_summary_prompt, NoResultsFoundError, SQLExecutionError, NO_RESULTS_MESSAGE, SQL_RESULT_LIMIT
from .utility_functions import (
    Castell,
    FirstCallResponseFormat,
    get_all_colla_options,
    get_all_castell_options,
    get_all_any_options,
    get_all_lloc_options,
    get_all_diada_options,
    warm_entity_cache
)

__all__ = [
    'Xiquet',
    'xiquet_agent',
    'llm_call',
    'is_guardrail_violation',
    'list_available_providers',
    'list_provider_models',
    'LLMSQLGenerator',
    'get_sql_summary_prompt',
    'NoResultsFoundError',
    'SQLExecutionError',
    'NO_RESULTS_MESSAGE',
    'SQL_RESULT_LIMIT',
    'Castell',
    'FirstCallResponseFormat',
    'get_all_colla_options',
    'get_all_castell_options',
    'get_all_any_options',
    'get_all_lloc_options',
    'get_all_diada_options',
    'warm_entity_cache',
]

