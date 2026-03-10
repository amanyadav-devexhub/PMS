from django.contrib import admin

# Register your models here.
from .models import Department, Designation, UserProfile, User


admin.site.register(User)
admin.site.register(Department)
admin.site.register(Designation)