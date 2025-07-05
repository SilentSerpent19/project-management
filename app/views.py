from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import CustomAuthenticationForm, CustomUserCreationForm
from django.views.decorators.http import require_POST
from .models import Project, Employee, Task, Comment
from .forms import ProjectForm, TaskForm, CommentForm
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth import update_session_auth_hash


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Role is not set at registration; admin assigns role via Django admin
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def home(request):
    user = request.user
    employee = user.employee

    # Project counts
    if user.is_superuser:
        all_projects = Project.objects.all()
    else:
        all_projects = employee.projects.all()
    active_projects_count = all_projects.filter(status='active').count()

    # Task counts (as before)
    in_progress_count = employee.main_tasks.filter(status='in_progress').count()
    overdue_count = 0
    for task in employee.main_tasks.all():
        if task.due_date and task.due_date < timezone.now().date() and task.status != 'done':
            overdue_count += 1

    # Recent activity: show 5 most recently updated main tasks
    recent_activity = employee.main_tasks.order_by('-updated_at')[:5]

    # Recent projects: 5 most recently created projects assigned to the user
    recent_projects = employee.projects.order_by('-created_at')[:5]

    context = {
        'today': timezone.now().date(),
        'in_progress_count': in_progress_count,
        'overdue_count': overdue_count,
        'active_projects_count': active_projects_count,
        'recent_activity': recent_activity,
        'recent_activity_count': recent_activity.count(),
        'recent_projects': recent_projects,
        # add other project stats as needed
    }
    return render(request, 'home.html', context)

@login_required
def project_list(request):
    user = request.user
    employee = user.employee
    # Superuser sees all projects, others see only assigned
    if user.is_superuser:
        projects = Project.objects.all()
    else:
        projects = employee.projects.all()

    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Apply sorting
    sort_by = request.GET.get('sort', 'name')
    if sort_by == 'created_at':
        projects = projects.order_by('created_at')
    elif sort_by == 'status':
        projects = projects.order_by('status')
    elif sort_by == 'total_tasks':
        projects = projects.order_by('name')
    else:  # default to name
        projects = projects.order_by('name')

    # Group projects by status and calculate stats
    def group_stats(projects_qs):
        total_tasks = sum(p.tasks.count() for p in projects_qs)
        member_ids = set()
        for p in projects_qs:
            member_ids.update(p.employees.values_list('id', flat=True))
        total_members = len(member_ids)
        return total_tasks, total_members

    active_projects = projects.filter(status='active')
    draft_projects = projects.filter(status='draft')
    completed_projects = projects.filter(status='completed')
    archived_projects = projects.filter(status='archived')

    status_groups = [
        {
            'label': 'Active Projects',
            'projects': active_projects,
            'color': 'green',
            'icon': 'fa-bolt',
            'status': 'active',
            'total_tasks': group_stats(active_projects)[0],
            'total_members': group_stats(active_projects)[1],
        },
        {
            'label': 'Draft Projects',
            'projects': draft_projects,
            'color': 'gray',
            'icon': 'fa-pencil-alt',
            'status': 'draft',
            'total_tasks': group_stats(draft_projects)[0],
            'total_members': group_stats(draft_projects)[1],
        },
        {
            'label': 'Completed Projects',
            'projects': completed_projects,
            'color': 'blue',
            'icon': 'fa-check-circle',
            'status': 'completed',
            'total_tasks': group_stats(completed_projects)[0],
            'total_members': group_stats(completed_projects)[1],
        },
        {
            'label': 'Archived Projects',
            'projects': archived_projects,
            'color': 'red',
            'icon': 'fa-archive',
            'status': 'archived',
            'total_tasks': group_stats(archived_projects)[0],
            'total_members': group_stats(archived_projects)[1],
        },
    ]
    # Add a flag to indicate if there are any projects in any group
    has_projects = any(group['projects'].exists() for group in status_groups)
    context = {
        'status_groups': status_groups,
        'search_query': search_query,
        'has_projects': has_projects,
    }
    return render(request, 'project_list.html', context)

@login_required
def project_create(request):
    user = request.user
    if not (user.role == 'pm' or user.is_superuser):
        return HttpResponseForbidden('You do not have permission to create projects.')
    employee = user.employee
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            # Ensure the PM is always assigned to the project
            if employee not in project.employees.all():
                project.employees.add(employee)
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('project_list')
    else:
        form = ProjectForm()
    return render(request, 'project_form.html', {'form': form})

@login_required
def project_edit(request, pk):
    user = request.user
    project = get_object_or_404(Project, pk=pk)
    employee = user.employee
    if not (user.is_superuser or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to edit this project.')
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated successfully!')
            return redirect('project_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'project_form.html', {'form': form, 'edit': True})

@login_required
def project_delete(request, pk):
    user = request.user
    project = get_object_or_404(Project, pk=pk)
    employee = user.employee
    if not (user.is_superuser or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to delete this project.')
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('project_list')
    return render(request, 'project_confirm_delete.html', {'project': project})

@login_required
def task_list(request, project_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    # Only allow access if the user is assigned to the project, or is superuser
    if not (user.is_superuser or employee in project.employees.all()):
        return HttpResponseForbidden('You do not have access to this project.')
    if user.is_superuser or user.role == 'pm':
        tasks = project.tasks.all()
    elif user.role == 'dev':
        tasks = project.tasks.filter(
            Q(main_employee=employee) | Q(pair_employee=employee)
        )
    else:
        tasks = project.tasks.none()
    
    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        tasks = tasks.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    # Apply priority filter
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Apply assignee filter
    assignee_filter = request.GET.get('assignee', '')
    if assignee_filter:
        tasks = tasks.filter(
            Q(main_employee__user__username__icontains=assignee_filter) |
            Q(pair_employee__user__username__icontains=assignee_filter)
        )
    
    # Calculate statistics
    total_tasks = tasks.count()
    todo_count = tasks.filter(status='todo').count()
    in_progress_count = tasks.filter(status='in_progress').count()
    done_count = tasks.filter(status='done').count()
    
    # Calculate overdue tasks
    overdue_count = 0
    for task in tasks:
        if task.due_date and task.due_date < timezone.now().date() and task.status != 'done':
            overdue_count += 1
    
    context = {
        'project': project,
        'tasks': tasks,
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'assignee_filter': assignee_filter,
        'total_tasks': total_tasks,
        'todo_count': todo_count,
        'in_progress_count': in_progress_count,
        'done_count': done_count,
        'overdue_count': overdue_count,
    }
    return render(request, 'task_list.html', context)

@login_required
def task_create(request, project_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    # Only allow PMs assigned to the project or superuser to create tasks
    if not (user.is_superuser or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to create tasks in this project.')
    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, f'Task "{task.name}" created successfully!')
            return redirect('task_list', project_pk=project.pk)
    else:
        form = TaskForm(project=project)
    return render(request, 'task_form.html', {'form': form, 'project': project})

@login_required
def task_edit(request, project_pk, task_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    # Only allow PMs assigned to the project or superuser to edit tasks
    if not (user.is_superuser or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to edit this task.')
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, project=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Task "{task.name}" updated successfully!')
            return redirect('task_list', project_pk=project.pk)
    else:
        form = TaskForm(instance=task, project=project)
    return render(request, 'task_form.html', {'form': form, 'project': project, 'edit': True})

@login_required
def comment_list(request, project_pk, task_pk):
    user = request.user
    employee, created = Employee.objects.get_or_create(user=user)
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if not (user.is_superuser or employee in project.employees.all()):
        return HttpResponseForbidden('You do not have access to this task.')
    comments = task.comments.all().order_by('created_at')
    comment_form = CommentForm()
    
    # Add debugging info
    print(f"Task: {task.name}")
    print(f"Comments count: {comments.count()}")
    for comment in comments:
        print(f"Comment: {comment.content} by {comment.employee.user.username}")
    
    return render(request, 'comment_list.html', {
        'project': project, 
        'task': task, 
        'comments': comments,
        'comment_form': comment_form
    })

@login_required
def comment_create(request, project_pk, task_pk):
    user = request.user
    employee, created = Employee.objects.get_or_create(user=user)
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if not (user.is_superuser or employee in project.employees.all()):
        return HttpResponseForbidden('You do not have access to comment on this task.')
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.employee = employee
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('comment_list', project_pk=project.pk, task_pk=task.pk)
        else:
            # Add error message for debugging
            messages.error(request, f'Form errors: {form.errors}')
    else:
        form = CommentForm()
    return render(request, 'comment_form.html', {'form': form, 'project': project, 'task': task})

@login_required
def comment_edit(request, project_pk, task_pk, comment_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    comment = get_object_or_404(task.comments, pk=comment_pk)
    if not (user.is_superuser or employee == comment.employee or (user.role == 'pm' and employee in project.employees.all())):
        return HttpResponseForbidden('You do not have permission to edit this comment.')
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Comment updated successfully!')
            return redirect('comment_list', project_pk=project.pk, task_pk=task.pk)
    else:
        form = CommentForm(instance=comment)
    return render(request, 'comment_form.html', {'form': form, 'project': project, 'task': task, 'edit': True})

@login_required
def comment_delete(request, project_pk, task_pk, comment_pk):
    user = request.user
    comment = get_object_or_404(Comment, pk=comment_pk, task__pk=task_pk, task__project__pk=project_pk)
    # Only the comment author, a project manager assigned, or superuser can delete
    if not (user.is_superuser or comment.employee.user == user or (user.role == 'pm')):
        return HttpResponseForbidden('You do not have permission to delete this comment.')
    if request.method == 'POST':
        comment.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('comment_list', project_pk=project_pk, task_pk=task_pk)
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk)
    return render(request, 'comment_confirm_delete.html', {'comment': comment, 'project': project, 'task': task})

@login_required
def my_tasks(request):
    employee = request.user.employee
    # Active/draft tasks
    active_statuses = ['active', 'draft']
    main_tasks = Task.objects.filter(main_employee=employee, project__status__in=active_statuses)
    pair_tasks = Task.objects.filter(pair_employee=employee, project__status__in=active_statuses).exclude(main_employee=employee)
    # Completed/archived tasks
    completed_statuses = ['completed', 'archived']
    main_tasks_completed = Task.objects.filter(main_employee=employee, project__status__in=completed_statuses)
    pair_tasks_completed = Task.objects.filter(pair_employee=employee, project__status__in=completed_statuses).exclude(main_employee=employee)
    return render(request, 'my_tasks.html', {
        'main_tasks': main_tasks,
        'pair_tasks': pair_tasks,
        'main_tasks_completed': main_tasks_completed,
        'pair_tasks_completed': pair_tasks_completed,
    })

@login_required
def update_task_status(request, project_pk, task_pk):
    user = request.user
    employee = user.employee
    project = get_object_or_404(Project, pk=project_pk)
    task = get_object_or_404(Task, pk=task_pk, project=project)
    if not (user.is_superuser or (user.role == 'pm' and employee in project.employees.all())):
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status not in ['todo', 'in_progress', 'done', 'blocked']:
            return JsonResponse({'error': 'Invalid status.'}, status=400)
        task.status = new_status
        task.save()
        return JsonResponse({'success': True, 'status': new_status})
    return JsonResponse({'error': 'Invalid request.'}, status=400)

@login_required
def project_list_by_status(request, status):
    user = request.user
    employee = user.employee
    # Superuser sees all projects, others see only assigned
    if user.is_superuser:
        projects = Project.objects.filter(status=status)
    else:
        projects = employee.projects.filter(status=status)

    # Apply search filter
    search_query = request.GET.get('search', '')
    if search_query:
        projects = projects.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Smarter sort options
    sort_by = request.GET.get('sort', 'name_asc')
    if sort_by == 'name_asc':
        projects = projects.order_by('name')
    elif sort_by == 'name_desc':
        projects = projects.order_by('-name')
    elif sort_by == 'created_newest':
        projects = projects.order_by('-created_at')
    elif sort_by == 'created_oldest':
        projects = projects.order_by('created_at')
    elif sort_by == 'tasks_most':
        projects = sorted(projects, key=lambda p: p.tasks.count(), reverse=True)
    elif sort_by == 'tasks_least':
        projects = sorted(projects, key=lambda p: p.tasks.count())
    elif sort_by == 'members_most':
        projects = sorted(projects, key=lambda p: p.employees.count(), reverse=True)
    elif sort_by == 'members_least':
        projects = sorted(projects, key=lambda p: p.employees.count())
    else:
        projects = projects.order_by('name')

    # Get status display name and color
    status_choices = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived")
    ]
    status_display = dict(status_choices).get(status, status.title())
    status_colors = {
        'active': 'green',
        'draft': 'gray', 
        'completed': 'blue',
        'archived': 'red'
    }
    status_color = status_colors.get(status, 'gray')

    context = {
        'projects': projects,
        'status': status,
        'status_display': status_display,
        'status_color': status_color,
        'search_query': search_query,
        'sort_by': sort_by,
        'filtered_count': len(projects) if isinstance(projects, list) else projects.count(),
        'total_count': Project.objects.filter(status=status).count() if not user.is_superuser else Project.objects.filter(status=status).count(),
    }
    return render(request, 'project_list_by_status.html', context)

@login_required
def activity_log(request):
    try:
        user = request.user
        
        # Refresh session to prevent timeout
        update_session_auth_hash(request, user)
        
        employee = user.employee
        
        # Get all main tasks for the user, ordered by most recent updates
        activities = employee.main_tasks.order_by('-updated_at')
        
        # Apply search filter
        search_query = request.GET.get('search', '').strip()
        if search_query:
            activities = activities.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(project__name__icontains=search_query)
            )
        
        # Apply project filter
        project_filter = request.GET.get('project', '').strip()
        if project_filter and project_filter.isdigit():
            activities = activities.filter(project_id=int(project_filter))
        
        # Apply status filter
        status_filter = request.GET.get('status', '').strip()
        if status_filter in ['todo', 'in_progress', 'done', 'blocked']:
            activities = activities.filter(status=status_filter)
        
        # Apply date filter with proper timezone handling
        date_filter = request.GET.get('date', '').strip()
        if date_filter == 'today':
            activities = activities.filter(updated_at__date=timezone.now().date())
        elif date_filter == 'week':
            week_ago = timezone.now() - timezone.timedelta(days=7)
            activities = activities.filter(updated_at__gte=week_ago)
        elif date_filter == 'month':
            month_ago = timezone.now() - timezone.timedelta(days=30)
            activities = activities.filter(updated_at__gte=month_ago)
        
        # Pagination
        paginator = Paginator(activities, 20)  # 20 activities per page
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.get_page(page_number)
        except (ValueError, TypeError):
            page_obj = paginator.get_page(1)
        
        # Get available projects for filter dropdown
        available_projects = employee.projects.all().order_by('name')
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'project_filter': project_filter,
            'status_filter': status_filter,
            'date_filter': date_filter,
            'available_projects': available_projects,
            'total_activities': activities.count(),
        }
        return render(request, 'activity_log.html', context)
        
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in activity_log view: {str(e)}")
        
        # Return a safe error response
        messages.error(request, 'An error occurred while loading the activity log. Please try again.')
        return redirect('home')


