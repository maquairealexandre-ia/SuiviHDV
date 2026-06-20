-- SuiviHDV.lua  (chargé en dernier, après Scanner.lua et Sales.lua)
-- Point d'entrée : initialisation, gestion des événements, commande slash.

-- SavedVariables : WoW écrit ce tableau dans SuiviHDV.lua à chaque /logout ou /reload
SuiviHDVDB = SuiviHDVDB or {}

SuiviHDV = {}
local addon = SuiviHDV

function addon:print(msg)
    print("|cffffd100[SuiviHDV]|r " .. tostring(msg))
end

-- ------------------------------------------------------------------ init

local function init()
    -- Garantit que toutes les clés existent dès le premier lancement
    SuiviHDVDB.version      = 1
    SuiviHDVDB.joueur       = UnitName("player")
    SuiviHDVDB.realm        = GetRealmName()
    SuiviHDVDB.items        = SuiviHDVDB.items       or {}
    SuiviHDVDB.mes_annonces = SuiviHDVDB.mes_annonces or {}
    SuiviHDVDB.scan_complet = SuiviHDVDB.scan_complet or false
    SuiviHDVDB.derniere_maj = SuiviHDVDB.derniere_maj or 0

    SuiviHDV_Scanner:init()
    SuiviHDV_Sales:init()

    addon:print("Prêt. Allez à l'HdV pour lancer le scan.")
end

-- ------------------------------------------------------------------ événements

local frame = CreateFrame("Frame", "SuiviHDVFrame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("AUCTION_HOUSE_SHOW")
frame:RegisterEvent("AUCTION_HOUSE_CLOSED")
frame:RegisterEvent("AUCTION_ITEM_LIST_UPDATED")
frame:RegisterEvent("OWNED_AUCTIONS_UPDATED")
frame:RegisterEvent("MAIL_INBOX_UPDATE")

frame:SetScript("OnEvent", function(self, event)
    if event == "PLAYER_LOGIN" then
        init()

    elseif event == "AUCTION_HOUSE_SHOW" then
        SuiviHDV_Scanner:startScan()

    elseif event == "AUCTION_HOUSE_CLOSED" then
        SuiviHDV_Scanner:onClose()

    elseif event == "AUCTION_ITEM_LIST_UPDATED" then
        SuiviHDV_Scanner:onResults()

    elseif event == "OWNED_AUCTIONS_UPDATED" then
        -- Données de vos propres annonces disponibles
        SuiviHDV_Sales:readOwnAuctions()

    elseif event == "MAIL_INBOX_UPDATE" then
        SuiviHDV_Sales:scanMailbox()
    end
end)

-- ------------------------------------------------------------------ slash command

SLASH_SUIVIHDV1 = "/suivihdv"
SlashCmdList["SUIVIHDV"] = function()
    local items = 0
    for _ in pairs(SuiviHDVDB.items) do items = items + 1 end
    local ventes   = #SuiviHDVDB.mes_ventes
    local annonces = #SuiviHDVDB.mes_annonces
    local maj      = SuiviHDVDB.derniere_maj
    local age      = maj > 0 and (math.floor((time() - maj) / 60) .. " min") or "jamais"
    local complet  = SuiviHDVDB.scan_complet and "oui" or "partiel"
    addon:print(string.format(
        "HdV: %d articles (%s) | Vos annonces: %d | Ventes: %d | Mise à jour: il y a %s",
        items, complet, annonces, ventes, age
    ))
end
