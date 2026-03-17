import google.generativeai as genai
from django.conf import settings
import logging
import time

logger = logging.getLogger(__name__)


class GeminiService:
    """
    A service class that handles all AI operations.
    
    Why a class? 
    - Groups related functions together
    - Can reuse the same AI configuration
    - Easier to maintain and extend
    """

    def __init__(self):
        """
        Constructor - runs when we create a new GeminiService object.
        Sets up the AI model with our API key.
        """
        # Get API key from Django settings
        self.api_key = settings.GEMINI_API_KEY
        
        # Configure the Gemini library with our key
        genai.configure(api_key=self.api_key)
        
        # Choose which AI model to use
        # 'gemini-1.5-pro' is good for text generation
        # 'gemini-1.5-flash' is faster but slightly less capable
        self.model = genai.GenerativeModel('models/gemini-2.5-pro')
        
        logger.info("✅ Gemini Service initialized successfully")


    def gen_task_description(self,task_name,project_name=None):
        # Generate a professional task description using AI.
        
        # Args:
        #     task_name: The name of the task (required)
        #     project_name: Optional project context
            
        # Returns:
        #     Dictionary with 'success' and either 'description' or 'error'
        # """

        try:
            # Build context string (add project name if provided)
            project_context = f" for project: {project_name}" if project_name else ""

            prompt = f"""
            Task Name: {task_name}{project_context}
            
            You are a professional project management assistant. 
            Write a clear, structured task description with:
            
            1. **Objective**: What needs to be done (1-2 sentences)
            2. **Key Requirements**: 3-5 bullet points
            3. **Expected Outcome**: What success looks like
            
            Make it professional but concise.
            """

            # Send to AI and get response
            # This is where the magic happens!
            response = self.model.generate_content(prompt)
            return {
                'success': True,
                'description': response.text.strip()
            }
            
        except Exception as e:
            # If anything goes wrong, log error and return failure
            logger.error(f"❌ AI Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def enhance_description(self, current_description, task_name):
        """
        Improve an existing description.
        
        This is useful when users already wrote something
        but want to make it better.
        """
        try:
            prompt = f"""
            Task Name: {task_name}
            Current Description: {current_description}
            
            Improve this task description:
            1. Make it more professional
            2. Better structure
            3. Keep all important information
            """
            
            response = self.model.generate_content(prompt)
            
            return {
                'success': True,
                'description': response.text.strip()
            }
            
        except Exception as e:
            logger.error(f"❌ Enhancement Error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }    
