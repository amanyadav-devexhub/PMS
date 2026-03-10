from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser   ## Abstractuser -- it is a built in class in django which is used to create custom user model

# Create your models here.
class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN','Admin'),
        ('TEAM_LEAD','Team Lead'),
        ('EMPLOYEE','Employee'),
    )
    role = models.CharField(max_length=20,choices=ROLE_CHOICES)
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    


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
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
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