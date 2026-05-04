import json
import requests


class OllamaClient:
    """Client for interacting with local Ollama LLM"""
    
    def __init__(self, host="http://localhost:11434", model = "qwen2.5:1.5b"):
        self.host = host
        self.model = model
    
    def is_available(self):
        """Check if Ollama server is running"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt, system_prompt=None):
        """Send a prompt to Ollama and get response"""
        url = f"{self.host}/api/generate"
        
        # Build the payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Lower temperature for more consistent JSON output
                "num_predict": 500   # Limit response length
            }
        }
        
        if system_prompt:
            # For phi3, we need to combine system prompt with user prompt
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant: "
            payload["prompt"] = full_prompt
        else:
            payload["prompt"] = prompt
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                print(f"Ollama API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ollama error: {e}")
            return None
    
    def extract_intent(self, user_message, conversation_history=None):
        """Extract intent and entities from user message"""
        from .prompts import get_system_prompt
        
        system_prompt = get_system_prompt()
        
        # Build the user prompt
        user_prompt = f"""Extract intent and entities from this message. Return ONLY valid JSON, no other text.

User message: "{user_message}"

Required JSON format:
{{
    "intent": "intent_name",
    "entities": {{
        "field_name": "extracted_value"
    }},
    "missing_fields": []
}}

Available intents: create_task, create_project, create_user, view_tasks, view_projects, start_task, pause_task, complete_task, greeting

For create_user, extract: first_name, last_name, email, username, role
For create_task, extract: name, assigned_to, project, start_date, end_date
For create_project, extract: name, description, start_date, end_date

Respond ONLY with JSON, nothing else."""
        
        response = self.generate(user_prompt, system_prompt=system_prompt)
        
        print(f"Ollama raw response: {response}")  # Debug
        
        if not response:
            return {
                "intent": "unknown",
                "entities": {},
                "missing_fields": [],
                "confidence": 0,
                "error": "LLM not available"
            }
        
        try:
            # Find JSON in response (between { and })
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = response[start:end]
                result = json.loads(json_str)
            else:
                # Try to parse the whole response as JSON
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
                "missing_fields": [],
                "confidence": 0,
                "error": f"Failed to parse response: {response[:100]}"
            }


# Create singleton instance
ollama_client = OllamaClient()