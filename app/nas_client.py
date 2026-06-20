# -*- coding: utf-8 -*-
"""
Client HTTP léger pour le serveur de sync NAS.
Aucune dépendance externe : urllib uniquement.
"""

import json
import urllib.request
import urllib.error


class NasClient:
    def __init__(self, url, api_key):
        self.url     = url.rstrip("/")
        self.api_key = api_key

    def _req(self, method, path, data=None):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
        req  = urllib.request.Request(
            self.url + path,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key":    self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def ping(self):
        return self._req("GET", "/sante") is not None

    # -------- joueurs

    def push_joueur(self, nom, addon_data):
        """Envoie les données de scan d'un joueur vers le NAS."""
        items_str = {
            str(k): v for k, v in (addon_data.get("items") or {}).items()
        }
        payload = {
            "joueur":       addon_data.get("joueur", nom),
            "realm":        addon_data.get("realm", ""),
            "derniere_maj": addon_data.get("derniere_maj", 0),
            "scan_complet": addon_data.get("scan_complet", False),
            "items":        items_str,
            "mes_annonces": addon_data.get("mes_annonces", []),
            "mes_ventes":   addon_data.get("mes_ventes", []),
        }
        return self._req("POST", f"/joueur/{nom}", payload)

    def get_joueurs(self):
        return self._req("GET", "/joueurs") or []

    # -------- marché

    def get_marche(self):
        return self._req("GET", "/marche")

    def push_marche_blizzard(self, cache):
        """Envoie le snapshot Blizzard au NAS pour partage avec tous les joueurs."""
        return self._req("POST", "/marche/blizzard", {
            "timestamp": cache.get("timestamp", 0),
            "realm_id":  cache.get("realm_id", 0),
            "items":     cache.get("items", {}),
        })
