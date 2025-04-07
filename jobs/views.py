# from django.shortcuts import render
# from django.http import JsonResponse
# from django.shortcuts import get_object_or_404
# from .models import Job
# from django.views.decorators.csrf import csrf_exempt
# from jobs.models import Trait, Action

# Create your views here.
def get_job_details(request, job_id):
    job = get_object_or_404(Job, _id=job_id)  # Recherche le job dans la base de données
    return JsonResponse({
        "id": job._id,
        "name": job.name,
        "skills": job.skills,
        "inter_choice": job.inter_choice,
        "mastery": job.mastery
    }, safe=False)

# @csrf_exempt
# def get_traits_or_actions(request, category):
#     """Renvoie la liste des traits, actions, ou les deux selon le paramètre dans l'URL."""
    
#     if category == "traits":
#         data = list(Trait.objects.values("trait_id", "name", "bonus"))
#     elif category == "actions":
#         data = list(Action.objects.values("action_id", "name", "description", "mana", "chance"))
#     elif category == "all":
#         data = {
#             "traits": list(Trait.objects.values("trait_id", "name", "bonus")),
#             "actions": list(Action.objects.values("action_id", "name", "description", "mana", "chance"))
#         }
#     else:
#         return JsonResponse({"error": "Invalid category. Use 'traits', 'actions', or 'all'."}, status=400)

#     return JsonResponse(data, safe=False, status=200)