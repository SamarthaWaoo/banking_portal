from django.urls import path
from . import views

app_name = 'loans'

urlpatterns = [
    path('apply/',                        views.apply_view,       name='apply'),
    path('my-loans/',                     views.my_loans_view,    name='my_loans'),
    path('<str:application_id>/',         views.loan_detail_view, name='loan_detail'),
    path('<str:application_id>/disburse/',views.disburse_view,    name='disburse'),
    path('<str:application_id>/repay/',   views.repay_view,       name='repay'),
]
