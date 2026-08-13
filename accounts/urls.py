from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/',        views.register_view,        name='register'),
    path('login/',           views.login_view,            name='login'),
    path('logout/',          views.logout_view,           name='logout'),
    path('profile/',         views.profile_view,          name='profile'),
    path('set-pin/',         views.set_pin_view,          name='set_pin'),
    # Separate admin registration and login
    path('admin/register/',  views.admin_register_view,   name='admin_register'),
    path('admin/login/',     views.admin_login_view,      name='admin_login'),
]
