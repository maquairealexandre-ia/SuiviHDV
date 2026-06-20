# -*- coding: utf-8 -*-
"""
Lecture du fichier TradeSkillMaster.lua (SavedVariables).
Ce module ne dépend d'aucune bibliothèque externe : il lit le fichier texte
et en extrait les ventes, achats, expirations et annonces en cours.
"""

import re
from collections import defaultdict


def _find_realms(text):
    """Liste les royaumes présents dans le fichier (ex. 'Cho'gall')."""
    realms = set()
    for m in re.finditer(r'\["r@([^@]+)@internalData@csvSales"\]', text):
        realms.add(m.group(1))
    return sorted(realms)


def _extract_csv(text, key):
    """Récupère un bloc CSV stocké en valeur de chaîne TSM et renvoie une liste de dict."""
    m = re.search(r'\["' + re.escape(key) + r'"\]\s*=\s*"((?:[^"\\]|\\.)*)"', text)
    if not m:
        return []
    raw = m.group(1).replace("\\n", "\n")
    lines = raw.split("\n")
    if not lines:
        return []
    header = lines[0].split(",")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        parts = ln.split(",")
        if len(parts) < len(header):
            continue
        rows.append(dict(zip(header, parts[:len(header)])))
    return rows


def _extract_auction_quantity(text):
    """
    Récupère les quantités actuellement en vente, par personnage.
    Clé TSM : s@<Perso> - <Faction> - <Royaume>@internalData@auctionQuantity = { [itemString]=qte, ... }
    Renvoie : { "Perso": { itemString: quantite } }
    """
    result = defaultdict(dict)
    # On localise chaque bloc auctionQuantity et on lit son contenu entre accolades.
    pattern = re.compile(
        r'\["s@([^@]+?) - [^@]+? - [^@]+?@internalData@auctionQuantity"\]\s*=\s*\{(.*?)\n\}',
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        perso = m.group(1).strip()
        body = m.group(2)
        for mm in re.finditer(r'\["(i:[^"]+)"\]\s*=\s*(\d+)', body):
            result[perso][mm.group(1)] = int(mm.group(2))
    return result


def load(path):
    """
    Lit le fichier TSM et renvoie un dictionnaire structuré :
    {
      "realms": [...],
      "sales":   [ {itemString, quantity, price, otherPlayer, player, time, source}, ... ],
      "buys":    [...],
      "expired": [...],
      "cancelled": [...],
      "auction_qty": { perso: { itemString: qte } },
      "players": [...]
    }
    Les montants 'price' sont en cuivre (TSM stocke tout en cuivre).
    Dans csvSales/csvExpired, 'price' est le montant TOTAL de la ligne.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    realms = _find_realms(text)
    sales, buys, expired, cancelled = [], [], [], []
    for realm in realms:
        sales += _extract_csv(text, f"r@{realm}@internalData@csvSales")
        buys += _extract_csv(text, f"r@{realm}@internalData@csvBuys")
        expired += _extract_csv(text, f"r@{realm}@internalData@csvExpired")
        cancelled += _extract_csv(text, f"r@{realm}@internalData@csvCancelled")

    auction_qty = _extract_auction_quantity(text)

    players = sorted({r.get("player", "") for r in sales if r.get("player")})

    return {
        "realms": realms,
        "sales": sales,
        "buys": buys,
        "expired": expired,
        "cancelled": cancelled,
        "auction_qty": auction_qty,
        "players": players,
    }


def compute_profitability(data, player=None, source="Auction"):
    """
    Agrège les ventes par objet pour calculer la rentabilité.
    - player : si fourni, ne garde que ce personnage. Sinon, tous.
    - source : 'Auction' pour l'hôtel des ventes (par défaut), None pour tout inclure.

    Renvoie une liste triée par revenu total décroissant :
    [ {itemString, qte_vendue, qte_expiree, revenu_total, prix_moyen, taux_reussite}, ... ]
    """
    sales = data["sales"]
    expired = data["expired"]

    def keep(r):
        if player and r.get("player") != player:
            return False
        if source and r.get("source") != source:
            return False
        return True

    agg = defaultdict(lambda: {"qte": 0, "total": 0, "nb": 0})
    for r in sales:
        if not keep(r):
            continue
        item = r["itemString"]
        agg[item]["qte"] += int(r["quantity"])
        agg[item]["total"] += int(r["price"])
        agg[item]["nb"] += 1

    exp_count = defaultdict(int)
    for r in expired:
        if player and r.get("player") != player:
            continue
        exp_count[r["itemString"]] += int(r.get("quantity", 1))

    result = []
    for item, d in agg.items():
        qte = d["qte"]
        exp = exp_count.get(item, 0)
        total_tries = qte + exp
        taux = round(100 * qte / total_tries) if total_tries else 100
        prix_moyen = round(d["total"] / qte) if qte else 0
        result.append({
            "itemString": item,
            "qte_vendue": qte,
            "qte_expiree": exp,
            "revenu_total": d["total"],
            "prix_moyen": prix_moyen,
            "taux_reussite": taux,
            "nb_transactions": d["nb"],
        })

    result.sort(key=lambda x: x["revenu_total"], reverse=True)
    return result


def detect_new_sales(data, previous_count_by_player):
    """
    Compare le nombre de ventes par personnage avec un état précédent
    pour repérer les nouvelles ventes (utilisé pour les alertes).
    previous_count_by_player : { player: nb_ventes_precedent }
    Renvoie : (nouvelles_par_player, total_count_by_player)
    """
    current = defaultdict(int)
    for r in data["sales"]:
        if r.get("source") == "Auction":
            current[r.get("player", "")] += 1

    nouvelles = {}
    for player, cnt in current.items():
        prev = previous_count_by_player.get(player, None)
        if prev is not None and cnt > prev:
            nouvelles[player] = cnt - prev
    return nouvelles, dict(current)


def copper_to_gold_str(copper):
    """Convertit un montant en cuivre en chaîne lisible 'X po Y pa Z pc'."""
    copper = int(copper)
    g = copper // 10000
    s = (copper % 10000) // 100
    c = copper % 100
    parts = []
    if g:
        parts.append(f"{g:,}".replace(",", " ") + " po")
    if s:
        parts.append(f"{s} pa")
    if c:
        parts.append(f"{c} pc")
    return " ".join(parts) if parts else "0"
