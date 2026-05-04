import json
import re
from groq import Groq


class GroqClient:
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"  # Fast and accurate
    
    def generate(self, prompt, system_prompt=None):
        """Send a prompt to Groq and get response"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq API error: {e}")
            return None
    
    def extract_intent(self, user_message, conversation_history=None):
        """Extract intent and entities from user message"""
        from .prompts import get_system_prompt
        
        system_prompt = get_system_prompt()
        
        # Build conversation context if available
        context = ""
        if conversation_history:
            context = "\n".join(conversation_history[-6:])
            context = f"Previous conversation:\n{context}\n\n"
        
        user_prompt = f"""{context}Extract intent and entities from this message. Return ONLY valid JSON.

User message: "{user_message}"

Required JSON format:
{{
    "intent": "intent_name",
    "entities": {{}},
    "missing_fields": []
}}

Available intents: create_task, create_project, create_user, view_tasks, view_projects, start_task, pause_task, resume_task, complete_task, greeting

Respond ONLY with JSON, nothing else."""
        
        response = self.generate(user_prompt, system_prompt=system_prompt)
        
        print(f"Groq response: {response[:200]}..." if response else "No response")
        
        if not response:
            return {
                "intent": "unknown",
                "entities": {},
                "missing_fields": []
            }
        
        # Extract JSON from response
        try:
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
            
            return result
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return {
                "intent": "unknown",
                "entities": {},
                "missing_fields": []
            }


# Global instance
_groq_client = None

def get_groq_client(api_key):
    global _groq_client
    if _groq_client is None and api_key:
        _groq_client = GroqClient(api_key)
    return _groq_client