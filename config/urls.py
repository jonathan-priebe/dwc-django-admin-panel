"""
URL configuration for DWC Server Admin Panel
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from dwc_admin import views

urlpatterns = [
    # Custom Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Django Admin
    path('admin/', admin.site.urls),

    # API
    path('api/', include('dwc_api.urls')),
]

# Serve media files in all environments (needed for DLS1 server to download files)
if settings.DEBUG or True:  # Always serve media files for this application
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)