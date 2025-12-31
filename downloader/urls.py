from django.urls import path
from . import views

app_name = 'downloader'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/video-info/', views.get_video_info, name='video_info'),
    path('api/download/', views.download_video, name='download'),
    path('api/download-file/<str:download_id>/', views.serve_download, name='serve_download'),
    path('api/check-status/<str:download_id>/', views.check_status, name='check_status'),
]
