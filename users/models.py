from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser,Permission  


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='roles'
    )

    def __str__(self):
        return self.name
    

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('TEAM_LEAD', 'Team Lead'),
        ('EMPLOYEE', 'Employee'),
    )
    role = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(unique=True)
    role_obj = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    preferred_name = models.CharField(max_length=100, blank=True, null=True, help_text="Name user prefers to be called by AI assistant")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if self.role_obj:
            self.role = self.role_obj.name
        elif self.role:
            try:
                self.role_obj = Role.objects.get(name=self.role)
            except Role.DoesNotExist:
                self.role_obj = None
        super().save(*args, **kwargs)

    def has_perm(self, perm, obj=None):
        """
        Check if user has a permission.
        
        Priority Order (HIGHEST to LOWEST):
            1. Superuser → Always True
            2. Role-based permission → Baseline access
            3. User-specific override → Exception (can GRANT or DENY)
        
        How it works:
            - First, check if user is superuser → Always allow
            - Then, check if role has this permission (baseline)
            - Then, check if there's a user-specific override
                - If override.is_granted = True → Allow (even if role didn't have it)
                - If override.is_granted = False → Deny (even if role had it)
            - If no override, return the role permission result
        """
        # 1. SUPERUSER - Always allow
        if self.is_active and self.is_superuser:
            return True
        
        # 2. CHECK ROLE-BASED PERMISSION FIRST (Baseline)
        has_role_permission = False
        
        # Check ADMIN role (legacy support)
        if self.is_active and self.role == 'ADMIN':
            has_role_permission = True
        else:
            # Check Django's default permissions
            if super().has_perm(perm, obj=obj):
                has_role_permission = True
            # Check role_obj permissions
            elif self.role_obj:
                try:
                    app_label, codename = perm.split('.', 1)
                except ValueError:
                    has_role_permission = False
                else:
                    has_role_permission = self.role_obj.permissions.filter(
                        content_type__app_label=app_label,
                        codename=codename
                    ).exists()
        
        # 3. CHECK USER-SPECIFIC OVERRIDE (Exception)
        try:
            from .models import UserPermissionOverride
            override = UserPermissionOverride.objects.get(user=self, permission=perm)
            
            if override.is_granted:
                # GRANT override → Allow (even if role didn't have it)
                return True
            else:
                # DENY override → Block (even if role had it)
                return False
        except UserPermissionOverride.DoesNotExist:
            # No override, use role permission result
            return has_role_permission
        

    def has_module_perms(self, app_label):
            if self.is_active and (self.is_superuser or self.role == 'ADMIN'):
                return True
            if super().has_module_perms(app_label):
                return True
            if self.role_obj:
                return self.role_obj.permissions.filter(
                    content_type__app_label=app_label
                ).exists()
            return False
        

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    employee_id = models.CharField(max_length=20, unique=True, null=False, blank=False)
    phone = models.CharField(max_length=15, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)

    ctc = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    salary_in_hand = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_no = models.CharField(max_length=50, null=True, blank=True)
    ifsc = models.CharField(max_length=20, null=True, blank=True)

    aadhar_no = models.CharField(max_length=20, null=True, blank=True)
    pan_no = models.CharField(max_length=20, null=True, blank=True)

    emergency_contact = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"
    


class ActivityLog(models.Model):
        ACTION_CHOICES = (
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('deleted', 'Deleted'),
            ('restored', 'Restored'),
        )
        
        ENTITY_CHOICES = (
            ('project', 'Project'),
            ('task', 'Task'),
        )
        
        user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='activities')
        action = models.CharField(max_length=20, choices=ACTION_CHOICES)
        entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES)
        entity_id = models.PositiveIntegerField()
        entity_name = models.CharField(max_length=255, blank=True, null=True)
        old_value = models.TextField(blank=True, null=True)
        new_value = models.TextField(blank=True, null=True)
        ip_address = models.GenericIPAddressField(blank=True, null=True)
        timestamp = models.DateTimeField(auto_now_add=True)
        
        def __str__(self):
            return f"{self.user} {self.action} {self.entity_type} #{self.entity_id} at {self.timestamp}"
        
        class Meta:
            ordering = ['-timestamp']



    

# ============================================================================
# USER PERMISSION OVERRIDE MODEL
# ============================================================================

class UserPermissionOverride(models.Model):
    """
    User-specific permission overrides that take precedence over role-based permissions.
    
    Priority Order:
        1. Superuser → Always allowed
        2. Role-based permission → Baseline access
        3. UserPermissionOverride → Exception (GRANT or DENY)
    
    Usage Examples:
        - Grant 'users.add_user' to a specific Team Lead
        - Deny 'Tasks.view_all_tasks' from a specific Employee
        - Grant 'projects.delete_projects' to a specific Project Manager
    """
    
    # Which user gets this override
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permission_overrides'
    )
    
    # Which permission (e.g., 'users.add_user', 'projects.delete_projects')
    # Uses string instead of ForeignKey to Permission for simplicity and speed
    permission = models.CharField(max_length=100)
    
    # True = GRANT the permission (user gets it even if role doesn't have it)
    # False = DENY the permission (user loses it even if role has it)
    is_granted = models.BooleanField(default=True)
    
    # Who created this override (audit trail)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_overrides'
    )
    
    # When was this override created (auto-set on creation)
    granted_at = models.DateTimeField(auto_now_add=True)
    
    # Optional reason/documentation for why this override was given
    reason = models.TextField(blank=True, null=True)
    
    class Meta:
        # A user can have only ONE override per permission
        unique_together = ['user', 'permission']
        
        # Index for faster lookups when checking permissions
        indexes = [
            models.Index(fields=['user', 'permission']),
        ]
        
        # Order by most recent first
        ordering = ['-granted_at']
    
    def __str__(self):
        action = "GRANTED" if self.is_granted else "DENIED"
        granted_by_name = self.granted_by.username if self.granted_by else 'System'
        return f"{self.user.username}: {self.permission} → {action} (by {granted_by_name})"
    
    # @property
    # def permission_display(self):
    #     """Returns human-readable permission name from Django's Permission model"""
    #     try:
    #         from django.contrib.auth.models import Permission
    #         app_label, codename = self.permission.split('.', 1)
    #         perm = Permission.objects.get(
    #             content_type__app_label=app_label,
    #             codename=codename
    #         )
    #         return perm.name  # Django already has a 'name' field for each permission
    #     except Exception:
    #         return self.permission