import requests
from .base import BaseAction
from users.permissions import can_add_task, can_change_task, can_view_task, can_delete_task
from users.models import User
from projects.models import Projects


class TaskActions(BaseAction):
    """Handles all task-related actions with multi-turn conversation"""
    
    def _call_api(self, endpoint, method='POST', data=None, use_form_data=False):
        """Call the actual task API"""
        from rest_framework_simplejwt.tokens import RefreshToken
        import requests
        
        refresh = RefreshToken.for_user(self.user)
        token = str(refresh.access_token)
        
        headers = {
            'Authorization': f'Bearer {token}',
        }
        
        url = f"http://localhost:8000{endpoint}"
        
        try:
            if method == 'GET':
                headers['Content-Type'] = 'application/json'
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if use_form_data:
                    response = requests.post(url, headers=headers, data=data, timeout=30)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PATCH':
                headers['Content-Type'] = 'application/json'
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return None
            
            print(f"Task API Response Status: {response.status_code}")
            print(f"Task API Response Body: {response.text}")
            
            if response.status_code in [200, 201, 204]:
                if response.text:
                    return response.json()
                return {"success": True}
            return {"error": f"API returned {response.status_code}: {response.text}"}
        except Exception as e:
            print(f"API Error: {e}")
            return {"error": str(e)}
    
    # ============================================================
    # SMART USER RESOLVER (ID, username, or full name)
    # ============================================================
    
    def _resolve_user_id(self, username_or_id):
        """
        Find user by ID (numeric), username, or full name (first_name + last_name)
        """
        from users.models import User

        if not username_or_id:
            return None, None

        identifier = str(username_or_id).strip()

        # 1. Try by ID
        if identifier.isdigit():
            try:
                user = User.objects.get(id=int(identifier), is_active=True)
                print(f"🔍 Found user by ID: {user.id} - {user.username}")
                return user.id, user.username
            except User.DoesNotExist:
                pass

        # 2. Try by username (case‑insensitive)
        try:
            user = User.objects.get(username__iexact=identifier, is_active=True)
            print(f"🔍 Found user by username: {user.id} - {user.username}")
            return user.id, user.username
        except User.DoesNotExist:
            pass

        # 3. Try by full name (first_name + " " + last_name)
        parts = identifier.split()
        if len(parts) >= 2:
            first = parts[0]
            last = ' '.join(parts[1:])
            try:
                user = User.objects.get(first_name__iexact=first, last_name__iexact=last, is_active=True)
                print(f"🔍 Found user by full name: {user.id} - {user.username}")
                return user.id, user.username
            except User.DoesNotExist:
                pass

        # 4. Multiple matches? (return None for simplicity)
        return None, None
    
    def _resolve_user_ids(self, usernames_or_ids):
        """Convert comma-separated usernames OR IDs to list of user IDs"""
        ids = []
        for item in usernames_or_ids.split(','):
            item = item.strip()
            user_id, _ = self._resolve_user_id(item)
            if user_id:
                ids.append(user_id)
        return ids
    
    # ============================================================
    # SMART PROJECT RESOLVER (ID or Name)
    # ============================================================
    
    def _resolve_project_id(self, project_name_or_id):
        """Convert project name OR ID to project ID"""
        from projects.models import Projects
        
        if not project_name_or_id:
            return None, None
        
        identifier = str(project_name_or_id).strip()
        
        if identifier.isdigit():
            try:
                project = Projects.objects.get(id=int(identifier), is_deleted=False)
                print(f"🔍 Found project by ID: {project.id} - {project.name}")
                return project.id, project.name
            except Projects.DoesNotExist:
                print(f"❌ No project found with ID: {identifier}")
                return None, None
        
        try:
            projects = Projects.objects.filter(name__iexact=identifier, is_deleted=False)
            count = projects.count()
            
            if count == 0:
                print(f"❌ No project found with name: {identifier}")
                return None, None
            elif count == 1:
                project = projects.first()
                print(f"🔍 Found project by name: {project.id} - {project.name}")
                return project.id, project.name
            else:
                project_list = [{"id": p.id, "name": p.name} for p in projects]
                print(f"⚠️ Multiple projects found for '{identifier}': {len(project_list)}")
                return None, project_list
        except Exception as e:
            print(f"Error resolving project: {e}")
            return None, None
    
    # ============================================================
    # SMART TASK FINDER (ID or Name)
    # ============================================================
    
    def _find_task_id(self, identifier):
        """Find task ID by ID number or name"""
        from Tasks.models import Task
        
        if not identifier:
            return None
        
        identifier_str = str(identifier).strip()
        
        if identifier_str.isdigit():
            try:
                task = Task.objects.get(id=int(identifier_str), is_deleted=False)
                print(f"🔍 Found task by ID: {task.id} - {task.name}")
                return task.id
            except Task.DoesNotExist:
                print(f"❌ No task found with ID: {identifier_str}")
                return None
        
        try:
            task = Task.objects.get(name__iexact=identifier_str, is_deleted=False)
            print(f"🔍 Found task by name: {task.id} - {task.name}")
            return task.id
        except Task.DoesNotExist:
            print(f"❌ No task found with name: {identifier_str}")
            pass
        except Task.MultipleObjectsReturned:
            task = Task.objects.filter(name__iexact=identifier_str, is_deleted=False).first()
            if task:
                print(f"🔍 Found task by name (multiple matches, using first): {task.id} - {task.name}")
                return task.id
        
        return None
    
    # ============================================================
    # TASK 3: PARSE PROJECT SELECTION (Natural Language)
    # ============================================================
    
    def _parse_project_selection(self, user_input, project_choices):
        """
        Parse natural language selection like "first one", "ID 1", "56"
        
        Examples:
            "first one" → returns project_choices[0]['id']
            "ID 56" → returns 56
            "56" → returns 56
            "second" → returns project_choices[1]['id']
        """
        if not project_choices or not user_input:
            return None
        
        user_lower = str(user_input).lower().strip()
        
        # Pattern 1: "first", "1st", "one"
        if user_lower in ['first', '1st', 'one']:
            return project_choices[0]['id']
        
        # Pattern 2: "second", "2nd", "two"
        if user_lower in ['second', '2nd', 'two']:
            if len(project_choices) > 1:
                return project_choices[1]['id']
        
        # Pattern 3: "third", "3rd", "three"
        if user_lower in ['third', '3rd', 'three']:
            if len(project_choices) > 2:
                return project_choices[2]['id']
        
        # Pattern 4: Just a number (e.g., "56")
        if user_lower.isdigit():
            requested_id = int(user_lower)
            for project in project_choices:
                if project['id'] == requested_id:
                    return requested_id
        
        # Pattern 5: "ID 56" or "id 56" or "project 56" or "#56"
        import re
        id_match = re.search(r'(?:id|project|#)\s*(\d+)', user_lower)
        if id_match:
            requested_id = int(id_match.group(1))
            for project in project_choices:
                if project['id'] == requested_id:
                    return requested_id
        
        return None
    
    # ============================================================
    # CREATE TASK (with duplicate project handling and full name support)
    # ============================================================
    
    def create_task(self, entities, session_context=None):
        """Create a new task with multi-turn conversation"""
        
        if not can_add_task(self.user):
            return self.format_access_denied("Tasks.add_task")
        
        # Merge with existing context if this is a follow-up
        if session_context and session_context.get('pending_entities'):
            partial = session_context.get('pending_entities', {})
            for key, value in entities.items():
                if value:
                    partial[key] = value
            entities = partial
        
        # Define required fields in order
        required_fields = [
            ('name', 'task name'),
            ('project', 'project name'),
            ('assigned_to', 'assignee username'),
            ('start_date', 'start date (YYYY-MM-DD)'),
            ('end_date', 'end date (YYYY-MM-DD)'),
            ('description', 'description')
        ]
        
        # Optional fields
        optional_fields = ['deadline', 'observers', 'estimated_time']
        
        # Find first missing required field
        missing_fields = []
        for field, display_name in required_fields:
            if not entities.get(field):
                missing_fields.append((field, display_name))
        
        # If there are missing required fields, ask for the first one
        if missing_fields:
            first_missing_field, first_missing_display = missing_fields[0]
            
            if first_missing_field == 'name':
                question = f"📝 What is the task name?"
            elif first_missing_field == 'project':
                question = f"📝 Which project is this task for?\n\nYou can use project name or ID (e.g., 'Website' or '5')"
            elif first_missing_field == 'assigned_to':
                question = f"📝 Who should this task be assigned to?\n\nYou can use username, ID, or full name (e.g., 'john', '7', 'John Doe')"
            elif first_missing_field == 'start_date':
                question = f"📝 What is the start date? (YYYY-MM-DD)\n\nType 'skip' to use today's date\nExample: 2026-04-20"
            elif first_missing_field == 'end_date':
                question = f"📝 What is the end date? (YYYY-MM-DD)\n\nType 'skip' to use next week's date\nExample: 2026-04-27"
            elif first_missing_field == 'description':
                question = f"📝 Please provide a description for this task:"
            else:
                question = f"📝 Please provide the {first_missing_display}:"
            
            return {
                "success": True,
                "message": question,
                "need_more_info": True,
                "missing_field": first_missing_field,
                "partial_data": entities
            }
        
        # Check if we need to ask for optional fields
        asked_optional = session_context.get('asked_optional', []) if session_context else []
        
        for opt_field in optional_fields:
            if opt_field not in asked_optional and opt_field not in entities:
                if opt_field == 'deadline':
                    question = f"📝 Do you want to set a deadline? (YYYY-MM-DD HH:MM)\n\nType 'skip' to skip or provide the deadline:"
                elif opt_field == 'observers':
                    question = f"📝 Any observers for this task? (Enter usernames or IDs separated by commas)\n\nExample: john, 5, mike\nType 'skip' to skip:"
                elif opt_field == 'estimated_time':
                    question = f"📝 What is the estimated time for this task? (in minutes)\n\nExample: 120 for 2 hours\nType 'skip' to skip:"
                else:
                    continue
                
                new_asked = asked_optional + [opt_field]
                return {
                    "success": True,
                    "message": question,
                    "need_more_info": True,
                    "missing_field": opt_field,
                    "partial_data": entities,
                    "asked_optional": new_asked
                }
        
        # All required fields present - create the task
        task_name = entities.get('name')
        project_name = entities.get('project')
        assignee_name = entities.get('assigned_to')
        start_date = entities.get('start_date')
        end_date = entities.get('end_date')
        description = entities.get('description')
        
        # Handle 'skip' for start_date - use today's date
        from datetime import date, timedelta
        
        if start_date == 'skip' or start_date == '':
            start_date = date.today().strftime('%Y-%m-%d')
            print(f"📝 Using default start date: {start_date}")
        
        if end_date == 'skip' or end_date == '':
            end_date = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"📝 Using default end date: {end_date}")
        
        # Validate date format
        import re
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        
        if not re.match(date_pattern, start_date):
            return self.format_success(
                f"❌ Invalid start date format: '{start_date}'\n\n"
                f"Please use YYYY-MM-DD format or type 'skip'.\n"
                f"Example: 2026-04-20"
            )
        
        if not re.match(date_pattern, end_date):
            return self.format_success(
                f"❌ Invalid end date format: '{end_date}'\n\n"
                f"Please use YYYY-MM-DD format or type 'skip'.\n"
                f"Example: 2026-05-20"
            )
        
        # ============================================================
        # TASK 3: PROJECT RESOLUTION WITH DUPLICATE HANDLING (FIXED)
        # ============================================================
        
        # Resolve project (supports ID or name)
        project_id, project_result = self._resolve_project_id(project_name)
        
        if project_id is None and project_result is None:
            return self.format_success(
                f"❌ Project '{project_name}' not found.\n\n"
                f"Please check the project name/ID and try again."
            )
        elif project_id is None and isinstance(project_result, list):
            # FIRST: Check if user already provided a project_id in entities
            if entities.get('project_id'):
                # User already provided a project_id, use it
                try:
                    project_id = int(entities['project_id'])
                    print(f"✅ Using existing project_id from entities: {project_id}")
                    # Clear any selection context
                    if session_context:
                        session_context.pop('project_choices', None)
                        session_context.pop('selection_attempts', None)
                except (ValueError, TypeError):
                    pass
            
            # SECOND: Check if user is responding to selection prompt (session_context has project_choices)
            if not project_id and session_context and session_context.get('project_choices'):
                # User is responding to selection prompt
                user_choice = project_name
                selected_id = self._parse_project_selection(user_choice, project_result)
                
                if selected_id:
                    # Valid selection made
                    project_id = selected_id
                    print(f"✅ User selected project ID: {project_id}")
                    # Clear selection context
                    if 'project_choices' in session_context:
                        del session_context['project_choices']
                    if 'selection_attempts' in session_context:
                        del session_context['selection_attempts']
                else:
                    # Invalid selection - show options again
                    attempt_count = session_context.get('selection_attempts', 0)
                    attempt_count += 1
                    session_context['selection_attempts'] = attempt_count
                    session_context.save()
                    
                    if attempt_count >= 2:
                        return {
                            "success": True,
                            "message": f"⚠️ Please select a valid project by typing the ID number:\n\n"
                                      + "\n".join([f"  • {p['name']} (ID: {p['id']})" for p in project_result]) + "\n\n"
                                      f"Type the number (e.g., '{project_result[0]['id']}') or type 'cancel' to start over.",
                            "need_more_info": True,
                            "missing_field": "project_id",
                            "partial_data": entities,
                            "project_choices": project_result
                        }
                    else:
                        return {
                            "success": True,
                            "message": f"⚠️ Please select a valid project:\n\n"
                                      + "\n".join([f"  • {p['name']} (ID: {p['id']})" for p in project_result]) + "\n\n"
                                      f"Type the ID number (e.g., '{project_result[0]['id']}') or type 'cancel' to start over.",
                            "need_more_info": True,
                            "missing_field": "project_id",
                            "partial_data": entities,
                            "project_choices": project_result
                        }
            
            # THIRD: First time showing choices - store in session_context
            if not project_id:
                return {
                    "success": True,
                    "message": f"⚠️ Multiple projects found with name '{project_name}':\n\n"
                              + "\n".join([f"  • {p['name']} (ID: {p['id']})" for p in project_result]) + "\n\n"
                              f"**Type the project ID number** (e.g., '{project_result[0]['id']}') to continue:\n"
                              f"Or type **'cancel'** to start over.",
                    "need_more_info": True,
                    "missing_field": "project_id",
                    "partial_data": entities,
                    "project_choices": project_result
                }
        
        # Resolve assignee (supports ID, username, full name)
        assignee_id, assignee_result = self._resolve_user_id(assignee_name)
        
        if assignee_id is None and assignee_result is None:
            return self.format_success(
                f"❌ User '{assignee_name}' not found.\n\n"
                f"Please check the username/ID/full name and try again."
            )
        elif assignee_id is None and isinstance(assignee_result, list):
            user_list = "\n".join([f"  • {u['username']} (ID: {u['id']})" for u in assignee_result])
            return {
                "success": True,
                "message": f"⚠️ Multiple users found with username '{assignee_name}':\n\n{user_list}\n\n"
                           f"Please specify which user by ID.\n"
                           f"Example: 'Use user ID {assignee_result[0]['id']}'",
                "need_more_info": True,
                "missing_field": "assignee_id",
                "partial_data": entities,
                "user_choices": assignee_result
            }
        
        # Handle optional fields - treat 'skip' as None
        deadline = entities.get('deadline')
        if deadline == 'skip' or deadline == '':
            deadline = None
        
        observers = entities.get('observers')
        observers_ids = []
        if observers and observers != 'skip' and observers != '':
            observers_ids = self._resolve_user_ids(observers)
        
        estimated_time = entities.get('estimated_time')
        if estimated_time and estimated_time != 'skip' and estimated_time != '':
            try:
                estimated_time = int(estimated_time) * 60  # Convert minutes to seconds
            except:
                estimated_time = 3600
        else:
            estimated_time = 3600
        
        # Prepare task data
        task_data = {
            "name": task_name,
            "description": description,
            "project": project_id,
            "assigned_to": [assignee_id],
            "assigned_by": [self.user.id],
            "start_date": start_date,
            "end_date": end_date,
            "status": "PENDING",
            "estimated_time": estimated_time,
            "created_by": self.user.id
        }
        
        if deadline:
            task_data["deadline"] = deadline
        if observers_ids:
            task_data["observers"] = observers_ids
        
        print(f"📝 Creating task with: {task_data}")
        
        # Call the actual API
        response = self._call_api('/api/tasks/', method='POST', data=task_data)
        
        print(f"📝 API Response: {response}")
        
        if response and response.get('id'):
            message = f"✅ Task '{task_name}' created successfully!\n\n"
            message += f"📋 Task ID: #{response['id']}\n"
            message += f"👤 Assigned to: {assignee_name}\n"
            message += f"📁 Project: {project_name}\n"
            message += f"📅 Timeline: {start_date} to {end_date}\n"
            message += f"📝 Description: {description[:100]}{'...' if len(description) > 100 else ''}\n"
            message += f"📊 Status: PENDING"
            
            if deadline:
                message += f"\n⏰ Deadline: {deadline}"
            if observers_ids:
                message += f"\n👀 Observers: {observers}"
            
            return {
                "success": True,
                "message": message,
                "task_created": True
            }
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(
                f"❌ Failed to create task: {error_msg}\n\n"
                f"Please check the information and try again."
            )
    
    # ============================================================
    # VIEW TASKS
    # ============================================================
    
    def view_tasks(self, entities):
        """View user's tasks"""
        if not can_view_task(self.user):
            return self.format_access_denied("Tasks.view_task")
        
        response = self._call_api('/api/tasks/', method='GET')
        
        if response and 'results' in response:
            tasks = response['results']
            if not tasks:
                return self.format_success("📋 You have no tasks assigned to you.")
            
            task_list = []
            for task in tasks[:10]:
                status_icon = "🟡" if task['status'] == 'PENDING' else "🔵" if task['status'] == 'ONGOING' else "✅"
                task_list.append(f"{status_icon} {task['name']} (ID: {task['id']}) - {task.get('status_display', task['status'])}")
            
            message = f"📋 Your tasks ({len(tasks)} total):\n\n" + "\n".join(task_list)
            if len(tasks) > 10:
                message += f"\n\n... and {len(tasks) - 10} more tasks"
            
            return self.format_success(message, {"total": len(tasks)})
        else:
            return self.format_success("📋 You have no tasks assigned to you.")
    
    # ============================================================
    # VIEW TASK DETAIL
    # ============================================================
    
    def view_task_detail(self, entities):
        """Show details of a specific task (by ID or name)"""
        from Tasks.models import Task
        
        if not can_view_task(self.user):
            return self.format_access_denied("Tasks.view_task")
        
        task_identifier = entities.get('task_id_or_name')
        info_type = entities.get('info_type', 'details')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to see details for?\n\n"
                "Example: 'show details of task 42' or 'what is deadline of task Fix bug'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        response = self._call_api(f'/api/tasks/{task_id}/', method='GET')
        
        if not response or not response.get('id'):
            return self.format_success(f"❌ Could not fetch details for task '{task_identifier}'.")
        
        if info_type == 'deadline' or info_type == 'due date':
            deadline = response.get('deadline')
            if deadline:
                try:
                    from datetime import datetime
                    deadline_str = deadline.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(deadline_str)
                    formatted_deadline = dt.strftime('%B %d, %Y at %I:%M %p')
                except:
                    formatted_deadline = deadline
                return self.format_success(
                    f"📅 Task '{response['name']}' (ID: {response['id']}) deadline is: **{formatted_deadline}**"
                )
            else:
                return self.format_success(f"📅 Task '{response['name']}' has no deadline set.")
        
        else:
            status_icon = "🟡" if response['status'] == 'PENDING' else "🔵" if response['status'] == 'ONGOING' else "✅"
            
            message = f"{status_icon} **Task: {response['name']}** (ID: {response['id']})\n\n"
            message += f"📝 **Description:** {response['description'] or 'No description'}\n"
            message += f"📊 **Status:** {response.get('status_display', response['status'])}\n"
            
            if response.get('deadline'):
                message += f"⏰ **Deadline:** {response['deadline']}\n"
            if response.get('start_date'):
                message += f"📅 **Start Date:** {response['start_date']}\n"
            if response.get('end_date'):
                message += f"📅 **End Date:** {response['end_date']}\n"
            
            message += f"⏱️ **Time Spent:** {response.get('time_display', '00:00:00')}\n"
            message += f"🎯 **Estimated Time:** {response.get('estimated_display', 'Not set')}\n"
            
            if response.get('assigned_to_details'):
                assignees = ", ".join([u.get('full_name', u.get('username')) for u in response['assigned_to_details']])
                message += f"👤 **Assigned to:** {assignees}\n"
            
            if response.get('project_name'):
                message += f"📁 **Project:** {response['project_name']}\n"
            
            if response.get('summary'):
                message += f"\n📝 **Summary:** {response['summary']}"
            
            return self.format_success(message)
    
    # ============================================================
    # START TASK
    # ============================================================
    
    def start_task(self, entities):
        """Start a task - supports task ID or name"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name') or entities.get('name')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to start?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'start task Fix bug' or 'start task 42'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        response = self._call_api(f'/task/{task_id}/start/', method='POST')
        
        if response and response.get('success'):
            return self.format_success(f"▶️ Task started successfully! Time tracking has begun.")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            
            if '404' in str(error_msg) or 'No Task matches' in str(error_msg):
                return self.format_success(
                    f"❌ Task '{task_identifier}' not found in the system.\n\n"
                    f"Please check the task name or ID and try again.\n"
                    f"Use 'show my tasks' to see your active tasks."
                )
            
            return self.format_success(f"❌ Failed to start task: {error_msg}")
    
    # ============================================================
    # PAUSE TASK
    # ============================================================
    
    def pause_task(self, entities):
        """Pause a task - supports task ID or name"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name') or entities.get('name')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to pause?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'pause task Fix bug' or 'pause task 42'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again."
            )
        
        response = self._call_api(f'/task/{task_id}/pause/', method='POST')
        
        if response and response.get('success'):
            return self.format_success(f"⏸️ Task paused successfully.")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to pause task: {error_msg}")
    
    # ============================================================
    # RESUME TASK
    # ============================================================
    
    def resume_task(self, entities):
        """Resume a paused task - supports task ID or name"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name') or entities.get('name')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to resume?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'resume task Fix bug' or 'resume task 42'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again."
            )
        
        response = self._call_api(f'/task/{task_id}/resume/', method='POST')
        
        if response and response.get('success'):
            return self.format_success(f"▶️ Task resumed successfully! Time tracking continues.")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to resume task: {error_msg}")
    
    # ============================================================
    # COMPLETE TASK
    # ============================================================
    
    def complete_task(self, entities):
        """Complete a task - supports task ID or name"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name') or entities.get('name')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to complete?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'complete task Fix bug' or 'complete task 42'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        response = self._call_api(f'/task/{task_id}/complete/', method='POST')
        
        if response and response.get('success'):
            time_display = response.get('time_display', '')
            return self.format_success(f"✅ Task completed successfully!{time_display}")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            
            if 'summary' in str(error_msg).lower() or 'Please add a task summary' in str(error_msg):
                redirect_url = response.get('redirect_url', '')
                return self.format_success(
                    f"⚠️ Task '{task_identifier}' needs a summary before completing.\n\n"
                    f"Please add a summary first using the link below:\n"
                    f"📝 {redirect_url}\n\n"
                    f"Or type: 'add summary for task {task_id}'"
                )
            
            return self.format_success(f"❌ Failed to complete task: {error_msg}")
    
    # ============================================================
    # ADD SUMMARY
    # ============================================================
    
    def add_summary(self, entities):
        """Add a summary to a task"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name')
        summary = entities.get('summary')
        
        if not task_identifier and entities.get('task_id'):
            task_id = entities.get('task_id')
            task_identifier = str(task_id)
        else:
            task_id = None
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to add a summary to?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'add summary to task 46: Fixed the bug' or 'add summary to task Fix bug: Fixed it'"
            )
        
        if not task_id:
            task_id = self._find_task_id(task_identifier)
        
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        if not summary:
            return {
                "success": True,
                "message": f"📝 Please provide the summary for task '{task_identifier}':\n\n"
                        f"Example: 'Fixed the login validation issue'",
                "need_more_info": True,
                "missing_field": "summary",
                "partial_data": {"task_id_or_name": task_identifier, "task_id": task_id}
            }
        
        if len(summary.strip()) < 10:
            return self.format_success(
                f"⚠️ Please provide a more detailed summary (at least 10 characters).\n\n"
                f"Current summary: '{summary}'\n\n"
                f"Example: 'Fixed the login validation issue in the authentication module'"
            )
        
        response = self._call_api(f'/task/{task_id}/summary/add/', 
                                method='POST', 
                                data={"summary": summary},
                                use_form_data=True)
        
        print(f"📝 Add Summary API Response: {response}")
        
        if response and response.get('success'):
            return self.format_success(f"✅ Summary added to task '{task_identifier}' successfully!\n\n"
                                    f"📝 Summary: {summary}\n\n"
                                    f"You can now complete the task using 'complete task {task_identifier}'")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to add summary: {error_msg}")
    
    # ============================================================
    # EDIT TASK
    # ============================================================
    
    def edit_task(self, entities):
        """Edit an existing task - supports task ID or name"""
        if not can_change_task(self.user):
            return self.format_access_denied("Tasks.change_task")
        
        task_identifier = entities.get('task_id_or_name')
        field = entities.get('field')
        new_value = entities.get('new_value')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to edit?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'edit task 46 name to New Task Name' or 'edit task Fix bug status to ONGOING'"
            )
        
        if not field:
            return self.format_success(
                "📝 What field would you like to edit?\n\n"
                "Available fields: name, description, status, start_date, end_date, deadline\n"
                "Example: 'edit task 46 status to ONGOING'"
            )
        
        if not new_value:
            return self.format_success(
                f"📝 What is the new value for '{field}'?\n\n"
                f"Example: 'edit task {task_identifier} {field} to New Value'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        update_data = {field: new_value}
        response = self._call_api(f'/api/tasks/{task_id}/', method='PATCH', data=update_data)
        
        print(f"📝 Edit Task API Response: {response}")
        
        if response and response.get('success'):
            return self.format_success(f"✅ Task '{task_identifier}' updated successfully!\n\n"
                                    f"📝 Updated {field} to: {new_value}")
        elif response and response.get('id'):
            return self.format_success(f"✅ Task '{task_identifier}' updated successfully!\n\n"
                                    f"📝 Updated {field} to: {new_value}")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to edit task: {error_msg}")
    
    # ============================================================
    # DELETE TASK
    # ============================================================
    
    def delete_task(self, entities):
        """Delete (soft delete) a task - move to trash"""
        if not can_delete_task(self.user):
            return self.format_access_denied("Tasks.delete_task")
        
        task_identifier = entities.get('task_id_or_name')
        
        if not task_identifier:
            return self.format_success(
                "📝 Which task would you like to delete?\n\n"
                "Please provide the task name or ID.\n"
                "Example: 'delete task 46' or 'trash task Fix bug'"
            )
        
        task_id = self._find_task_id(task_identifier)
        if not task_id:
            return self.format_success(
                f"❌ Task '{task_identifier}' not found.\n\n"
                f"Please check the task name or ID and try again.\n"
                f"Use 'show my tasks' to see your tasks."
            )
        
        response = self._call_api(f'/api/tasks/{task_id}/', method='DELETE')
        
        print(f"📝 Delete Task API Response: {response}")
        
        if response and response.get('success'):
            return self.format_success(f"✅ Task '{task_identifier}' has been moved to trash.\n\n"
                                    f"You can restore it from the Trash page within 15 days.")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to delete task: {error_msg}")