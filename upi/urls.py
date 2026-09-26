from django.urls import path
from . import views

app_name = 'upi'

urlpatterns = [
    path('dashboard/',              views.dashboard_view,           name='dashboard'),
    path('send-money/',             views.send_money_view,          name='send_money'),
    path('transactions/',           views.transaction_history_view, name='transactions'),
    path('statement/pdf/',          views.download_statement,       name='download_statement'),
    path('statement/xml/',          views.download_statement_xml,   name='download_statement_xml'),
    path('receipt/<int:txn_id>/',   views.transaction_receipt,      name='transaction_receipt'),
    path('search-users/',           views.search_users,             name='search_users'),
    path('get-all-users/',          views.get_all_users,            name='get_all_users'),
    path('add-beneficiary/',        views.add_beneficiary,          name='add_beneficiary'),
    path('remove-beneficiary/<int:beneficiary_id>/', views.remove_beneficiary, name='remove_beneficiary'),
    path('add-amount/',             views.add_amount_view,          name='add_amount'),
    path('notifications/',          views.fetch_notifications,      name='fetch_notifications'),
    path('notifications/unread-count/', views.notifications_unread_count, name='notifications_unread_count'),
    path('budgets/',                views.budgets_view,             name='budgets'),
    path('budgets/<int:budget_id>/delete/', views.delete_budget,    name='delete_budget'),
]
