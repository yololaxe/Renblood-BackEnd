# Budget quotidien des PNJ

Les contrats de toutes les routes partagent `npc-contracts`. Une seule configuration finance donc les contrats, quel que soit le nombre de routes. `inn-customers` peut être ajouté à la même configuration pour le budget des voyageurs d’auberge. Les deux enveloppes puisent dans `treasury:npc`.

Le service complète l’enveloppe jusqu’au disponible cible, avec un plafond par jour et par enveloppe. Il conserve les fonds restants et tient compte des entrées déjà réservées. Par exemple, avec une cible de 1 000 fer, un plafond de 500 et 700 fer disponibles, le service transfère 300 fer si la trésorerie peut les couvrir. Une trésorerie vide produit l’état `TREASURY_EMPTY`. Une trésorerie partiellement financée permet un transfert à hauteur du disponible.

Un transfert confirmé clôt le réapprovisionnement de cette enveloppe pour la journée UTC, même si le versement était partiel. Tant qu’aucun versement n’a eu lieu, un prochain passage peut réessayer. Les jours manqués ne se cumulent pas. Les deux caisses et le reçu sont mis à jour dans la même transaction Mongo. Deux passages simultanés ne créent qu’un reçu.

## Préparer une fois

Depuis `Renblood-BackEnd`, créer une configuration en copiant `economy/npc-budget.example.json`, puis choisir des montants adaptés aux contrats réellement proposés. Les montants sont des chaînes d’entiers en fer. Les enveloppes présentes dans le fichier sont celles que la tâche traite.

```powershell
Copy-Item economy/npc-budget.example.json npc-budget.json
python -m economy.npc_budget --env-file .env.local --database renblood_mongo_staging --rules npc-budget.json --prepare --apply
```

La préparation enregistre la trésorerie et les enveloppes si elles manquent. Elle laisse les caisses existantes en place. Ensuite, utiliser **Intendance économique → Trésorerie des PNJ → Alimenter la caisse**, ou transférer depuis la banque d’un admin Minecraft lié à un compte web Admin. L’exemple ci-dessous transfère 5 000 fer de sa banque.

```text
/economie budget treasury:npc 5000
```

## Contrôler et programmer

```powershell
# Aperçu en lecture seule
python -m economy.npc_budget --env-file .env.local --database renblood_mongo_staging --rules npc-budget.json

# Exécuter un passage, puis quitter
python -m economy.npc_budget --env-file .env.local --database renblood_mongo_staging --rules npc-budget.json --apply

# Option pour un processus surveillé qui vérifie chaque minute
python -m economy.npc_budget --env-file .env.local --database renblood_mongo_staging --rules npc-budget.json --apply --watch
```

Sur le serveur, programmer le passage ponctuel avec le planificateur du système, ou superviser le processus `--watch` avec redémarrage en cas d’échec. Le jour est calculé en UTC au passage du service. Les reçus apparaissent dans l’intendance sous **Réapprovisionnement quotidien des PNJ** et figurent dans le rapprochement `economy.audit`. Contrôler le disponible de la trésorerie et les états du service pendant le pilote. En cas de budget déjà utilisé pour la journée, un financement ponctuel de l’enveloppe reste possible depuis l’intendance.
