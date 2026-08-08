from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('',                                    views.dashboard_view,           name='dashboard'),
    path('transactions/<int:txn_id>/resolve/',  views.resolve_transaction_view, name='resolve_transaction'),
    path('accounts/<int:account_id>/freeze/',   views.freeze_account_view,      name='freeze_account'),
    path('accounts/<int:account_id>/unfreeze/', views.unfreeze_account_view,    name='unfreeze_account'),
]
