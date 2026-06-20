# -*- coding: utf-8 -*-
"""
Suivi Hôtel des Ventes — interface web stylée WoW.

L'application lance un mini-serveur local et ouvre une fenêtre native
(via pywebview) qui affiche l'interface HTML. Le moteur de données
(lecture TSM, rentabilité, alertes) est partagé avec la version précédente.
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import config
import tsm_parser as tsm
import addon_parser
from item_names import ItemNames
from blizzard_ah import BlizzardAH
from nas_client import NasClient


def ressource(rel):
    """Trouve un fichier qu'on soit en .exe (PyInstaller) ou en script normal."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class Moteur:
    """Contient l'état et toute la logique métier."""
    def __init__(self):
        self.cfg = config.load_config()
        self.state = config.load_state()
        self.names = self._make_names()
        self.blizzard_ah = self._make_blizzard_ah()
        self.nas = self._make_nas()
        self.data = None
        self.addon_data = None           # données de notre propre addon
        self.marche_cache = None         # cache marché Blizzard API
        self.watch_mtime = 0
        self.watch_addon_mtime = 0
        self.changed_flag = False
        self.marche_changed_flag = False
        self.statut = ""
        self.derniere_nouvelles = {}
        self.charger()
        threading.Thread(target=self._watch_loop, daemon=True).start()
        threading.Thread(target=self._marche_loop, daemon=True).start()

    def _make_names(self):
        return ItemNames(
            config.cache_path(),
            client_id=self.cfg.get("blizzard_client_id", ""),
            client_secret=self.cfg.get("blizzard_client_secret", ""),
            region=self.cfg.get("region", "eu"),
            locale=self.cfg.get("locale", "fr_FR"),
            icons_dir=config.icons_dir(),
        )

    def _make_blizzard_ah(self):
        ah_cache = os.path.join(config.config_dir(), "marche_cache.json")
        return BlizzardAH(
            client_id=self.cfg.get("blizzard_client_id", ""),
            client_secret=self.cfg.get("blizzard_client_secret", ""),
            region=self.cfg.get("region", "eu"),
            cache_path=ah_cache,
        )

    def _make_nas(self):
        url = self.cfg.get("nas_url", "")
        key = self.cfg.get("nas_api_key", "")
        return NasClient(url, key) if url else None

    def charger(self):
        path = self.cfg.get("tsm_file", "")
        if not path or not os.path.exists(path):
            self.data = None
            self.statut = "Aucun fichier TSM sélectionné. Ouvrez Réglages."
            return
        try:
            self.data = tsm.load(path)
            self.watch_mtime = os.path.getmtime(path)
        except Exception as e:
            self.data = None
            self.statut = f"Erreur de lecture : {e}"
            return
        # Détection nouvelles ventes
        prev = self.state.get("sales_count_by_player", {})
        nouvelles, current = tsm.detect_new_sales(self.data, prev)
        self.state["sales_count_by_player"] = current
        config.save_state(self.state)
        self.derniere_nouvelles = nouvelles
        self.statut = "Récupération des noms d'objets en cours…"
        # Pré-charger les noms en arrière-plan
        threading.Thread(target=self._prefetch, daemon=True).start()

    def _prefetch(self):
        if not self.data:
            return
        items = [r["itemString"] for r in self.data["sales"]]
        def progress(i, total):
            self.statut = f"Noms d'objets : {i}/{total}"
        self.names.prefetch(items, progress=progress)
        self.statut = "Prêt."
        self.changed_flag = True

    def _watch_loop(self):
        while True:
            try:
                # Surveiller l'addon en priorité, TSM en fallback
                addon_path = self.cfg.get("addon_file", "")
                tsm_path   = self.cfg.get("tsm_file", "")
                if addon_path and os.path.exists(addon_path):
                    m = os.path.getmtime(addon_path)
                    if m > self.watch_addon_mtime + 0.5:
                        self.watch_addon_mtime = m
                        self._charger_addon(addon_path)
                        self.changed_flag = True
                elif tsm_path and os.path.exists(tsm_path):
                    m = os.path.getmtime(tsm_path)
                    if m > self.watch_mtime + 0.5:
                        self.charger()
                        self.changed_flag = True
            except Exception:
                pass
            time.sleep(5)

    def _marche_loop(self):
        """Rafraîchit le marché toutes les heures (Blizzard API + push NAS)."""
        while True:
            try:
                self.marche_cache = self.blizzard_ah.load_cache()
                if self.marche_cache is None:
                    self._refresh_marche()
                elif self.nas:
                    # Partager le cache Blizzard avec tous les joueurs via le NAS
                    self.nas.push_marche_blizzard(self.marche_cache)
            except Exception:
                pass
            time.sleep(3600)

    def _charger_addon(self, path):
        try:
            self.addon_data = addon_parser.load(path)
            nb = len(self.addon_data.get("items", {}))
            self.statut = f"Addon: {nb} articles. Prêt."
            # Pousser vers le NAS en arrière-plan
            if self.nas and self.addon_data.get("joueur"):
                threading.Thread(
                    target=self.nas.push_joueur,
                    args=(self.addon_data["joueur"], self.addon_data),
                    daemon=True,
                ).start()
        except Exception as e:
            self.addon_data = None
            self.statut = f"Erreur lecture addon : {e}"

    def _refresh_marche(self):
        """Déclenche un rafraîchissement du marché depuis l'API Blizzard."""
        realm_id = self.cfg.get("connected_realm_id", 0)
        if not realm_id:
            slug = self.cfg.get("realm_slug", "")
            if slug:
                realm_id = self.blizzard_ah.resolve_realm_id(slug)
                if realm_id:
                    self.cfg["connected_realm_id"] = realm_id
                    config.save_config(self.cfg)
        if realm_id:
            self.marche_cache = self.blizzard_ah.fetch(realm_id)
            self.marche_changed_flag = True

    def _marche_json(self):
        # Priorité : NAS (agrège tous les joueurs) > cache Blizzard local
        source = "local"
        if self.nas:
            nas_data = self.nas.get_marche()
            if nas_data and nas_data.get("items"):
                cache = nas_data
                source = "nas"
            else:
                cache = self.marche_cache
        else:
            cache = self.marche_cache

        if not cache or not cache.get("items"):
            return {"erreur": "Marché non disponible. Configurez votre royaume et vos clés Blizzard dans Réglages."}

        joueurs_actifs = []
        if self.nas:
            joueurs_actifs = [j["nom"] for j in (self.nas.get_joueurs() or []) if j.get("actif")]

        lignes = []
        for item_id_str, d in cache["items"].items():
            item_str = f"i:{item_id_str}"
            nom = self.names.get(item_str)
            lignes.append({
                "item_id":  item_id_str,
                "nom":      nom,
                "qte":      d.get("qte", 0),
                "prix_min": d.get("prix_min", 0),
                "sources":  d.get("sources", d.get("vendeurs", [])),
            })
        lignes.sort(key=lambda x: x["qte"], reverse=True)

        ts = cache.get("timestamp", 0)
        age = ""
        if ts:
            minutes = int((time.time() - ts) / 60)
            age = f"il y a {minutes} min" if minutes < 60 else f"il y a {minutes // 60}h"

        return {
            "lignes":         lignes[:2000],
            "nb_total":       len(lignes),
            "age":            age,
            "source":         source,
            "joueurs_actifs": joueurs_actifs,
        }

    def data_json(self, perso):
        if not self.data:
            return {"erreur": self.statut or "Aucune donnée. Ouvrez Réglages pour choisir le fichier TSM."}
        self.cfg["last_player"] = perso
        config.save_config(self.cfg)
        sel = None if perso in ("", "Tous") else perso
        rows = tsm.compute_profitability(self.data, player=sel, source="Auction")
        out_rows = []
        for r in rows:
            item_id = r["itemString"].split(":")[1] if ":" in r["itemString"] else ""
            out_rows.append({
                "nom":          self.names.get(r["itemString"]),
                "item_id":      item_id,
                "qte_vendue":   r["qte_vendue"],
                "qte_expiree":  r["qte_expiree"],
                "revenu_total": r["revenu_total"],
                "prix_moyen":   r["prix_moyen"],
                "taux_reussite": r["taux_reussite"],
            })
        total = sum(r["revenu_total"] for r in rows)
        nb_ventes = sum(r["nb_transactions"] for r in rows)
        source = "Addon SuiviHDV" if self.cfg.get("addon_file") else "TradeSkillMaster"
        or_joueur = 0
        if self.addon_data and sel:
            or_joueur = self.addon_data.get("or_par_joueur", {}).get(sel, 0)
        return {
            "persos": ["Tous"] + self.data["players"],
            "perso_courant": self.cfg.get("last_player") or "Tous",
            "lignes": out_rows,
            "total": total,
            "nb_ventes": nb_ventes,
            "nouvelles": self.derniere_nouvelles,
            "statut": self.statut,
            "source": source,
            "or_joueur": or_joueur,
        }


MOTEUR = None
WINDOW = None
MAJ_WINDOW = None
MAJ_INFO = {"url": "", "version": "", "notes": "", "progression": -1, "erreur": ""}


def _telecharger_maj():
    import ssl, os, tempfile, subprocess, urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    MAJ_INFO["progression"] = 0
    MAJ_INFO["erreur"] = ""
    try:
        req = urllib.request.Request(MAJ_INFO["url"], headers={"User-Agent": "SuiviHDV"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            chunks = []
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if total:
                    MAJ_INFO["progression"] = int(downloaded / total * 100)

        data = b"".join(chunks)
        installeur = os.path.join(tempfile.gettempdir(), "SuiviHDV_Installeur.exe")
        with open(installeur, "wb") as f:
            f.write(data)

        MAJ_INFO["progression"] = 100
        time.sleep(0.5)
        # Lance l'installeur détaché puis quitte proprement
        subprocess.Popen(
            [installeur],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        time.sleep(1)
        os._exit(0)

    except Exception as e:
        MAJ_INFO["erreur"] = str(e)[:200]


MAJ_HTML = """<!DOCTYPE html><html lang=fr><head><meta charset=utf-8>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#1a1410;color:#f0e6d2;font-family:'Segoe UI',sans-serif;padding:24px;user-select:none;}
h2{color:#ffd100;font-size:17px;margin-bottom:6px;}
.versions{font-size:12px;color:#c9b285;margin-bottom:16px;}
.versions span{color:#ffd100;}
.notes-titre{font-size:12px;color:#c9b285;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}
.notes{background:#221a12;border:1px solid #3a2c1a;border-radius:5px;padding:12px;font-size:13px;
       color:#f0e6d2;max-height:180px;overflow-y:auto;white-space:pre-wrap;margin-bottom:20px;line-height:1.5;}
.notes::-webkit-scrollbar{width:8px;}
.notes::-webkit-scrollbar-track{background:#140f08;}
.notes::-webkit-scrollbar-thumb{background:#6b5a2f;border-radius:4px;}
.barre-fond{background:#221a12;border:1px solid #3a2c1a;border-radius:4px;height:22px;overflow:hidden;margin-bottom:10px;display:none;}
#barre{height:100%;background:linear-gradient(90deg,#5a4420,#ffd100);width:0%;transition:width .2s;border-radius:4px;}
#statut{font-size:12px;color:#c9b285;margin-bottom:16px;min-height:18px;}
.btns{display:flex;gap:10px;}
button{flex:1;padding:9px;border-radius:4px;font-size:13px;cursor:pointer;font-family:inherit;border:1px solid;}
#btn-ok{background:linear-gradient(180deg,#5a4420,#2e2210);border-color:#ffd100;color:#ffd100;}
#btn-ok:hover:not(:disabled){background:linear-gradient(180deg,#7a5a28,#4a3418);}
#btn-ok:disabled{opacity:.5;cursor:default;}
#btn-non{background:#221a12;border-color:#6b5a2f;color:#c9b285;}
#btn-non:hover:not(:disabled){border-color:#ffd100;color:#ffd100;}
</style></head><body>
<h2>Mise a jour disponible</h2>
<div class=versions>Version installee : <span>__ACTUELLE__</span> &nbsp;&rarr;&nbsp; Nouvelle version : <span>__NOUVELLE__</span></div>
<div class=notes-titre>Nouveautes</div>
<div class=notes>__NOTES__</div>
<div class=barre-fond id=barre-fond><div id=barre></div></div>
<div id=statut>Cliquez sur Mettre a jour pour telecharger et installer automatiquement.</div>
<div class=btns>
  <button id=btn-ok onclick=demarrer()>Telecharger et installer</button>
  <button id=btn-non onclick=ignorer()>Plus tard</button>
</div>
<script>
var _dl=false;
function demarrer(){
  if(_dl) return;
  _dl=true;
  document.getElementById('btn-ok').disabled=true;
  document.getElementById('btn-non').disabled=true;
  document.getElementById('barre-fond').style.display='block';
  document.getElementById('statut').textContent='Telechargement en cours...';
  fetch('/api/maj/telecharger');
  poll();
}
function ignorer(){ fetch('/api/maj/ignorer'); }
function poll(){
  fetch('/api/maj/progression').then(r=>r.json()).then(d=>{
    if(d.erreur){ document.getElementById('statut').textContent='Erreur : '+d.erreur;
      document.getElementById('btn-ok').disabled=false; document.getElementById('btn-non').disabled=false; _dl=false; return; }
    document.getElementById('barre').style.width=d.pct+'%';
    if(d.pct>=100){ document.getElementById('statut').textContent='Installation en cours... L application va redemarrer.'; }
    else { document.getElementById('statut').textContent='Telechargement : '+d.pct+' %'; setTimeout(poll,400); }
  }).catch(function(){ setTimeout(poll,400); });
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # silencieux

    def _send(self, content, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.end_headers()
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        path = parsed.path

        if path == "/" or path == "/index.html":
            with open(ressource(os.path.join("web", "index.html")), encoding="utf-8") as f:
                self._send(f.read(), "text/html")
            return

        if path == "/api/data":
            perso = q.get("perso", ["Tous"])[0]
            MOTEUR.changed_flag = False
            self._send(json.dumps(MOTEUR.data_json(perso), ensure_ascii=False))
            return

        if path == "/api/config":
            self._send(json.dumps({"sound_enabled": MOTEUR.cfg.get("sound_enabled", True)}))
            return

        if path == "/api/version":
            self._send(json.dumps({
                "changed":         MOTEUR.changed_flag,
                "marche_changed":  MOTEUR.marche_changed_flag,
            }))
            return

        if path == "/api/marche":
            MOTEUR.marche_changed_flag = False
            self._send(json.dumps(MOTEUR._marche_json(), ensure_ascii=False))
            return

        if path == "/api/addon":
            if not MOTEUR.addon_data:
                self._send(json.dumps({
                    "erreur": "Addon non configuré. Ouvrez Réglages et choisissez le fichier SuiviHDV.lua."
                }, ensure_ascii=False))
                return
            d = MOTEUR.addon_data
            annonces = []
            for a in d.get("mes_annonces", []):
                item_id = a["item"]
                nom = MOTEUR.names.get(f"i:{item_id}") if item_id else "?"
                qte = max(a["qte"], 1)
                annonces.append({
                    "item_id": item_id,
                    "nom":     nom,
                    "qte":     a["qte"],
                    "prix":    a["prix"],
                    "prix_u":  a["prix"] // qte,
                    "tls":     max(0, a.get("tls", 0) - (int(time.time()) - a.get("t", 0))) if a.get("t") else 0,
                })
            annonces.sort(key=lambda x: x["prix"], reverse=True)
            ventes = sorted(
                d.get("mes_ventes", []),
                key=lambda x: x["t"], reverse=True
            )[:100]
            derniere_maj = d.get("derniere_maj", 0)
            age = ""
            if derniere_maj:
                minutes = int((time.time() - derniere_maj) / 60)
                age = f"il y a {minutes} min" if minutes < 60 else f"il y a {minutes // 60}h"
            self._send(json.dumps({
                "joueur":        d.get("joueur", ""),
                "realm":         d.get("realm", ""),
                "nb_items_scan": len(d.get("items", {})),
                "age_scan":      age,
                "scan_complet":  d.get("scan_complet", False),
                "annonces":      annonces,
                "ventes":        ventes,
            }, ensure_ascii=False))
            return

        if path == "/api/marche/refresh":
            threading.Thread(target=MOTEUR._refresh_marche, daemon=True).start()
            self._send(json.dumps({"ok": True}))
            return

        if path == "/maj":
            html = (MAJ_HTML
                    .replace("__ACTUELLE__", config.VERSION)
                    .replace("__NOUVELLE__", MAJ_INFO.get("version", ""))
                    .replace("__NOTES__", MAJ_INFO.get("notes", "")))
            self._send(html, "text/html")
            return

        if path == "/api/maj/progression":
            self._send(json.dumps({
                "pct":    MAJ_INFO["progression"],
                "erreur": MAJ_INFO["erreur"],
            }))
            return

        if path == "/api/maj/ignorer":
            def _fermer():
                global MAJ_WINDOW
                if MAJ_WINDOW:
                    MAJ_WINDOW.destroy()
                    MAJ_WINDOW = None
            threading.Thread(target=_fermer, daemon=True).start()
            self._send(json.dumps({"ok": True}))
            return

        if path == "/api/maj/telecharger":
            if MAJ_INFO["progression"] < 0:
                threading.Thread(target=_telecharger_maj, daemon=True).start()
            self._send(json.dumps({"ok": True}))
            return

        if path == "/api/icone":
            item_id = q.get("id", [""])[0]
            if item_id:
                local_path = MOTEUR.names.get_icon_path(f"i:{item_id}")
                if local_path and os.path.exists(local_path):
                    try:
                        with open(local_path, "rb") as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Cache-Control", "max-age=86400")
                        self.end_headers()
                        self.wfile.write(data)
                        return
                    except Exception:
                        pass
            self.send_response(204)
            self.end_headers()
            return

        if path == "/api/son":
            actif = q.get("actif", ["1"])[0] == "1"
            MOTEUR.cfg["sound_enabled"] = actif
            config.save_config(MOTEUR.cfg)
            self._send(json.dumps({"ok": True}))
            return

        if path == "/api/reglages":
            # Ouvre la boîte de dialogue de réglages (fenêtre native)
            threading.Thread(target=ouvrir_reglages, daemon=True).start()
            self._send(json.dumps({"ok": True}))
            return

        self.send_response(404)
        self.end_headers()


def ouvrir_reglages():
    """Dialogue de réglages via une petite fenêtre webview secondaire."""
    import webview
    cfg = MOTEUR.cfg
    html = REGLAGES_HTML \
        .replace("__ADDON__",  cfg.get("addon_file", "")) \
        .replace("__FILE__",   cfg.get("tsm_file", "")) \
        .replace("__CID__",    cfg.get("blizzard_client_id", "")) \
        .replace("__CS__",     cfg.get("blizzard_client_secret", "")) \
        .replace("__REGION__", cfg.get("region", "eu")) \
        .replace("__REALM__",  cfg.get("realm_slug", "")) \
        .replace("__NAS__",    cfg.get("nas_url", "")) \
        .replace("__NASKEY__", cfg.get("nas_api_key", ""))
    win = webview.create_window("Réglages", html=html, width=580, height=560,
                                js_api=ReglagesAPI())
    # La fenêtre se ferme elle-même via l'API JS


class ReglagesAPI:
    def parcourir(self):
        import webview
        result = webview.windows[-1].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("Fichier TSM (TradeSkillMaster.lua)", "Tous (*.*)"))
        if result:
            return result[0]
        return ""

    def enregistrer(self, tsm_file, addon_file, cid, cs, region, realm_slug, nas_url, nas_api_key):
        MOTEUR.cfg.update({
            "tsm_file":              tsm_file,
            "addon_file":            addon_file,
            "blizzard_client_id":    cid.strip(),
            "blizzard_client_secret": cs.strip(),
            "region":                region,
            "realm_slug":            realm_slug.strip().lower(),
            "connected_realm_id":    0,
            "nas_url":               nas_url.strip(),
            "nas_api_key":           nas_api_key.strip(),
        })
        config.save_config(MOTEUR.cfg)
        MOTEUR.names       = MOTEUR._make_names()
        MOTEUR.blizzard_ah = MOTEUR._make_blizzard_ah()
        MOTEUR.nas         = MOTEUR._make_nas()
        MOTEUR.charger()
        MOTEUR.changed_flag = True
        # Résoudre l'ID royaume en arrière-plan si slug fourni
        if realm_slug.strip():
            threading.Thread(target=MOTEUR._refresh_marche, daemon=True).start()
        import webview
        webview.windows[-1].destroy()
        return True


REGLAGES_HTML = """<!DOCTYPE html><html lang=fr><head><meta charset=utf-8>
<style>
body{background:#1a1410;color:#f0e6d2;font-family:'Segoe UI',sans-serif;padding:18px;}
h2{color:#ffd100;font-size:16px;margin-bottom:4px;}
.note{color:#c9b285;font-size:12px;margin-bottom:14px;}
label{display:block;font-size:12px;color:#c9b285;margin:10px 0 3px;}
input,select{width:100%;background:#221a12;color:#f0e6d2;border:1px solid #6b5a2f;border-radius:4px;padding:7px 9px;font-size:13px;}
.row{display:flex;gap:8px;}.row input{flex:1;}
button{margin-top:16px;background:linear-gradient(180deg,#5a4420,#2e2210);color:#ffd100;border:1px solid #ffd100;border-radius:4px;padding:8px 16px;font-size:13px;cursor:pointer;}
button.sec{background:#221a12;border-color:#6b5a2f;color:#f0e6d2;}
a{color:#4a9eff;}
hr{border:none;border-top:1px solid #3a2c1a;margin:14px 0;}
</style></head><body>
<h2>Réglages</h2>
<div class=note>Fichier de données principal : notre addon (recommandé) ou TradeSkillMaster (legacy).</div>

<label>📦 Fichier SuiviHDV.lua <span style="color:#6b5a2f">(notre addon — recommandé)</span></label>
<div class=row><input id=addon value="__ADDON__"><button class=sec onclick=parcourirAddon()>Parcourir…</button></div>

<label>Fichier TradeSkillMaster.lua <span style="color:#6b5a2f">(optionnel — si vous n'utilisez pas notre addon)</span></label>
<div class=row><input id=file value="__FILE__"><button class=sec onclick=parcourir()>Parcourir…</button></div>

<hr>
<label>Client ID Blizzard <span style="color:#6b5a2f">(noms d'objets + marché — facultatif)</span></label>
<input id=cid value="__CID__">
<label>Client Secret Blizzard</label>
<input id=cs type=password value="__CS__">
<label>Région</label>
<select id=region></select>
<label>Slug du royaume <span style="color:#6b5a2f">(pour le marché — ex: chogall, kirin-tor)</span></label>
<input id=realm placeholder="ex: chogall" value="__REALM__">

<hr>
<label>URL du serveur NAS <span style="color:#6b5a2f">(sync multi-joueurs — ex: http://192.168.1.10:8765)</span></label>
<input id=nas placeholder="http://192.168.1.10:8765" value="__NAS__">
<label>Clé API NAS <span style="color:#6b5a2f">(même valeur que API_KEY dans docker-compose.yml)</span></label>
<input id=naskey type=password value="__NASKEY__">

<div><button onclick=enregistrer()>Enregistrer</button></div>
<script>
const r="__REGION__";["eu","us","kr","tw"].forEach(x=>{const o=document.createElement("option");o.value=x;o.textContent=x;if(x===r)o.selected=true;region.appendChild(o);});
async function parcourir(){const p=await window.pywebview.api.parcourir();if(p)file.value=p;}
async function parcourirAddon(){const p=await window.pywebview.api.parcourir();if(p)addon.value=p;}
async function enregistrer(){await window.pywebview.api.enregistrer(file.value,addon.value,cid.value,cs.value,region.value,realm.value,nas.value,naskey.value);}
</script></body></html>"""


def demarrer_serveur():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


def main():
    global MOTEUR, WINDOW
    MOTEUR = Moteur()
    port = demarrer_serveur()

    # Vérification de mise à jour en arrière-plan
    def check():
        global MAJ_WINDOW
        version, url, notes = config.check_update()
        if version and url:
            MAJ_INFO["url"]        = url
            MAJ_INFO["version"]    = version.lstrip("v")
            MAJ_INFO["notes"]      = (notes or "Aucune note de version.")
            MAJ_INFO["progression"] = -1
            MAJ_INFO["erreur"]     = ""
            import webview
            MAJ_WINDOW = webview.create_window(
                "Mise à jour disponible",
                url=f"http://127.0.0.1:{port}/maj",
                width=480, height=420, resizable=False)
    threading.Thread(target=check, daemon=True).start()

    import webview
    WINDOW = webview.create_window(
        "Suivi Hôtel des Ventes",
        url=f"http://127.0.0.1:{port}/",
        width=1000, height=680, min_size=(820, 560),
        background_color="#1a1410",
    )
    webview.start()


if __name__ == "__main__":
    main()
