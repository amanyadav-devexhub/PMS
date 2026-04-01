from django.contrib import admin

# Register your models here.
from .models import Department, Designation, Role, User, UserProfile


admin.site.register(User)
admin.site.register(Department)
admin.site.register(Designation)
admin.site.register(UserProfile)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ('name',)
	filter_horizontal = ('permissions',)