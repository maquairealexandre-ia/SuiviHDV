-- Scanner.lua
-- Scan de l'HdV en arrière-plan, sans ralentir le jeu.
-- Technique : on collecte les résultats au fil des événements et on les traite
-- en petits lots (BATCH_SIZE) via C_Timer.After(0) = tick suivant, jamais en bloc.

SuiviHDV_Scanner = {}
local S = SuiviHDV_Scanner

local BATCH_SIZE  = 150   -- items traités par tick (ajuster si micro-lag)
local TTL_SECONDES = 7200 -- on vire les items non vus depuis > 2h

local isScanning = false
local pending    = {}  -- résultats bruts en attente de traitement
local numSeen    = 0   -- combien de résultats on a déjà collectés

-- ------------------------------------------------------------------ init

function S:init()
    isScanning = false
    pending    = {}
    numSeen    = 0
end

-- ------------------------------------------------------------------ scan

function S:startScan()
    if isScanning then return end
    isScanning = true
    pending    = {}
    numSeen    = 0

    -- Nettoyer les entrées périmées avant d'ajouter les nouvelles
    local now = time()
    for id, d in pairs(SuiviHDVDB.items) do
        if (d.t or 0) < now - TTL_SECONDES then
            SuiviHDVDB.items[id] = nil
        end
    end

    SuiviHDV:print("Scan HdV démarré…")
    C_AuctionHouse.SendBrowseQuery({
        searchString    = "",
        sorts           = {},
        minLevel        = nil,
        maxLevel        = nil,
        filters         = Enum.AuctionHouseFilter.None,
        itemClassFilters = {},
    })
end

-- ------------------------------------------------------------------ résultats

-- Appelé sur AUCTION_ITEM_LIST_UPDATED (peut arriver plusieurs fois en rafale)
function S:onResults()
    if not isScanning then return end

    local total = C_AuctionHouse.GetNumBrowseResults()
    for i = numSeen + 1, total do
        local r = C_AuctionHouse.GetBrowseResultByIndex(i)
        if r and r.itemKey then
            pending[#pending + 1] = r
        end
    end
    numSeen = total

    -- Lancer le traitement en arrière-plan (pas dans cet événement)
    C_Timer.After(0, function() S:processBatch() end)

    -- Blizzard nous dit si tous les résultats sont arrivés
    if C_AuctionHouse.HasFullBrowseResults() then
        isScanning = false
        -- processBatch finira le travail et appellera _saveResults
    end
end

-- Traite BATCH_SIZE items puis reprogramme si nécessaire
function S:processBatch()
    local t    = time()
    local done = 0

    while #pending > 0 and done < BATCH_SIZE do
        local r  = table.remove(pending, 1)
        local id = r.itemKey.itemID
        SuiviHDVDB.items[id] = { q = r.totalQuantity, p = r.minPrice, t = t }
        done = done + 1
    end

    if #pending > 0 then
        -- Il reste du travail → prochain tick
        C_Timer.After(0, function() S:processBatch() end)
    elseif not isScanning then
        -- Tout traité + scan terminé → on consolide
        S:_saveResults()
    end
    -- Si isScanning est encore vrai : on attend encore des événements
end

function S:_saveResults()
    SuiviHDVDB.derniere_maj  = time()
    SuiviHDVDB.scan_complet  = true
    SuiviHDVDB.joueur        = UnitName("player")
    SuiviHDVDB.realm         = GetRealmName()

    local count = 0
    for _ in pairs(SuiviHDVDB.items) do count = count + 1 end
    SuiviHDV:print(count .. " articles enregistrés.")
end

-- ------------------------------------------------------------------ fermeture HdV

function S:onClose()
    if isScanning or #pending > 0 then
        isScanning = false
        SuiviHDVDB.scan_complet = false
        -- Finir quand même le traitement déjà en cours
        if #pending > 0 then
            C_Timer.After(0, function() S:processBatch() end)
        else
            S:_saveResults()
        end
    end
end
