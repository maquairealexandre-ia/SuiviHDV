-- Sales.lua
-- Détection des ventes personnelles (boîte aux lettres + annonces actives).

SuiviHDV_Sales = {}
local S = SuiviHDV_Sales

-- Patterns pour identifier les mails de l'Hôtel des Ventes (toutes locales)
local AH_SENDERS = {
    ["Auction House"]      = true,  -- EN
    ["Maison des ench"]    = true,  -- FR (préfixe suffisant)
    ["Casa de subastas"]   = true,  -- ES
    ["Auktionshaus"]       = true,  -- DE
    ["경매소"]              = true,  -- KR
    ["拍卖行"]              = true,  -- CN/TW
}

local function isAHMail(sender)
    if not sender then return false end
    for pattern in pairs(AH_SENDERS) do
        if sender:find(pattern, 1, true) then return true end
    end
    return false
end

-- ------------------------------------------------------------------ init

function S:init()
    SuiviHDVDB.mes_ventes    = SuiviHDVDB.mes_ventes    or {}
    SuiviHDVDB.mes_annonces  = SuiviHDVDB.mes_annonces  or {}
    SuiviHDVDB.ventes_vus    = SuiviHDVDB.ventes_vus    or {}
end

-- ------------------------------------------------------------------ mailbox

function S:scanMailbox()
    local num = GetInboxNumItems()
    local now = time()

    for i = 1, num do
        local _, _, sender, subject, money, _, _, _, _, wasReturned = GetInboxHeaderInfo(i)

        -- Mail de l'AH, avec de l'or, qui n'est pas un retour = vente réussie
        if isAHMail(sender) and money and money > 0 and not wasReturned then
            -- Clé de déduplication : sujet + montant (évite de compter deux fois)
            local uid = (subject or "") .. "|" .. tostring(money)
            if not SuiviHDVDB.ventes_vus[uid] then
                SuiviHDVDB.ventes_vus[uid] = true
                table.insert(SuiviHDVDB.mes_ventes, {
                    sujet = subject or "",
                    total = money,
                    t     = now,
                })
            end
        end
    end

    -- Limiter l'historique (garder les 500 plus récentes)
    while #SuiviHDVDB.mes_ventes > 500 do
        table.remove(SuiviHDVDB.mes_ventes, 1)
    end
    -- Limiter les clés de dédup (mémoire)
    local count = 0
    for k in pairs(SuiviHDVDB.ventes_vus) do
        count = count + 1
        if count > 2000 then SuiviHDVDB.ventes_vus[k] = nil end
    end

    -- Push temps réel vers l'application
    SuiviHDV:push({
        joueur  = SuiviHDVDB.joueur,
        realm   = SuiviHDVDB.realm,
        ventes  = SuiviHDVDB.mes_ventes,
    })
end

-- ------------------------------------------------------------------ annonces actives

-- Lit vos propres annonces depuis l'interface de l'HdV
function S:readOwnAuctions()
    SuiviHDVDB.mes_annonces = {}
    local num = C_AuctionHouse.GetNumOwnedAuctions()
    if not num or num == 0 then return end

    for i = 1, num do
        local info = C_AuctionHouse.GetOwnedAuctionInfo(i)
        if info and info.itemKey then
            table.insert(SuiviHDVDB.mes_annonces, {
                item = info.itemKey.itemID or 0,
                q    = info.quantity       or 1,
                p    = info.buyoutAmount   or 0,
                t    = time(),
            })
        end
    end

    -- Push temps réel vers l'application
    SuiviHDV:push({
        joueur   = SuiviHDVDB.joueur,
        realm    = SuiviHDVDB.realm,
        annonces = SuiviHDVDB.mes_annonces,
    })
end
