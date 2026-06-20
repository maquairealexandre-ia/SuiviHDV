# -*- coding: utf-8 -*-
"""
Récupération des noms d'objets WoW.

Stratégie en 2 temps :
1. Un cache local (fichier JSON) pour ne jamais redemander deux fois le même objet.
2. Si l'objet est inconnu, on interroge l'API Blizzard officielle.

L'utilisateur doit fournir UNE FOIS son Client ID et Client Secret Blizzard
(création gratuite sur https://develop.battle.net/access/clients).
Si aucune clé n'est configurée, l'appli affiche les identifiants bruts (i:259085)
sans planter.
"""

import json
import os
import ssl
import time
import urllib.request
import urllib.parse

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class ItemNames:
    def __init__(self, cache_path, client_id="", client_secret="", region="eu", locale="fr_FR", icons_dir=""):
        self.cache_path = cache_path
        self.icons_dir = icons_dir
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.locale = locale
        self._token = None
        self._token_expiry = 0
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False)
        except Exception:
            pass

    def _item_id(self, item_string):
        # 'i:259085::2:43:12769' -> 259085
        try:
            return item_string.split(":")[1]
        except Exception:
            return None

    def _get_token(self):
        if self.client_id == "" or self.client_secret == "":
            return None
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        url = f"https://{self.region}.battle.net/oauth/token"
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        import base64
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode())
            self._token = payload["access_token"]
            self._token_expiry = time.time() + payload.get("expires_in", 3600)
            return self._token
        except Exception:
            return None

    def get(self, item_string):
        """Renvoie le nom de l'objet, ou l'identifiant brut si introuvable."""
        item_id = self._item_id(item_string)
        if item_id is None:
            return item_string
        if item_id in self.cache:
            return self.cache[item_id]

        token = self._get_token()
        if token is None:
            return item_string

        url = (f"https://{self.region}.api.blizzard.com/data/wow/item/{item_id}"
               f"?namespace=static-{self.region}&locale={self.locale}")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode())
            name = payload.get("name", item_string)
            self.cache[item_id] = name
            self._save_cache()
            return name
        except Exception:
            return item_string

    def get_icon(self, item_string):
        """Renvoie l'URL de l'icône de l'objet, ou chaîne vide si introuvable."""
        item_id = self._item_id(item_string)
        if item_id is None:
            return ""
        cache_key = f"icon_{item_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        token = self._get_token()
        if token is None:
            return ""

        url = (f"https://{self.region}.api.blizzard.com/data/wow/media/item/{item_id}"
               f"?namespace=static-{self.region}")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read().decode())
            icon_url = ""
            for asset in payload.get("assets", []):
                if asset.get("key") == "icon":
                    icon_url = asset.get("value", "")
                    break
            self.cache[cache_key] = icon_url
            self._save_cache()
            return icon_url
        except Exception:
            return ""

    def get_icon_path(self, item_string):
        """Renvoie le chemin local de l'icône (télécharge depuis Wowhead si absente)."""
        if not self.icons_dir:
            return ""
        icon_url = self.get_icon(item_string)
        if not icon_url:
            return ""
        # Extraire le nom de l'icône depuis l'URL Blizzard
        # ex: .../inv_misc_coin_16.jpg -> inv_misc_coin_16
        icon_name = icon_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        local_path = os.path.join(self.icons_dir, icon_name + ".jpg")
        if os.path.exists(local_path):
            return local_path
        # Télécharger depuis Wowhead
        wowhead_url = f"https://wow.zamimg.com/images/wow/icons/large/{icon_name}.jpg"
        try:
            req = urllib.request.Request(wowhead_url, headers={"User-Agent": "SuiviHDV"})
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                data = resp.read()
            with open(local_path, "wb") as f:
                f.write(data)
            return local_path
        except Exception:
            return ""

    def prefetch(self, item_strings, progress=None):
        """Pré-charge une liste de noms (utile au démarrage). progress(i, total) optionnel."""
        unique = []
        seen = set()
        for s in item_strings:
            iid = self._item_id(s)
            if iid and iid not in self.cache and iid not in seen:
                seen.add(iid)
                unique.append(s)
        total = len(unique)
        for i, s in enumerate(unique):
            self.get(s)
            if progress:
                progress(i + 1, total)
