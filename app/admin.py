from django.contrib import admin
from app.models import CustomUser, Employee, Project, Task, Comment, SyncLog

admin.site.register(SyncLog)

@admin.register(CustomUser)
class CustomUser(admin.ModelAdmin):
    list_display= ('username', 'role')


@admin.register(Comment)
class Comment(admin.ModelAdmin):
    list_display = ('task', 'employee', 'content')

@admin.register(Employee)
class Employee(admin.ModelAdmin):
    list_display = ('user', 'is_active')

@admin.register(Project)
class Project(admin.ModelAdmin):
    list_display = ('name', 'status')

@admin.register(Task)
class Task(admin.ModelAdmin):
    list_display = ('project', 'main_employee', 'pair_employee', 'name', 'status', 'priority')

