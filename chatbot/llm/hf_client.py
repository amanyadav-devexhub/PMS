# chatbot/llm/hf_client.py

import json
import re
import os
from huggingface_hub import InferenceClient
from django.conf import settings


class HuggingFaceClient:
    """Hugging Face Inference API for Qwen2.5-7B-Instruct using InferenceClient"""
    
    def __init__(self, hf_token=None):
        self.hf_token = hf_token or settings.HF_TOKEN
        self.model = "Qwen/Qwen2.5-7B-Instruct:together"  # Using the together endpoint
        # Initialize the InferenceClient
        self.client = InferenceClient(
            api_key=self.hf_token,
        )
        print(f"✅ Hugging Face client initialized with model: {self.model}")
    
    def is_available(self):
        return bool(self.hf_token)
    
    def generate(self, prompt, system_prompt=None):
        """Send a prompt to Qwen model using chat completion"""
        
        # Build messages in chat format
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            print(f"📡 Calling Hugging Face InferenceClient for Qwen...")
            
            # Use the chat completions API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.1,
                top_p=0.95,
                stream=False
            )
            
            # Extract the response text
            if completion and completion.choices:
                response_text = completion.choices[0].message.content
                print(f"✅ Successfully got response from model")
                return response_text
            else:
                print("❌ No response choices returned")
                return None
                
        except Exception as e:
            print(f"Hugging Face error: {e}")
            return None
    
    def extract_intent(self, user_message, conversation_history=None):
        """Extract intent and entities from user message"""
        from .prompts import get_system_prompt
        
        system_prompt = get_system_prompt()
        
        # Build conversation context
        context = ""
        if conversation_history:
            context = "\n".join(conversation_history[-6:])
            context = f"Previous conversation:\n{context}\n\n"
        
        user_prompt = f"""{context}Extract intent and entities from this message. Return ONLY valid JSON, no other text.

User message: "{user_message}"

Required JSON format:
{{
    "intent": "intent_name",
    "entities": {{}},
    "missing_fields": []
}}

Available intents: create_task, create_project, create_user, view_tasks, view_projects, start_task, pause_task, resume_task, complete_task, greeting, edit_task, delete_task, add_summary

For create_task, extract: name, assigned_to, project
For create_project, extract: name, description
For create_user, extract: first_name, last_name, email, role

Respond ONLY with JSON, nothing else."""
        
        response = self.generate(user_prompt, system_prompt=system_prompt)
        
        print(f"HF Response: {response[:200]}..." if response else "No response")
        
        if not response:
            return {
                "intent": "unknown",
                "entities": {},
                "missing_fields": []
            }
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group()
            result = json.loads(response)
            
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


_hf_client = None

def get_hf_client():
    global _hf_client
    if _hf_client is None and settings.HF_TOKEN:
        _hf_client = HuggingFaceClient()
    return _hf_client