from django.http import JsonResponse
from .views import endpoint, method, game
from .store import get_bank
from .domain import EconomyError
from .merchant import Merchant

@endpoint
def notebook(request):
    method(request,'GET')
    return JsonResponse(Merchant(get_bank()).notebook(request.economy_owner))

@endpoint
def config(request):
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    service=Merchant(get_bank())
    if request.method=='GET':return JsonResponse(service.config())
    method(request,'POST')
    return JsonResponse(service.save(request.economy_body,request.economy_actor))

@endpoint
def branch(request):
    method(request,'POST')
    return JsonResponse(Merchant(get_bank()).choose(request.economy_owner,request.economy_body.get('branch')))

@endpoint
def contracts(request):
    method(request,'POST')
    return JsonResponse(Merchant(get_bank()).accept(request.economy_owner,
        request.headers.get('Idempotency-Key') or request.economy_body.get('key'),
        {k:v for k,v in request.economy_body.items() if k!='key'}))

@endpoint
def contract(request,ident,action):
    service=Merchant(get_bank())
    if action=='delivery':
        method(request,'GET');game(request)
        return JsonResponse(service.delivery(request.economy_owner,ident))
    if action=='cancel':
        method(request,'POST')
        return JsonResponse(service.cancel(request.economy_owner,ident))
    raise EconomyError('INVALID_REQUEST','Action inconnue.',400)
