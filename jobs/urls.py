from django.urls import path, include
from rest_framework.routers import DefaultRouter

from jobs.viewsets.dice_viewset import roll_dice
from jobs.viewsets.job_viewset    import JobViewSet
from jobs.viewsets.trait_viewset  import TraitViewSet
from jobs.viewsets.action_viewset import ActionViewSet
from jobs.viewsets.global_viewset import GlobalViewSet
from jobs.viewsets.node_viewset   import NodeViewSet

router = DefaultRouter()
router.register(r"jobs",    JobViewSet,    basename="job")
router.register(r"trait",   TraitViewSet,  basename="trait")
router.register(r"action",  ActionViewSet, basename="action")
router.register(r"globals", GlobalViewSet, basename="global")
router.register(r"nodes",   NodeViewSet)

urlpatterns = [
    path("api/jobs/", include(router.urls)),
    # endpoint HTTP POST /api/jobs/dice/roll/
    path("api/jobs/dice/roll/", roll_dice, name="dice-roll"),
]
