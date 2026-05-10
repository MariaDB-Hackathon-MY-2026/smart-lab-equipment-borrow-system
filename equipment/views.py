from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from accounts.services.profile_service import ProfileService
from equipment.models import Equipment
from equipment.services.equipment_service import EquipmentService
from lending.models import LendingRequest, Penalty
from lending.services.lending_service import LendingService


equipment_service = EquipmentService()
profile_service = ProfileService()
lending_service = LendingService()


def admin_required(user):
    return profile_service.is_admin(user)


@login_required
def available_equipment(request):
    active_equipment_ids = list(lending_service.active_equipment_ids())
    equipments = list(
        equipment_service.attach_category_icons(
            equipment_service.list_available_equipment().exclude(id__in=active_equipment_ids)
        )
    )
    category_groups_by_id = {}
    for equipment in equipments:
        category_id = equipment.category_id
        if category_id not in category_groups_by_id:
            category_groups_by_id[category_id] = {
                'id': category_id,
                'name': equipment.category.name,
                'icon_class': equipment.category_icon_class,
                'equipments': [],
            }
        category_groups_by_id[category_id]['equipments'].append(equipment)

    user_requests = lending_service.list_user_requests(request.user)
    penalties = lending_service.list_penalties_for_user(request.user)
    unpaid_penalties = penalties.filter(status=Penalty.STATUS_UNPAID).count()
    return render(request, 'equipment/user_equipment_list.html', {
        'equipments': equipments,
        'category_groups': category_groups_by_id.values(),
        'requests': user_requests,
        'recent_requests': user_requests[:6],
        'penalties': penalties,
        'active_requests': user_requests.exclude(status__in=[
            LendingRequest.STATUS_RETURNED,
            LendingRequest.STATUS_DENIED,
        ]).count(),
        'pending_requests': user_requests.filter(status=LendingRequest.STATUS_PENDING).count(),
        'unpaid_penalties': unpaid_penalties,
        'can_borrow': unpaid_penalties == 0,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
@user_passes_test(admin_required)
def manifest(request):
    equipments = equipment_service.attach_category_icons(equipment_service.list_active_equipment())
    return render(request, 'equipment/manifest.html', {
        'equipments': equipments,
        'categories': equipment_service.list_categories(),
        'category_options': equipment_service.list_category_options(),
        'condition_options': equipment_service.CONDITION_CHOICES,
        'statuses': Equipment.STATUS_CHOICES,
    })


@login_required
@user_passes_test(admin_required)
@require_http_methods(['GET', 'POST'])
def create_equipment(request):
    if request.method == 'POST':
        try:
            equipment_service.create_equipment(request.POST)
            messages.success(request, 'Equipment record created successfully.')
            return redirect('equipment:manifest')
        except ValueError as exc:
            messages.error(request, str(exc))
            if request.POST.get('source') == 'manifest_modal':
                return redirect('equipment:manifest')
    return render(request, 'equipment/form.html', {
        'equipment': request.POST if request.method == 'POST' else None,
        'category_options': equipment_service.list_category_options(),
        'condition_options': equipment_service.CONDITION_CHOICES,
        'statuses': Equipment.STATUS_CHOICES,
        'mode': 'Create',
    })


@login_required
@user_passes_test(admin_required)
@require_http_methods(['GET', 'POST'])
def edit_equipment(request, equipment_id):
    equipment = equipment_service.get_equipment(equipment_id)
    if request.method == 'POST':
        try:
            equipment = equipment_service.update_equipment(equipment_id, request.POST)
            messages.success(request, 'Equipment record updated successfully.')
            return redirect('equipment:manifest')
        except ValueError as exc:
            messages.error(request, str(exc))
            equipment = request.POST
    return render(request, 'equipment/form.html', {
        'equipment': equipment,
        'category_options': equipment_service.list_category_options(),
        'condition_options': equipment_service.CONDITION_CHOICES,
        'statuses': Equipment.STATUS_CHOICES,
        'mode': 'Edit',
    })


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def delete_equipment(request, equipment_id):
    try:
        equipment_service.soft_delete_equipment(equipment_id)
        messages.success(request, 'Equipment record soft deleted successfully.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('equipment:manifest')


@require_http_methods(['POST'])
def manage_category(request):
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': 'Your session has expired. Please log in again.'}, status=401)
        return redirect('accounts:login')

    if not admin_required(request.user):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': 'You do not have permission to manage categories.'}, status=403)
        messages.error(request, 'You do not have permission to manage categories.')
        return redirect('equipment:manifest')

    action = request.POST.get('action')
    try:
        if action == 'create':
            equipment_service.create_category(
                request.POST.get('name', ''),
                request.POST.get('description', ''),
            )
        elif action == 'update':
            equipment_service.update_category(
                request.POST.get('category_id'),
                request.POST.get('name', ''),
                request.POST.get('description', ''),
            )
        elif action == 'delete':
            equipment_service.soft_delete_category(request.POST.get('category_id'))
        else:
            messages.error(request, 'No category action selected.')
    except ValueError as exc:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': str(exc)}, status=400)
        messages.error(request, str(exc))
        return redirect('equipment:manifest')
    except Exception as exc:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': f'Category action failed: {exc}'}, status=500)
        messages.error(request, 'Category action failed. Please try again.')
        return redirect('equipment:manifest')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        categories = list(equipment_service.list_categories().values('id', 'name'))
        return JsonResponse({
            'ok': True,
            'message': 'Category action completed successfully.',
            'categories': categories,
        })
    return redirect('equipment:manifest')

# Create your views here.
