# Suivi Hôtel des Ventes — Guide de démarrage

Bonjour Alexandre ! Voici ton application. Ce guide est écrit étape par étape,
sans rien supposer de tes connaissances en programmation. Suis-le dans l'ordre.

---

## Ce que fait l'application

- Lit ton fichier **TradeSkillMaster.lua** (tes vraies données de jeu)
- Affiche un **classement de rentabilité** : quels objets te rapportent le plus
  (revenu total, prix moyen, nombre vendu, **taux de réussite** = vendus vs expirés)
- Te permet de **choisir le personnage** (Goldloum, Celinéa, Soléanne…)
- T'**alerte** (visuellement + son activable) quand de nouvelles ventes sont
  détectées, c'est-à-dire à chaque fois que tu te déconnectes du jeu
- Se **met à jour toute seule** : dès que tu quittes WoW, le fichier change et
  l'appli recharge les données dans les 5 secondes
- Vérifie au démarrage s'il existe une **nouvelle version** sur GitHub

---

L'interface est désormais **stylée comme l'hôtel des ventes de WoW** : panneau
parchemin sombre, bordures dorées, noms d'objets en bleu, montants en or, et un
petit son d'alerte quand de nouvelles ventes sont détectées.

## PARTIE 1 — Première utilisation (le plus simple)

Si tu veux juste **tester tout de suite** sans rien construire :

1. Installe **Python** depuis https://www.python.org/downloads/
   → Pendant l'installation, **coche la case « Add Python to PATH »** (important !)
2. Ouvre une invite de commande dans le dossier `app` et tape :
   `pip install pywebview`
   (c'est la seule dépendance, elle gère la jolie fenêtre)
3. Toujours dans `app`, double-clique sur **`main_web.py`**
   (s'il ne se lance pas, fais clic droit → « Ouvrir avec » → Python)
4. L'application s'ouvre. Au premier lancement, clique sur **« ⚙ Réglages »**
   pour choisir ton fichier `TradeSkillMaster.lua`.

C'est tout pour tester. Mais pour avoir une **vraie appli installable** (icône,
menu Démarrer, raccourci bureau), passe à la Partie 2.

> Note : il existe aussi une ancienne version simple sans dépendance
> (`app/main.py`, interface classique). La version recommandée est `main_web.py`.

---

## PARTIE 2 — Créer le fichier .exe (l'application autonome)

Le but : transformer le code en **un seul fichier `.exe`** que n'importe quel PC
Windows peut lancer, **même sans Python installé**.

1. Vérifie que **Python est installé** (voir Partie 1, étape 1).
2. Dans le dossier de l'application, **double-clique sur `1_construire_exe.bat`**.
3. Une fenêtre noire s'ouvre et travaille toute seule (1 à 3 minutes).
4. À la fin, tu trouves ton application ici : **`dist\SuiviHDV.exe`**

Tu peux déjà double-cliquer sur ce `.exe` : c'est ton appli !

---

## PARTIE 3 — Créer l'installeur (optionnel mais propre)

Pour avoir un vrai installeur (comme « Suivi de Production »), avec raccourci
bureau et désinstallation :

1. Installe **Inno Setup** (gratuit) : https://jrsoftware.org/isdl.php
2. Fais clic droit sur **`2_creer_installeur.iss`** → « Open with Inno Setup Compiler »
3. Dans Inno Setup, clique sur **Build → Compile** (ou le bouton ▶).
4. Ton installeur apparaît dans le dossier **`Sortie\`** :
   `SuiviHDV_Installeur_1.0.0.exe`

C'est ce fichier que tu peux garder, partager, ou publier sur GitHub.

---

## PARTIE 4 — Afficher les noms d'objets (au lieu de « i:259085 »)

Par défaut, l'appli affiche les **identifiants** des objets. Pour voir les vrais
noms (« Flacon d'… », etc.), il faut une clé gratuite Blizzard. Tu avais déjà
exploré l'API Blizzard, donc ça te sera familier :

1. Va sur https://develop.battle.net/access/clients (connexion avec ton compte
   Battle.net)
2. Clique sur **« Create Client »**, donne un nom quelconque (ex. « SuiviHDV »)
3. Tu obtiens un **Client ID** et un **Client Secret**
4. Dans l'appli : bouton **« Réglages… »** → colle les deux clés → Enregistrer
5. L'appli récupère alors automatiquement tous les noms (et les mémorise, donc
   c'est instantané les fois suivantes)

Sans cette étape, l'appli fonctionne quand même : elle affiche juste les
identifiants au lieu des noms. Rien ne plante.

---

## PARTIE 5 — Mettre à jour l'application plus tard

Quand tu voudras une nouvelle version (corrections, nouvelles fonctions) :

1. Ouvre `app\config.py`, change la ligne `VERSION = "1.0.0"` en `"1.1.0"`
2. Mets ton vrai pseudo GitHub dans les lignes `GITHUB_OWNER` et `GITHUB_REPO`
3. Reconstruis le `.exe` (Partie 2), puis l'installeur (Partie 3)
4. Sur GitHub, crée une **Release** avec le tag `v1.1.0` et attache ton `.exe`

Les utilisateurs (toi) seront alors prévenus automatiquement au démarrage.

---

## Où sont stockés mes réglages ?

Dans `C:\Utilisateurs\<toi>\AppData\Roaming\SuiviHDV` :
- `config.json` : tes réglages (fichier TSM, clés Blizzard, son…)
- `item_cache.json` : les noms d'objets déjà récupérés
- `state.json` : la mémoire des ventes (pour détecter les nouvelles)

Tu n'as jamais besoin d'y toucher, c'est automatique.

---

## En cas de souci

- **« Python n'est pas reconnu »** → tu as oublié de cocher « Add Python to PATH »
  à l'installation. Réinstalle Python en cochant la case.
- **L'appli ne trouve pas mes ventes** → vérifie que tu as bien **quitté WoW
  complètement** au moins une fois (le fichier n'est écrit qu'à ce moment-là).
- **Les noms ne s'affichent pas** → vérifie tes clés Blizzard dans Réglages, et
  que ton PC a accès à Internet.

Bon jeu et bonnes ventes !
