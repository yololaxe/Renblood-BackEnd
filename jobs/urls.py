from django.urls import path
from .views import get_job_details, get_traits_or_actions

urlpatterns = [
    path('<str:job_id>/', get_job_details, name='get_job_details'),
    path("get/<str:category>/", get_traits_or_actions, name="get_traits_or_actions"),
]
