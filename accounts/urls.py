from django.urls import path
from . import views

urlpatterns = [
    path('role-selection/', views.RoleSelectionView.as_view(), name='role_selection'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('current-user/', views.CurrentUserView.as_view(), name='current_user'),
]
