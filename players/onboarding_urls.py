from django.urls import path
from . import onboarding as views

urlpatterns = [
    path("session/", views.session_view),
    path("me/", views.profile_view),
    path("submit/", views.submit_view),
    path("minecraft/code/", views.code_view),
    path("requests/cancel/", views.cancel_view),
    path("minecraft/confirm/", views.confirm_view),
    path("admin/settings/", views.settings_view),
    path("admin/queue/", views.queue_view),
    path("admin/review/<str:uid>/", views.review_view),
]
