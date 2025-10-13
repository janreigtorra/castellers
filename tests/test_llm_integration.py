#!/usr/bin/env python3
"""
test_llm_integration.py
Simple test script to verify a specific LLM provider and model works with Xiquet.
"""

import os
import sys
from dotenv import load_dotenv
from llm_function import llm_call, list_available_providers, list_provider_models

# Load environment variables
load_dotenv()

def test_provider_model(provider, model):
    """Test a specific provider and model with Xiquet"""
    print(f"Testing {provider}:{model}")
    print("-" * 40)
    
    # Test basic LLM call
    test_prompt = "Explica breument què és un castell de 3 pisos"
    
    try:
        print("1. Testing basic LLM call...")
        response = llm_call(test_prompt, model=f"{provider}:{model}")
        print(f"   SUCCESS: {response[:100]}...")
    except Exception as e:
        print(f"   FAILED: {e}")
        return False
    
    # Test Xiquet agent integration
    try:
        print("2. Testing Xiquet agent integration...")
        from agent import Xiquet
        
        xiquet = Xiquet()
        # Temporarily change the model for testing
        import agent
        original_model_name = agent.MODEL_NAME
        agent.MODEL_NAME = f"{provider}:{model}"
        
        test_question = "Quina va ser la millor diada dels castellers de Vilafranca l'any 2024?"
        
        response = xiquet.process_question(test_question)
        print(f"   SUCCESS: {response[:100]}...")
        
        # Restore original model
        agent.MODEL_NAME = original_model_name
        
    except Exception as e:
        print(f"   FAILED: {e}")
        # Restore original model even if test failed
        try:
            agent.MODEL_NAME = original_model_name
        except:
            pass
        return False
    
    print("3. All tests passed!")
    return True

def list_models():
    """List all available providers and models"""
    print("Available providers and models:")
    providers = list_available_providers()
    for provider, info in providers.items():
        print(f"  {provider}: {info['description']}")
        for model in info['models']:
            print(f"    - {provider}:{model}")

if __name__ == "__main__":
    
    provider = 'gemini'
    model = 'gemini-2.0-flash-lite'
    
    print(f"Testing {provider}:{model} with Xiquet agent")
    print("=" * 50)
    
    success = test_provider_model(provider, model)
    
    if success:
        print("\nSUCCESS: Provider and model work correctly with Xiquet!")
    else:
        print("\nFAILED: Provider and model have issues.")
        sys.exit(1)
