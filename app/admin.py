from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from app.models import CustomUser, Employee, Project, Task, Comment, SyncLog

admin.site.register(SyncLog)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'display_role', 'is_superuser_flag')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role',)}),
    )

    def display_role(self, obj):
        return obj.get_role_display()
    display_role.short_description = 'Role'

    def is_superuser_flag(self, obj):
        return obj.is_superuser
    is_superuser_flag.boolean = True  # Shows as a checkmark in admin
    is_superuser_flag.short_description = 'Superuser'

@admin.register(Comment)
class Comment(admin.ModelAdmin):
    list_display = ('task', 'employee', 'content')

@admin.register(Employee)
class Employee(admin.ModelAdmin):
    list_display = ('user', 'is_active')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description')
    actions = ['mark_as_completed']
    filter_horizontal = ('employees',)

    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} project(s) marked as completed.')
    mark_as_completed.short_description = 'Mark selected projects as completed'

@admin.register(Task)
class Task(admin.ModelAdmin):
    list_display = ('project', 'main_employee', 'pair_employee', 'name', 'status', 'priority')

