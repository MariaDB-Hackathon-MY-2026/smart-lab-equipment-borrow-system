from django.contrib.auth.decorators import login_required, user_passes_test
from accounts.services.profile_service import ProfileService
from analytics.services.analytics_service import AnalyticsService
from django.shortcuts import render


profile_service = ProfileService()
analytics_service = AnalyticsService()


def admin_required(user):
    return profile_service.is_admin(user)


@login_required
@user_passes_test(admin_required)
def analytics_dashboard(request):
    context = {
        'stats': analytics_service.dashboard_stats(),
        'request_status_counts': analytics_service.request_status_counts(),
        'equipment_status_counts': analytics_service.equipment_status_counts(),
    }
    return render(request, 'analytics/dashboard.html', context)

# Create your views here.
