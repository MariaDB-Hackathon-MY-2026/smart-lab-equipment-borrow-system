from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from datetime import date, timedelta
import calendar

from lendr_project.decorators import admin_required

from .forms import EquipmentForm
from .models import Equipment, Borrow


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

    pending_requests = (
        Borrow.objects
        .filter(status='Pending')
        .select_related('member__user', 'equipment')
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

    pending_count = Borrow.objects.filter(status='Pending').count()

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
    with transaction.atomic():
        borrow = get_object_or_404(
            Borrow.objects.select_for_update().select_related('equipment', 'member__user'),
            pk=borrow_id,
        )

        if borrow.status != 'Pending':
            messages.warning(request, 'Only pending borrowing requests can be approved.')
            return redirect('dashboard:overview')

        equipment = Equipment.objects.select_for_update().get(pk=borrow.equipment_id)
        if equipment.status != 'available':
            messages.error(request, f'{equipment.name} is not available, so this request cannot be approved.')
            return redirect('dashboard:overview')

        approved_date = date.today()
        due_date = add_weekdays(approved_date, 5)

        borrow.status = 'Active'
        borrow.borrow_date = approved_date
        borrow.due_date = due_date
        borrow.return_date = due_date
        _append_note(borrow, f'Approved by {request.user.get_username()} on {date.today().isoformat()}.')
        borrow.save(update_fields=['status', 'borrow_date', 'due_date', 'return_date', 'notes'])

        equipment.status = 'borrowed'
        equipment.save(update_fields=['status'])

    messages.success(request, f'Borrowing request for {borrow.equipment.name} was approved.')
    return redirect('dashboard:overview')


@admin_required
@require_POST
def reject_borrow_request(request, borrow_id):
    with transaction.atomic():
        borrow = get_object_or_404(
            Borrow.objects.select_for_update().select_related('equipment', 'member__user'),
            pk=borrow_id,
        )

        if borrow.status != 'Pending':
            messages.warning(request, 'Only pending borrowing requests can be rejected.')
            return redirect('dashboard:overview')

        borrow.status = 'Rejected'
        _append_note(borrow, f'Rejected by {request.user.get_username()} on {date.today().isoformat()}.')
        borrow.save(update_fields=['status', 'notes'])

    messages.success(request, f'Borrowing request for {borrow.equipment.name} was rejected.')
    return redirect('dashboard:overview')
