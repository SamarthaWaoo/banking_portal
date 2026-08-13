from django.urls import path
from . import views

app_name = 'upi'

urlpatterns = [
    path('dashboard/',         views.dashboard_view,           name='dashboard'),
    path('send-money/',              views.send_money_view,          name='send_money'),
    path('transactions/',      views.transaction_history_view, name='transactions'),
    path('statement/pdf/',     views.download_statement_pdf,   name='download_statement'),
    path('search-users/',      views.search_users,             name='search_users'),
    path('get-all-users/',     views.get_all_users,            name='get_all_users'),
    path('add-beneficiary/',    views.add_beneficiary,          name='add_beneficiary'),
    path('remove-beneficiary/<int:beneficiary_id>/', views.remove_beneficiary, name='remove_beneficiary'),
]
