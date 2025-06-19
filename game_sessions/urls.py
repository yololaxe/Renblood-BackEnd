from django.urls import path, include
from rest_framework.routers import DefaultRouter

# … vos autres imports …
from game_sessions.viewsets.session_viewset        import SessionViewSet
from game_sessions.viewsets.future_viewset import FutureViewSet

router = DefaultRouter()
# … vos enregistrements actuels …
router.register(r'', SessionViewSet, basename='session')
router.register(r'futures', FutureViewSet, basename='sessionfuture')

urlpatterns = [
    path('', include(router.urls)),
]
