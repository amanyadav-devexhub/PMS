import json
import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from users.decorators import jwt_or_session_required
from projects.models import Projects
from Tasks.models import Task
from users.models import User
from django.db.models import Q
from django.urls import reverse

@jwt_or_session_required
def dashboard_bot_page(request):
    """Render the functional assistant interface"""
    return render(request, 'chatbot/functional_assistant.html')

@jwt_or_session_required
@csrf_exempt
@require_http_methods(["POST"])
def dashboard_bot_api(request):
    """API endpoint for functional assistant commands"""
    try:
        data = json.loads(request.body)
        raw_command = data.get('command', '').strip()
        command = raw_command.lower()
        
        if not command:
            return JsonResponse({'success': False, 'error': 'Command is required'}, status=400)
            
        # Check if user wants to cancel current flow
        if command in ['cancel', 'stop', 'quit', 'abort']:
            if 'functional_bot_state' in request.session:
                del request.session['functional_bot_state']
                request.session.modified = True
            return JsonResponse({'success': True, 'type': 'text', 'message': '❌ Action cancelled. How else can I help you?'})
            
        # --- COMMAND PROCESSING (Stateless) ---
        if command == 'show_projects':
            if 'functional_bot_state' in request.session: del request.session['functional_bot_state']
            
            from users.permissions import get_projects_queryset
            projects = get_projects_queryset(request.user)
                
            project_list = [{"id": p.id, "name": p.name} for p in projects]
            return JsonResponse({
                'success': True, 
                'type': 'projects',
                'data': project_list,
                'message': f'Found {projects.count()} projects.'
            })
            
        elif command == 'show_tasks':
            if 'functional_bot_state' in request.session: del request.session['functional_bot_state']
            
            from users.permissions import get_task_queryset
            tasks = get_task_queryset(request.user)
                
            task_list = [{"id": t.id, "name": t.name, "project": t.project.name if t.project else "N/A"} for t in tasks]
            return JsonResponse({
                'success': True,
                'type': 'tasks',
                'data': task_list,
                'message': f'Found {tasks.count()} tasks.'
            })
            
        elif command == 'create_task':
            # Initialize State Machine for Task Creation
            request.session['functional_bot_state'] = {
                'action': 'create_task',
                'step': 'name',
                'data': {}
            }
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'type': 'input_required',
                'message': "Let's create a task! First, what should be the **Name** of the task?"
            })
            
        elif command == 'create_project':
            from users.permissions import can_add_projects
            if not can_add_projects(request.user):
                return JsonResponse({'success': True, 'type': 'text', 'message': "❌ You do not have permission to create projects."})
                
            request.session['functional_bot_state'] = {
                'action': 'create_project',
                'step': 'name',
                'data': {}
            }
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'type': 'input_required',
                'message': "Let's create a new project! First, what is the **Project Name**?"
            })
            
        elif command == 'create_user':
            from users.permissions import can_add_user
            if not can_add_user(request.user):
                return JsonResponse({'success': True, 'type': 'text', 'message': "❌ You do not have permission to create users."})
                
            # Initialize State Machine for User Creation
            request.session['functional_bot_state'] = {
                'action': 'create_user',
                'step': 'first_name',
                'data': {}
            }
            request.session.modified = True
            return JsonResponse({
                'success': True,
                'type': 'input_required',
                'message': "Let's create a new user! First, what is their **First Name**?"
            })
            
        # --- STATE MACHINE PROCESSING (Stateful) ---
        if 'functional_bot_state' in request.session:
            state = request.session['functional_bot_state']
            
            if state['action'] == 'create_task':
                step = state['step']
                
                if step == 'name':
                    if not raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "Task name cannot be empty. Please provide a name:"})
                    state['data']['name'] = raw_command
                    state['step'] = 'project'
                    request.session.modified = True
                    
                    from users.permissions import get_projects_queryset
                    projects = get_projects_queryset(request.user)
                    project_list = [{"id": p.id, "name": p.name} for p in projects]
                    
                    return JsonResponse({
                        'success': True, 
                        'type': 'select_project', 
                        'data': project_list,
                        'message': f"Got it. The task name is '{raw_command}'.\n\nWhich **Project** is this for? Please select from the list below or type the name."
                    })
                    
                elif step == 'project':
                    # Find project
                    project = None
                    if raw_command.isdigit():
                        project = Projects.objects.filter(id=int(raw_command), is_deleted=False).first()
                    if not project:
                        project = Projects.objects.filter(name__iexact=raw_command, is_deleted=False).first()
                        
                    if not project:
                        return JsonResponse({'success': True, 'type': 'text', 'message': f"❌ Could not find a project matching '{raw_command}'. Please try again."})
                        
                    state['data']['project_id'] = project.id
                    state['step'] = 'assigned_to'
                    request.session.modified = True
                    
                    users = User.objects.filter(is_active=True, is_superuser=False).order_by('first_name', 'username')
                    user_list = [{"id": u.id, "name": u.get_full_name() or u.username} for u in users]
                    
                    return JsonResponse({
                        'success': True, 
                        'type': 'select_user', 
                        'data': user_list,
                        'message': f"Selected project: **{project.name}**.\n\nWho should this be **Assigned To**? Please select from the list below or type their name."
                    })
                    
                elif step == 'assigned_to':
                    # Find user
                    user = None
                    if raw_command.isdigit():
                        user = User.objects.filter(id=int(raw_command), is_active=True).first()
                    if not user:
                        user = User.objects.filter(username__iexact=raw_command, is_active=True).first()
                        
                    if not user:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': f"❌ Could not find an active user matching '{raw_command}'. Please try again."})
                        
                    state['data']['assigned_to_id'] = user.id
                    state['step'] = 'description'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': f"Assigned to **{user.username}**.\n\nPlease provide a brief **Description** for the task (or type 'skip'):"})
                    
                elif step == 'description':
                    state['data']['description'] = "" if command == 'skip' else raw_command
                    state['step'] = 'start_date'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': "What is the **Start Date**? (Format: YYYY-MM-DD, or type 'skip' to use today)"})
                    
                elif step == 'start_date':
                    start_date = None
                    if command == 'skip':
                        start_date = timezone.now().date()
                    else:
                        try:
                            start_date = datetime.datetime.strptime(raw_command, "%Y-%m-%d").date()
                        except ValueError:
                            return JsonResponse({'success': True, 'type': 'input_required', 'message': "❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'."})
                            
                    state['data']['start_date'] = start_date.isoformat()
                    state['step'] = 'end_date'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': "What is the **End Date**? (Format: YYYY-MM-DD, or type 'skip' to set it 7 days from the start date)"})
                    
                elif step == 'end_date':
                    end_date = None
                    start_date = datetime.date.fromisoformat(state['data']['start_date'])
                    if command == 'skip':
                        end_date = start_date + datetime.timedelta(days=7)
                    else:
                        try:
                            end_date = datetime.datetime.strptime(raw_command, "%Y-%m-%d").date()
                        except ValueError:
                            return JsonResponse({'success': True, 'type': 'input_required', 'message': "❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'."})
                            
                    # CREATE THE TASK
                    try:
                        project = Projects.objects.get(id=state['data']['project_id'])
                        assigned_user = User.objects.get(id=state['data']['assigned_to_id'])
                        
                        task = Task.objects.create(
                            name=state['data']['name'],
                            description=state['data']['description'],
                            project=project,
                            start_date=start_date,
                            end_date=end_date,
                            status='PENDING',
                            created_by=request.user
                        )
                        task.assigned_to.add(assigned_user)
                        
                        # Clear state
                        del request.session['functional_bot_state']
                        request.session.modified = True
                        
                        return JsonResponse({
                            'success': True,
                            'type': 'redirect',
                            'url': f"{reverse('employee_tasks')}?task_id={task.id}",
                            'message': "✅ Task created successfully! Redirecting you to the task page..."
                        })
                    except Exception as e:
                        print(f"Error creating task: {e}")
                        return JsonResponse({'success': True, 'type': 'text', 'message': "❌ Failed to create task due to an internal error."})
                        
            elif state['action'] == 'create_project':
                step = state['step']
                
                if step == 'name':
                    if not raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "Project name cannot be empty. Please provide a Name:"})
                    state['data']['name'] = raw_command
                    state['step'] = 'description'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': f"Got it. Please provide a brief **Description** for the project:"})
                    
                elif step == 'description':
                    if not raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "Description cannot be empty. Please provide a Description:"})
                    state['data']['description'] = raw_command
                    state['step'] = 'start_date'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': "What is the **Start Date**? (Format: YYYY-MM-DD, or type 'skip' to use today)"})
                    
                elif step == 'start_date':
                    start_date = None
                    if command == 'skip':
                        start_date = timezone.now().date()
                    else:
                        try:
                            start_date = datetime.datetime.strptime(raw_command, "%Y-%m-%d").date()
                        except ValueError:
                            return JsonResponse({'success': True, 'type': 'input_required', 'message': "❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'."})
                            
                    state['data']['start_date'] = start_date.isoformat()
                    state['step'] = 'end_date'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': "What is the **End Date**? (Format: YYYY-MM-DD, or type 'skip' to set it 30 days from the start date)"})
                    
                elif step == 'end_date':
                    end_date = None
                    start_date = datetime.date.fromisoformat(state['data']['start_date'])
                    if command == 'skip':
                        end_date = start_date + datetime.timedelta(days=30)
                    else:
                        try:
                            end_date = datetime.datetime.strptime(raw_command, "%Y-%m-%d").date()
                        except ValueError:
                            return JsonResponse({'success': True, 'type': 'input_required', 'message': "❌ Invalid date format. Please use YYYY-MM-DD or type 'skip'."})
                            
                    state['data']['end_date'] = end_date.isoformat()
                    state['step'] = 'assigned_to'
                    request.session.modified = True
                    
                    users = User.objects.filter(is_active=True, is_superuser=False).order_by('first_name', 'username')
                    user_list = [{"id": u.id, "name": u.get_full_name() or u.username} for u in users]
                    
                    return JsonResponse({
                        'success': True, 
                        'type': 'select_user', 
                        'data': user_list,
                        'message': f"Dates accepted.\n\nWho should be the initial **Assignee** for this project? Please select from the list below or type their name."
                    })
                    
                elif step == 'assigned_to':
                    # Find user
                    user = None
                    if raw_command.isdigit():
                        user = User.objects.filter(id=int(raw_command), is_active=True).first()
                    if not user:
                        user = User.objects.filter(username__iexact=raw_command, is_active=True).first()
                        
                    if not user:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': f"❌ Could not find an active user matching '{raw_command}'. Please try again."})
                        
                    # Create Project
                    try:
                        from projects.models import Projects
                        
                        start_date = datetime.date.fromisoformat(state['data']['start_date'])
                        end_date = datetime.date.fromisoformat(state['data']['end_date'])
                        
                        project = Projects.objects.create(
                            name=state['data']['name'],
                            description=state['data']['description'],
                            start_date=start_date,
                            end_date=end_date,
                            created_by=request.user,
                            status='PENDING'
                        )
                        project.assigned_to.add(user)
                        
                        del request.session['functional_bot_state']
                        request.session.modified = True
                        
                        from django.urls import reverse
                        return JsonResponse({
                            'success': True,
                            'type': 'redirect',
                            'url': reverse('view_project_detail', args=[project.id]),
                            'message': "✅ Project created successfully! Redirecting you to the project page..."
                        })
                    except Exception as e:
                        print(f"Error creating project: {e}")
                        return JsonResponse({'success': True, 'type': 'text', 'message': "❌ Failed to create project due to an internal error."})
                        
            elif state['action'] == 'create_user':
                step = state['step']
                
                if step == 'first_name':
                    if not raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "First name cannot be empty. Please provide a First Name:"})
                    state['data']['first_name'] = raw_command
                    state['step'] = 'last_name'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': f"Got it. What is their **Last Name**?"})
                    
                elif step == 'last_name':
                    if not raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "Last name cannot be empty. Please provide a Last Name:"})
                    state['data']['last_name'] = raw_command
                    state['step'] = 'email'
                    request.session.modified = True
                    return JsonResponse({'success': True, 'type': 'input_required', 'message': f"Got it. What is their **Email Address**?"})
                    
                elif step == 'email':
                    if not raw_command or '@' not in raw_command:
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "Invalid email format. Please provide a valid email:"})
                    
                    if User.objects.filter(email=raw_command).exists() or User.objects.filter(username=raw_command).exists():
                        return JsonResponse({'success': True, 'type': 'input_required', 'message': "❌ A user with this email or username already exists. Please provide a different email:"})
                        
                    state['data']['email'] = raw_command
                    state['step'] = 'role'
                    request.session.modified = True
                    
                    from users.models import Role
                    roles = Role.objects.all()
                    role_list = [{"id": r.id, "name": r.name} for r in roles]
                    
                    return JsonResponse({
                        'success': True, 
                        'type': 'select_role', 
                        'data': role_list,
                        'message': f"Email accepted.\n\nFinally, what should be their **Role**? Please select from the list below."
                    })
                    
                elif step == 'role':
                    from users.models import Role, UserProfile
                    import random
                    import string
                    
                    role = None
                    if raw_command.isdigit():
                        role = Role.objects.filter(id=int(raw_command)).first()
                    if not role:
                        role = Role.objects.filter(name__iexact=raw_command).first()
                        
                    if not role:
                        return JsonResponse({'success': True, 'type': 'text', 'message': f"❌ Could not find a role matching '{raw_command}'. Please try again."})
                        
                    # Create the user!
                    try:
                        # Auto generate password
                        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + "@123"
                        email = state['data']['email']
                        
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                            password=password,
                            first_name=state['data']['first_name'],
                            last_name=state['data']['last_name'],
                            role_obj=role,
                            role=role.name
                        )
                        
                        # The post_save signal auto-creates the profile with an auto-generated employee_id
                        profile = UserProfile.objects.get(user=user)
                        auto_emp_id = profile.employee_id
                        
                        # Send email to the new user
                        try:
                            from django.core.mail import send_mail
                            from django.conf import settings
                            
                            subject = "Welcome to ReadyTask PMS - Your Login Credentials"
                            message = f"Hello {user.get_full_name()},\n\nWelcome to ReadyTask PMS! Your account has been created successfully.\n\nHere are your login credentials:\nEmail / Username: {user.email}\nPassword: {password}\nRole: {role.name}\nEmployee ID: {auto_emp_id}\n\nPlease log in and change your password as soon as possible.\n\nBest regards,\nReadyTask PMS Team"
                            
                            send_mail(
                                subject,
                                message,
                                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@readytask.com'),
                                [user.email],
                                fail_silently=True,
                            )
                        except Exception as email_err:
                            print(f"Failed to send email to {user.email}: {email_err}")
                            
                        # Clear state
                        del request.session['functional_bot_state']
                        request.session.modified = True
                        
                        msg = f"🎉 **User Created Successfully!**\n\n**Name:** {user.get_full_name()}\n**Email:** {user.email}\n**Role:** {role.name}\n**Emp ID:** {auto_emp_id}\n\n**Generated Password:** `{password}`"
                        
                        return JsonResponse({
                            'success': True,
                            'type': 'text',
                            'message': msg
                        })
                    except Exception as e:
                        print(f"Error creating user: {e}")
                        return JsonResponse({'success': True, 'type': 'text', 'message': "❌ Failed to create user due to an internal error."})
            
        # If no state and no matched command
        return JsonResponse({
            'success': True,
            'type': 'text',
            'message': "I didn't understand that command. Try clicking one of the buttons or type 'cancel' to exit an action."
        })
            
    except Exception as e:
        print(f"Error in functional bot API: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)
