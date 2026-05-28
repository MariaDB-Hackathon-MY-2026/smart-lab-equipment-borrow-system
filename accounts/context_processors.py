from accounts.services.profile_service import ProfileService


def portal_role(request):
    service = ProfileService()
    return {
        'is_portal_admin': service.is_admin(request.user),
    }
