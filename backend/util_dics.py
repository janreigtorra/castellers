
# Available providers and their models
AVAILABLE_PROVIDERS = {
    "groq": {
        "description": "Very fast and cheap inference",
        "models": [
            "llama-3.1-8b-instant", 
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ]
    },
    "openai": {
        "description": "High quality, reliable",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo"
        ]
    },
    "anthropic": {
        "description": "High quality responses",
        "models": [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
    },
    "ollama": {
        "description": "Free local models",
        "models": [
            "llama3.1:8b",
            "llama3.1:70b",
            "mistral:7b",
            "codellama:7b"
        ]
    },
    "gemini": {
        "description": "Google's advanced AI models",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",  # best choice for production (30 RPM 1M TPM)
            "gemini-2.5-pro",
            "gemini-2.0-pro-exp",
            "gemini-flash-latest",
            "gemini-pro-latest"
        ]
    },
    "deepseek": {
        "description": "Fast and cost-effective models",
        "models": [
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
            "deepseek-vl"
        ]
    },
    "cerebras": {
        "description": "High-performance large models",
        "models": [
            "gpt-oss-120b",
            "llama-4-maverick-17b-128e-instruct",
            "qwen-3-235b-a22b-instruct-2507",
            "qwen-3-32b"
        ]
    },
    "sambanova": {
        "description": "SambaNova AI models",
        "models": [
            "Meta-Llama-3.1-8B-Instruct",
            "Meta-Llama-3.1-70B-Instruct",
            "Meta-Llama-3.1-405B-Instruct"
        ]
    }
}

