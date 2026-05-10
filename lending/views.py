from decimal import Decimal, ROUND_HALF_UP
from contextlib import contextmanager
import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from accounts.services.profile_service import ProfileService
from equipment.services.equipment_service import EquipmentService
from lending.models import LendingRequest, Penalty
from lending.services.lending_service import LendingService
from lending.services.notification_service import LendingNotificationService


lending_service = LendingService()
equipment_service = EquipmentService()
profile_service = ProfileService()
notification_service = LendingNotificationService()


def admin_required(user):
    return profile_service.is_admin(user)


@login_required
def my_requests(request):
    return redirect('equipment:available')


@login_required
@require_http_methods(['GET', 'POST'])
def create_request(request, equipment_id):
    equipment = equipment_service.get_equipment(equipment_id)
    equipment.category_icon_class = equipment_service.category_icon_class(equipment.category.name)
    if request.method == 'POST':
        try:
            lending_request = lending_service.create_request(
                request.user,
                equipment_id,
                request.POST.get('purpose', ''),
                request.POST.get('requested_from'),
                request.POST.get('requested_until'),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('lending:create_request', equipment_id=equipment_id)
        notification_service.borrowing_request_submitted([lending_request])
        messages.success(request, 'Lending request submitted for administrator review.')
        return redirect('equipment:available')
    return render(request, 'lending/request_form.html', {'equipment': equipment})


@login_required
@require_http_methods(['POST'])
def create_bulk_request(request):
    if not request.POST.get('terms_accepted'):
        messages.error(request, 'You must agree to the terms and conditions before submitting.')
        return redirect('equipment:available')

    try:
        created_requests = lending_service.create_bulk_requests(
            request.user,
            request.POST.getlist('equipment_ids'),
            request.POST.get('purpose', ''),
            request.POST.get('requested_from'),
            request.POST.get('requested_until'),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('equipment:available')

    request_count = len(created_requests)
    notification_service.borrowing_request_submitted(created_requests)
    messages.success(request, f'{request_count} lending request{"s" if request_count != 1 else ""} submitted for administrator review.')
    return redirect('equipment:available')


@login_required
@user_passes_test(admin_required)
def admin_requests(request):
    requests = lending_service.list_all_requests()
    penalties = lending_service.list_all_penalties()
    return render(request, 'lending/admin_requests.html', {
        'requests': requests,
        'penalties': penalties,
    })


@login_required
@require_http_methods(['GET'])
def borrow_code(request, request_id):
    try:
        lending_request = lending_service.list_user_requests(request.user).get(id=request_id)
    except LendingRequest.DoesNotExist:
        return JsonResponse({'ok': False, 'message': 'Borrowing request not found.'}, status=404)

    if lending_request.status != lending_request.STATUS_APPROVED:
        return JsonResponse({
            'ok': False,
            'message': 'Borrow code is only available for approved requests.',
            'status': lending_request.status,
        })

    try:
        code, remaining_seconds = lending_service.borrow_code_for_request(lending_request)
    except Exception as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)

    return JsonResponse({
        'ok': True,
        'code': code,
        'remaining_seconds': remaining_seconds,
        'status': lending_request.status,
    })


def stripe_amount_cents(amount):
    return int((Decimal(amount) * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def stripe_object_to_dict(stripe_object):
    if hasattr(stripe_object, 'to_dict_recursive'):
        return stripe_object.to_dict_recursive()
    if hasattr(stripe_object, 'to_dict'):
        return stripe_object.to_dict()
    return dict(stripe_object)


@contextmanager
def stripe_without_broken_local_proxy():
    proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']
    removed = {}
    if os.environ.get('STRIPE_USE_SYSTEM_PROXY', '').lower() == 'true':
        yield
        return

    for key in proxy_keys:
        if key in os.environ:
            removed[key] = os.environ.pop(key)
    try:
        yield
    finally:
        os.environ.update(removed)


@login_required
@require_http_methods(['POST'])
def create_penalty_checkout(request, penalty_id):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if not settings.STRIPE_SECRET_KEY:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': 'Stripe is not configured yet. Add STRIPE_SECRET_KEY to .env.'}, status=400)
        messages.error(request, 'Stripe is not configured yet. Add STRIPE_SECRET_KEY to .env.')
        return redirect('equipment:available')

    try:
        penalty = lending_service.list_penalties_for_user(request.user).get(
            id=penalty_id,
            status=Penalty.STATUS_UNPAID,
        )
    except Penalty.DoesNotExist:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': 'This penalty is not available for payment.'}, status=404)
        messages.error(request, 'This penalty is not available for payment.')
        return redirect('equipment:available')

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        with stripe_without_broken_local_proxy():
            session = stripe.checkout.Session.create(
                mode='payment',
                client_reference_id=str(penalty.id),
                customer_email=request.user.email or None,
                line_items=[{
                    'price_data': {
                        'currency': settings.STRIPE_CURRENCY,
                        'product_data': {
                            'name': f'Lendr penalty #{penalty.id}',
                            'description': f'{penalty.lending_request.equipment.name} return penalty',
                        },
                        'unit_amount': stripe_amount_cents(penalty.amount),
                    },
                    'quantity': 1,
                }],
                metadata={
                    'penalty_id': str(penalty.id),
                    'user_id': str(request.user.id),
                },
                success_url=request.build_absolute_uri(reverse('lending:penalty_payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('lending:penalty_payment_cancel')),
            )
    except Exception as exc:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': f'Unable to start Stripe payment: {exc}'}, status=400)
        messages.error(request, f'Unable to start Stripe payment: {exc}')
        return redirect('equipment:available')

    if is_ajax:
        return JsonResponse({'ok': True, 'session_id': session.id})
    return redirect(session.url)


@login_required
@require_http_methods(['GET'])
def penalty_payment_success(request):
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, 'Stripe payment session was not provided.')
        return redirect('equipment:available')

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Stripe is not configured.')
        return redirect('equipment:available')

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        with stripe_without_broken_local_proxy():
            session = stripe.checkout.Session.retrieve(session_id)
        session_data = stripe_object_to_dict(session)
        metadata = session_data.get('metadata') or {}
        penalty_id = metadata.get('penalty_id') or session_data.get('client_reference_id')
        user_id = metadata.get('user_id')
        if session_data.get('payment_status') != 'paid' or user_id != str(request.user.id):
            messages.error(request, 'Stripe payment was not completed.')
            return redirect('equipment:available')
        penalty = lending_service.mark_penalty_paid(penalty_id, request.user)
        notification_service.penalty_status_changed(penalty)
        messages.success(request, 'Penalty payment completed successfully.')
    except Exception as exc:
        messages.error(request, f'Unable to verify Stripe payment: {exc}')
    return redirect('equipment:available')


@login_required
@require_http_methods(['GET'])
def penalty_payment_cancel(request):
    messages.error(request, 'Penalty payment was cancelled.')
    return redirect('equipment:available')


@login_required
@require_http_methods(['POST'])
def request_return(request, request_id):
    try:
        lending_service.request_return(request.user, request_id)
        messages.success(request, 'Return request submitted for administrator approval.')
    except LendingRequest.DoesNotExist:
        messages.error(request, 'Borrowing request not found.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('equipment:available')


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def approve_request(request, request_id):
    lending_request = lending_service.approve_request(request_id, request.user, request.POST.get('admin_note', ''))
    notification_service.borrowing_request_approved(lending_request)
    messages.success(request, 'Request approved.')
    return redirect('lending:admin_requests')


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def deny_request(request, request_id):
    lending_service.deny_request(request_id, request.user, request.POST.get('admin_note', ''))
    messages.success(request, 'Request denied.')
    return redirect('lending:admin_requests')


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def mark_borrowed(request, request_id):
    try:
        lending_service.mark_borrowed(request_id, request.POST.get('borrow_code'))
        messages.success(request, 'Equipment checked out to borrower.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('lending:admin_requests')


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def mark_returned(request, request_id):
    try:
        lending_request = lending_service.mark_returned(
            request_id,
            request.POST.get('penalty_amount', '0'),
            request.POST.get('penalty_note', ''),
        )
        notification_service.return_completed(lending_request)
        messages.success(request, 'Return completed and equipment availability restored.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('lending:admin_requests')


@login_required
@user_passes_test(admin_required)
def overdue_management(request):
    lending_service.refresh_overdue_and_penalties()
    overdue_requests = lending_service.list_overdue_requests()
    penalties = lending_service.list_all_penalties()
    return render(request, 'lending/overdue.html', {'overdue_requests': overdue_requests, 'penalties': penalties, 'statuses': Penalty.STATUS_CHOICES})


@login_required
@user_passes_test(admin_required)
@require_http_methods(['POST'])
def update_penalty(request, penalty_id):
    try:
        penalty = lending_service.update_penalty_status(penalty_id, request.POST.get('status'))
        notification_service.penalty_status_changed(penalty)
        messages.success(request, 'Penalty status updated.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get('next') or 'lending:overdue')

# Create your views here.
