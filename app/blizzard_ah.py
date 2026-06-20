# -*- coding: utf-8 -*-
"""
Récupération des données de l'Hôtel des Ventes via l'API publique Blizzard.
Mise à jour toutes les heures (Blizzard actualise leurs snapshots à cette fréquence).
"""

import gzip
import json
import os
import re
import ssl
import time
import urllib.request
import urllib.parse
import base64

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class BlizzardAH:
    def __init__(self, client_id, client_secret, region, cache_path):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region.lower()
        self.cache_path = cache_path   # fichier JSON local
        self._token = None
        self._token_expiry = 0

    # ------------------------------------------------------------------ auth

    def _get_token(self):
        if not self.client_id or not self.client_secret:
            return None
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        url = f"https://{self.region}.battle.net/oauth/token"
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                payload = json.loads(resp.read())
            self._token = payload["access_token"]
            self._token_expiry = time.time() + payload.get("expires_in", 3600)
            return self._token
        except Exception:
            return None

    def _get(self, url):
        token = self._get_token()
        if not token:
            return None
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    # --------------------------------------------------------- realm ID

    def resolve_realm_id(self, realm_slug):
        """Retourne l'ID du royaume connecté depuis un slug (ex: 'chogall')."""
        url = (f"https://{self.region}.api.blizzard.com/data/wow/realm/{realm_slug}"
               f"?namespace=dynamic-{self.region}&locale=fr_FR")
        data = self._get(url)
        if not data:
            return None
        href = (data.get("connected_realm") or {}).get("href", "")
        m = re.search(r'/connected-realm/(\d+)', href)
        return int(m.group(1)) if m else None

    # --------------------------------------------------------- fetch data

    def fetch(self, connected_realm_id):
        """
        Télécharge toutes les annonces du royaume (items + commodités),
        agrège par item_id et sauvegarde le cache.
        Retourne le dict agrégé ou None en cas d'erreur.
        """
        base = (f"https://{self.region}.api.blizzard.com"
                f"/data/wow/connected-realm/{connected_realm_id}")
        ns = f"dynamic-{self.region}"

        items_data = self._get(f"{base}/auctions?namespace={ns}")
        comm_data  = self._get(f"{base}/auctions/commodities?namespace={ns}")

        if items_data is None and comm_data is None:
            return None

        aggregated = {}

        for auction in (items_data or {}).get("auctions", []):
            item_id = str((auction.get("item") or {}).get("id", 0))
            if not item_id or item_id == "0":
                continue
            price = auction.get("unit_price") or auction.get("buyout") or 0
            qty   = auction.get("quantity", 1)
            owner = auction.get("owner", "")
            if item_id not in aggregated:
                aggregated[item_id] = {"qte": 0, "prix_min": 0, "vendeurs": []}
            d = aggregated[item_id]
            d["qte"] += qty
            if price and (d["prix_min"] == 0 or price < d["prix_min"]):
                d["prix_min"] = price
            if owner and owner not in d["vendeurs"]:
                d["vendeurs"].append(owner)

        for auction in (comm_data or {}).get("auctions", []):
            item_id = str((auction.get("item") or {}).get("id", 0))
            if not item_id or item_id == "0":
                continue
            price = auction.get("unit_price", 0)
            qty   = auction.get("quantity", 1)
            if item_id not in aggregated:
                aggregated[item_id] = {"qte": 0, "prix_min": 0, "vendeurs": []}
            d = aggregated[item_id]
            d["qte"] += qty
            if price and (d["prix_min"] == 0 or price < d["prix_min"]):
                d["prix_min"] = price

        cache = {
            "timestamp": int(time.time()),
            "realm_id": connected_realm_id,
            "items": aggregated,
        }
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

        return cache

    # --------------------------------------------------------- cache read

    def load_cache(self):
        """Charge le cache local. Retourne None si absent ou > 2h."""
        if not os.path.exists(self.cache_path):
            return None
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            if time.time() - cache.get("timestamp", 0) > 7200:
                return None
            return cache
        except Exception:
            return None
