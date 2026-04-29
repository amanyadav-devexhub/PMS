from django.contrib import admin
from .models import Department, Designation, Role, User, UserProfile, UserPermissionOverride


admin.site.register(User)
admin.site.register(Department)
admin.site.register(Designation)
admin.site.register(UserProfile)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('permissions',)


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission', 'is_granted', 'granted_by', 'granted_at')
    list_filter = ('is_granted',)
    search_fields = ('user__username', 'user__email', 'permission')
    readonly_fields = ('granted_at',)
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)