from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser,Permission   ## Abstractuser -- it is a built in class in django which is used to create custom user model

## Role and Permission management
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='roles'
    )

    def __str__(self):
        return self.name
    
# Create your models here.
class User(AbstractUser):
    # ✅ Add ROLE_CHOICES here
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
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        # Keep role text and role object in sync for backward compatibility.
        if self.role_obj:
            self.role = self.role_obj.name
        elif self.role:
            try:
                self.role_obj = Role.objects.get(name=self.role)
            except Role.DoesNotExist:
                self.role_obj = None
        super().save(*args, **kwargs)

    def has_perm(self, perm, obj=None):
        if self.is_active and (self.is_superuser or self.role == 'ADMIN'):
            return True
        if super().has_perm(perm, obj=obj):
            return True
        if self.role_obj:
            try:
                app_label, codename = perm.split('.', 1)
            except ValueError:
                return False
            return self.role_obj.permissions.filter(
                content_type__app_label=app_label,
                codename=codename
            ).exists()
        return False
    
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
    


## for department and designation tab
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
    ## basic details
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    employee_id = models.CharField(max_length=20, unique=True, null=False, blank=False)
    phone = models.CharField(max_length=15, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)

    ## Salary details
    ctc = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    salary_in_hand = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    ## Bank details
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_no = models.CharField(max_length=50, null=True, blank=True)
    ifsc = models.CharField(max_length=20, null=True, blank=True)

    ## Verification
    aadhar_no = models.CharField(max_length=20, null=True, blank=True)
    pan_no = models.CharField(max_length=20, null=True, blank=True)

    # Additional
    emergency_contact = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"