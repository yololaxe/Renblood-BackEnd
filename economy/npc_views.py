from django.http import JsonResponse
from .views import endpoint, method, game
from .store import get_bank
from .domain import EconomyError, public
from .npc_services import NpcShops, contract_terms as save_contract_terms


@endpoint
def contract_terms(request):
    method(request, 'POST'); game(request)
    return JsonResponse(save_contract_terms(get_bank(), request.economy_body))


@endpoint
def catalogue(request):
    method(request, 'GET')
    return JsonResponse(NpcShops(get_bank()).metadata(request.GET.get('city_id') or None))


@endpoint
def shops(request, ident=None):
    ident = str(ident) if ident else None
    service = NpcShops(get_bank())
    if request.method == 'GET':
        if ident: return JsonResponse(service.catalogue(ident, request.economy_admin))
        if not request.economy_admin: raise EconomyError('ADMIN_REQUIRED', 'Administrateur requis.', 403)
        rows = list(service.db.npc_shops.find({}, {'_id': 0, 'offers': 0}).sort('name', 1).limit(200))
        return JsonResponse({'shops': rows, 'cities': service.metadata()['cities']})
    method(request, 'POST')
    if not request.economy_admin: raise EconomyError('ADMIN_REQUIRED', 'Administrateur requis.', 403)
    body = request.economy_body
    if ident and ident != body.get('id'): raise EconomyError('INVALID_REQUEST', 'Boutique incohérente.', 400)
    return JsonResponse(service.save(body, request.economy_actor))


@endpoint
def purchase(request, ident):
    method(request, 'POST'); game(request)
    return JsonResponse(public(NpcShops(get_bank()).prepare(str(ident), request.economy_owner, request.economy_actor, request.economy_body)))
