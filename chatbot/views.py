import json
import re
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from users.decorators import jwt_or_session_required
from django.conf import settings

from .models import ChatSession, ChatMessage
from .actions.task_actions import TaskActions
from .actions.project_actions import ProjectActions
from .actions.user_actions import UserActions
from .actions.view_actions import ViewActions
from .llm.hf_client import get_hf_client


def generate_general_response(hf_client, user_message):
    """Generate natural response for general queries"""
    try:
        response = hf_client.client.chat.completions.create(
            model=hf_client.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ General response error: {e}")
        return "Sorry, I couldn't process that."


@jwt_or_session_required
def chatbot_page(request):
    """Render the chatbot interface page"""
    ChatSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
    session = ChatSession.objects.create(
        user=request.user,
        is_active=True,
        context={}
    )
    messages = session.messages.all().order_by('created_at')
    groq_available = bool(settings.GROQ_API_KEY)
    return render(request, 'chatbot/index.html', {
        'session_id': session.id,
        'messages': messages,
        'llm_available': groq_available
    })


@jwt_or_session_required
@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """API endpoint for chatbot messages"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')

        print(f"\n{'='*50}")
        print(f"📨 Message: {user_message}")

        if not user_message:
            return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)

        # Get or create session
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            except ChatSession.DoesNotExist:
                session = ChatSession.objects.create(user=request.user)
        else:
            session = ChatSession.objects.create(user=request.user)

        print(f"🔍 Session context: {session.context}")
        print(f"🔍 Pending action: {session.context.get('pending_action')}")

        # Initialize action handlers
        task_actions = TaskActions(request.user)
        project_actions = ProjectActions(request.user)
        user_actions = UserActions(request.user)
        view_actions = ViewActions(request.user)

        message_lower = user_message.lower()

        # ============================================================
        # FAST TRACK - Direct command matching (BEFORE anything else)
        # ============================================================

        fast_track_commands = [
            'show my tasks', 'show tasks', 'my tasks', 'view tasks',
            'list tasks', 'show me tasks', 'show me my tasks', 'tasks'
        ]
        if message_lower in fast_track_commands:
            print("🎯 Fast track - view_tasks detected")
            intent = 'view_tasks'
            entities = {}
            response_data = task_actions.view_tasks(entities)
            assistant_message = response_data.get('message', '')
            ChatMessage.objects.create(
                session=session, role='assistant', content=assistant_message,
                intent=intent, entities=entities
            )
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

        fast_track_projects = [
            'show my projects', 'show projects', 'my projects',
            'view projects', 'list projects', 'projects'
        ]
        if message_lower in fast_track_projects:
            print("🎯 Fast track - view_projects detected")
            intent = 'view_projects'
            entities = {}
            response_data = project_actions.view_projects(entities)
            assistant_message = response_data.get('message', '')
            ChatMessage.objects.create(
                session=session, role='assistant', content=assistant_message,
                intent=intent, entities=entities
            )
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

        fast_track_users = [
            'show users', 'view users', 'team members', 'list users',
            'show team members', 'users', 'team'
        ]
        if message_lower in fast_track_users:
            print("🎯 Fast track - view_users detected")
            intent = 'view_users'
            entities = {}
            response_data = user_actions.view_users(entities)
            assistant_message = response_data.get('message', '')
            ChatMessage.objects.create(
                session=session, role='assistant', content=assistant_message,
                intent=intent, entities=entities
            )
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

        fast_track_greetings = ['hello', 'hi', 'hey', 'helo', 'hlo', 'hii', 'heyy']
        if message_lower in fast_track_greetings:
            print("🎯 Fast track - greeting detected")
            response_data = view_actions.greeting(user_message)
            assistant_message = response_data.get('message', '')
            ChatMessage.objects.create(
                session=session, role='assistant', content=assistant_message,
                intent='greeting', entities={}
            )
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': 'greeting', 'session_id': session.id})

        if message_lower in ['cancel', 'nevermind', 'forget it', 'abort', 'stop']:
            print("🎯 Fast track - cancel detected")
            session.context.pop('pending_action', None)
            session.context.pop('pending_entities', None)
            session.context.pop('missing_field', None)
            session.context.pop('project_choices', None)
            session.context.pop('selection_attempts', None)
            session.context.pop('pending_question', None)
            session.save()
            assistant_message = "✅ Cancelled. What would you like to do instead?"
            ChatMessage.objects.create(
                session=session, role='assistant', content=assistant_message,
                intent='cancel', entities={}
            )
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': 'cancel', 'session_id': session.id})

        # ============================================================
        # CHECK FOR RESET COMMAND
        # ============================================================
        if user_message.strip().lower() == '/reset':
            print("🔄 Reset command received - clearing session")
            session.messages.all().delete()
            session.context = {}
            session.save()
            return JsonResponse({
                'success': True,
                'message': "🔄 Conversation has been reset. Start a new conversation!",
                'intent': 'reset',
                'session_id': session.id
            })

        # Save user message
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        response_data = None
        intent = None
        assistant_message = ""
        entities = {}

        # ============================================================
        # TYPO CORRECTION - Fix common typos BEFORE intent detection
        # ============================================================
        typo_map = {
            'taks': 'tasks', 'taskk': 'task', 'taskes': 'tasks', 'tassk': 'task', 'tsak': 'task',
            'projct': 'project', 'projekt': 'project', 'projet': 'project', 'projec': 'project', 'porject': 'project',
            'usr': 'user', 'usres': 'users', 'useer': 'user',
            'creat': 'create', 'cretae': 'create', 'crate': 'create',
            'starrt': 'start', 'strat': 'start', 'pauese': 'pause', 'pausse': 'pause',
            'resumee': 'resume', 'resme': 'resume', 'complet': 'complete', 'compete': 'complete',
            'deleet': 'delete', 'delte': 'delete', 'editt': 'edit', 'edt': 'edit',
            'shwo': 'show', 'sho': 'show', 'vieew': 'view', 'veiw': 'view', 'listt': 'list', 'lisst': 'list',
        }
        corrected_message = message_lower
        for typo, correction in typo_map.items():
            if typo in corrected_message:
                corrected_message = corrected_message.replace(typo, correction)
                print(f"🔧 Typo fixed: '{typo}' → '{correction}'")
        if corrected_message != message_lower:
            message_lower = corrected_message
            print(f"📝 Corrected message: '{message_lower}'")

        # ============================================================
        # PROGRESSIVE FALLBACK - Track user failures
        # ============================================================
        if 'fallback_count' not in session.context:
            session.context['fallback_count'] = 0

        # ============================================================
        # FIRST: Check for PENDING CONVERSATION (Multi-turn)
        # ============================================================
        if session.context.get('pending_action') and session.context.get('missing_field'):
            msg_lower = user_message.lower().strip()
            reset_commands = ['cancel', 'start over', 'reset', 'new']
            is_reset = any(msg_lower == cmd or msg_lower.startswith(cmd + ' ') for cmd in reset_commands)
            greeting_commands = ['hello', 'hi', 'hey']
            is_greeting = any(msg_lower == cmd or msg_lower.startswith(cmd + ' ') for cmd in greeting_commands)

            if is_reset:
                print("🔄 Reset command detected - clearing pending conversation")
                session.context.pop('pending_action', None)
                session.context.pop('pending_entities', None)
                session.context.pop('missing_field', None)
                session.context.pop('pending_question', None)
                session.save()
            elif is_greeting:
                print("🎯 Greeting during pending - responding without clearing")
                response_data = view_actions.greeting(user_message)
                assistant_message = response_data.get('message', '')
                # Re-ask pending question
                pending_question = session.context.get('pending_question', f"What is the {session.context.get('missing_field')}?")
                continuation = f"\n\n🔄 Now continuing with your {session.context.get('pending_action').replace('_', ' ')}:\n{pending_question}"
                assistant_message = assistant_message + continuation
                ChatMessage.objects.create(session=session, role='assistant', content=assistant_message, intent='greeting', entities={})
                session.save()
                return JsonResponse({'success': True, 'message': assistant_message, 'intent': 'greeting', 'session_id': session.id})
            else:
                pending_action = session.context.get('pending_action')
                pending_entities = session.context.get('pending_entities', {})
                missing_field = session.context.get('missing_field')

                # Helper for date validation
                def is_valid_date_or_skip(value):
                    if value.lower() == 'skip':
                        return True
                    return re.match(r'^\d{4}-\d{2}-\d{2}$', value) is not None

                # ============================================================
                # STEP 1: Prepare common variables
                # ============================================================
                is_valid = False      # will be set to True if answer is acceptable
                error_message = None
                side_response = None
                side_intent = None
                is_side_query = False

                # ============================================================
                # STEP 2: Handle each action and missing field
                # ============================================================

                # ---------- CREATE USER ----------
                if pending_action == 'create_user':
                    if missing_field == 'email':
                        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                        if not re.match(email_pattern, user_message):
                            error_message = "❌ Invalid email format. Please provide a valid email address (e.g., john@example.com):"
                        else:
                            from users.models import User
                            if User.objects.filter(email=user_message).exists():
                                error_message = f"❌ Email '{user_message}' is already registered. Please use a different email:"
                            else:
                                is_valid = True
                    elif missing_field == 'username':
                        if len(user_message) < 3:
                            error_message = "❌ Username must be at least 3 characters long. Please try again:"
                        elif not re.match(r'^[a-zA-Z0-9._]+$', user_message):
                            error_message = "❌ Username can only contain letters, numbers, dots, and underscores. Please try again:"
                        else:
                            is_valid = True
                    elif missing_field == 'role':
                        from users.models import Role
                        if Role.objects.filter(name__iexact=user_message).exists():
                            is_valid = True
                        else:
                            roles = user_actions._get_available_roles()
                            role_list = ", ".join(roles)
                            error_message = f"❌ Role '{user_message}' not found. Available roles: {role_list}\n\nPlease enter a valid role:"
                    elif missing_field == 'department':
                        from users.models import Department
                        if Department.objects.filter(name__iexact=user_message).exists():
                            is_valid = True
                        else:
                            depts = user_actions._get_available_departments()
                            dept_list = ", ".join(depts)
                            error_message = f"❌ Department '{user_message}' not found. Available departments: {dept_list}\n\nPlease enter a valid department:"
                    elif missing_field == 'designation':
                        from users.models import Designation
                        if Designation.objects.filter(name__iexact=user_message).exists():
                            is_valid = True
                        else:
                            desigs = user_actions._get_available_designations()
                            desig_list = ", ".join(desigs)
                            error_message = f"❌ Designation '{user_message}' not found. Available designations: {desig_list}\n\nPlease enter a valid designation:"

                
                # ---------- CREATE PROJECT ----------
                elif pending_action == 'create_project':
                    # For name and description, we need to detect general queries
                    if missing_field in ['name', 'description']:
                        # Use HF client to check if it's a general query
                        hf_client = get_hf_client()
                        is_general_query = False
                        general_response = None
                        if hf_client and hf_client.is_available():
                            try:
                                # Only need to classify intent, not full conversation
                                intent_result = hf_client.extract_intent(user_message, [])
                                intent = intent_result.get('intent', 'unknown')
                                if intent == 'general_query':
                                    is_general_query = True
                                    general_response = intent_result.get('response')
                                    if not general_response:
                                        general_response = generate_general_response(hf_client, user_message)
                            except Exception as e:
                                print(f"⚠️ General query detection error: {e}")
                        # Also fast check for obvious question words (optional)
                        if not is_general_query:
                            question_words = ['who', 'what', 'where', 'when', 'why', 'how', 'which']
                            if any(user_message.lower().strip().startswith(w + ' ') for w in question_words):
                                is_general_query = True
                                general_response = generate_general_response(hf_client, user_message) if hf_client else "I'm not sure about that."
                        
                        if is_general_query and general_response:
                            # Answer the general query and repeat the pending project question
                            pending_question = session.context.get('pending_question', f"What is the {missing_field}?")
                            continuation = f"\n\n🔄 Now continuing with your {pending_action.replace('_', ' ')}:\n{pending_question}"
                            full_response = general_response + continuation
                            ChatMessage.objects.create(session=session, role='assistant', content=full_response, intent='general_query', entities={})
                            session.save()
                            return JsonResponse({'success': True, 'message': full_response, 'intent': 'general_query', 'session_id': session.id})
                        else:
                            # Not a general query – accept as valid field answer
                            if user_message.strip():
                                is_valid = True
                            else:
                                error_message = f"❌ Project {missing_field} cannot be empty. Please enter a valid value."
                    elif missing_field == 'name':
                        if user_message.strip():
                            is_valid = True
                        else:
                            error_message = "❌ Project name cannot be empty. Please enter a valid name:"
                    elif missing_field == 'description':
                        if user_message.strip():
                            is_valid = True
                        else:
                            error_message = "❌ Description cannot be empty. Please provide a description:"
                    elif missing_field in ['start_date', 'end_date']:
                        if is_valid_date_or_skip(user_message):
                            is_valid = True
                        else:
                            error_message = f"❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'.\nExample: 2026-04-20"
                    else:
                       
                        if user_message.strip():
                            is_valid = True
                        else:
                            error_message = f"❌ Please provide a valid value for {missing_field}."

                # ---------- CREATE TASK ----------
                elif pending_action == 'create_task':
                    # --- Name field ---
                    if missing_field == 'name':
                        if user_message.strip():
                            is_valid = True
                        else:
                            error_message = "❌ Task name cannot be empty. Please enter a valid name:"

                    # --- Project field : validate project existence AND detect side queries ---
                    elif missing_field == 'project':
                        from projects.models import Projects
                        msg_clean = user_message.strip()
                        # Try to resolve as a project ID or name
                        project_found = None
                        if msg_clean.isdigit():
                            try:
                                project_found = Projects.objects.get(id=int(msg_clean), is_deleted=False)
                            except Projects.DoesNotExist:
                                pass
                        else:
                            try:
                                project_found = Projects.objects.get(name__iexact=msg_clean, is_deleted=False)
                            except Projects.DoesNotExist:
                                pass
                            except Projects.MultipleObjectsReturned:
                                project_found = Projects.objects.filter(name__iexact=msg_clean, is_deleted=False).first()
                        if project_found:
                            # Valid project – accept it
                            is_valid = True
                            # Store the ID for later (will be converted in task_actions)
                            user_message = str(project_found.id)
                        else:
                            # Not a valid project – check for side query (show projects)
                            side_patterns = [
                                'show my projects', 'show projects', 'my projects', 'view projects',
                                'list projects', 'show my project', 'show project', 'show me projects',
                                'project list', 'projects list'
                            ]
                            if any(phrase in msg_clean.lower() for phrase in side_patterns):
                                # Answer the side query
                                pa = ProjectActions(request.user)
                                resp = pa.view_projects({})
                                side_response = resp.get('message', '')
                                side_intent = 'view_projects'
                                is_side_query = True
                            else:
                                error_message = f"❌ Project '{user_message}' not found. Please enter a valid project name or ID.\n(Type 'show my projects' to see your projects.)"

                    # --- Assignee field : validate user existence ---
                    elif missing_field == 'assigned_to':
                        from users.models import User
                        user_found = None
                        # Try by ID
                        if user_message.isdigit():
                            try:
                                user_found = User.objects.get(id=int(user_message), is_active=True)
                            except User.DoesNotExist:
                                pass
                        if not user_found:
                            # Try by username
                            try:
                                user_found = User.objects.get(username__iexact=user_message, is_active=True)
                            except User.DoesNotExist:
                                pass
                        if not user_found:
                            # Try by full name (first + last)
                            parts = user_message.split()
                            if len(parts) >= 2:
                                first = parts[0]
                                last = ' '.join(parts[1:])
                                try:
                                    user_found = User.objects.get(first_name__iexact=first, last_name__iexact=last, is_active=True)
                                except User.DoesNotExist:
                                    pass
                        if user_found:
                            is_valid = True
                        else:
                            error_message = f"❌ User '{user_message}' not found. Please enter a valid username, ID, or full name."

                    # --- Dates ---
                    elif missing_field in ['start_date', 'end_date']:
                        if is_valid_date_or_skip(user_message):
                            is_valid = True
                        else:
                            error_message = f"❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'.\nExample: 2026-04-20"

                    # --- Description, deadline, observers, estimated_time ---
                    else:
                        # For these fields, any non‑empty answer is valid (including 'skip')
                        is_valid = True

                # ---------- ADD SUMMARY (example) ----------
                elif pending_action == 'add_summary':
                    if missing_field == 'summary':
                        if len(user_message.strip()) >= 10:
                            is_valid = True
                        else:
                            error_message = "❌ Summary must be at least 10 characters. Please provide a more detailed summary."

                # ============================================================
                # STEP 3: Act on the result
                # ============================================================

                # If it's a side query, answer it and repeat the pending question
                if is_side_query and side_response:
                    pending_question = session.context.get('pending_question', f"What is the {missing_field}?")
                    continuation = f"\n\n🔄 Now continuing with your {pending_action.replace('_', ' ')}:\n{pending_question}"
                    full_response = side_response + continuation
                    ChatMessage.objects.create(session=session, role='assistant', content=full_response, intent=side_intent, entities={})
                    session.save()
                    return JsonResponse({'success': True, 'message': full_response, 'intent': side_intent, 'session_id': session.id})

                # If valid, store the answer and continue
                if is_valid:
                    print(f"✅ Validation passed for {missing_field}: {user_message}")
                    pending_entities[missing_field] = user_message
                    print(f"📝 Added {missing_field}: {user_message}")

                    if pending_action == 'create_user':
                        response_data = user_actions.create_user(pending_entities, session.context)
                    elif pending_action == 'create_project':
                        response_data = project_actions.create_project(pending_entities, session.context)
                    elif pending_action == 'create_task':
                        response_data = task_actions.create_task(pending_entities, session.context)
                    elif pending_action == 'add_summary':
                        response_data = task_actions.add_summary(pending_entities)
                    else:
                        response_data = None

                    if response_data and response_data.get('need_more_info'):
                        session.context['pending_action'] = pending_action
                        session.context['pending_entities'] = response_data.get('partial_data', {})
                        session.context['missing_field'] = response_data.get('missing_field')
                        session.context['pending_question'] = response_data.get('message')
                        session.save()
                        intent = pending_action
                        assistant_message = response_data.get('message', '')
                        print(f"💬 Still need more: {assistant_message[:50]}...")
                    else:
                        session.context.pop('pending_action', None)
                        session.context.pop('pending_entities', None)
                        session.context.pop('missing_field', None)
                        session.context.pop('pending_question', None)
                        session.save()
                        intent = pending_action
                        assistant_message = response_data.get('message', '')
                        print(f"💬 Final response: {assistant_message[:100]}...")

                    ChatMessage.objects.create(
                        session=session,
                        role='assistant',
                        content=assistant_message,
                        intent=intent,
                        entities=pending_entities
                    )
                    return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

                # If not valid and not a side query, return the error message (keep pending context)
                if error_message:
                    print(f"❌ Validation failed for {missing_field}: {user_message}")
                    return JsonResponse({
                        'success': True,
                        'message': error_message,
                        'intent': pending_action,
                        'session_id': session.id
                    })

                # Fallback (should not happen)
                return JsonResponse({
                    'success': True,
                    'message': "I didn't understand that. Please try again.",
                    'intent': pending_action,
                    'session_id': session.id
                })

        # ============================================================
        # KEYWORD FALLBACK - Check for common commands (no pending)
        # ============================================================
        keyword_intent = None
        keyword_entities = {}

        # Project detail queries
        if re.search(r'show\s+details?\s+of\s+project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_project_detail'
            project_match = re.search(r'project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if project_match:
                keyword_entities = {
                    'project_id_or_name': project_match.group(1).strip(),
                    'info_type': 'details'
                }
            print(f"🎯 Keyword - view_project_detail")
        elif re.search(r'(status|progress)\s+of\s+project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_project_detail'
            project_match = re.search(r'project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if project_match:
                keyword_entities = {
                    'project_id_or_name': project_match.group(1).strip(),
                    'info_type': 'status'
                }
            print(f"🎯 Keyword - view_project_detail")
        elif re.search(r'(end date|deadline|due date)\s+of\s+project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_project_detail'
            project_match = re.search(r'project\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if project_match:
                keyword_entities = {
                    'project_id_or_name': project_match.group(1).strip(),
                    'info_type': 'end_date'
                }
            print(f"🎯 Keyword - view_project_detail")
        # Task detail queries
        elif re.search(r'show\s+details?\s+of\s+task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_task_detail'
            task_match = re.search(r'task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities = {
                    'task_id_or_name': task_match.group(1).strip(),
                    'info_type': 'details'
                }
            print(f"🎯 Keyword - view_task_detail")
        elif re.search(r'(deadline|due date)\s+of\s+task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_task_detail'
            task_match = re.search(r'task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities = {
                    'task_id_or_name': task_match.group(1).strip(),
                    'info_type': 'deadline'
                }
            print(f"🎯 Keyword - view_task_detail")
        elif re.search(r'(status|progress)\s+of\s+task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE):
            keyword_intent = 'view_task_detail'
            task_match = re.search(r'task\s+[\'"]?([^\'"]+)[\'"]?', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities = {
                    'task_id_or_name': task_match.group(1).strip(),
                    'info_type': 'status'
                }
            print(f"🎯 Keyword - view_task_detail")
        # Task action commands
        elif re.search(r'\b(start|begin)\s+task\b', message_lower, re.IGNORECASE):
            keyword_intent = 'start_task'
            task_match = re.search(r'(?:start|begin)\s+task\s+[\'"]?([^\'"]+?)[\'"]?(?:\s|$)', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities['task_id_or_name'] = task_match.group(1).strip()
            print(f"🎯 Keyword - start_task")
        elif re.search(r'\b(pause|hold)\s+task\b', message_lower, re.IGNORECASE):
            keyword_intent = 'pause_task'
            task_match = re.search(r'(?:pause|hold)\s+task\s+[\'"]?([^\'"]+?)[\'"]?(?:\s|$)', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities['task_id_or_name'] = task_match.group(1).strip()
            print(f"🎯 Keyword - pause_task")
        elif re.search(r'\b(complete|finish|done)\s+task\b', message_lower, re.IGNORECASE):
            keyword_intent = 'complete_task'
            task_match = re.search(r'(?:complete|finish|done)\s+task\s+[\'"]?([^\'"]+?)[\'"]?(?:\s|$)', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities['task_id_or_name'] = task_match.group(1).strip()
            print(f"🎯 Keyword - complete_task")
        elif re.search(r'\bresume\s+task\b', message_lower, re.IGNORECASE):
            keyword_intent = 'resume_task'
            task_match = re.search(r'resume\s+task\s+[\'"]?([^\'"]+?)[\'"]?(?:\s|$)', message_lower, re.IGNORECASE)
            if task_match:
                keyword_entities['task_id_or_name'] = task_match.group(1).strip()
            print(f"🎯 Keyword - resume_task")

        # ============================================================
        # SMALL TALK HANDLERS
        # ============================================================
        how_are_you_patterns = ['how are you', 'how are u', 'how you doing', 'how do you do', 'howdy', 'whats up', "what's up", 'sup']
        what_can_you_do_patterns = ['what can you do', 'what do you do', 'capabilities', 'what can you help with', 'features', 'your skills']
        joke_patterns = ['tell me a joke', 'say a joke', 'make me laugh', 'joke', 'funny', 'humor']
        who_made_you_patterns = ['who made you', 'who created you', 'your creator', 'built you', 'developed you', 'made you']
        whats_your_name_patterns = ['what is your name', "what's your name", 'your name', 'called', 'who are you']
        thanks_patterns = ['thanks', 'thank you', 'thx', 'appreciate', 'grateful', 'ty']
        bye_patterns = ['bye', 'goodbye', 'see you', 'farewell', 'take care', 'cya', 'see ya']

        # Define side‑query intents that should NOT clear pending context (for general flow, not inside pending)
        side_query_intents = ['greeting', 'general_query', 'how_are_you', 'joke', 'capabilities', 'thanks', 'farewell', 'help']

        if any(pattern in message_lower for pattern in how_are_you_patterns):
            print("🎯 How are you detected")
            response_data = view_actions.handle_how_are_you(user_message)
            intent = 'how_are_you'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in what_can_you_do_patterns):
            print("🎯 What can you do detected")
            response_data = view_actions.handle_what_can_you_do(user_message)
            intent = 'capabilities'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in joke_patterns):
            print("🎯 Joke detected")
            response_data = view_actions.handle_tell_joke(user_message)
            intent = 'joke'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in who_made_you_patterns):
            print("🎯 Who made you detected")
            response_data = view_actions.handle_who_made_you(user_message)
            intent = 'origin'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in whats_your_name_patterns):
            print("🎯 What's your name detected")
            response_data = view_actions.handle_whats_your_name(user_message)
            intent = 'introduction'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in thanks_patterns):
            print("🎯 Thanks detected")
            response_data = view_actions.handle_thanks(user_message)
            intent = 'thanks'
            assistant_message = response_data.get('message', '')
        elif any(pattern in message_lower for pattern in bye_patterns):
            print("🎯 Bye detected")
            response_data = view_actions.handle_bye(user_message)
            intent = 'farewell'
            assistant_message = response_data.get('message', '')

        # If small talk matched, preserve context if needed
        if assistant_message:
            # Check if there is a pending action (context preservation)
            pending_action = session.context.get('pending_action')
            missing_field = session.context.get('missing_field')
            
            if pending_action and missing_field and intent in side_query_intents:
                pending_question = session.context.get('pending_question', f"What is the {missing_field}?")
                continuation = f"\n\n🔄 Now continuing with your {pending_action.replace('_', ' ')}:\n{pending_question}"
                assistant_message = assistant_message + continuation
                # Do NOT clear pending_action – keep it for the next message
                session.save()
            else:
                # No pending action or not a side query – normal path (clear pending context if it was a final action)
                if intent not in side_query_intents:
                    session.context.pop('pending_action', None)
                    session.context.pop('pending_entities', None)
                    session.context.pop('missing_field', None)
                    session.context.pop('pending_question', None)
                    session.save()

            ChatMessage.objects.create(session=session, role='assistant', content=assistant_message, intent=intent, entities=entities)
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

        # ============================================================
        # ROUTING: Use keyword match or Hugging Face
        # ============================================================
        if keyword_intent:
            intent = keyword_intent
            entities = keyword_entities
        else:
            hf_client = get_hf_client()
            if hf_client and hf_client.is_available():
                print("🎯 Using Hugging Face (Qwen2.5-7B-Instruct) for intent extraction...")
                try:
                    recent_messages = session.get_recent_messages(limit=6)
                    history = [f"{m.role}: {m.content}" for m in recent_messages if m.role != 'system']
                    intent_result = hf_client.extract_intent(user_message, history)
                    intent = intent_result.get('intent', 'unknown')
                    entities = intent_result.get('entities', {})
                    print(f"🎯 HF Result - Intent: {intent}, Entities: {entities}")

                    if intent == "general_query":
                        print("🧠 General query detected")
                        assistant_message = intent_result.get("response")
                        if not assistant_message:
                            assistant_message = generate_general_response(hf_client, user_message)
                        
                        # --- Context preservation for general query ---
                        pending_action = session.context.get('pending_action')
                        missing_field = session.context.get('missing_field')
                        if pending_action and missing_field:
                            pending_question = session.context.get('pending_question', f"What is the {missing_field}?")
                            continuation = f"\n\n🔄 Now continuing with your {pending_action.replace('_', ' ')}:\n{pending_question}"
                            assistant_message = assistant_message + continuation
                            # Keep pending context (do not clear)
                            session.save()
                        else:
                            # No pending context, clear any stale state
                            session.context.pop('pending_action', None)
                            session.context.pop('pending_entities', None)
                            session.context.pop('missing_field', None)
                            session.context.pop('pending_question', None)
                            session.save()
                        
                        ChatMessage.objects.create(session=session, role='assistant', content=assistant_message, intent='general_query', entities={})
                        session.context['fallback_count'] = 0
                        session.save()
                        return JsonResponse({'success': True, 'message': assistant_message, 'intent': 'general_query', 'session_id': session.id})

                    if intent != 'unknown':
                        session.context['fallback_count'] = 0
                    else:
                        session.context['fallback_count'] += 1
                    session.save()
                except Exception as hf_error:
                    print(f"⚠️ Hugging Face error: {hf_error}")
                    intent = 'unknown'
                    entities = {}
            else:
                print("🎯 HF not available, using keyword matching")
                if 'create user' in message_lower or 'add user' in message_lower:
                    intent = 'create_user'
                elif 'create project' in message_lower or 'new project' in message_lower:
                    intent = 'create_project'
                elif 'create task' in message_lower or 'new task' in message_lower:
                    intent = 'create_task'
                elif 'start task' in message_lower:
                    intent = 'start_task'
                elif 'pause task' in message_lower:
                    intent = 'pause_task'
                elif 'resume task' in message_lower:
                    intent = 'resume_task'
                elif 'complete task' in message_lower:
                    intent = 'complete_task'
                elif 'show my tasks' in message_lower or 'my tasks' in message_lower:
                    intent = 'view_tasks'
                elif 'show my projects' in message_lower or 'my projects' in message_lower:
                    intent = 'view_projects'
                elif 'view users' in message_lower or 'show users' in message_lower or 'team members' in message_lower:
                    intent = 'view_users'
                elif 'add summary' in message_lower or 'add a summary' in message_lower:
                    intent = 'add_summary'
                elif 'edit task' in message_lower:
                    intent = 'edit_task'
                elif 'edit project' in message_lower:
                    intent = 'edit_project'
                elif 'delete task' in message_lower or 'trash task' in message_lower:
                    intent = 'delete_task'
                elif 'delete project' in message_lower or 'trash project' in message_lower:
                    intent = 'delete_project'
                else:
                    intent = 'unknown'

        # ============================================================
        # PROGRESSIVE FALLBACK RESPONSE (if intent is unknown)
        # ============================================================
        if intent in ['unknown', None]:
            fallback_count = session.context.get('fallback_count', 0)
            frustration_keywords = ['stupid', 'dumb', 'not working', 'useless', 'frustrated', 'annoying', 'waste']
            is_frustrated = any(word in message_lower for word in frustration_keywords)

            if is_frustrated:
                assistant_message = (
                    "😅 I apologize for the confusion. Let me help you better.\n\n"
                    "Here's what I can do:\n"
                    "• Create tasks, projects, or users\n"
                    "• Show your tasks or projects\n"
                    "• Start, pause, or complete tasks\n\n"
                    "Try saying: 'create task Fix bug' or 'show my tasks'\n"
                    "Or type 'help' for complete guide."
                )
                intent = 'fallback_frustration'
                session.context['fallback_count'] = 0
                session.save()
            elif fallback_count == 1:
                assistant_message = (
                    "🤔 I didn't understand that. Could you please rephrase?\n\n"
                    "Try starting with words like: Create, Show, Start, Pause, Complete"
                )
                intent = 'fallback_level1'
            elif fallback_count == 2:
                assistant_message = (
                    "😕 Still not getting it. Here are some examples:\n\n"
                    "• 'create task Fix bug for John'\n"
                    "• 'show my tasks'\n"
                    "• 'start task Fix bug'\n\n"
                    "Or type 'help' to see all commands."
                )
                intent = 'fallback_level2'
            else:
                assistant_message = (
                    "🆘 I'm having trouble understanding. Here's what you can do:\n\n"
                    "• Type 'help' to see all available commands\n"
                    "• Type 'reset' to start a new conversation\n"
                    "• Type 'cancel' to exit current operation\n\n"
                    "Example: 'create task Write documentation for John in Website Project'"
                )
                intent = 'fallback_level3'

            ChatMessage.objects.create(session=session, role='assistant', content=assistant_message, intent=intent, entities=entities)
            session.save()
            return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

        # ============================================================
        # Route to appropriate action based on intent
        # ============================================================
        if intent == 'create_user':
            response_data = user_actions.create_user(entities, session.context)
        elif intent == 'create_project':
            response_data = project_actions.create_project(entities, session.context)
        elif intent == 'create_task':
            response_data = task_actions.create_task(entities, session.context)
        elif intent == 'start_task':
            response_data = task_actions.start_task(entities)
        elif intent == 'pause_task':
            response_data = task_actions.pause_task(entities)
        elif intent == 'resume_task':
            response_data = task_actions.resume_task(entities)
        elif intent == 'complete_task':
            response_data = task_actions.complete_task(entities)
        elif intent == 'view_tasks':
            response_data = task_actions.view_tasks(entities)
        elif intent == 'view_task_detail':
            response_data = task_actions.view_task_detail(entities)
        elif intent == 'view_projects':
            response_data = project_actions.view_projects(entities)
        elif intent == 'view_project_detail':
            response_data = project_actions.view_project_detail(entities)
        elif intent == 'view_users':
            response_data = user_actions.view_users(entities)
        elif intent == 'add_summary':
            response_data = task_actions.add_summary(entities)
        elif intent == 'edit_task':
            response_data = task_actions.edit_task(entities)
        elif intent == 'edit_project':
            response_data = project_actions.edit_project(entities)
        elif intent == 'delete_task':
            response_data = task_actions.delete_task(entities)
        elif intent == 'delete_project':
            response_data = project_actions.delete_project(entities)
        else:
            response_data = view_actions.unknown(user_message)

        # Check if we need more information (multi-turn)
        if response_data and response_data.get('need_more_info'):
            session.context['pending_action'] = intent
            session.context['pending_entities'] = response_data.get('partial_data', {})
            session.context['missing_field'] = response_data.get('missing_field')
            session.context['pending_question'] = response_data.get('message')
            session.save()
            assistant_message = response_data.get('message', '')
            print(f"💬 Asking for more: {assistant_message[:50]}...")
        else:
            assistant_message = response_data.get('message', '')
            if response_data and (response_data.get('user_created') or response_data.get('project_created') or response_data.get('task_created')):
                session.context.pop('pending_action', None)
                session.context.pop('pending_entities', None)
                session.context.pop('missing_field', None)
                session.context.pop('pending_question', None)
                session.save()
            print(f"💬 Response: {assistant_message[:100]}...")

        print(f"💬 Final Response: {assistant_message[:100]}...")

        ChatMessage.objects.create(session=session, role='assistant', content=assistant_message, intent=intent, entities=entities)
        session.save()
        return JsonResponse({'success': True, 'message': assistant_message, 'intent': intent, 'session_id': session.id})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)