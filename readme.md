pip install django
pip install django-cors-headers
pip install djongo
pip install dnspython

3️⃣ Appliquer les migrations
python manage.py makemigrations players
python manage.py migrate
4️⃣ Lancer le serveur Django
python manage.py runserver


Exemple de création sur powershell : 
$body = @{
    id = "0kX4gctisIcOKvHDKJmlDRLSLFu2"
    id_minecraft = "mc-uuid-456"
    pseudo_minecraft = "ShadowAlban"
    name = "Alban"
    surname = "Moragny"
    total_lvl = 10
    description = "Joueur test"
    rank = "Seigneur"
    money = 500
    divin = $true
} | ConvertTo-Json -Depth 10

Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/create/" `
                  -Method POST `
                  -ContentType "application/json" `
                  -Body $body


Exemple récupération d'un joueur avec son id : 
Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/get/0kX4gctisIcOKvHDKJmlDRLSLFu2/" -Method GET


Exemple suppresion joueur : 
Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/delete/0kX4gctisIcOKvHDKJmlDRLSLFu2/" -Method DELETE

Modification d'un joueur
Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/update/0kX4gctisIcOKvHDKJmlDRLSLFu2/" `
    -Method PATCH `
    -Headers @{"Content-Type"="application/json"} `
    -Body '{"pseudo_minecraft": "Yololaxe_", "rank": "Admin"}'



$body = @{
    id = "0kX4gctisIcOKvHDKJmlDRLSLFu2"
    id_minecraft = "010203040506070809"
    pseudo_minecraft = "Gotaga"
    name = "Technoblade"
    surname = "Never dies"
    description = "Un player"
    rank = "Esclave"
    money = 0
    divin = $false

    # Liste des traits et actions
    trait = @()
    actions = @()

    # Statistiques
    life = 10
    strength = 1
    speed = 100
    reach = 5
    resistance = 0
    place = 18
    haste = 78
    regeneration = 1

    # Capacités
    dodge = 2
    discretion = 3
    charisma = 1
    rethoric = 1
    mana = 100
    negotiation = 0
    influence = 1
    skill = 100

    # Expériences
    experiences = @{
        "Lumberjack" = 0
        "Artisan" = 0
        "Naval_Architect" = 0
        "Carpenter" = 0
        "Miner" = 0
        "Blacksmith" = 0
        "Glassmaker" = 0
        "Mason" = 0
        "Farmer" = 0
        "Breeder" = 0
        "Fisherman" = 0
        "Innkeeper" = 0
        "Guard" = 0
        "Merchant" = 0
        "Transporter" = 0
        "Explorer" = 0
        "Builder" = 0
        "Bestiary" = 0
        "Politician" = 0
        "Banker" = 0
    }
} | ConvertTo-Json -Depth 10

Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/create/" `
                  -Method POST `
                  -ContentType "application/json" `
                  -Body $body
