import re
import random
from datetime import datetime
from difflib import SequenceMatcher
from .base import BaseAction

class ViewActions(BaseAction):
    """Handles greeting, help, small talk, and unknown actions with smart matching"""
    
    def __init__(self, user):
        super().__init__(user)
        self.user = user  # Store user to update preferred_name
    
    # ============================================================
    # FUZZY GREETING MATCHER - Handles typos and variants
    # ============================================================
    
    def _normalize_text(self, text):
        """Remove extra repeating characters - converts 'hiiiiii' to 'hi'"""
        if not text:
            return text
        # Replace 3+ repeated chars with 2 of that char
        result = re.sub(r'(.)\1{2,}', r'\1\1', text)
        return result.lower().strip()
    
    def _get_similarity(self, a, b):
        """Calculate similarity ratio between two strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def _match_greeting(self, message):
        """Match greeting with fuzzy logic - handles 'hiiiiii', 'heeeelooooo', etc."""
        normalized = self._normalize_text(message)
        
        # Define greeting patterns with their normalized forms
        greeting_patterns = {
            'hi': ['hi', 'hii', 'hy', 'hlo'],
            'hello': ['hello', 'helo', 'hllo', 'helloo'],
            'hey': ['hey', 'heyy', 'hyy'],
            'good morning': ['good morning', 'gud morning', 'gd morning', 'morning'],
            'good afternoon': ['good afternoon', 'gud afternoon', 'afternoon'],
            'good evening': ['good evening', 'gud evening', 'evening'],
            'good night': ['good night', 'gud night', 'night']
        }
        
        for pattern, variants in greeting_patterns.items():
            for variant in variants:
                if self._get_similarity(normalized, variant) > 0.7:
                    return pattern
                if variant in normalized:
                    return pattern
        
        return None
    
    # ============================================================
    # TIME-AWARE GREETINGS
    # ============================================================
    
    def _get_time_greeting(self):
        """Return greeting based on time of day"""
        current_hour = datetime.now().hour
        
        if 5 <= current_hour < 12:
            return {
                'greeting': "Good morning",
                'icon': "☀️",
                'responses': [
                    "Good morning! Ready to tackle your tasks?",
                    "Morning! Hope you had a great start to your day!",
                    "Good morning! Let's make today productive!",
                    "Morning! What's on your agenda today?",
                    "Good morning! I'm here to help you stay organized.",
                    "Rise and shine! Ready to crush your to-do list?",
                    "Good morning! Fresh day, fresh opportunities!",
                    "Morning! How can I assist you today?"
                ]
            }
        elif 12 <= current_hour < 17:
            return {
                'greeting': "Good afternoon",
                'icon': "🌤️",
                'responses': [
                    "Good afternoon! How's your day going?",
                    "Afternoon! Still plenty of time to get things done!",
                    "Good afternoon! Need help with anything?",
                    "Afternoon! Let's keep the momentum going!",
                    "Good afternoon! What can I do for you?",
                    "Hope your day is going well! How can I help?"
                ]
            }
        elif 17 <= current_hour < 21:
            return {
                'greeting': "Good evening",
                'icon': "🌙",
                'responses': [
                    "Good evening! Wrapping up for the day?",
                    "Evening! Need to finish any tasks?",
                    "Good evening! I'm still here to help!",
                    "Evening! Let me know what you need.",
                    "Good evening! How can I assist you?",
                    "Evening! One last push to finish your tasks?"
                ]
            }
        else:
            return {
                'greeting': "Working late",
                'icon': "🌟",
                'responses': [
                    "Working late? I admire the dedication!",
                    "Late night session? Let me help you power through!",
                    "Burning the midnight oil? I'm here for you!",
                    "Late worker! What do you need help with?",
                    "Still working? You're dedicated! How can I help?",
                    "Late night productivity session? Let's do this!"
                ]
            }
    
    # ============================================================
    # NAME EXTRACTION AND STORAGE
    # ============================================================
    
    def _extract_and_save_name(self, message):
        """Extract user name from message and save to database"""
        # Patterns to match: "I am Anmol", "My name is Anmol", "Call me Anmol"
        patterns = [
            r'(?:i am|i\'m)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|\!|\?|$| and)',
            r'(?:my name is|name is)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|\!|\?|$| and)',
            r'(?:call me|you can call me)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|\!|\?|$| and)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower(), re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                # Save to database
                if self.user and not self.user.preferred_name:
                    self.user.preferred_name = name
                    self.user.save(update_fields=['preferred_name'])
                    return name
                elif self.user and self.user.preferred_name != name:
                    # Optional: update if different? Let's keep original
                    return self.user.preferred_name
                return name
        return None
    
    def _get_user_name(self):
        """Get user's preferred name from database"""
        if self.user and self.user.preferred_name:
            return self.user.preferred_name
        return None
    
    # ============================================================
    # SMALL TALK RESPONSES
    # ============================================================
    
    def _get_joke(self):
        """Return a random clean joke (work-appropriate)"""
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "Why did the developer go broke? Because he used up all his cache! 💰",
            "What do you call a fake noodle? An impasta! 🍝",
            "Why don't scientists trust atoms? Because they make up everything! ⚛️",
            "What did the computer do at lunch? Had a byte! 💻",
            "Why was the JavaScript developer sad? Because he didn't Node how to Express himself! 😢",
            "What's a computer's favorite beat? An micro-chip! 🎵",
            "Why did the spreadsheet go to therapy? It had too many issues! 📊",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why don't eggs tell jokes? They'd crack each other up! 🥚",
            "What do you call a sleeping bull? A bulldozer! 💤",
            "Why did the coffee file a police report? It got mugged! ☕",
            "What's the best thing about Switzerland? I don't know, but the flag is a big plus! 🇨🇭",
            "Why did the task go to therapy? It had commitment issues! 📋"
        ]
        return random.choice(jokes)
    
    def _get_capabilities(self):
        """Return bot capabilities as formatted message"""
        return (
            "Here's what I can help you with:\n\n"
            "📝 **Create Things:**\n"
            "• Create a task - 'Create task Fix bug for John'\n"
            "• Create a project - 'Create project Website Redesign'\n"
            "• Create a user - 'Create user John Doe as Employee'\n\n"
            "👀 **View Things:**\n"
            "• View tasks - 'Show my tasks'\n"
            "• View projects - 'Show my projects'\n"
            "• View users - 'Show team members'\n\n"
            "▶️ **Manage Tasks:**\n"
            "• Start a task - 'Start task Fix bug'\n"
            "• Pause a task - 'Pause task Fix bug'\n"
            "• Resume a task - 'Resume task Fix bug'\n"
            "• Complete a task - 'Complete task Fix bug'\n\n"
            "✏️ **Edit Things:**\n"
            "• Edit task - 'Edit task 42 name to New Name'\n"
            "• Edit project - 'Edit project 42 status to COMPLETED'\n\n"
            "🗑️ **Delete Things:**\n"
            "• Delete task - 'Delete task 42'\n"
            "• Delete project - 'Delete project 42'\n\n"
            "💬 **Just type naturally and I'll understand!** 🚀"
        )
    
    # ============================================================
    # MAIN GREETING METHOD
    # ============================================================
    
    def greeting(self, message):
        """Handle greeting messages with fuzzy matching, time awareness, and personalization"""
        
        # First, try to extract and save user name
        extracted_name = self._extract_and_save_name(message)
        user_name = self._get_user_name()
        
        # Match greeting type using fuzzy logic
        greeting_type = self._match_greeting(message)
        
        # Get time-based greeting
        time_greeting = self._get_time_greeting()
        
        # Build personalized greeting
        if greeting_type:
            # Select random response from time-appropriate list
            base_response = random.choice(time_greeting['responses'])
            
            # Add user name if available
            if user_name:
                # Replace generic greeting with personalized one
                if 'Good morning' in base_response:
                    base_response = base_response.replace('Good morning', f'Good morning, {user_name}')
                elif 'Good afternoon' in base_response:
                    base_response = base_response.replace('Good afternoon', f'Good afternoon, {user_name}')
                elif 'Good evening' in base_response:
                    base_response = base_response.replace('Good evening', f'Good evening, {user_name}')
                elif 'Morning' in base_response:
                    base_response = base_response.replace('Morning', f'Morning, {user_name}')
                elif 'Afternoon' in base_response:
                    base_response = base_response.replace('Afternoon', f'Afternoon, {user_name}')
                elif 'Evening' in base_response:
                    base_response = base_response.replace('Evening', f'Evening, {user_name}')
                else:
                    base_response = f"{base_response.split('!')[0]}, {user_name}!{base_response.split('!')[1] if '!' in base_response else ''}"
            
            # Add icon
            response = f"{time_greeting['icon']} {base_response}"
            
            # If we just learned user's name, add a nice message
            if extracted_name and not user_name:
                response = f"🎉 Nice to meet you, {extracted_name}! {response}"
            
            return self.format_success(response)
        
        # If not a greeting, return None to let other handlers process
        return None
    
    # ============================================================
    # SMALL TALK HANDLERS
    # ============================================================
    
    def handle_how_are_you(self, message):
        """Handle 'how are you' type questions"""
        responses = [
            "I'm doing great, thanks for asking! 😊 Ready to help you!",
            "All systems operational! How can I assist you today?",
            "I'm fantastic! Just helped someone complete their tasks. What about you?",
            "Doing well! Powered by coffee and code. ☕ How can I help?",
            "I'm great! No bugs in my system today! 🐛 How are you doing?",
            "Feeling productive! Let's get some work done together! 💪",
            "I'm awesome! Thanks for checking in. What do you need help with?",
            "Running smoothly! Ready to tackle your to-do list!"
        ]
        return self.format_success(random.choice(responses))
    
    def handle_what_can_you_do(self, message):
        """Handle 'what can you do' questions"""
        return self.format_success(self._get_capabilities())
    
    def handle_tell_joke(self, message):
        """Handle 'tell me a joke' requests"""
        return self.format_success(f"Here's a joke for you: {self._get_joke()}")
    
    def handle_who_made_you(self, message):
        """Handle 'who made you' questions"""
        responses = [
            "I was built by the ReadyTask team to help you manage projects efficiently! 🚀",
            "The brilliant developers at ReadyTask created me to be your project management assistant!",
            "I'm a product of the ReadyTask PMS system, designed to make your work easier!",
            "The ReadyTask team built me with love and lots of code! 💻"
        ]
        return self.format_success(random.choice(responses))
    
    def handle_whats_your_name(self, message):
        """Handle 'what's your name' questions"""
        user_name = self._get_user_name()
        responses = [
            f"I'm ReadyBot, your AI assistant! 👋{' Nice to meet you, ' + user_name if user_name else ''}",
            "I'm your ReadyTask AI Assistant! Call me ReadyBot for short. 🤖",
            "I'm the ReadyTask PMS Assistant, here to help you stay organized!",
            "You can call me ReadyBot! I'm your personal project management companion."
        ]
        return self.format_success(random.choice(responses))
    
    def handle_thanks(self, message):
        """Handle thank you messages"""
        responses = [
            "You're very welcome! 😊 Anything else I can help with?",
            "My pleasure! Happy to assist you anytime!",
            "Glad I could help! What's next on your list?",
            "Anytime! That's what I'm here for. Need anything else?",
            "You got it! Let me know if you need more help!",
            "Happy to help! Keep crushing those tasks! 💪",
            "No problem at all! Anything else on your mind?"
        ]
        return self.format_success(random.choice(responses))
    
    def handle_bye(self, message):
        """Handle goodbye messages"""
        user_name = self._get_user_name()
        responses = [
            f"Goodbye{' ' + user_name if user_name else ''}! 👋 Have a productive day!",
            f"See you later{' ' + user_name if user_name else ''}! Come back if you need help.",
            f"Take care{' ' + user_name if user_name else ''}! Ready to help whenever you need me.",
            f"Bye for now{' ' + user_name if user_name else ''}! Keep those tasks moving! 🚀",
            f"Farewell{' ' + user_name if user_name else ''}! Happy task managing!",
            f"Until next time{' ' + user_name if user_name else ''}! Stay productive!"
        ]
        return self.format_success(random.choice(responses))
    

    
    def help(self):
        """Help message"""
        return self.format_success(self._get_capabilities())
    
    def unknown(self, message):
        """Handle unknown intent with a short, friendly response"""
        return self.format_success(
            "Sorry, I didn't get that. 🙏\n\n"
            "Try saying:\n"
            "• 'create task Fix bug'\n"
            "• 'show my tasks'\n"
            "• 'help' for more commands"
        )