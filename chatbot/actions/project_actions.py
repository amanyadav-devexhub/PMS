import requests
from .base import BaseAction
from users.permissions import can_add_projects, can_view_projects,can_change_projects,can_delete_projects
from users.models import User


class ProjectActions(BaseAction):
    
    
    def _call_api(self, endpoint, method='POST', data=None):
      
        from rest_framework_simplejwt.tokens import RefreshToken
        import requests
        
        refresh = RefreshToken.for_user(self.user)
        token = str(refresh.access_token)
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        url = f"http://localhost:8000{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return None
            
            print(f"Project API Response Status: {response.status_code}")
            print(f"Project API Response Body: {response.text}")
            
            if response.status_code in [200, 201, 204]:
                if response.text:
                    return response.json()
                return {"success": True}
            return {"error": f"API returned {response.status_code}: {response.text}"}
        except Exception as e:
            print(f"API Error: {e}")
            return {"error": str(e)}
    
    def create_project(self, entities, session_context=None):
        
        if not can_add_projects(self.user):
            return self.format_access_denied("projects.add_projects")
        
        if session_context and session_context.get('pending_entities'):
            partial = session_context.get('pending_entities', {})
            for key, value in entities.items():
                if value:
                    partial[key] = value
            entities = partial
        
        required_fields = [
            ('name', 'project name'),
            ('description', 'description'),
            ('start_date', 'start date (YYYY-MM-DD)'),
            ('end_date', 'end date (YYYY-MM-DD)')
        ]
        
        missing_fields = []
        for field, display_name in required_fields:
            if not entities.get(field):
                missing_fields.append((field, display_name))
        
        if missing_fields:
            first_missing_field, first_missing_display = missing_fields[0]
            
            if first_missing_field == 'name':
                question = f"📝 What is the project name?"
            elif first_missing_field == 'description':
                question = f"📝 Please provide a brief description for the project:"
            elif first_missing_field == 'start_date':
                question = f"📝 What is the start date? (YYYY-MM-DD)\n\nType 'skip' to use today's date\nExample: 2026-04-20"
            elif first_missing_field == 'end_date':
                question = f"📝 What is the end date? (YYYY-MM-DD)\n\nType 'skip' to use next week's date\nExample: 2026-05-20"
            else:
                question = f"📝 Please provide the {first_missing_display}:"
            
            return {
                "success": True,
                "message": question,
                "need_more_info": True,
                "missing_field": first_missing_field,
                "partial_data": entities
            }
        
        asked_assigned_to = session_context.get('asked_assigned_to', False) if session_context else False
        
        if not asked_assigned_to and 'assigned_to' not in entities:
            question = f"📝 Any team members to assign to this project? (Enter usernames separated by commas)\n\nExample: john, sarah, mike\nType 'skip' to skip:"
            
            return {
                "success": True,
                "message": question,
                "need_more_info": True,
                "missing_field": 'assigned_to',
                "partial_data": entities,
                "asked_assigned_to": True
            }
        
        project_name = entities.get('name')
        description = entities.get('description')
        start_date = entities.get('start_date')
        end_date = entities.get('end_date')
        
        from datetime import date, timedelta
        
        if start_date == 'skip' or start_date == '':
            start_date = date.today().strftime('%Y-%m-%d')
            print(f"📝 Using default start date: {start_date}")
        
        if end_date == 'skip' or end_date == '':
            end_date = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
            print(f"📝 Using default end date: {end_date}")
        
        assigned_to_input = entities.get('assigned_to')
        assigned_to_ids = []
        if assigned_to_input and assigned_to_input != 'skip':
            assigned_to_ids = self._resolve_user_ids(assigned_to_input)
        
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
        
        project_data = {
            "name": project_name,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "status": "PENDING"
        }
        
        if assigned_to_ids:
            project_data["assigned_to"] = assigned_to_ids
        
        print(f"📝 Creating project with: {project_data}")
        
        response = self._call_api('/api/projects/', method='POST', data=project_data)
        
        print(f"📝 API Response: {response}")
        
        if response and response.get('id'):
            assigned_text = ""
            if assigned_to_ids:
                assigned_text = f"\n👥 Assigned to: {assigned_to_input}"
            
            return {
                "success": True,
                "message": f"✅ Project '{project_name}' created successfully!\n\n"
                          f"📋 Project ID: #{response['id']}\n"
                          f"📅 Timeline: {start_date} to {end_date}\n"
                          f"📊 Status: PENDING{assigned_text}\n\n"
                          f"📝 Description: {description[:100]}{'...' if len(description) > 100 else ''}",
                "project_created": True
            }
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(
                f"❌ Failed to create project: {error_msg}\n\n"
                f"Please check the information and try again."
            )
    
    def view_projects(self, entities):
        
        if not can_view_projects(self.user):
            return self.format_access_denied("projects.view_projects")
        
        response = self._call_api('/api/projects/', method='GET')
        
        if response and 'results' in response:
            projects = response['results']
            if not projects:
                return self.format_success("📁 You have no projects assigned to you.")
            
            project_list = []
            for project in projects[:10]:
                status_icon = "🟡" if project['status'] == 'PENDING' else "🔵" if project['status'] == 'ONGOING' else "✅"
                project_list.append(f"{status_icon} {project['name']} (ID: {project['id']})")
            
            message = f"📁 Your projects ({len(projects)} total):\n\n" + "\n".join(project_list)
            if len(projects) > 10:
                message += f"\n\n... and {len(projects) - 10} more projects"
            
            return self.format_success(message, {"total": len(projects)})
        else:
            return self.format_success("📁 You have no projects assigned to you.")
    
    def _find_project_id(self, identifier):
        """Find project ID by name or ID string"""
        from projects.models import Projects
        
        if str(identifier).isdigit():
            try:
                project = Projects.objects.get(id=int(identifier), is_deleted=False)
                return project.id
            except Projects.DoesNotExist:
                pass
        
        try:
            project = Projects.objects.get(name__iexact=identifier, is_deleted=False)
            return project.id
        except Projects.DoesNotExist:
            pass
        except Projects.MultipleObjectsReturned:
            project = Projects.objects.filter(name__iexact=identifier, is_deleted=False).first()
            return project.id if project else None
        
        return None

    def _resolve_user_ids(self, usernames_or_ids):
        """
        Convert comma-separated usernames OR IDs to list of user IDs
        """
        from users.models import User
        
        ids = []
        for item in usernames_or_ids.split(','):
            item = item.strip()
            if item.isdigit():
                try:
                    user = User.objects.get(id=int(item), is_active=True)
                    ids.append(user.id)
                    continue
                except User.DoesNotExist:
                    pass
            try:
                user = User.objects.get(username__iexact=item, is_active=True)
                ids.append(user.id)
            except User.DoesNotExist:
                print(f"User not found: {item}")
        return ids

    def edit_project(self, entities):
        """Edit an existing project"""
        if not can_change_projects(self.user):
            return self.format_access_denied("projects.change_projects")
        
        project_identifier = entities.get('project_id_or_name')
        field = entities.get('field')
        new_value = entities.get('new_value')
        
        if not project_identifier:
            return self.format_success(
                "📝 Which project would you like to edit?\n\n"
                "Please provide the project name or ID.\n"
                "Example: 'edit project 42 name to New Project Name'"
            )
        
        if not field:
            return self.format_success(
                "📝 What field would you like to edit?\n\n"
                "Available fields: name, description, status, start_date, end_date\n"
                "Example: 'edit project 42 status to COMPLETED'"
            )
        
        if not new_value:
            return self.format_success(
                f"📝 What is the new value for '{field}'?\n\n"
                f"Example: 'edit project {project_identifier} {field} to New Value'"
            )
        
        # Find project ID
        project_id = self._find_project_id(project_identifier)
        if not project_id:
            return self.format_success(
                f"❌ Project '{project_identifier}' not found.\n\n"
                f"Please check the project name or ID and try again.\n"
                f"Use 'show my projects' to see your projects."
            )
        
        # Prepare update data
        update_data = {field: new_value}
        
        # Call update API (PATCH request)
        response = self._call_api(f'/api/projects/{project_id}/', method='PATCH', data=update_data)
        
        print(f"📝 Edit Project API Response: {response}")
        
        if response and response.get('success'):
            return self.format_success(f"✅ Project '{project_identifier}' updated successfully!\n\n"
                                    f"📝 Updated {field} to: {new_value}")
        elif response and response.get('id'):
            return self.format_success(f"✅ Project '{project_identifier}' updated successfully!\n\n"
                                    f"📝 Updated {field} to: {new_value}")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to edit project: {error_msg}")

    def delete_project(self, entities):
        """Delete (soft delete) a project - move to trash"""
        if not can_delete_projects(self.user):
            return self.format_access_denied("projects.delete_projects")
        
        project_identifier = entities.get('project_id_or_name')
        
        if not project_identifier:
            return self.format_success(
                "📝 Which project would you like to delete?\n\n"
                "Please provide the project name or ID.\n"
                "Example: 'delete project 42' or 'trash project Website'"
            )
        
        # Find project ID
        project_id = self._find_project_id(project_identifier)
        if not project_id:
            return self.format_success(
                f"❌ Project '{project_identifier}' not found.\n\n"
                f"Please check the project name or ID and try again.\n"
                f"Use 'show my projects' to see your projects."
            )
        
        # Call delete API (soft delete)
        response = self._call_api(f'/api/projects/{project_id}/', method='DELETE')
        
        print(f"📝 Delete Project API Response: {response}")
        
        if response and response.get('success'):
            return self.format_success(f"✅ Project '{project_identifier}' has been moved to trash.\n\n"
                                    f"You can restore it from the Trash page within 15 days.")
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(f"❌ Failed to delete project: {error_msg}")

    def view_project_detail(self, entities):
        """Show details of a specific project (by ID or name)"""
        from projects.models import Projects
        from users.permissions import can_view_projects
        
        if not can_view_projects(self.user):
            return self.format_access_denied("projects.view_projects")
        
        project_identifier = entities.get('project_id_or_name')
        info_type = entities.get('info_type', 'details')
        
        if not project_identifier:
            return self.format_success(
                "📝 Which project would you like to see details for?\n\n"
                "Example: 'show details of project 5' or 'what is status of project Website'"
            )
        
        project_id = self._find_project_id(project_identifier)
        if not project_id:
            return self.format_success(
                f"❌ Project '{project_identifier}' not found.\n\n"
                f"Please check the project name or ID and try again.\n"
                f"Use 'show my projects' to see your projects."
            )
        
        response = self._call_api(f'/api/projects/{project_id}/', method='GET')
        
        if not response or not response.get('id'):
            return self.format_success(f"❌ Could not fetch details for project '{project_identifier}'.")
        
        if info_type == 'status':
            status_icon = "🟡" if response['status'] == 'PENDING' else "🔵" if response['status'] == 'ONGOING' else "✅"
            return self.format_success(
                f"{status_icon} Project '{response['name']}' (ID: {response['id']}) status is: **{response.get('status_display', response['status'])}**"
            )
        
        elif info_type == 'end_date' or info_type == 'deadline' or info_type == 'due date':
            end_date = response.get('end_date')
            if end_date:
                return self.format_success(
                    f"📅 Project '{response['name']}' (ID: {response['id']}) end date is: **{end_date}**"
                )
            else:
                return self.format_success(f"📅 Project '{response['name']}' has no end date set.")
        
        else:
            status_icon = "🟡" if response['status'] == 'PENDING' else "🔵" if response['status'] == 'ONGOING' else "✅"
            
            message = f"{status_icon} **Project: {response['name']}** (ID: {response['id']})\n\n"
            message += f"📝 **Description:** {response.get('description') or 'No description'}\n"
            message += f"📊 **Status:** {response.get('status_display', response['status'])}\n"
            
            if response.get('start_date'):
                message += f"📅 **Start Date:** {response['start_date']}\n"
            if response.get('end_date'):
                message += f"📅 **End Date:** {response['end_date']}\n"
            
            try:
                tasks_response = self._call_api(f'/api/tasks/?project={response["id"]}', method='GET')
                if tasks_response and 'results' in tasks_response:
                    task_count = len(tasks_response['results'])
                    message += f"📋 **Total Tasks:** {task_count}\n"
            except:
                pass
            
            if response.get('assigned_to_details'):
                assignees = ", ".join([u.get('full_name', u.get('username')) for u in response['assigned_to_details']])
                message += f"👥 **Assigned to:** {assignees}\n"
            
            return self.format_success(message)