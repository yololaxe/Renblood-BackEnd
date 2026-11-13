# Répertoire des personnages et profils de jeu

La fiche de lore publiée (`wiki_versions`) reste distincte du profil `npcs`, du compte `players` et de ses apparitions `npc_spawns`.

`character_links` conserve le lien par NPC ID stable, sa révision, le personnage et le compte éventuel. Plusieurs anciens NPC IDs peuvent représenter le même personnage (Carl Sand, Ava, Isaure). Il ne faut pas fusionner leurs identifiants : les quêtes peuvent les référencer.

Les liaisons utilisent des transactions MongoDB, un index unique sur le compte et un verrou par personnage. Un compte ne contrôle qu’un profil et un personnage n’a qu’un contrôleur. Les tentatives répétées avec le même `operation_id` renvoient leur reçu ; une révision périmée donne 409. Aucune opération de ce module n’écrit dans `players`, les banques ou les inventaires.

Archiver un profil préserve son identité, le lore et les références de quêtes. Le compte reste attribué jusqu’à sa dissociation explicite. Tout profil correspondant à un personnage contrôlé par un joueur voit ses apparitions automatiques désactivées, y compris ses anciens doublons. Les API publiques n’exposent pas le compte associé. `configured_enabled` conserve la configuration éditable indépendamment de cette exclusion.

`character_link_audit` contient les modifications privées. L’outbox `character_identity_outbox` publie des événements UPSERT dans le journal existant ; un échec est repris au prochain sondage des mods. Les répétitions sont sans effet supplémentaire. Aucun nouveau sondage par tick n’est ajouté.

L’édition du lore crée un brouillon explicite du WikiStore existant, avec aperçu et publication contrôlée. Les conflits de version ne doivent pas écraser un autre brouillon. Seuls les champs publics sont acceptés ; un proche nécessite un lien parent/enfant/conjoint/fratrie explicite. Ne jamais importer ici des secrets de préparation.

API privée : `/api/characters/v1/admin/`, `bind/`, `profiles/`, `lore/<id>/`, `prepare/`, `publish/`. Toutes exigent Firebase Admin. Écran : `/admin/characters`.

Tests sans base : `python manage.py test characters.test_views npcs.tests wiki.test_service wiki.test_views`. Tests transactionnels : définir explicitement `RENBLOOD_IDENTITY_TEST_MONGO_URI`, puis exécuter `python -m unittest characters.test_integration`. Ces tests créent une base `renblood_identity_test_<12 caractères>` et suppriment uniquement cette base. Ils ne réutilisent pas une base de production/staging comme destination.

Le journal `npcs.native_changes.ChangeLog` alloue et insère une révision dans la même transaction : un sondage ne peut dépasser un événement non encore commité. Djongo ne générait pas les BigAutoField dans la collection de production. `repair_missing_revisions()` récupère les anciennes notifications sans modifier leur contenu ; exécuter seulement avec sauvegarde et base cible explicitement vérifiée.
