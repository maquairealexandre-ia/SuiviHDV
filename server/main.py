# -*- coding: utf-8 -*-
"""
SuiviHDV — Serveur de synchronisation (NAS).
Stocke et agrège les données de scan de chaque joueur.
Déploiement : docker-compose up -d
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ------------------------------------------------------------------ config

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
API_KEY  = os.environ.get("API_KEY", "changez-moi")
TTL_JOUEUR   = 7200    # données d'un joueur ignorées si > 2h
TTL_BLIZZARD = 7200    # cache Blizzard ignoré si > 2h

DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SuiviHDV Sync", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ------------------------------------------------------------------ auth

def verifier_cle(x_api_key: Optional[str] = Header(None)):
    if API_KEY != "none" and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")

# ------------------------------------------------------------------ modèles

class DonneesJoueur(BaseModel):
    joueur:      str
    realm:       str
    derniere_maj: int
    scan_complet: bool = False
    items:       dict = {}   # { "item_id": {"qte": int, "prix_min": int} }
    mes_annonces: list = []
    mes_ventes:  list = []

class DonneesBlizzard(BaseModel):
    timestamp: int
    realm_id:  int
    items:     dict = {}   # { "item_id": {"qte": int, "prix_min": int, "vendeurs": list} }

# ------------------------------------------------------------------ routes

@app.get("/")
def racine():
    joueurs = _liste_joueurs_actifs()
    return {
        "service":  "SuiviHDV Sync",
        "version":  "1.0.0",
        "joueurs_actifs": len(joueurs),
        "ts": int(time.time()),
    }

@app.get("/sante")
def sante():
    return {"statut": "ok", "ts": int(time.time())}

# -------------------- joueurs

@app.post("/joueur/{nom}", dependencies=[Depends(verifier_cle)])
def push_joueur(nom: str, data: DonneesJoueur):
    """Reçoit et stocke le scan HdV d'un joueur."""
    path = DATA_DIR / f"joueur_{nom}.json"
    payload = data.model_dump()
    payload["_recu_le"] = int(time.time())
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "items": len(data.items)}

@app.get("/joueur/{nom}", dependencies=[Depends(verifier_cle)])
def get_joueur(nom: str):
    path = DATA_DIR / f"joueur_{nom}.json"
    if not path.exists():
        raise HTTPException(404, "Joueur introuvable")
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/joueurs", dependencies=[Depends(verifier_cle)])
def list_joueurs():
    """Liste tous les joueurs ayant envoyé des données."""
    return _liste_joueurs_actifs(inclure_inactifs=True)

# -------------------- marché agrégé

@app.get("/marche", dependencies=[Depends(verifier_cle)])
def get_marche():
    """
    Agrège les données de tous les joueurs + cache Blizzard.
    Un item vu par plusieurs sources prend la quantité totale et le prix min.
    """
    aggregated = {}
    now = int(time.time())

    # Données des joueurs (scans HdV en direct)
    for f in DATA_DIR.glob("joueur_*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if now - d.get("_recu_le", 0) > TTL_JOUEUR:
                continue
            joueur = d.get("joueur", "?")
            for item_id, info in (d.get("items") or {}).items():
                _merge(aggregated, str(item_id), info.get("qte", 0), info.get("prix_min", 0), joueur)
        except Exception:
            pass

    # Cache Blizzard API (snapshot horaire complet)
    bc_path = DATA_DIR / "marche_blizzard.json"
    if bc_path.exists():
        try:
            bc = json.loads(bc_path.read_text(encoding="utf-8"))
            if now - bc.get("timestamp", 0) <= TTL_BLIZZARD:
                for item_id, info in (bc.get("items") or {}).items():
                    vendeurs = info.get("vendeurs", [])
                    _merge(aggregated, str(item_id), info.get("qte", 0), info.get("prix_min", 0),
                           vendeurs[0] if vendeurs else "API Blizzard")
        except Exception:
            pass

    return {
        "items":     aggregated,
        "nb_total":  len(aggregated),
        "timestamp": now,
    }

@app.post("/marche/blizzard", dependencies=[Depends(verifier_cle)])
def push_marche_blizzard(data: DonneesBlizzard):
    """Reçoit un snapshot complet de l'API Blizzard et le stocke."""
    path = DATA_DIR / "marche_blizzard.json"
    payload = data.model_dump()
    payload["timestamp"] = int(time.time())
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "items": len(data.items)}

# ------------------------------------------------------------------ helpers

def _merge(agg, item_id, qte, prix, source):
    if item_id not in agg:
        agg[item_id] = {"qte": 0, "prix_min": 0, "sources": []}
    d = agg[item_id]
    d["qte"] += qte
    if prix and (d["prix_min"] == 0 or prix < d["prix_min"]):
        d["prix_min"] = prix
    if source and source not in d["sources"]:
        d["sources"].append(source)

def _liste_joueurs_actifs(inclure_inactifs=False):
    now = int(time.time())
    joueurs = []
    for f in DATA_DIR.glob("joueur_*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            age = now - d.get("_recu_le", 0)
            if not inclure_inactifs and age > TTL_JOUEUR:
                continue
            joueurs.append({
                "nom":         d.get("joueur", f.stem.replace("joueur_", "")),
                "realm":       d.get("realm", ""),
                "nb_items":    len(d.get("items", {})),
                "derniere_maj": d.get("_recu_le", 0),
                "actif":       age <= TTL_JOUEUR,
            })
        except Exception:
            pass
    return sorted(joueurs, key=lambda x: x["derniere_maj"], reverse=True)
