from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from rm_auth.decorators import rm_login_required

from .models import CustomerProfile


@rm_login_required
def customer_list(request):
    qs = CustomerProfile.objects.select_related().order_by("customer_id")

    # filters
    account_type = request.GET.get("account_type", "")
    search = request.GET.get("q", "").strip()

    if account_type:
        qs = qs.filter(account_type=account_type)
    if search:
        qs = qs.filter(name__icontains=search) | qs.filter(customer_id__icontains=search)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "customers/customer_list.html", {
        "page_obj": page,
        "account_types": CustomerProfile.ACCOUNT_TYPES,
        "selected_account_type": account_type,
        "search": search,
        "total": qs.count(),
    })


@rm_login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(
        CustomerProfile.objects.prefetch_related(
            "transactions", "cc_transactions", "credit_cards", "loan_history"
        ),
        customer_id=customer_id,
    )
    return render(request, "customers/customer_detail.html", {"customer": customer})
