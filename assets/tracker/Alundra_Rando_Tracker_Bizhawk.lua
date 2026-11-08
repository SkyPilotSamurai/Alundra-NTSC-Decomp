-- HP and MP address
local current_magic_address = 0x1DD820
local current_magic_value = 0x00
local max_magic_address = 0x1DD822
local max_magic_value = 0x04

-- Setup variables
local frame_counter = 0
local boss = ""
local loadzone = ""
local current_location = "location"
local formatted_location = ""

-- Checks if in load zone
local transition_check = 0x1F9480
local current_map_check = 0x1F11FC
local current_map_ID

-- Boss addresses
local addrBoss = 0x1AC9A0
local addrWatcher = 0x1AD15C
local addrWorm = 0x1ACC34

-- Using dagger check if in gameplay
local dagger = 0x1DD834

-- Boss defeat variables
local LarsGolem = false
local Watcher = false
local Worm = false
local Maximus = false
local Nirude = false
local Zazan = false
local Wilda = false
local Zorgia = false

-- Crests hints
local RubyHint = false
local SapphireHint = false
local TopazHint = false
local AgateHint = false
local GarnetHint = false
local EmeraldHint = false
local DiamondHint = false
local FireWandHint = false

map_IDs = {
    "Overworld A1 Great Tree","Overworld A2 Murgg Woods","Overworld A3","Overworld A4 F.Manor (outside)",
    "Overworld B1 (Lake sector)","Overworld B2 (C.Mine sector)","Overworld B3 (Riverside sector)","Overworld B4 (Nava's sector)",
    "Overworld C1 (Magy sector)","Overworld C2 (Sanctuary sector)","Debug Map (village outside)","Overworld C4 (Merrick's sector)",
    "Overworld D1 (Torla sector)","Overworld D2 (Mill sector)","Overworld D3 (Tarn Manor sector)","Overworld D4 (R.Lair sector)",
    "Overworld E1 (Nirude sector)","Overworld E2 (Upper desert)","Overworld E3 (Lower desert)","Overworld E4 (Cliffs of Madness)",
    "Lars Crypt 1","Lars Crypt 2","Lars Crypt 3","Lars Crypt 4","Lars Crypt 5",
    "Ancient Shrine 1","Ancient Shrine 2","Ancient Shrine 3","Ancient Shrine 4","Ancient Shrine 5","Ancient Shrine 6","Ancient Shrine 7","Ancient Shrine 8","Ancient Shrine 9",
    "Nirude's Lair Broken 1","Nirude's Lair Broken 2","Nirude's Lair Broken 3","Nirude's Lair Broken 4","Nirude's Lair Broken 5","Nirude's Lair Broken 6",
    "Bonaire's Dream 1","Bonaire's Dream 2","Bonaire's Dream Unused 1",
    "Wendell's Dream","Wendell's Dream Unused 1","Wendell's Dream Unused 2",
    "Bonaire's Dream 3",
    "Elene's Dream 1","Elene's Dream 2","Elene's Dream 3","Elene's Dream 4","Elene's Dream 5","Elene's Dream 6","Elene's Dream 7",
    "Torla Mountain Unused 1","Torla Mountain Unused 2","Torla Mountain Unused 3","Torla Mountain Unused 4","Torla Mountain Unused 5","Torla Mountain Unused 6",
    "Coal Mine 1","Coal Mine 2","Coal Mine 3","Coal Mine 4","Coal Mine Unused 1","Coal Mine 5","Coal Mine 6","Coal Mine 7",
    "Coastal Cave 1","Coastal Cave 2","Coastal Cave 3","Coastal Cave 4","Coastal Cave 5","Coastal Cave 6","Coastal Cave 7","Coastal Cave 8",
    "Underground Waterway 1","Underground Waterway 2","Underground Waterway 3",
    "Reptile Lair 1","Reptile Lair 2","Reptile Lair 3","Reptile Lair 4","Reptile Lair 5","Reptile Lair 6",
    "Magyscar 1","Magyscar 2","Magyscar 3","Magyscar 4","Magyscar 5","Magyscar 6","Magyscar 7","Magyscar 8","Magyscar 9","Magyscar 10",
    "Giles's Dream Unused 1","Giles's Dream Unused 2","Giles's Dream Unused 3","Giles's Dream Unused 4",
    "Giles's Dream 1","Giles's Dream 2","Giles's Dream 3","Giles's Dream 4","Giles's Dream 5","Giles's Dream 6","Giles's Dream 7","Giles's Dream 8","Giles's Dream 9",
    "Nestus's Dream 1","Nestus's Dream 2","Nestus's Dream 3","Nestus's Dream 4","Nestus's Dream 5","Nestus's Dream 6",
    "Tarn's Manor 1","Tarn's Manor 2","Tarn's Manor 3",
    "Cliffs of Madness Cavern Unused 1","Cliffs of Madness Cavern Unused 2","Cliffs of Madness Cavern Unused 3","Cliffs of Madness Cavern Unused 4","Cliffs of Madness Cavern Unused 5",
    "Kline's Dream 1","Kline's Dream 2","Kline's Dream 3","Kline's Dream 4","Kline's Dream 5","Kline's Dream 6",
    "Inoa Village Debug Inside 1","Inoa Village Debug Inside 2","Inoa Village Debug Inside 3","Inoa Village Debug Inside 4","Inoa Village Debug Inside 5","Inoa Village Debug Inside 6 Merrick's Shop",
    "Sanctuary 1","Sanctuary 2","Sanctuary 3","Sanctuary 4",
    "Beach Caves - Circle Of Fishes - Cave Before Fire","Fire Manor + (Cavern)","Cave To Lake",
    "Upper Mines (Cavern)","house near Coal",
    "Nava's Keep 1 & Cabin",
    "Magy-Enterance + Sanctuary Top-Left Cave","Overworld D2 (Cavern)",
    "Great Tree House","Great Tree 1","Great Tree 2","Great Tree 3","Great Tree 4","Great Tree 5","Great Tree 6","Great Tree 7","Great Tree 8","Great Tree 9",
    "Fairy Pond Unused","Fairy Pond 1","Fairy Pond 2","Fairy Pond 3","Fairy Pond 4",
    "Inoa Village 1.0","Inoa Village 1.1","Inoa Village 1.2","Inoa Village 1.3","Inoa Village 1.4","Inoa Village 1.5","Inoa Village 1.6","Inoa Village 2.0",
    "Inoa Village 2.1","Inoa Village 2.2","Inoa Village 2.3","Inoa Village 2.4","Inoa Village 2.5","Inoa Village 2.6","Inoa Village 3.0","Inoa Village 3.1","Inoa Village 3.2","Inoa Village 3.3",
    "Inoa Village 3.4","Inoa Village 3.5","Inoa Village 3.6","Inoa Village 4.0","Inoa Village 4.1","Inoa Village 4.2","Inoa Village 5.0","Inoa Village 5.1","Inoa Village 5.2","Inoa Village 5.3",
    "Inoa Village 5.4","Inoa Village 5.5","Inoa Village 5.6","Inoa Village 6.0","Inoa Village 6.1","Inoa Village 6.2","Inoa Village 6.3","Inoa Village 6.4","Inoa Village 7.0","Inoa Village 7.1",
    "Inoa Village 7.2","Inoa Village 7.3","Inoa Village 7.4","Inoa Village 7.5","Inoa Village 7.6","Inoa Village 8.0","Inoa Village 8.1","Inoa Village 8.2","Inoa Village 8.3","Inoa Village 8.4",
    "Inoa Village 8.5","Inoa Village 8.6","Inoa Village 9.0","Inoa Village 9.1","Inoa Village 9.2","Inoa Village 9.3","Inoa Village 9.4","Inoa Village 9.5","Inoa Village 9.6","Inoa Village 10.0",
    "Inoa Village 10.1","Inoa Village 10.2","Inoa Village 10.3","Inoa Village 10.4","Inoa Village 10.5","Inoa Village 10.6","Inoa Village 11.0","Inoa Village 11.1","Inoa Village 11.2","Inoa Village 11.3",
    "Inoa Village 12.0","Inoa Village 12.1","Inoa Village 12.2","Inoa Village 12.3","Inoa Village 12.4","Inoa Village 12.5","Inoa Village 12.6","Inoa Village 13.0","Inoa Village 13.1","Inoa Village 13.2",
    "Inoa Village 13.3","Inoa Village","Jess's House","Inoa Village","Inoa Village","Inoa Village","Inoa Village","Inoa Village","Inoa Village 15.0","Inoa Village 15.1",
    "Inoa Village 15.2","Inoa Village 15.3","Inoa Village 16.0","Inoa Village 16.1","Inoa Village 16.2","Inoa Village 16.3","Inoa Village 16.4","Inoa Village 16.5","Inoa Village 16.6 Naomi's Shop","Inoa Village 17.0",
    "Jess's House Blue Chest","Inoa Village 17.2","Inoa Village 17.3","Inoa Village 17.4","Inoa Village 17.5","Inoa Village 17.6","Inoa Village 18.0","Inoa Village 18.1","Inoa Village 18.2","Inoa Village 18.3",
    "Inoa Village 18.4","Inoa Village 19.0","Inoa Village 19.1","Inoa Village 19.2","Inoa Village 19.3","Inoa Village 20.0","Inoa Village 20.1","Inoa Village 20.2","Inoa Village 20.3","Inoa Village 20.4",
    "Inoa Village 20.5","Inoa Village 20.6","Inoa Village 21.0","Inoa Village 21.1","Inoa Village 21.2","Inoa Village 21.3","Inoa Village 21.4","Inoa Village 21.5","Inoa Village 21.6","Inoa Village 22.0",
    "Inoa Village 22.1","Inoa Village 22.2","Inoa Village 22.3","Inoa Village 23.0","Inoa Village 23.1","Inoa Village 23.2","Inoa Village 23.3","Inoa Village 24.0","Inoa Village 24.1","Inoa Village 24.2",
    "Inoa Village 24.3","Inoa Village 25.0","Inoa Village 25.1",
    "Olen's House",
    "Ice Manor",
    "Meia's Dream Unused 1","Meia's Dream Unused 2","Meia's Dream Unused 3","Meia's Dream Memory 1","Meia's Dream Memory 2","Meia's Dream Memory 3",
    "Lurvy's Well","Klark Ship Unused 1","Klark Ship Unused 2",
    "Nava's Keep Unused 1 (Murgg Woods Base)","Nava's Keep Unused 2 (Murgg Woods Base)","Nava's Keep Unused 3 (Murgg Woods Base)","Nava's Keep Unused 4 (Murgg Woods Base)",
    "Nava's Keep Unused 5 (Murgg Woods Base)","Nava's Keep Unused 6 (Murgg Woods Base)",
    "Klark Ship Unused 3",
    "Zorgia Boss Room","Corpse Worm Boss Room","Dark Dragon Boss Room","Nirude Boss Room","Torla Moutain Wilda Boss Room","Ronan Boss Room","Melzas Boss Room",
    "Coal Mine 8","Coal Mine 9",
    "Jess Cutscene 1","Jess Cutscene 2","Jess Cutscene 3 Lutas's House","Jess Cutscene 4","Jess Cutscene 5","Jess Cutscene 6","Jess Cutscene 7",
    "Lake Shrine Inside 1","Lake Shrine Inside 2","Lake Shrine Inside 3","Lake Shrine Inside 4","Lake Shrine Inside 5","Lake Shrine Inside 6","Lake Shrine Inside 7","Lake Shrine Inside 8","Lake Shrine Inside 9",
    "Lake Shrine Inside 10","Lake Shrine Inside 11","Lake Shrine Inside 12","Lake Shrine Inside 13","Lake Shrine Inside 14",
    "Lake Shrine Outside 1","Lake Shrine Outside 2","Lake Shrine Outside 3","Lake Shrine Outside 4","Lake Shrine Balcony 1","Lake Shrine Balcony 2",
    "Inoa Village 26.0","Inoa Village 26.1","Inoa Village 26.2","Inoa Village 26.3","Inoa Village 27.0","Olen's Dream 1","Olen's Dream 2","Inoa Village 28.0","Inoa Village 28.1",
    "Inoa Village 28.2","Inoa Village 29.0",
    "Great Tree Melzas Cutscene","Great Tree Burgus Cutscene",
    "Inoa Village 30.6 (unused)","Inoa Village 30.0","Inoa Village 30.1","Inoa Village 30.2","Inoa Village 30.3","Inoa Village 30.4","Inoa Village 30.5","Inoa Village 30.6",
    "Lake Shrine Bridge","Lake Shrine Outside 5",
    "Mimics Cave","Megalith Portal Chamber",
    "Overworld A2 Murgg Woods 1","Overworld A2 Murgg Woods 2","Overworld A2 Murgg Woods 3","Overworld A2 Murgg Woods 4","Overworld A2 Murgg Woods 5",
    "Inoa Village 15.4",
    "Nirude's Lair Cutscene 2",
    "Klark Ship 1","Klark Ship 2","Klark Ship 3","Klark Ship 4",
    "Mill Cutscene",
    "Riverside Bar 1 Casino","Overworld D2 Watermill House",
    "E2 Berue's Chamber - Burning Pillars Cave",
    "Shack Cavern Unused",
    "Lurvy's Shop",
    "Overworld A2 Murgg Woods 6",
    "Ancient Shrine Unused 1",
    "Cliffs of Madness Cavern",
    "Overworld E3 Despair Desert Cave (Sand Cape)","Despair Desert Maze 1","Despair Desert Maze 2","Despair Desert Maze 3","Despair Desert Maze 4",
    "Overworld C4 Outlook Point 2",
    "Reptile Lair 1","Reptile Lair 2","Reptile Lair 3","Reptile Lair 4",
    "Sybill Cutscene 1","Sybill Cutscene 2","Sybill Cutscene 3","Sybill Cutscene 4",
    "Beach Arrival Cutscene",
    "Inoa Village 31.0","Inoa Village 31.2","Inoa Village 31.3",
    "Nava's Keep Unused",
    "Nirude's Lair 1","Nirude's Lair 2","Nirude's Lair 3","Nirude's Lair 4","Nirude's Lair 5","Nirude's Lair 6",
    "Unknown Dungeon Unused 1","Unknown Dungeon Unused 2",
    "Nava's Keep 2","Nava's Keep 3","Nava's Keep 4","Nava's Keep 5",
    "Lake Shrine Outside 6","Lake Shrine Outside 7",
    "Elene's Dream End 1","Elene's Dream End 2","Elene's Dream End 3","Elene's Dream End 4",
    "Overworld E1 (Nirude sector)",
    "Meia's Dream 1","Meia's Dream 2","Meia's Dream 3",
    "Torla Mountain 1","Torla Mountain 2","Torla Mountain 3","Torla Mountain 4","Torla Mountain 5","Torla Mountain 6",
    "Giles's Dream Boss Room",
    "Overworld E2 Despair Desert North Drained",
    "Nirude's Lair Cutscene 1",
    "Coal Mine Save Room","Lars Crypt Save Room","Coastal Cave Save Room","Ancient Shrine Save Room","Fairy Pond Save Room Unused","Underground Waterway Save Room Unused","Reptile Lair Save Room","Magyscar Save Room",
    "Nirude's Lair Save Room","Torla Mountain Save Room","Great Tree Save Room Unused","Coastal Cave Save Room","Lake Shrine Inside Save Room Unused","Bonaire's Dream Save Room","Kline's Dream Save Room","Giles's Dream Save Room",
    "Meia's Dream Save Room","Elene's Dream Save Room","Nestus's Dream Save Room","Melzas Brain Boss Room",
    "Casino Slime Bash","Casino Slime Shooter","Casino Roulette",
    "Yustel Map",
    "Lars & Melzas Cutscene",
    "Death Screen","Inoa Arrival Cutscene","Lake Bridge Raised (outside)",
    "Lake Shrine Final Room",
    "Sybill Death Cutscene","Sanctuary Basement Holy Sword","Unknown"}

-- Memory Addresses
local memory_addresses = {
    magic_seed = 0x1DD822,
    hunters_bow = 0x1DD844,
    spirit_wand = 0x1DD84C,
    iron_flail = 0x1DD854,
    steel_flail = 0x1DD858,
    ice_wand = 0x1DD868,
    fire_wand = 0x1DD870,
    bomb = 0x1DD8BC,
    aqua_cape = 0x1DD8D0,
    earth_scroll = 0x1DD8DC,
    earth_book = 0x1DD8E0,
    water_scroll = 0x1DD8E4,
    water_book = 0x1DD8E8,
    fire_scroll = 0x1DD8EC,
    fire_book = 0x1DD8F0,
    wind_scroll = 0x1DD8F4,
    wind_book = 0x1DD8F8,
    olgas_ring = 0x1DD8FC,
    oaks_ring = 0x1DD900,
    silver_armlet = 0x1DD904,
    charm = 0x1DD908,
    recovery_ring = 0x1DD90C,
    secret_pass = 0x1DD914,
    power_glove = 0x1DD91C,
    elevator_key = 0x1DD920,
    ruby_crest = 0x1DD928,
    sapphire_crest = 0x1DD92C,
    topaz_crest = 0x1DD930,
    agate_crest = 0x1DD934,
    garnet_crest = 0x1DD938,
    emerald_crest = 0x1DD93C,
    bouquet = 0x1DD958,
    leather_armor = 0x1DD878,
    ancient_armor = 0x1DD87C,
    silver_armor = 0x1DD880,
    long_boots = 0x1DD898,
    merman_boots = 0x1DD89C,
    charm_boots = 0x1DD8A0,
    spring_bean = 0x1DD8AC,
    sand_cape = 0x1DD8B0,
    broken_armor = 0x1DD8B4,
    sword = 0x1DD838,
    fiend_blade = 0x1DD83C,
    holy_sword = 0x1DD840,
    legend_sword = 0x1DD850,
    willow_bow = 0x1DD848,
    diamond_crest = 0x1DD940,
    small_key = 0x1DD95C,
    tree_gem = 0x1DD964,

    -- Upgrades
    sword_upgrade = 0x1DD838,
    sword_upgrade = 0x1DD85C,
    sword_upgrade_2 = 0x1DD83C,
    sword_upgrade_3 = 0x1DD840,
    sword_upgrade_4 = 0x1DD850,
    flail_upgrade = 0x1DD854,
    flail_upgrade_2 = 0x1DD858,
    bow_upgrade = 0x1DD844,
    bow_upgrade_2 = 0x1DD848,
    armor_upgrade = 0x1DD878,
    armor_upgrade_2 = 0x1DD87C,
    armor_upgrade_3 = 0x1DD880,
    earth_magic = 0x1DD8DC,
    earth_magic_2 = 0x1DD8E0,
    water_magic = 0x1DD8E4,
    water_magic_2 = 0x1DD8E8,
    fire_magic = 0x1DD8EC,
    fire_magic_2 = 0x1DD8F0,
    wind_magic = 0x1DD8F4,
    wind_magic_2 = 0x1DD8F8,
    herbs = 0x1DD8C0,
    strength_elixir = 0x1DD8C4,
    magic_elixir = 0x1DD8C8,
    wonder_essence = 0x1DD8CC,
    strength_tonic = 0x1DD8D4,
    dungeon_key = 0x1DD924,
    gilded_falcon = 0x1DD82A,
    dagger = 0x1DD834
}

local locations = {
    ["Overworld (Indoors)"] = {"Watermill", "Left Cave", "Upper Mines", "D2 (Cavern)", "Olen's House", "Lutas's House", "Blue Chest", "House Near Coal", "Cave Next To Underground",
    "Cave To Lake", "Cabin", "House Basement", "Mimics Cave", "Circle Of Fishes", "Cave Before Fire", "Well"},
    ["Overworld"] = {"A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C4", "D1", "D2", "D3", "D4"},
    ["Tarn's Manor"] = "Tarn's Manor",
    ["Coal Mine"] = "Coal Mine:", 
    ["Lars Crypt"] = "Lars Crypt",
    ["Cliffs of Madness"] = "E4",
    ["Desert"] = {"E3", "E2"},
    ["Ancient Shrine"] = "Ancient Shrine",
    ["Coastal Cave"] = "Coastal Cave", 
    ["Reptile Lair"] = "Reptile Lair",
    ["Magyscar"] = "Magyscar",
    ["Fire-Ice Manor"] = {"Fire Manor", "Ice Manor"},
    ["Underground Waterway"] = "Underground Waterway",
    ["Nirude's Lair-Site"] = {"Nirude's Lair", "E1"},
    ["Murgg Woods"] = "A2", 
    ["Murgg Tree"] = "Great Tree",
    ["Fairy Pond"] = "Fairy Pond",
    ["Torla Mountain"] = "Torla Mountain", 
    ["Nava's Keep"] = "Nava's Keep",
    ["Shops"] = {"Naomi's Shop", "Merrick's Shop", "Lurvy's Shop"},
    ["Lake Shrine"] = "Lake Shrine",
    ["Casino"] = "Casino"
}

local previous_values = {}
for item, address in pairs(memory_addresses) do
    previous_values[item] = memory.readbyte(address)
end

local function formatItemName(itemName)
    itemName = itemName:gsub("_%d", "") 
    itemName = itemName:gsub("_", " ") 
    return itemName:gsub("(%l)(%u)", "%1 %2")
                   :gsub("^%l", string.upper)
end

local function clearLogFile()
    local logFile = io.open("log.txt", "w")
    if logFile then
        logFile:close()
    end
end

local function clearLocationFile()
    local logFile = io.open("location.txt", "w")
    if logFile then
        logFile:close()
    end
end

local function logItem(item, current_location)
    local logFile = io.open("log.txt", "a")
    if logFile then
        local formattedItem = formatItemName(item)
        local timestamp = os.date("[%Y-%m-%d %H:%M:%S]")
        
        if formatted_location == "Bean Cave & Magyscar Alter" then formatted_location = "Bean Cave" end

        logFile:write(string.format("%s [Location: %s] Obtained: %s\n", timestamp, formatted_location, formattedItem))
        logFile:close()
    end
end

local function logHint(hint, current_location)
    local logFile = io.open("log.txt", "a")
    if logFile then
        local formattedItem = formatItemName(hint)
        local timestamp = os.date("[%Y-%m-%d %H:%M:%S]")
        
        if formatted_location == "Bean Cave & Magyscar Alter" then formatted_location = "Bean Cave" end

        logFile:write(string.format("%s [Location: %s] Obtained: %s\n", timestamp, formatted_location, hint))
        logFile:close()
    end
end

local function unlogItem(item)
    local lines = {}
    local item_lower = formatItemName(item):lower()
    local found = false

    -- Items that prevent a line from being removed
    local protected_items = { "crest", "gem", "bouquet", "small key", "broken armor"}

    -- Check if item_lower contains any protected item
    local function containsProtectedItem(str)
        for _, keyword in ipairs(protected_items) do
            if str:find(keyword, 1, true) then
                return true
            end
        end
        return false
    end

    for line in io.lines("log.txt") do
        if not found and line:lower():find(item_lower, 1, true) then
            if containsProtectedItem(item_lower) then
                table.insert(lines, line)  -- Keep the line if protected
            else
                found = true  -- Skip the line
            end
        else
            table.insert(lines, line)
        end
    end

    local file = io.open("log.txt", "w")
    for _, line in ipairs(lines) do
        file:write(line, "\n")
    end
    file:close()
end

function check_location(current_location)
    if not current_location then
        return "Unknown Location"
    end

    current_location = current_location:gsub(":", ""):lower()

    for key, value in pairs(locations) do
        if type(value) == "table" then
            for _, sub_location in ipairs(value) do
                local formatted_sub_location = sub_location:gsub(":", ""):lower()
                if current_location:find(formatted_sub_location, 1, true) then
                    return sub_location
                end
            end
        else
            local formatted_value = value:gsub(":", ""):lower()
            if current_location:find(formatted_value, 1, true) then
                return value
            end
        end
    end
    return current_location
end

local function removeObtainedItem(item)
    local lines = {}
    local file = io.open("tracker.txt", "r")

    current_location = check_location(current_location)

    if file then
        for line in file:lines() do
            table.insert(lines, line)
        end
        file:close()

        local formattedItem = formatItemName(item):lower() .. " "
        local newLines = {}
        local removedLines = {}
        local itemLine = nil

        if formattedItem:match("^charm%s*$") then
            formattedItem = "nava's charm "
        end

        if formattedItem:match("^olgas ring $") then
            formattedItem = "olga's ring "
        end

        if current_location == "Top-Left Cave" then
            current_location = "Left Cave"
        end

        for _, line in ipairs(lines) do
            local lineLower = line:lower()
            local currentLower = current_location:lower()
        
            if not itemLine and lineLower:find(formattedItem, 1, true) and (
                lineLower:find(currentLower, 1, true) or
                (currentLower == "olen's house" and lineLower:find("house basement", 1, true)) or
                (currentLower == "circle of fishes" and lineLower:find("cave before fire", 1, true)) or
                (currentLower == "burning pillars" and lineLower:find("(sluice key)", 1, true)) or
                (currentLower == "d2 (cavern)" and lineLower:find("d2 (cavern)", 1, true))
            ) then
                itemLine = line
                removedLines[line] = true
            elseif not removedLines[line] then
                table.insert(newLines, line)
            end
        end

        --print("LOCATION:" .. current_location .. "  ITEM:" .. formattedItem)

        file = io.open("tracker.txt", "w")
        if file then
            file:write(table.concat(newLines, "\n") .. "\n")
            file:close()
        end
    end
end

function is_game_playing()
    return memory.read_u16_le(0x1DD810, "MainRAM") == 0x1EE
end

local function checkItems()
    if is_game_playing() == true then
        for item, address in pairs(memory_addresses) do
            local currentValue = memory.readbyte(address)

            if currentValue > previous_values[item] then
                removeObtainedItem(item)
                logItem(item)
            end
            if currentValue < previous_values[item] and item ~= "gilded_falcon" then -- falcons: Merrick zeroes the carried count
                unlogItem(item)
            end

            previous_values[item] = currentValue
        end
    end
end

function count_location_lines(tracker_file, current_location)
    local file = io.open(tracker_file, "r")
    if not file then return 0 end

    local count = 0
    local previous_lines = {}

    local main_loc = string.lower(current_location)
    local keywords = {main_loc}

    local sub_locations = {
        ["overworld d2"] = {"d2 (cavern)"},
        ["olen's house"] = {"house basement"},
        ["circle of fishes"] = {"cave before fire"},
        ["burning pillars"] = {"(sluice key)"}
    }

    if sub_locations[main_loc] then
        for _, sub in ipairs(sub_locations[main_loc]) do
            table.insert(keywords, string.lower(sub))
        end
    end

    for line in file:lines() do
        local lower_line = string.lower(line)
        for _, keyword in ipairs(keywords) do
            if lower_line:find(keyword, 1, true) and not previous_lines[line] then
                previous_lines[line] = true
                count = count + 1
                break
            end
        end
    end

    file:close()
    return count
end

function drawOutlinedText(x, y, text, textColor)
    fontSize = 10
    outlineColor = "black"
    -- Draw the text in 8 directions to simulate an outline
    gui.drawText(x - 1, y - 1, text, outlineColor, nil, fontSize) -- Top-Left
    gui.drawText(x + 1, y - 1, text, outlineColor, nil, fontSize) -- Top-Right
    gui.drawText(x - 1, y + 1, text, outlineColor, nil, fontSize) -- Bottom-Left
    gui.drawText(x + 1, y + 1, text, outlineColor, nil, fontSize) -- Bottom-Right
    gui.drawText(x, y - 1, text, outlineColor, nil, fontSize) -- Top
    gui.drawText(x, y + 1, text, outlineColor, nil, fontSize) -- Bottom
    gui.drawText(x - 1, y, text, outlineColor, nil, fontSize) -- Left
    gui.drawText(x + 1, y, text, outlineColor, nil, fontSize) -- Right

    -- Draw the main text in the center
    gui.drawText(x, y, text, textColor, nil, fontSize)
end

function drawNewText(x, y, text, textColor)
    fontSize = "10"
    gui.drawText(x, y, text, textColor, nil, fontSize)
end

function toCamelCase(str)
    return str:gsub("(%a)([%w']*)", function(first, rest)
        return first:upper() .. rest:lower()
    end)
end

last_saved_frame = 0

function display_location()
    if current_location == "Inoa Village" then current_location = "Inoa" end
    if current_location == "Top-Left Cave" then current_location = "Left Cave" end
    if current_location == "Burning Pillars" then current_location = "(Sluice Key)" end

    current_location = check_location(current_location)

    local location_count = count_location_lines("tracker.txt", current_location)

    current_location = toCamelCase(current_location)

    if current_location == "Inoa" then current_location = "Inoa Village" end
    if current_location == "Blue Chest" then current_location = "Jess's House" end
    if current_location == "Olen's House" then current_location = "Olen's House - Cephas's Basement" end
    if current_location == "Cabin" then current_location = "Nava's Cabin" end
    if current_location == "Left Cave" then current_location = "Bean Cave & Magyscar Alter" end
    if current_location == "House Near Coal" then current_location = "House Near Coal Mine" end
    if current_location == "Well" then current_location = "Lurvy's Well" end
    if current_location == "Cave (Sand Cape)" then current_location = "Sand Cape Cave" end
    if current_location == "Great Tree" then current_location = "Murgg Tree" end
    if current_location == "A2" then current_location = "Murgg Woods" end
    if current_location == "E1" then current_location = "Nirude Site" end
    if current_location == "E2" then current_location = "Desert (Upper)" end
    if current_location == "E3" then current_location = "Desert (Lower)" end
    if current_location == "E4" then current_location = "Cliffs of Madness" end
    if current_location == "Circle Of Fishes" then current_location = "Beach Caves" end
    if current_location == "(Sluice Key)" then current_location = "Burning Pillar Cave" end

    if #current_location == 2 then current_location = "Overworld " .. current_location end

    local current_location = tostring(current_location)
    formatted_location = current_location  

    local current_frame = emu.framecount()
    if current_frame - last_saved_frame >= 30 then
        local file = io.open("location.txt", "w")
        if file then
            file:write(current_location .. " (" .. location_count .. ")\n")
            file:close()
        end
        last_saved_frame = current_frame
    end
end

local previous_location = ""

while true do
    current_map_ID = mainmemory.read_u16_le(current_map_check)
    current_location = map_IDs[current_map_ID] 

    -- if current_location ~= previous_location then previous_location = current_location end

    loadzone = memory.read_u16_be(transition_check)
    boss = memory.read_u8(addrBoss, "System Bus")

    if frame_counter == 20 then
        checkItems()
        --print(current_map_ID)
        frame_counter = 0
    end

    --if frame_counter == 60 then print(current_location) end

    if current_location == "Lars Crypt 5" then
        if boss > 0 then LarsGolem = true end
        if LarsGolem then  
            if boss == 0 then RubyHint = true end
        end
    end

    if current_location == "Ancient Shrine 5" then 
        FireWandHint = true 
        TopazHint = true
    end

    if (current_location) == "Coastal Cave 8" then
        boss = memory.read_u8(addrWatcher, "System Bus")
        if boss > 0 then Watcher = true end
        if Watcher then
            if boss == 0 then
                if io.open("log.txt","r"):read(0) == nil then FireWandHint = true  end
                for line in io.lines("log.txt") do
                    if line:lower():find("fire wand", 1, true) then
                        AgateHint = true
                    else
                        AgateHint = true 
                    end
                end
            end
        end
    end

    if (current_location) == "Reptile Lair 6" then
        if boss > 0 then Maximus = true end
        if Maximus then
            if boss == 0 then SapphireHint = true end
        end
    end

    if (current_location) == "Corpse Worm Boss Room" or (current_location) == "Magyscar 10" then
        boss = memory.read_u8(addrWorm, "System Bus")
        if boss > 0 then Worm = true end
        if Worm then
            if boss == 0 then
                if io.open("log.txt","r"):read(0) == nil then FireWandHint = true  end
                for line in io.lines("log.txt") do
                    if line:lower():find("fire wand", 1, true) then
                        GarnetHint = true
                    else
                        GarnetHint = true 
                    end
                end
            end
        end
    end
    
    if (current_location) == "Nirude Boss Room" then Nirude = true end
    if Nirude and (current_location) == "Overworld E1 (Nirude sector)" then TopazHint = true end

    if (current_location) == "Great Tree 6" then
        if boss > 0 then Zazan = true end
        if Zazan then
            if boss == 0 then 
                AgateHint = true 
                GarnetHint = true
            end
        end
    end

    if (current_location) == "Wilda Boss Room" then
        if boss > 0 then Wilda = true end
        if Wilda then  
            if boss == 0 then EmeraldHint = true end
        end
    end

    if (current_location) ==  "Zorgia Boss Room" then
        if boss > 0 then Zorgia = true end
        if Zazan then  
            if boss == 0 then DiamondHint = true end
        end
    end

    if RubyHint or SapphireHint or TopazHint or AgateHint or GarnetHint or EmeraldHint or DiamondHint or FireWandHint then
        if RubyHint then logHint("Ruby Hint", current_location) end
        if SapphireHint then logHint("Sapphire Hint", current_location) end
        if TopazHint then logHint("Topaz Hint", current_location) end
        if AgateHint then logHint("Agate Hint", current_location) end
        if GarnetHint then logHint("Garnet Hint", current_location) end
        if EmeraldHint then logHint("Emerald Hint", current_location) end
        if DiamondHint then logHint("Diamond Hint", current_location) end
        if FireWandHint then logHint("Fire Wand Hint", current_location) end

        LarsGolem = false
        Watcher = false
        Maximus = false
        Worm = false
        Nirude = false
        Zazan = false
        Wilda = false
        Zorgia = false
        RubyHint = false
        SapphireHint = false
        TopazHint = false
        AgateHint = false
        GarnetHint = false
        EmeraldHint = false
        DiamondHint = false
        FireWandHint = false
    end

    display_location()

    frame_counter = frame_counter + 1

    emu.frameadvance()
end