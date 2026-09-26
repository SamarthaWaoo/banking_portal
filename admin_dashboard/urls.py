from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('',                                            views.dashboard_view,          name='dashboard'),
    path('customer/<str:customer_id>/',                 views.customer_detail_view,    name='customer_detail'),
    path('customer/<str:customer_id>/xbrl/',            views.xbrl_statement_view,     name='xbrl_statement'),
    path('notify/',                                     views.send_notification_view,  name='send_notification'),
    path('transactions/<int:txn_id>/resolve/',          views.resolve_transaction_view,name='resolve_transaction'),
    path('accounts/<int:account_id>/freeze/',           views.freeze_account_view,     name='freeze_account'),
    path('accounts/<int:account_id>/unfreeze/',         views.unfreeze_account_view,   name='unfreeze_account'),
    path('accounts/<int:account_id>/approve/',          views.approve_account_view,    name='approve_account'),
    path('accounts/<int:account_id>/reject/',           views.reject_account_view,     name='reject_account'),
]
