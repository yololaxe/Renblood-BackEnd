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
