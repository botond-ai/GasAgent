"""
URL configuration for KnowledgeRouter project.
"""
from django.urls import path, include
from django.http import JsonResponse

def healthz(request):
    return JsonResponse({'status': 'healthy'}, status=200)

urlpatterns = [
    path('api/healthz', healthz, name='healthz'),
    path('api/', include('api.urls')),
]
