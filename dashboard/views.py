from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import date, timedelta
import calendar

from lendr_project.decorators import admin_required

from .forms import EquipmentForm
from .models import Equipment, Borrow, BorrowRequest


def add_weekdays(start_date, weekdays):
    current_date = start_date
    remaining = weekdays

    while remaining:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:
            remaining -= 1

    return current_date


def _append_note(borrow, note):
    if borrow.notes:
        borrow.notes = f'{borrow.notes}\n{note}'
    else:
        borrow.notes = note


def _equipment_queryset(request):
    equipment = Equipment.objects.order_by('name')
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        equipment = equipment.filter(
            Q(name__icontains=query)
            | Q(category__icontains=query)
            | Q(serial_number__icontains=query)
        )
    if status:
        equipment = equipment.filter(status=status)

    return equipment, query, status


def _borrowing_queryset(request):
    borrowings = (
        Borrow.objects
        .select_related('member__user', 'equipment')
        .order_by('-borrow_date', '-created_at')
    )
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        borrowings = borrowings.filter(
            Q(member__user__first_name__icontains=query)
            | Q(member__user__last_name__icontains=query)
            | Q(member__user__username__icontains=query)
            | Q(member__member_id__icontains=query)
            | Q(equipment__name__icontains=query)
            | Q(equipment__category__icontains=query)
            | Q(equipment__serial_number__icontains=query)
        )
    if status:
        borrowings = borrowings.filter(status=status)

    return borrowings, query, status


def _overdue_queryset(request):
    today = date.today()
    overdue = (
        Borrow.objects
        .select_related('member__user', 'equipment')
        .filter(
            Q(status='Overdue')
            | (
                Q(due_date__lt=today)
                & ~Q(status__in=['Returned', 'Rejected'])
            )
        )
        .order_by('due_date', '-created_at')
    )
    query = request.GET.get('q', '').strip()

    if query:
        overdue = overdue.filter(
            Q(member__user__first_name__icontains=query)
            | Q(member__user__last_name__icontains=query)
            | Q(member__user__username__icontains=query)
            | Q(member__member_id__icontains=query)
            | Q(equipment__name__icontains=query)
            | Q(equipment__category__icontains=query)
            | Q(equipment__serial_number__icontains=query)
        )

    return overdue, query, today


@admin_required
def equipment_management(request):
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            equipment = form.save()
            messages.success(request, f'{equipment.name} was added to the equipment inventory.')
            return redirect('dashboard:equipment_management')
    else:
        form = EquipmentForm()

    equipment, query, status = _equipment_queryset(request)
    context = {
        'equipment': equipment,
        'form': form,
        'editing_equipment': None,
        'query': query,
        'selected_status': status,
        'status_choices': Equipment.STATUS_CHOICES,
        'total_equipment': Equipment.objects.count(),
        'available_count': Equipment.objects.filter(status='available').count(),
        'borrowed_count': Equipment.objects.filter(status='borrowed').count(),
        'maintenance_count': Equipment.objects.filter(status='maintenance').count(),
        'retired_count': Equipment.objects.filter(status='retired').count(),
    }
    return render(request, 'equipment_management.html', context)


@admin_required
def edit_equipment(request, equipment_id):
    editing_equipment = get_object_or_404(Equipment, pk=equipment_id)

    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=editing_equipment)
        if form.is_valid():
            equipment = form.save()
            messages.success(request, f'{equipment.name} was updated.')
            return redirect('dashboard:equipment_management')
    else:
        form = EquipmentForm(instance=editing_equipment)

    equipment, query, status = _equipment_queryset(request)
    context = {
        'equipment': equipment,
        'form': form,
        'editing_equipment': editing_equipment,
        'query': query,
        'selected_status': status,
        'status_choices': Equipment.STATUS_CHOICES,
        'total_equipment': Equipment.objects.count(),
        'available_count': Equipment.objects.filter(status='available').count(),
        'borrowed_count': Equipment.objects.filter(status='borrowed').count(),
        'maintenance_count': Equipment.objects.filter(status='maintenance').count(),
        'retired_count': Equipment.objects.filter(status='retired').count(),
    }
    return render(request, 'equipment_management.html', context)


@admin_required
@require_POST
def deactivate_equipment(request, equipment_id):
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    equipment.status = 'retired'
    if not equipment.condition_remarks:
        equipment.condition_remarks = f'Deactivated by {request.user.get_username()} on {date.today().isoformat()}.'
    equipment.save(update_fields=['status', 'condition_remarks'])
    messages.success(request, f'{equipment.name} was deactivated.')
    return redirect('dashboard:equipment_management')


@admin_required
def borrowing_records(request):
    borrowings, query, status = _borrowing_queryset(request)
    context = {
        'borrowings': borrowings,
        'query': query,
        'selected_status': status,
        'status_choices': Borrow.STATUS_CHOICES,
        'total_borrowings': Borrow.objects.count(),
        'active_count': Borrow.objects.filter(status='Active').count(),
        'overdue_count': Borrow.objects.filter(status='Overdue').count(),
        'returned_count': Borrow.objects.filter(status='Returned').count(),
        'pending_count': Borrow.objects.filter(status='Pending').count(),
    }
    return render(request, 'borrowing_records.html', context)


@admin_required
def overdue_records(request):
    overdue_items, query, today = _overdue_queryset(request)

    for item in overdue_items:
        item.days_overdue = max((today - item.due_date).days, 0)
        item.current_penalty = item.penalty if item.penalty is not None else item.calculate_penalty()

    context = {
        'overdue_items': overdue_items,
        'query': query,
        'total_overdue': overdue_items.count(),
        'flagged_overdue': overdue_items.filter(status='Overdue').count(),
        'total_penalty_amount': sum(
            (item.current_penalty or 0) for item in overdue_items
        ),
        'longest_overdue_days': max((item.days_overdue for item in overdue_items), default=0),
        'today': today,
    }
    return render(request, 'overdue_records.html', context)


@admin_required
def admin_dashboard(request):
    """
    LendR+ Admin Analytics Dashboard view.
    Aggregates all KPI data, chart data, and table records.
    """
    today = date.today()

    # ─── KPI CARDS ───────────────────────────────────────────────
    total_equipment = Equipment.objects.count()

    active_borrowings = Borrow.objects.filter(status='Active').count()

    overdue_count = Borrow.objects.filter(status='Overdue').count()

    total_penalties = (
        Borrow.objects.filter(penalty__isnull=False)
        .aggregate(total=Sum('penalty'))['total']
        or 0
    )
    total_penalties_display = f"RM {total_penalties:,.2f}"

    # ─── RECENT TRANSACTIONS ─────────────────────────────────────
    transactions = (
        Borrow.objects
        .select_related('member__user', 'equipment')
        .order_by('-created_at')[:10]
    )
    total_transactions = Borrow.objects.count()

    # Get pending borrowing requests from BorrowRequest model
    pending_requests = (
        BorrowRequest.objects
        .filter(status='pending')
        .select_related('user', 'equipment')
        .order_by('created_at')[:10]
    )

    # ─── MOST BORROWED EQUIPMENT ─────────────────────────────────
    top_equipment = (
        Equipment.objects
        .annotate(borrow_count=Count('borrowings'))
        .order_by('-borrow_count')[:5]
    )
    max_borrow = top_equipment[0].borrow_count if top_equipment else 1
    most_borrowed = [
        {
            'name': eq.name,
            'count': eq.borrow_count,
            'pct': round((eq.borrow_count / max_borrow) * 100) if max_borrow else 0,
        }
        for eq in top_equipment
    ]

    # ─── OVERDUE SUMMARY ─────────────────────────────────────────
    overdue_items = (
        Borrow.objects
        .filter(status='Overdue')
        .select_related('equipment')
        .order_by('due_date')[:5]
    )
    overdue_summary = []
    for borrow in overdue_items:
        days_overdue = (today - borrow.due_date).days
        overdue_summary.append({
            'name': borrow.equipment.name,
            'days': days_overdue,
            'pct': min(100, days_overdue * 12),
        })

    # ─── DONUT CHART PERCENTAGES ─────────────────────────────────
    total_borrows = Borrow.objects.count() or 1
    overdue_pct = round((overdue_count / total_borrows) * 100)
    returned_pct = round(
        (Borrow.objects.filter(status='Returned').count() / total_borrows) * 100
    )

    # ─── MONTHLY CHART DATA (last 6 months) ──────────────────────
    monthly_stats = []
    month_labels = []
    max_monthly = 1

    raw_months = []
    for i in range(5, -1, -1):
        first_day = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        _, last = calendar.monthrange(first_day.year, first_day.month)
        last_day = first_day.replace(day=last)
        borrows = Borrow.objects.filter(
            borrow_date__gte=first_day, borrow_date__lte=last_day
        ).count()
        returns = Borrow.objects.filter(
            return_date__gte=first_day, return_date__lte=last_day
        ).count()
        raw_months.append({'borrows': borrows, 'returns': returns})
        month_labels.append(first_day.strftime('%b'))
        if borrows > max_monthly:
            max_monthly = borrows
        if returns > max_monthly:
            max_monthly = returns

    for m in raw_months:
        monthly_stats.append({
            'borrow_pct': round((m['borrows'] / max_monthly) * 100) if max_monthly else 0,
            'return_pct': round((m['returns'] / max_monthly) * 100) if max_monthly else 0,
        })

    # ─── EXTRA COUNTS ─────────────────────────────────────────────
    returned_this_month = Borrow.objects.filter(
        status='Returned',
        return_date__month=today.month,
        return_date__year=today.year,
    ).count()

    # Count pending requests from BorrowRequest model
    pending_count = BorrowRequest.objects.filter(status='pending').count()

    context = {
        # KPI Cards
        'total_equipment': total_equipment,
        'active_borrowings': active_borrowings,
        'overdue_count': overdue_count,
        'total_penalties': total_penalties_display,

        # Table
        'transactions': transactions,
        'total_transactions': total_transactions,
        'pending_requests': pending_requests,

        # Reports
        'most_borrowed': most_borrowed,
        'overdue_summary': overdue_summary,

        # Chart
        'monthly_stats': monthly_stats,
        'month_labels': month_labels,

        # Donut
        'overdue_pct': overdue_pct,
        'returned_pct': returned_pct,

        # Extras
        'returned_this_month': returned_this_month,
        'pending_count': pending_count,
    }

    return render(request, 'admin_dashboard.html', context)


@admin_required
@require_POST
def approve_borrow_request(request, borrow_id):
    """Approve a borrowing request and create an active Borrow record."""
    with transaction.atomic():
        # Get the borrowing request
        borrow_request = get_object_or_404(
            BorrowRequest.objects.select_for_update().select_related('user', 'equipment'),
            pk=borrow_id,
        )

        if borrow_request.status != 'pending':
            messages.warning(request, 'Only pending borrowing requests can be approved.')
            return redirect('dashboard:overview')

        equipment = Equipment.objects.select_for_update().get(pk=borrow_request.equipment_id)
        if equipment.status != 'available':
            messages.error(request, f'{equipment.name} is not available, so this request cannot be approved.')
            return redirect('dashboard:overview')

        # Update the BorrowRequest status
        borrow_request.status = 'approved'
        borrow_request.save(update_fields=['status'])

        # Create a new Borrow record
        approved_date = date.today()
        due_date = add_weekdays(approved_date, 5)
        
        # Get or create member for the user
        from .models import Member
        member, created = Member.objects.get_or_create(
            user=borrow_request.user,
            defaults={
                'member_id': borrow_request.student_id,
                'phone': borrow_request.phone_number,
            }
        )
        
        # Create the Borrow record
        Borrow.objects.create(
            member=member,
            equipment=equipment,
            borrow_date=approved_date,
            due_date=due_date,
            return_date=due_date,
            status='Active',
            notes=f'Approved from request #{borrow_request.id} by {request.user.get_username()} on {date.today().isoformat()}.'
        )

        equipment.status = 'borrowed'
        equipment.save(update_fields=['status'])

    messages.success(request, f'Borrowing request for {borrow_request.equipment.name} was approved.')
    return redirect('dashboard:overview')


@admin_required
@require_POST
def reject_borrow_request(request, borrow_id):
    """Reject a borrowing request by updating its status."""
    with transaction.atomic():
        borrow_request = get_object_or_404(
            BorrowRequest.objects.select_for_update().select_related('user', 'equipment'),
            pk=borrow_id,
        )

        if borrow_request.status != 'pending':
            messages.warning(request, 'Only pending borrowing requests can be rejected.')
            return redirect('dashboard:overview')

        borrow_request.status = 'denied'
        borrow_request.save(update_fields=['status'])

    messages.success(request, f'Borrowing request for {borrow_request.equipment.name} was rejected.')
    return redirect('dashboard:overview')


@admin_required
def analytics(request):
    """
    Analytics page with detailed borrowing statistics and reports.
    """
    today = date.today()
    
    # Get query parameters for filtering
    status_filter = request.GET.get('status', '')
    equipment_filter = request.GET.get('equipment', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # ─── BORROW HISTORY LOGS ───────────────────────────────────────
    borrow_history = Borrow.objects.select_related(
        'member__user', 'equipment'
    ).order_by('-created_at', '-borrow_date')
    
    # Apply filters
    if status_filter:
        borrow_history = borrow_history.filter(status=status_filter)
    if equipment_filter:
        borrow_history = borrow_history.filter(
            Q(equipment__name__icontains=equipment_filter) |
            Q(equipment__category__icontains=equipment_filter)
        )
    if date_from:
        borrow_history = borrow_history.filter(borrow_date__gte=date_from)
    if date_to:
        borrow_history = borrow_history.filter(borrow_date__lte=date_to)
    
    # Paginate borrow history
    from django.core.paginator import Paginator
    paginator = Paginator(borrow_history, 20)  # Show 20 records per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # ─── MONTHLY BORROW ANALYTICS (last 12 months) ────────────────
    monthly_stats = []
    month_labels = []
    max_monthly = 1
    
    for i in range(11, -1, -1):
        first_day = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        _, last = calendar.monthrange(first_day.year, first_day.month)
        last_day = first_day.replace(day=last)
        
        borrows = Borrow.objects.filter(
            borrow_date__gte=first_day, borrow_date__lte=last_day
        ).count()
        returns = Borrow.objects.filter(
            return_date__gte=first_day, return_date__lte=last_day
        ).count()
        
        monthly_stats.append({
            'month': first_day.strftime('%B %Y'),
            'borrows': borrows,
            'returns': returns,
            'borrow_pct': round((borrows / max_monthly) * 100) if max_monthly else 0,
            'return_pct': round((returns / max_monthly) * 100) if max_monthly else 0,
        })
        month_labels.append(first_day.strftime('%b'))
        
        if borrows > max_monthly:
            max_monthly = borrows
        if returns > max_monthly:
            max_monthly = returns
    
    # Recalculate percentages with actual max
    for m in monthly_stats:
        m['borrow_pct'] = round((m['borrows'] / max_monthly) * 100) if max_monthly else 0
        m['return_pct'] = round((m['returns'] / max_monthly) * 100) if max_monthly else 0
    
    # ─── MOST BORROWED EQUIPMENT (top 10) ────────────────────────
    top_equipment = (
        Equipment.objects
        .annotate(borrow_count=Count('borrowings'))
        .order_by('-borrow_count')[:10]
    )
    max_borrow = top_equipment[0].borrow_count if top_equipment else 1
    most_borrowed = [
        {
            'name': eq.name,
            'serial_number': eq.serial_number or 'N/A',
            'category': eq.category or 'Uncategorized',
            'count': eq.borrow_count,
            'pct': round((eq.borrow_count / max_borrow) * 100) if max_borrow else 0,
        }
        for eq in top_equipment
    ]
    
    # ─── OVERDUE REPORTS ────────────────────────────────────────────
    overdue_items = (
        Borrow.objects
        .filter(status='Overdue')
        .select_related('member__user', 'equipment')
        .order_by('due_date')
    )
    
    # Calculate overdue details
    overdue_reports = []
    for borrow in overdue_items:
        days_overdue = (today - borrow.due_date).days
        penalty = borrow.penalty if borrow.penalty is not None else borrow.calculate_penalty()
        overdue_reports.append({
            'id': borrow.id,
            'equipment_name': borrow.equipment.name,
            'member_name': borrow.member.get_full_name(),
            'member_id': borrow.member.member_id,
            'due_date': borrow.due_date,
            'days_overdue': days_overdue,
            'penalty': penalty,
            'pct': min(100, days_overdue * 12),
        })
    
    # Calculate overdue statistics
    total_overdue = len(overdue_reports)
    total_penalty_amount = sum(r['penalty'] or 0 for r in overdue_reports)
    longest_overdue_days = max((r['days_overdue'] for r in overdue_reports), default=0)
    
    # ─── SUMMARY STATISTICS ────────────────────────────────────────
    total_borrows = Borrow.objects.count()
    total_returns = Borrow.objects.filter(status='Returned').count()
    total_active = Borrow.objects.filter(status='Active').count()
    total_rejected = Borrow.objects.filter(status='Rejected').count()
    
    context = {
        # Borrow History
        'page_obj': page_obj,
        'status_filter': status_filter,
        'equipment_filter': equipment_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Borrow.STATUS_CHOICES,
        
        # Monthly Analytics
        'monthly_stats': monthly_stats,
        'month_labels': month_labels,
        
        # Most Borrowed Equipment
        'most_borrowed': most_borrowed,
        
        # Overdue Reports
        'overdue_reports': overdue_reports,
        'total_overdue': total_overdue,
        'total_penalty_amount': total_penalty_amount,
        'longest_overdue_days': longest_overdue_days,
        
        # Summary Statistics
        'total_borrows': total_borrows,
        'total_returns': total_returns,
        'total_active': total_active,
        'total_rejected': total_rejected,
        
        # Today's date
        'today': today,
    }
    
    return render(request, 'analytics.html', context)
