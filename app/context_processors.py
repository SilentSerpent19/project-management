from django.utils import timezone
from .models import Task

def recent_activity_processor(request):
    """
    Context processor to add recent activity data to all templates.
    This allows the notification bell to show activity on all pages.
    """
    if request.user.is_authenticated:
        try:
            employee = request.user.employee
            recent_activity = employee.main_tasks.order_by('-updated_at')[:5]
            return {
                'recent_activity': recent_activity,
                'recent_activity_count': recent_activity.count(),
            }
        except:
            # If there's any error (e.g., no employee record), return empty data
            return {
                'recent_activity': [],
                'recent_activity_count': 0,
            }
    else:
        return {
            'recent_activity': [],
            'recent_activity_count': 0,
        } 