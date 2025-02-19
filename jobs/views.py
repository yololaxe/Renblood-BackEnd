from django.shortcuts import render
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Job

# Create your views here.
def get_job_details(request, job_id):
    job = get_object_or_404(Job, _id=job_id)  # Recherche le job dans la base de données
    return JsonResponse({
        "id": job._id,
        "name": job.name,
        "skills": job.skills,
        "mastery": job.mastery
    }, safe=False)