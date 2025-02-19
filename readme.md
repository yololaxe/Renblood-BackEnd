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
    id_minecraft = "Yololaxe"
    pseudo_minecraft = "Yololaxe_"
    name = "John"
    surname = "Doe"
    description = "Un aventurier intrépide."  # Éviter les accents pour tester
    rank = "Chevalier"
    money = 500.0
    divin = $false
    life = 15
    strength = 3
    speed = 120
    reach = 6
    resistance = 2
    place = 20
    haste = 85
    regeneration = 2
    trait = @("Brave", "Loyal")
    actions = @("Sword Mastery", "Shield Block")
    dodge = 4
    discretion = 2
    charisma = 5
    rethoric = 3
    mana = 80
    negotiation = 2
    influence = 4
    skill = 110
    experiences = @{
        jobs = @{
            lumberjack = @{
                xp = 1200
                level = 9
                progression = @($true, $true, $false, $true, $false, $false, $false, $false, $false, $false)
                choose_lvl_10 = "/firecamp"
            }
        }
    }
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
}

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/create/" `
    -Method POST `
    -Headers $headers `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
    -UseBasicParsing
