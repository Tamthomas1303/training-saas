"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from accounts.views import BrandSettingsView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    # UI dot 1 (Prompt_UI_Dot1_Theme.md) - dung URL dung nhu prompt yeu cau, KHONG nam duoi
    # prefix api/auth/ cua accounts.urls (de khop dung "/api/settings/brand/").
    path('api/settings/brand/', BrandSettingsView.as_view(), name='brand-settings'),
    path('api/restaurants/', include('restaurants.urls')),
    path('api/employees/', include('employees.urls')),
    path('api/checklist/', include('checklist.urls')),
    path('api/evaluation/', include('evaluation.urls')),
    path('api/kpi/', include('kpi.urls')),
    path('api/sourcing/', include('sourcing.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/courses/', include('courses.urls')),
    path('api/exams/', include('exams.urls')),
    path('api/integration/', include('integration.urls')),
    path('api/dashboard/', include('dashboard.urls')),
]
