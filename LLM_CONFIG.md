# LLM Configuration Guide
# This file explains how to configure different LLM providers for the Xiquet agent

## FREE PRODUCTION OPTIONS (Recommended!)

### Hugging Face Inference API (COMPLETELY FREE!)
```bash
# Get your free token at https://huggingface.co/settings/tokens
HUGGINGFACE_API_KEY=your_huggingface_token_here
```

**Benefits:**
- **100% FREE** - No usage limits for reasonable production use
- **Catalan-optimized models** available
- **Production-ready** - reliable API
- **No credit card required**

### Ollama (Local - completely free)
```bash
# No API key needed, but make sure Ollama is running locally
# Install Ollama from https://ollama.ai/
# Then run: ollama pull llama3.1:8b
```

## PAID OPTIONS (for comparison)

### OpenAI (Current default)
```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### Groq (Very fast and cheap)
```bash
GROQ_API_KEY=your_groq_api_key_here
```

### Anthropic Claude
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Model Configuration

In `agent.py`, you can change the `MODEL_NAME` variable to use different models:

```python
# FREE OPTIONS (Recommended for production):
MODEL_NAME = "production_free_catalan"  # FREE Catalan-optimized model (DEFAULT)
MODEL_NAME = "production_free"          # FREE Hugging Face model
MODEL_NAME = "production_free_llama"   # FREE Llama-2 model
MODEL_NAME = "local_free"              # FREE local Ollama model

# PAID OPTIONS (for comparison):
MODEL_NAME = "production_cheapest"     # OpenAI GPT-4o-mini ($0.00015/1k tokens) - CHEAPEST
MODEL_NAME = "production_fast"        # Groq Llama-3.1-70B ($0.00059/1k tokens) - FASTEST
MODEL_NAME = "high_quality"           # Anthropic Claude-3-Haiku ($0.00025/1k tokens)
```

## Cost Comparison (per 1k tokens)

### FREE OPTIONS
- **Hugging Face Marco-LLM-ES**: $0.00 (Catalan-optimized, production-ready)
- **Hugging Face Llama-2**: $0.00 (High-quality, production-ready)
- **Hugging Face DialoGPT**: $0.00 (Good for conversations)
- **Ollama Local**: $0.00 (completely free, local only)

### PAID OPTIONS
- **OpenAI GPT-4o-mini**: $0.00015 (CHEAPEST paid option)
- **Anthropic Claude-3-Haiku**: $0.00025 (high quality)
- **Groq Llama-3.1-70B**: $0.00059 (fastest responses)

## Custom Provider Usage

You can also use custom provider:model combinations:

```python
# In agent.py, change MODEL_NAME to:
MODEL_NAME = "groq:llama-3.1-70b-versatile"
MODEL_NAME = "openai:gpt-4o-mini"
MODEL_NAME = "ollama:llama3.1:8b"
MODEL_NAME = "anthropic:claude-3-haiku-20240307"
```

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Testing Different Models

You can test different models by running:

```python
from llm_function import llm_call, list_available_models

# List all available models
print(list_available_models())

# Test a specific model
response = llm_call("Explica què és un castell", model="production_cheap")
print(response)
```

## Production Recommendations

### FREE PRODUCTION DEPLOYMENT (Recommended!)
1. **For Vercel deployment**: Use `production_free_catalan` (Hugging Face Marco-LLM-ES) - **100% FREE**
2. **For high-quality free responses**: Use `production_free_llama` (Hugging Face Llama-2) - **100% FREE**
3. **For local development**: Use `local_free` (Ollama) - **100% FREE**

### PAID OPTIONS (if you need premium features)
1. **For cheapest paid option**: Use `production_cheapest` (OpenAI) - $0.00015/1k tokens
2. **For fastest responses**: Use `production_fast` (Groq) - $0.00059/1k tokens
3. **For highest quality**: Use `high_quality` (Anthropic Claude) - $0.00025/1k tokens

## Quick Start for FREE Production

1. **Get Hugging Face token** (free): https://huggingface.co/settings/tokens
2. **Add to .env file**:
   ```bash
   HUGGINGFACE_API_KEY=your_token_here
   ```
3. **Deploy to Vercel** - your app will work completely free!

**Total cost: $0.00** 
