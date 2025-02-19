from django.urls import path
from .views import get_job_details

urlpatterns = [
    path('<str:job_id>/', get_job_details, name='get_job_details'),
]
