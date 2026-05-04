import requests
import re
import random
from .base import BaseAction
from users.permissions import can_add_user, can_view_user
from users.models import Department, Designation, Role


class UserActions(BaseAction):
    """Handles all user-related actions with multi-turn conversation"""
    
    def _call_api(self, endpoint, method='GET', data=None):
        """Call the actual API"""
        from rest_framework_simplejwt.tokens import RefreshToken
        
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
            else:
                return None
            
            print(f"API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def _call_create_user_api(self, user_data):
        """Call the actual user creation API"""
        from rest_framework_simplejwt.tokens import RefreshToken
        
        print(f"\n🔍 Creating user with data: {user_data}")
        
        refresh = RefreshToken.for_user(self.user)
        token = str(refresh.access_token)
        
        headers = {
            'Authorization': f'Bearer {token}',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        url = "http://localhost:8000/user/create/"
        
        try:
            response = requests.post(url, data=user_data, headers=headers, timeout=30)
            print(f"API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except:
                    return {"success": True, "message": "User created"}
            else:
                return {"success": False, "error": response.text}
        except Exception as e:
            print(f"API Error: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_role_id(self, role_name):
        """Get role ID from role name"""
        role_map = {
            'admin': 'Admin',
            'administrator': 'Admin',
            'team lead': 'Team Lead',
            'teamlead': 'Team Lead',
            'employee': 'Employee',
            'emp': 'Employee'
        }
        
        role_key = role_map.get(role_name.lower(), 'Employee')
        
        try:
            role = Role.objects.get(name=role_key)
            return role.id
        except Role.DoesNotExist:
            return None
    
    def _get_available_roles(self):
        """Get list of available roles"""
        return list(Role.objects.values_list('name', flat=True))
    
    def _get_available_departments(self):
        """Get list of available departments"""
        return list(Department.objects.values_list('name', flat=True))
    
    def _get_available_designations(self):
        """Get list of available designations"""
        return list(Designation.objects.values_list('name', flat=True))
    
    def _generate_employee_id(self):
        """Generate a random employee ID (numbers only)"""
        return str(random.randint(10000, 99999))
    
    def create_user(self, entities, session_context=None):
        """Create a new user with multi-turn conversation"""
        
        if not can_add_user(self.user):
            return self.format_access_denied("users.add_user")
        
        # Merge with existing context if this is a follow-up
        if session_context and session_context.get('pending_entities'):
            partial = session_context.get('pending_entities', {})
            for key, value in entities.items():
                if value:
                    partial[key] = value
            entities = partial
        
        # Define required fields in order
        required_fields = [
            ('first_name', 'first name', self._validate_name),
            ('last_name', 'last name', self._validate_name),
            ('email', 'email address', self._validate_email),
            ('username', 'username', self._validate_username),
            ('role', 'role', self._validate_role_exists),
            ('department', 'department', self._validate_department_exists),
            ('designation', 'designation', self._validate_designation_exists)
        ]
        
        # Find first missing or invalid field
        for field, display_name, validator in required_fields:
            value = entities.get(field)
            
            # Check if field is missing
            if not value:
                question = self._get_question_for_field(field)
                return {
                    "success": True,
                    "message": question,
                    "need_more_info": True,
                    "missing_field": field,
                    "partial_data": entities
                }
            
            # Validate the field value
            is_valid, error_msg = validator(value)
            if not is_valid:
                return {
                    "success": True,
                    "message": f"❌ {error_msg}\n\nPlease provide a valid {display_name}:",
                    "need_more_info": True,
                    "missing_field": field,
                    "partial_data": entities
                }
        
        # All fields present and valid - create the user
        first_name = entities.get('first_name')
        last_name = entities.get('last_name')
        email = entities.get('email')
        username = entities.get('username')
        role_name = entities.get('role')
        department_name = entities.get('department')
        designation_name = entities.get('designation')
        
        # Get role ID
        role_id = self._get_role_id(role_name)
        
        # Generate employee_id
        employee_id = self._generate_employee_id()
        
        # Get department ID
        department = Department.objects.get(name__iexact=department_name)
        department_id = department.id
        
        # Get designation ID
        designation = Designation.objects.get(name__iexact=designation_name)
        designation_id = designation.id
        
        # Prepare data for API
        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'username': username,
            'role': role_id,
            'employee_id': employee_id,
            'department': department_id,
            'designation': designation_id,
        }
        
        print(f"📝 Creating user with: {user_data}")
        
        # Call the API
        response = self._call_create_user_api(user_data)
        
        if response and response.get('success'):
            role_display = Role.objects.get(id=role_id).name
            
            return {
                "success": True,
                "message": f"✅ User '{first_name} {last_name}' created successfully!\n\n"
                        f"📧 Email: {email}\n"
                        f"👤 Username: {username}\n"
                        f"🔑 Role: {role_display}\n"
                        f"🆔 Employee ID: {employee_id}\n"
                        f"🏢 Department: {department_name}\n"
                        f"💼 Designation: {designation_name}\n\n"
                        f"📧 An email with login credentials has been sent to {email}.",
                "user_created": True
            }
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'API call failed'
            return self.format_success(
                f"❌ Failed to create user: {error_msg}\n\n"
                f"Please check the information and try again."
            )

    def _validate_name(self, value):
        """Validate name (only letters, spaces, min 2 chars)"""
        if len(value.strip()) < 2:
            return False, "Name must be at least 2 characters long"
        if not re.match(r'^[a-zA-Z\s]+$', value):
            return False, "Name can only contain letters and spaces"
        return True, None

    def _validate_email(self, value):
        """Validate email format"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            return False, "Invalid email format. Example: john@example.com"
        return True, None

    def _validate_username(self, value):
        """Validate username (letters, numbers, dot, underscore, min 3 chars)"""
        import re
        if len(value) < 3:
            return False, "Username must be at least 3 characters long"
        if not re.match(r'^[a-zA-Z0-9._]+$', value):
            return False, "Username can only contain letters, numbers, dots, and underscores"
        return True, None

    def _validate_role_exists(self, value):
       
        role_id = self._get_role_id(value)
        if not role_id:
            roles = self._get_available_roles()
            role_list = ", ".join(roles)
            return False, f"Role '{value}' not found. Available roles: {role_list}"
        return True, None

    def _validate_department_exists(self, value):
       
        try:
            Department.objects.get(name__iexact=value)
            return True, None
        except Department.DoesNotExist:
            depts = self._get_available_departments()
            dept_list = ", ".join(depts)
            return False, f"Department '{value}' not found. Available departments: {dept_list}"

    def _validate_designation_exists(self, value):
       
        try:
            Designation.objects.get(name__iexact=value)
            return True, None
        except Designation.DoesNotExist:
            desigs = self._get_available_designations()
            desig_list = ", ".join(desigs)
            return False, f"Designation '{value}' not found. Available designations: {desig_list}"

    def _get_question_for_field(self, field):
        
        questions = {
            'first_name': "📝 What is the user's first name?",
            'last_name': "📝 What is the user's last name?",
            'email': "📝 What is the user's email address?\n\nExample: john@example.com",
            'username': "📝 What username should they have?\n\nExample: john.doe",
            'role': f"📝 What role should they have?\n\nAvailable roles: {', '.join(self._get_available_roles())}",
            'department': f"📝 What department are they in?\n\nAvailable departments: {', '.join(self._get_available_departments())}",
            'designation': f"📝 What is their designation?\n\nAvailable designations: {', '.join(self._get_available_designations())}"
        }
        return questions.get(field, f"📝 Please provide the {field}:")
    
    def view_users(self, entities):
        
        if not can_view_user(self.user):
            return self.format_access_denied("users.view_user")
        
        response = self._call_api('/api/users/', method='GET')
        
        print(f"📝 View Users API Response: {response}")
        
        if response and 'results' in response:
            users = response['results']
            if not users:
                return self.format_success("👥 No users found in the system.")
            
            user_list = []
            for user in users[:20]:
                role_display = user.get('role', 'No Role')
                is_active = user.get('is_active', False)
                status_icon = "🟢" if is_active else "⚫"
                full_name = user.get('full_name', user.get('username', 'Unknown'))
                email = user.get('email', 'No email')
                user_list.append(f"{status_icon} {full_name} ({email}) - {role_display}")
            
            message = f"👥 Team Members ({len(users)} total):\n\n"
            message += "\n".join(user_list)
            
            if len(users) > 20:
                message += f"\n\n... and {len(users) - 20} more users"
            
            return self.format_success(message, {"total": len(users)})
        
        elif response and 'users' in response:
            users = response['users']
            if not users:
                return self.format_success("👥 No users found in the system.")
            
            user_list = []
            for user in users[:20]:
                role_display = user.get('role', 'No Role')
                is_active = user.get('is_active', False)
                status_icon = "🟢" if is_active else "⚫"
                full_name = user.get('full_name', user.get('username', 'Unknown'))
                email = user.get('email', 'No email')
                user_list.append(f"{status_icon} {full_name} ({email}) - {role_display}")
            
            message = f"👥 Team Members ({len(users)} total):\n\n" + "\n".join(user_list)
            if len(users) > 20:
                message += f"\n\n... and {len(users) - 20} more users"
            
            return self.format_success(message, {"total": len(users)})
        else:
            return self.format_success("👥 Unable to fetch users at this time.")