from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta

from .decorators import user_required
from .forms import BorrowRequestForm, LoginForm, ProfileUpdateForm, UserRegistrationForm
from dashboard.models import BorrowRequest, Equipment


OPEN_BORROW_REQUEST_STATUSES = ['pending', 'approved', 'return_pending', 'returned']


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard:overview')
        return redirect('user-dashboard')

    login_form = LoginForm(request=request)
    register_form = UserRegistrationForm()
    active_panel = 'login'

    if request.method == 'POST':
        action = request.POST.get('action', 'login')

        if action == 'register':
            register_form = UserRegistrationForm(request.POST)
            login_form = LoginForm(request=request)
            active_panel = 'register'

            if register_form.is_valid():
                with transaction.atomic():
                    register_form.save()
                messages.success(request, 'Registration successful. You can now sign in with your new account.')
                return redirect('login')
        else:
            login_form = LoginForm(request=request, data=request.POST)
            register_form = UserRegistrationForm()
            active_panel = 'login'

            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                if user.is_staff or user.is_superuser:
                    return redirect('/dashboard/')
                return redirect('/user/dashboard/')

    return render(
        request,
        'registration/login.html',
        {
            'form': login_form,
            'register_form': register_form,
            'active_panel': active_panel,
        },
    )


def logout_view(request):
    logout(request)
    return redirect('login')


@user_required
def user_dashboard(request, section='dashboard'):
    allowed_sections = {'dashboard', 'equipment', 'history', 'profile'}
    if section not in allowed_sections:
        return redirect('user-dashboard')

    member = getattr(request.user, 'member', None)
    today = timezone.localdate()
    user_requests = (
        BorrowRequest.objects
        .filter(user=request.user)
        .select_related('equipment')
        .order_by('-created_at')
    )

    history_requests = list(user_requests)
    for borrow_request in history_requests:
        borrow_request.days_remaining = (borrow_request.expected_return_date - today).days

    existing_request_equipment_ids = [
        borrow_request.equipment_id
        for borrow_request in history_requests
        if borrow_request.status in OPEN_BORROW_REQUEST_STATUSES
    ]

    equipment_list = Equipment.objects.order_by('name')
    equipment_query = request.GET.get('q', '').strip()
    selected_category = request.GET.get('category', '').strip()
    equipment_categories = (
        Equipment.objects
        .exclude(category='')
        .order_by('category')
        .values_list('category', flat=True)
        .distinct()
    )

    if equipment_query:
        equipment_list = equipment_list.filter(
            Q(name__icontains=equipment_query)
            | Q(category__icontains=equipment_query)
            | Q(serial_number__icontains=equipment_query)
            | Q(condition__icontains=equipment_query)
        )
    if selected_category:
        equipment_list = equipment_list.filter(category=selected_category)

    context = {
        'member': member,
        'section': section,
        'equipment_list': equipment_list,
        'equipment_query': equipment_query,
        'equipment_categories': equipment_categories,
        'selected_category': selected_category,
        'existing_request_equipment_ids': existing_request_equipment_ids,
        'borrow_requests': history_requests,
        'recent_requests': history_requests[:5],
        'borrow_form': BorrowRequestForm(),
        'profile_form': ProfileUpdateForm(instance=request.user),
        'total_requests': len(history_requests),
        'approved_requests': sum(1 for item in history_requests if item.status == 'approved'),
        'pending_requests': sum(1 for item in history_requests if item.status == 'pending'),
        'currently_borrowed': sum(1 for item in history_requests if item.status == 'approved'),
        'today': today,
    }
    return render(request, 'user_dashboard.html', context)


@user_required
@require_POST
def borrow_equipment(request, equipment_id):
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    form = BorrowRequestForm(request.POST, equipment=equipment)

    if not form.is_valid():
        for error in form.errors.values():
            messages.error(request, error[0])
        return redirect('user-equipment')

    with transaction.atomic():
        equipment = Equipment.objects.select_for_update().get(pk=equipment_id)
        if equipment.status != 'available':
            messages.error(request, f'{equipment.name} is not available for borrowing right now.')
            return redirect('user-equipment')

        has_existing_request = BorrowRequest.objects.select_for_update().filter(
            user=request.user,
            equipment=equipment,
            status__in=OPEN_BORROW_REQUEST_STATUSES,
        ).exists()
        if has_existing_request:
            messages.warning(request, f'You already have a request for {equipment.name}.')
            return redirect('user-equipment')

        today = timezone.localdate()
        duration_days = form.cleaned_data['duration_days']
        BorrowRequest.objects.create(
            user=request.user,
            equipment=equipment,
            full_name=form.cleaned_data['full_name'],
            student_id=form.cleaned_data['student_id'],
            faculty_department=form.cleaned_data['faculty_department'],
            email=form.cleaned_data['email'],
            phone_number=form.cleaned_data['phone_number'],
            purpose=form.cleaned_data['purpose'],
            borrow_date=today,
            duration_days=duration_days,
            expected_return_date=today + timedelta(days=duration_days),
            status='pending',
        )

    messages.success(request, f'Borrow request for {equipment.name} was submitted.')
    return redirect('user-history')


@user_required
@require_POST
def request_return(request, request_id):
    borrow_request = get_object_or_404(
        BorrowRequest.objects.select_related('equipment'),
        pk=request_id,
        user=request.user,
    )

    if borrow_request.status != 'approved':
        messages.warning(request, 'Only approved borrowed items can be returned.')
        return redirect('user-history')

    borrow_request.status = 'return_pending'
    borrow_request.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Return request for {borrow_request.equipment.name} was submitted.')
    return redirect('user-history')


@user_required
@require_POST
def update_profile(request):
    form = ProfileUpdateForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, 'Your profile was updated.')
    else:
        for error in form.errors.values():
            messages.error(request, error[0])
    return redirect('user-profile')
