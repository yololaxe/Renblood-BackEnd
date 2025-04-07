from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from jobs.models.job import Job
from jobs.serializers.job_serializer import JobSerializer

class JobViewSet(viewsets.ReadOnlyModelViewSet):  # GET only (read-only)
    queryset = Job.objects.all()
    serializer_class = JobSerializer

    @action(detail=True, methods=['get'], url_path='details')
    def job_details(self, request, pk=None):
        job = self.get_object()
        serializer = self.get_serializer(job)  # 🔥 utilise le serializer
        return Response(serializer.data)
