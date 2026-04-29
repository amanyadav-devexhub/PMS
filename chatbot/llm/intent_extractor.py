import json
import re
from .client import ollama_client
from .prompts import get_system_prompt


def extract_intent(user_message, conversation_history=None):
    """
    Extract intent and entities from user message using LLM
    
    Args:
        user_message: The user's message text
        conversation_history: List of previous messages for context
    
    Returns:
        dict: {
            "intent": "create_task",
            "entities": {"name": "Fix bug", "assigned_to": "John"},
            "missing_fields": [],
            "confidence": 0.95
        }
    """
    
    # Build prompt with conversation history
    prompt = f"User message: \"{user_message}\"\n\nExtract intent and entities. Return ONLY JSON."
    
    if conversation_history:
        history_text = "\n".join(conversation_history[-6:])  # Last 3 exchanges
        prompt = f"Previous conversation:\n{history_text}\n\n{prompt}"
    
    # Get response from Ollama
    response = ollama_client.generate(prompt, system_prompt=get_system_prompt())
    
    if not response:
        return {
            "intent": "unknown",
            "entities": {},
            "missing_fields": [],
            "confidence": 0,
            "error": "LLM not available"
        }
    
    # Extract JSON from response (in case there's extra text)
    try:
        # Find JSON in response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group()
        result = json.loads(response)
        
        # Ensure required fields exist
        if "intent" not in result:
            result["intent"] = "unknown"
        if "entities" not in result:
            result["entities"] = {}
        if "missing_fields" not in result:
            result["missing_fields"] = []
        
        result["confidence"] = 0.95
        return result
        
    except json.JSONDecodeError:
        return {
            "intent": "unknown",
            "entities": {},
            "missing_fields": [],
            "confidence": 0,
            "error": "Failed to parse LLM response"
        }