local filename = "_internal/command.txt" -- File to get commands from

-- Gameplay
local invincibility_length = 900 -- Duration for Invincibility (in frames)
local no_iframes_length = 1800 -- Duration for No iFrames (in frames)
local no_jump_length = 900 -- Duration for No Jump (in frames)
local slow_motion_length = 300 -- Duration for Slow Motion (in frames)
local moon_jump_length = 60 -- Duration for Moon Jump (in frames)

-- Force weapon 
local swap_length = 1800 -- How long to force a weapon (frames)

-- Lock weapon / item
local lock_weapon_length = 1800 -- How long to lock a weapon (frames)
local lock_item_length = 1800 -- How long to lock an item (frames)

-- Gilder 
local gilder_give = 50 -- Amount of Gilder to give when command activated
local gilder_take = 50 -- Amount of Gilder to take when command activated

-- HP heal / damage command 
local hp_change = 2 -- hp change amount

-- Regen / Poison 
local regen_tick = 120 -- Time until a heal happens (frames)
local regen_length = 1200 -- Length of regen (healing) (frames)
local poison_tick = 120 -- Time until damage happens (frames)
local poison_length = 1200 -- Length of poison (frames)

-- If true timer based cheats will not count down while in the menu
local check_for_menu = true

-- Item display timer
local item_display_duration = 300 -- Duration to display various messages (frames)

-- Define colors for popup text
local textColor = "white"
local outlineColor = "black"
local fontSize = 11

-- Position on screen to display most cheats
local base_x = 20
local base_y = 200
local line_spacing = 10 -- Spacing between different cheats

-- Values used check to L1 - R1 weapon swaps
local allow_L_swaps = true -- This will allow L weapon swaps and L + select item swaps
local allow_R_swaps = true -- This will allow R weapon swaps and R + select item swaps

-- Initailising values (Used to cheat activation states, current timers and assign other values)
local cheat_active = false
local slow_motion_active = false
local slow_motion_timer = 0
local iFrame_cheat_active = false
local no_jump_active = false
local moon_jump_active = false
local debounce_invincibility = false
local debounce_iFrame = false
local debounce_moon_jump = false
local debounce_no_jump = false
local debounce_slow_motion = false
local debounce_gilder = false
local force_swap_active = false
local force_item_active = false
local L1_swap_check = false
local R1_swap_check = false
local select_L1_swap_check = false
local select_R1_swap_check = false
local regen_active = false
local poison_active = false
local debounce_health_increase = false
local debounce_health_decrease = false
local debounce_herb = false
local debounce_remove_herb = false
local debounce_key_cheat = false
local return_weapon = false
local invincibility_timer = 0 
local iFrame_timer = 0 
local no_jump_timer = 0 
local moon_jump_timer = 0
local debounce_reset_duration = 20
local debounce_duration_increase = 0
local debounce_duration_decrease = 0
local item_message_timer = 0
local swap_timer = 0
local lock_item_timer = 0
local swap_timer_reset = 0
local regen_timer = 0
local poison_timer = 0
local regen_ttimer = 0
local poison_ttimer = 0
local max_herb_value = 0x09
local item_message = ""
local swap_to = ""
local swap_back = ""
local locked_item = ""
local give_weapon = ""
local content = ""
local popupMessage = ""

-- Menu address and values, used to check if menu is active
local menu_value = 0x00
local menu_value2 = 0x00
local menu_check = 0x1F0060
local menu_check_value = 0x08

-- Invincibility cheat and values
local invincibility_cheat_address = 0x1AC8C4
local cheat_value = 0x4E

-- No I Frames address and values
local iFrame_cheat_address = 0x1AC8C4
local iFrame_cheat_value_on = 0x00

-- Moon Jump address and values
local moon_jump_address1 = 0x1DDA48
local moon_jump_value1 = 0x40
local moon_jump_address2 = 0x1AC7B2
local moon_jump_value2 = 0x03

-- Slow motion address and values
local slow_motion_address = 0xCB54C
local slow_motion_value = 0x0B5F

-- HP and MP address
local current_health_address = 0x1AC70C
local current_health_value = 0x01
local max_health_address = 0x1AC710
local max_health_value = 0x32
local current_magic_address = 0x1DD820
local current_magic_value = 0x00
local max_magic_address = 0x1DD822
local max_magic_value = 0x04

-- No Jump address
local no_jump_address = 0x1DDA48
local no_jump_value = 0x40

-- Item address
local herbs = 0x1DD8C0
local hunters_bow = 0x1DD844
local spirit_wand = 0x1DD84C
local iron_flail = 0x1DD854
local steel_flail = 0x1DD858
local ice_wand = 0x1DD868
local fire_wand = 0x1DD870
local gilded_falcon = 0x1DD82A
local mining_bomb = 0x1DD8BC
local strength_elixir = 0x1DD8C4
local magic_elixir = 0x1DD8C8
local wonder_essence = 0x1DD8CC
local aqua_cape = 0x1DD8D0
local earth_scroll = 0x1DD8DC
local earth_book = 0x1DD8E0
local water_scroll = 0x1DD8E4
local water_book = 0x1DD8E8
local fire_scroll = 0x1DD8EC
local fire_book = 0x1DD8F0
local wind_scroll = 0x1DD8F4
local wind_book = 0x1DD8F8
local olgas_ring = 0x1DD8FC
local oaks_ring = 0x1DD900
local silver_armlet = 0x1DD904
local navas_charm = 0x1DD908
local recovery_ring = 0x1DD90C
local refresher = 0x1DD910
local secret_pass = 0x1DD914
local power_glove = 0x1DD91C
local elevator_key = 0x1DD920
local ruby_crest = 0x1DD928
local sapphire_crest = 0x1DD92C
local topaz_crest = 0x1DD930
local agate_crest = 0x1DD934
local garnet_crest = 0x1DD938
local emerald_crest = 0x1DD93C
local bouquet = 0x1DD958
local leather_armor = 0x1DD878
local ancient_armor = 0x1DD87C
local silver_armor = 0x1DD880
local long_boots = 0x1DD898
local merman_boots = 0x1DD89C
local charm_boots = 0x1DD8A0
local spring_bean = 0x1DD8AC
local sand_cape = 0x1DD8B0
local broken_armor = 0x1DD8B4
local dagger = 0x1DD834
local sword = 0x1DD838
local fiend_blade = 0x1DD83C
local holy_sword = 0x1DD840
local legend_sword = 0x1DD850
local recovery_ring = 0x1DD90C
local strength_tonic = 0x1DD8D4
local willow_bow = 0x1DD848
local diamond_crest = 0x1DD940
local proto_flail = 0x1DD85C
local proto_fire_wand = 0x1DD85C
local key = 0x1DD924
local small_key = 0x1DD95C
local jess_letter = 0x1DD960
local tree_gem = 0x1DD964
local zolist_stone = 0x1DD968
local book_of_elna = 0x1DD990
local book_of_runes = 0x1DD98C
local curious_key = 0x1DD994

-- Gilder address
local gilder_address = 0x1DD824

-- Equipment and Item slot address
local weapon_slot = 0x1DD826
local item_slot = 0x1DD828

-- Item slot values
local items = {
    herbs = 0x24,
    strength_tonic = 0x29,
    strength_elixir = 0x25,
    magic_elixir = 0x26,
    wonder_essence = 0x27,
    mining_bomb = 0x23,
    earth_scroll = 0x2B,
    earth_book = 0x2C,
    water_scroll = 0x2D,
    water_book = 0x2E,
    fire_scroll = 0x2F,
    fire_book = 0x30,
    wind_scroll = 0x31,
    wind_book = 0x32,
    sand_cape = 0x20,
    aqua_cape = 0x28,
    navas_charm = 0x36,
    power_glove = 0x3B,
    spring_bean = 0x1F,
    olgas_ring = 0x33,
    silver_armlet = 0x35,
    recovery_ring = 0x37,
    refresher = 0x38,
}

-- Input Address and values
local input_address = 0x1DDA48
local input_select_start_address = 0x1DDA49
local X = 0x40
local O = 0x20
local triangle = 0x10
local square = 0x80
local L1 = 0x04
local L2 = 0x01
local R1 = 0x08
local R2 = 0x02
local select = 0x01
local start = 0x08
local input = ""
local input2 = ""
local LR_swap = false

local menu_closed = true
local LR_check = false

-- Take return: what chat gives is noted as given; when chat takes something the player earned in game, it
-- comes back after take_return_length (frames, counted with the menu closed, as Force Weapon's timer).
-- Given things that are taken never come back.  A return only fills back up to what the player had before the
-- take, so a reload or a save that already has the thing back gets nothing twice.
local ledger = {
    take_return_length = 1800, -- How long until a taken earned thing comes back (frames)
    given = {},     -- address -> how many of what is held there chat gave
    owed = {},      -- address -> how many earned ones are to come back
    ceiling = {},   -- address -> what the player had before the first of those takes
    returns = {},   -- {address, count, frames left}
    seen = {},      -- address -> what was held there last frame (what the player used is the given ones first)
    addresses = {max_health_address, max_magic_address, gilded_falcon},
}
for a = 0x1DD834, 0x1DD994, 4 do table.insert(ledger.addresses, a) end

function ledger_read(a)
    if a == gilder_address then return memory.readbyte(a) | (memory.readbyte(a + 1) << 8) end
    return memory.readbyte(a)
end

function ledger_write(a, v)
    if a == gilder_address then
        memory.writebyte(a, v & 0xFF); memory.writebyte(a + 1, (v >> 8) & 0xFF)
    else
        memory.writebyte(a, v)
    end
end

function ledger_snapshot()
    local s = {[gilder_address] = ledger_read(gilder_address)}
    for _, a in ipairs(ledger.addresses) do s[a] = ledger_read(a) end
    return s
end

function ledger_gift(a, n)
    ledger.given[a] = (ledger.given[a] or 0) + n
    ledger.seen[a] = ledger_read(a)
end

function ledger_after(before, kind)
    for a, old in pairs(before) do
        local new = ledger_read(a)
        if kind == "+" and new > old then
            ledger_gift(a, new - old)
        elseif kind == "-" and new < old then
            local taken = old - new
            local from_gift = math.min(ledger.given[a] or 0, taken)
            ledger.given[a] = (ledger.given[a] or 0) - from_gift
            local earned = taken - from_gift
            ledger.seen[a] = new
            if earned > 0 then
                if (ledger.owed[a] or 0) == 0 then ledger.ceiling[a] = old - from_gift
                else ledger.ceiling[a] = math.max(ledger.ceiling[a], old - from_gift) end
                ledger.owed[a] = (ledger.owed[a] or 0) + earned
                table.insert(ledger.returns, {a, earned, ledger.take_return_length})
            end
        end
    end
end

function ledger_reconcile()
    for a, n in pairs(ledger.given) do                  -- what the player used up or lost: the given ones first
        local held = ledger_read(a)
        local seen = ledger.seen[a] or held
        if held < seen then n = math.max(0, n - (seen - held)) end
        ledger.given[a] = math.min(n, held)
        ledger.seen[a] = held
        if ledger.given[a] == 0 then ledger.given[a] = nil; ledger.seen[a] = nil end
    end
end

function ledger_tick(counting)
    ledger_reconcile()
    local keep = {}
    for _, r in ipairs(ledger.returns) do
        if counting then r[3] = r[3] - 1 end
        if r[3] > 0 then
            table.insert(keep, r)
        else
            local a, n = r[1], r[2]
            local held = ledger_read(a)
            local back = math.max(0, math.min(n, ledger.ceiling[a] - held))
            if back > 0 then
                ledger_write(a, held + back)
                if ledger.seen[a] ~= nil then ledger.seen[a] = held + back end
                if item_message_timer == 0 then
                    item_message_timer = item_display_duration
                    item_message = "Item Returned"
                end
            end
            ledger.owed[a] = ledger.owed[a] - n
            if ledger.owed[a] <= 0 then ledger.owed[a] = nil; ledger.ceiling[a] = nil end
        end
    end
    ledger.returns = keep
end

while true do
    local function readFile(filename)
        local file = io.open(filename, "r") -- Open the file in read mode
        if not file then
            error("Could not open the file: " .. filename) -- Handle file open failure
        end
        content = file:read("*l") -- Read the first line
        popupMessage = file:read("*l") -- Read the second line
        if content == nil then
            content = ""
        end
        if popupMessage == nil then
            popupMessage = ""
        end
        file:close() -- Close the file
    end

    local input = joypad.get()

    menu_value = memory.readbyte(menu_check)
    menu_value2 = memory.readbyte(menu_check2)

    -- Checks for LR pressing in menu, a failsafe to ensure some cheats work as intended, when the menu is open
    if (input["P1 L1"] or input["P1 R1"]) and check_for_menu and not menu_closed then 
        LR_check = true
    else
        LR_check = false
    end

    -- Checks to see if the menu is closed
    if menu_value ~= menu_check_value then 
        menu_closed = true
    elseif check_for_menu then
        menu_closed = false
    end
    
    -- Function to draw text with an outline
    function drawOutlinedText(x, y, text, textColor, outlineColor)
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

    readFile(filename)

    -- Take return: the things before a give or take command, to see what it changed
    local ledger_before = nil
    local ledger_kind = string.sub(content, -1)
    if ledger_kind == "+" or ledger_kind == "-" then ledger_reconcile(); ledger_before = ledger_snapshot() end

    function clearFile()
        -- Clear the file after reading commands    
        local clear_file, clear_err = io.open(filename, "w")
        if not clear_file then
            -- emu.message("Error clearing file: " .. (clear_err or "Unknown error"))
        else
            clear_file:close()
        end
    end

    function give_item(address)
        clearFile()
        memory.writebyte(address, 0x01)
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    function take_item(address)
        clearFile()
        memory.writebyte(address, 0x00)
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    function swap_wpn(swap_value, check_weapon)
        clearFile()
        local weapon_exists = true
        swap_to = swap_value

        if check_weapon == dagger then
            if memory.readbyte(dagger) == 0x00 and memory.readbyte(sword) == 0x00 and memory.readbyte(fiend_blade) == 0x00 and 
            memory.readbyte(holy_sword) == 0x00 and memory.readbyte(legend_sword) == 0x00 then
                weapon_exists = false
            end
        end
        if check_weapon == iron_flail then
            if memory.readbyte(iron_flail) == 0x00 and memory.readbyte(steel_flail) == 0x00 then
                weapon_exists = false
            end
        end
        if check_weapon == hunters_bow then
            if memory.readbyte(hunters_bow) == 0x00 and memory.readbyte(willow_bow) == 0x00 then
                weapon_exists = false
            end
        end
        if memory.readbyte(check_weapon) == 0x00 then
            weapon_exists = false
        end

        if weapon_exists then 
            local address = weapon_slot
            memory.writebyte(address, swap_value)
            item_message_timer = item_display_duration
            item_message = popupMessage
            print(popupMessage .. "!")
        else
            item_message_timer = item_display_duration
            item_message = "Cannot Swap (no weapon)"
            print("Cannot swap to weapon" .. "!")
        end
    end

    function swap_item(swap_value, check_item)
        clearFile()
        local item_exists = true

        if check_item == spring_bean then
            if memory.readbyte(spring_bean) == 0x00 then
                item_exists = false
            end
        end
        if check_item == sand_cape then
            if memory.readbyte(sand_cape) == 0x00 then
                item_exists = false
            end
        end
        if check_item == mining_bomb then
            if memory.readbyte(mining_bomb) == 0x00 then
                item_exists = false
            end
        end
        if check_item == herbs then
            if memory.readbyte(herbs) == 0x00 then
                item_exists = false
            end
        end
        if check_item == strength_tonic then
            if memory.readbyte(strength_tonic) == 0x00 then
                item_exists = false
            end
        end
        if check_item == strength_elixir then
            if memory.readbyte(strength_elixir) == 0x00 then
                item_exists = false
            end
        end
        if check_item == magic_elixir then
            if memory.readbyte(magic_elixir) == 0x00 then
                item_exists = false
            end
        end
        if check_item == wonder_essence then
            if memory.readbyte(wonder_essence) == 0x00 then
                item_exists = false
            end
        end
        if check_item == earth_scroll == 0x00 or check_item == earth_book == 0x00 then
            if memory.readbyte(earth_scroll) == 0x00 and memory.readbyte(earth_book) == 0x00 then
                item_exists = false
            end
        end
        if check_item == water_scroll == 0x00 or check_item == water_book == 0x00 then
            if memory.readbyte(water_scroll) == 0x00 and memory.readbyte(water_book) == 0x00 then
                item_exists = false
            end
        end
        if check_item == fire_scroll == 0x00 or check_item == fire_book == 0x00 then
            if memory.readbyte(fire_scroll) == 0x00 and memory.readbyte(fire_book) == 0x00 then
                item_exists = false
            end
        end
        if check_item == wind_scroll == 0x00 or check_item == wind_book == 0x00 then
            if memory.readbyte(wind_scroll) == 0x00 and memory.readbyte(wind_book) == 0x00 then
                item_exists = false
            end
        end
        if check_item == aqua_cape then
            if memory.readbyte(aqua_cape) == 0x00 then
                item_exists = false
            end
        end
        if check_item == navas_charm then
            if memory.readbyte(navas_charm) == 0x00 then
                item_exists = false
            end
        end
        if check_item == power_glove then
            if memory.readbyte(power_glove) == 0x00 then
                item_exists = false
            end
        end
        if check_item == silver_armlet then
            if memory.readbyte(silver_armlet) == 0x00 then
                item_exists = false
            end
        end
        if check_item == olgas_ring or check_item == refresher then
            if memory.readbyte(olgas_ring) == 0x00 and memory.readbyte(refresher) == 0x00 then
                item_exists = false
            end
        end
        if check_item == recovery_ring then
            if memory.readbyte(recovery_ring) == 0x00 then
                item_exists = false
            end
        end
        if memory.readbyte(check_item) == 0x00 then
            item_exists = false
        end

        if item_exists then 
            local address = item_slot
            memory.writebyte(address, swap_value)
            item_message_timer = item_display_duration
            item_message = popupMessage
            print(popupMessage .. "!")
        else
            item_message_timer = item_display_duration
            item_message = "Cannot Swap (no item)"
            print("Cannot swap to weapon" .. "!")
        end
    end

    function force_wpn(swap_value, check_weapon)
        clearFile()
        local weapon_exists = true
        swap_to = swap_value
        force_swap_active = true

        if check_weapon == dagger then
            if memory.readbyte(dagger) == 0x00 and memory.readbyte(sword) == 0x00 and memory.readbyte(fiend_blade) == 0x00 and 
            memory.readbyte(holy_sword) == 0x00 and memory.readbyte(legend_sword) == 0x00 then
                weapon_exists = false
            end
        end
        if check_weapon == iron_flail then
            if memory.readbyte(iron_flail) == 0x00 and memory.readbyte(steel_flail) == 0x00 then
                weapon_exists = false
            end
        end
        if check_weapon == hunters_bow then
            if memory.readbyte(hunters_bow) == 0x00 and memory.readbyte(willow_bow) == 0x00 then
                weapon_exists = false
            end
        end
        if memory.readbyte(check_weapon) == 0x00 then
            weapon_exists = false
        end

        if check_weapon == "Lock_Weapon" then weapon_exists = true end

        if swap_timer_reset > 0 then 
            swap_length = swap_timer_reset
            swap_timer_reset = 0
        end

        if not weapon_exists then
            give_weapon = check_weapon
            memory.writebyte(give_weapon, 0x01)
            ledger_gift(give_weapon, 1) -- (a lent weapon is not the player's: taken, it does not come back)
            return_weapon = true
        end

        local address = weapon_slot
        memory.writebyte(address, swap_value)
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    function lock_wpn()
        clearFile()
        swap_to = memory.readbyte(weapon_slot)
        force_swap_active = true
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
        swap_timer_reset = swap_length
        swap_length = lock_weapon_length
    end

    function lock_itm()
        clearFile()
        locked_item = memory.readbyte(item_slot)
        force_item_active = true
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    -- Spawn enemy (Alundra PC only: the port places one of the map's enemies on screen)
    function spawn_enemy(kind, buffed)
        clearFile()
        local why = "no game"
        if alundra_pc ~= nil then why = alundra_pc.spawn_enemy(kind, buffed == true) end
        item_message_timer = item_display_duration
        if why == "" then item_message = popupMessage else item_message = "Cannot Spawn (" .. why .. ")" end
        print(item_message .. "!")
    end

    -- Force item: equips the item and holds it (as Lock Item); only an item the player has
    function force_itm(check_item)
        clearFile()
        if memory.readbyte(check_item) == 0x00 then
            item_message_timer = item_display_duration
            item_message = "Cannot Force (no item)"
            print("Cannot force item" .. "!")
            return
        end
        locked_item = (check_item - 0x1DD830) // 4 -- Item slot value: the item's place in the inventory
        memory.writebyte(item_slot, locked_item)
        force_item_active = true
        lock_item_timer = 0
        item_message_timer = item_display_duration
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    if not (input["P1 L1"]) and not input["P1 Select"] then L1_swap_check = false end
    if not (input["P1 R1"]) and not input["P1 Select"] then R1_swap_check = false end
    if not (input["P1 L1"]) then select_L1_swap_check = false end
    if not (input["P1 R1"]) then select_R1_swap_check = false end

    -- Weapon swap left, L1
    if input["P1 L1"] and not input["P1 Select"] and not L1_swap_check and menu_closed and LR_swap then
        L1_swap_check = true

        local swap_value = 0x01
        local weapon_value = memory.readbyte(weapon_slot)

        if weapon_value == 0x01 then swap_value = 0x06
        elseif weapon_value == 0x06 then swap_value = 0x05
        elseif weapon_value == 0x05 then swap_value = 0x04
        elseif weapon_value == 0x04 then swap_value = 0x02
        elseif weapon_value == 0x02 then swap_value = 0x03
        elseif weapon_value == 0x03 then swap_value = 0x01  
        end

        local weapon_exists = false

        for i = 1, 6 do
            if swap_value == 0x01 then
                if memory.readbyte(dagger) ~= 0x00 or memory.readbyte(sword) ~= 0x00 or memory.readbyte(fiend_blade) ~= 0x00 or 
                    memory.readbyte(holy_sword) ~= 0x00 or memory.readbyte(legend_sword) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x06
                end
            end
            if swap_value == 0x06 then
                if memory.readbyte(spirit_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x05
                end
            end
            if swap_value == 0x05 then
                if memory.readbyte(fire_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x04
                end
            end
            if swap_value == 0x04 then
                if memory.readbyte(ice_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x02
                end
            end
            if swap_value == 0x02 then
                if memory.readbyte(hunters_bow) ~= 0x00 or memory.readbyte(willow_bow) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x03
                end
            end
            if swap_value == 0x03 then
                if memory.readbyte(iron_flail) ~= 0x00 or memory.readbyte(steel_flail) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x01
                end
            end
        end

        if weapon_exists then 
            local address = weapon_slot
            memory.writebyte(address, swap_value)
        end
    end

    -- Weapon swap right R1
    if input["P1 R1"] and not input["P1 Select"] and not R1_swap_check and menu_closed and LR_swap then
        R1_swap_check = true

        local swap_value = 0x01
        local weapon_value = memory.readbyte(weapon_slot)

        if weapon_value == 0x01 then swap_value = 0x03
        elseif weapon_value == 0x03 then swap_value = 0x02
        elseif weapon_value == 0x02 then swap_value = 0x04
        elseif weapon_value == 0x04 then swap_value = 0x05
        elseif weapon_value == 0x05 then swap_value = 0x06
        elseif weapon_value == 0x06 then swap_value = 0x01
        end

        local weapon_exists = false

        for i = 1, 6 do
            if swap_value == 0x01 then
                if memory.readbyte(dagger) ~= 0x00 or memory.readbyte(sword) ~= 0x00 or memory.readbyte(fiend_blade) ~= 0x00 or 
                    memory.readbyte(holy_sword) ~= 0x00 or memory.readbyte(legend_sword) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x03
                end
            end
            if swap_value == 0x03 then
                if memory.readbyte(iron_flail) ~= 0x00 or memory.readbyte(steel_flail) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x02
                end
            end
            if swap_value == 0x02 then
                if memory.readbyte(hunters_bow) ~= 0x00 or memory.readbyte(willow_bow) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x04
                end
            end
            if swap_value == 0x04 then
                if memory.readbyte(ice_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x05
                end
            end
            if swap_value == 0x05 then
                if memory.readbyte(fire_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x06
                end
            end
            if swap_value == 0x06 then
                if memory.readbyte(spirit_wand) ~= 0x00 then
                    weapon_exists = true
                    break
                else
                    swap_value = 0x01
                end
            end
        end

        if weapon_exists then 
            local address = weapon_slot
            memory.writebyte(address, swap_value)
        end
    end

    -- Item swap left, select + L1
    if input["P1 L1"] and input["P1 Select"] and not select_L1_swap_check and menu_closed and LR_swap then
        select_L1_swap_check = true

        local swap_value = memory.readbyte(item_slot)
        if swap_value == 0x00 then swap_value = items.herbs end

        -- Reverse sequence starting from refresher
        if swap_value == items.refresher then swap_value = items.silver_armlet
        elseif swap_value == items.recovery_ring then swap_value = items.silver_armlet
        elseif swap_value == items.silver_armlet then swap_value = items.olgas_ring
        elseif swap_value == items.olgas_ring then swap_value = items.spring_bean
        elseif swap_value == items.oaks_ring then swap_value = items.spring_bean
        elseif swap_value == items.spring_bean then swap_value = items.power_glove
        elseif swap_value == items.power_glove then swap_value = items.navas_charm
        elseif swap_value == items.navas_charm then swap_value = items.aqua_cape
        elseif swap_value == items.aqua_cape then swap_value = items.sand_cape
        elseif swap_value == items.sand_cape then swap_value = items.wind_scroll
        elseif swap_value == items.wind_book then swap_value = items.fire_scroll
        elseif swap_value == items.wind_scroll then swap_value = items.fire_scroll
        elseif swap_value == items.fire_book then swap_value = items.water_scroll
        elseif swap_value == items.fire_scroll then swap_value = items.water_scroll
        elseif swap_value == items.water_book then swap_value = items.earth_scroll
        elseif swap_value == items.water_scroll then swap_value = items.earth_scroll
        elseif swap_value == items.earth_book then swap_value = items.mining_bomb
        elseif swap_value == items.earth_scroll then swap_value = items.mining_bomb
        elseif swap_value == items.mining_bomb then swap_value = items.wonder_essence
        elseif swap_value == items.wonder_essence then swap_value = items.magic_elixir
        elseif swap_value == items.magic_elixir then swap_value = items.strength_elixir
        elseif swap_value == items.strength_elixir then swap_value = items.strength_tonic
        elseif swap_value == items.strength_tonic then swap_value = items.herbs
        elseif swap_value == items.herbs then swap_value = items.recovery_ring
        end

        local item_exists = false

        -- Loop from 1 to 18, check for items in the reversed order
        for i = 1, 18 do
            local current_item = swap_value
            if current_item == items.recovery_ring or current_item == items.refresher then
                if memory.readbyte(recovery_ring) ~= 0x00 or memory.readbyte(refresher) ~= 0x00 then
                    if memory.readbyte(refresher) ~= 0x00 then current_item = items.herbs end
                    item_exists = true
                    break
                else
                    current_item = items.silver_armlet
                end
            elseif current_item == items.silver_armlet then
                if memory.readbyte(silver_armlet) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.olgas_ring
                end
            elseif current_item == items.olgas_ring or current_item == items.oaks_ring then
                if memory.readbyte(olgas_ring) ~= 0x00 or memory.readbyte(oaks_ring) ~= 0x00 then
                    if memory.readbyte(oaks_ring) ~= 0x00 then current_item = items.oaks_ring end
                    item_exists = true
                    break
                else
                    current_item = items.spring_bean
                end
            elseif current_item == items.spring_bean then
                if memory.readbyte(spring_bean) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.power_glove
                end
            elseif current_item == items.power_glove then
                if memory.readbyte(power_glove) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.navas_charm
                end
            elseif current_item == items.navas_charm then
                if memory.readbyte(navas_charm) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.aqua_cape
                end
            elseif current_item == items.aqua_cape then
                if memory.readbyte(aqua_cape) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.sand_cape
                end
            elseif current_item == items.sand_cape then
                if memory.readbyte(sand_cape) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.wind_scroll
                end
            elseif current_item == items.wind_scroll or current_item == items.wind_book then
                if memory.readbyte(wind_scroll) ~= 0x00 or memory.readbyte(wind_book) ~= 0x00 then
                    if memory.readbyte(wind_book) ~= 0x00 then current_item = items.wind_book end
                    item_exists = true
                    break
                else
                    current_item = items.fire_scroll
                end
            elseif current_item == items.fire_scroll or current_item == items.fire_book then
                if memory.readbyte(fire_scroll) ~= 0x00 or memory.readbyte(fire_book) ~= 0x00 then
                    if memory.readbyte(fire_book) ~=0x00 then current_item = items.fire_book end
                    item_exists = true
                    break
                else
                    current_item = items.water_scroll
                end
            elseif current_item == items.water_scroll or current_item == items.water_book  then
                if memory.readbyte(water_scroll) ~= 0x00 or memory.readbyte(water_book) ~= 0x00 then
                    if memory.readbyte(water_book) ~= 0x00 then current_item = items.water_book end
                    item_exists = true
                    break
                else
                    current_item = items.earth_scroll
                end
            elseif current_item == items.earth_scroll or current_item == items.earth_book then
                if memory.readbyte(earth_scroll) ~= 0x00 or memory.readbyte(earth_book) ~= 0x00 then
                    if memory.readbyte(earth_book) ~= 0x00 then current_item = items.earth_book end
                    item_exists = true
                    break
                else
                    current_item = items.mining_bomb
                end
            elseif current_item == items.mining_bomb then
                if memory.readbyte(mining_bomb) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.wonder_essence
                end
            elseif current_item == items.wonder_essence then
                if memory.readbyte(wonder_essence) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.magic_elixir
                end
            elseif current_item == items.magic_elixir then
                if memory.readbyte(magic_elixir) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.strength_elixir
                end
            elseif current_item == items.strength_elixir then
                if memory.readbyte(strength_elixir) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.strength_tonic
                end
            elseif current_item == items.strength_tonic then
                if memory.readbyte(strength_tonic) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.herbs
                end
            elseif current_item == items.herbs then
                if memory.readbyte(herbs) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.refresher
                end
            end
            
            if item_exists then
                local address = item_slot
                memory.writebyte(address, swap_value)
                break
            end
        end
    end

    -- Item swap right, select + R1
    if input["P1 R1"] and input["P1 Select"] and not select_R1_swap_check and menu_closed and LR_swap then
        select_R1_swap_check = true

        local swap_value = memory.readbyte(item_slot)
        if swap_value == 0x00 then swap_value = items.herbs end

        -- Reverse sequence starting from herbs
        if swap_value == items.herbs then swap_value = items.strength_tonic
        elseif swap_value == items.strength_tonic then swap_value = items.strength_elixir
        elseif swap_value == items.strength_elixir then swap_value = items.magic_elixir
        elseif swap_value == items.magic_elixir then swap_value = items.wonder_essence
        elseif swap_value == items.wonder_essence then swap_value = items.mining_bomb
        elseif swap_value == items.mining_bomb then swap_value = items.earth_scroll
        elseif swap_value == items.earth_scroll then swap_value = items.earth_book
        elseif swap_value == items.earth_book then swap_value = items.water_scroll
        elseif swap_value == items.water_scroll then swap_value = items.water_book
        elseif swap_value == items.water_book then swap_value = items.fire_scroll
        elseif swap_value == items.fire_scroll then swap_value = items.fire_book
        elseif swap_value == items.fire_book then swap_value = items.wind_scroll
        elseif swap_value == items.wind_scroll then swap_value = items.wind_book
        elseif swap_value == items.wind_book then swap_value = items.sand_cape
        elseif swap_value == items.sand_cape then swap_value = items.aqua_cape
        elseif swap_value == items.aqua_cape then swap_value = items.navas_charm
        elseif swap_value == items.navas_charm then swap_value = items.power_glove
        elseif swap_value == items.power_glove then swap_value = items.spring_bean
        elseif swap_value == items.spring_bean then swap_value = items.oaks_ring
        elseif swap_value == items.oaks_ring then swap_value = items.olgas_ring
        elseif swap_value == items.olgas_ring then swap_value = items.silver_armlet
        elseif swap_value == items.silver_armlet then swap_value = items.recovery_ring
        elseif swap_value == items.recovery_ring then swap_value = items.refresher
        end

        local item_exists = false

        -- Loop from 1 to 18, check for items in the reversed order
        for i = 1, 18 do
            local current_item = swap_value
            if current_item == items.recovery_ring or current_item == items.refresher then
                if memory.readbyte(recovery_ring) ~= 0x00 or memory.readbyte(refresher) ~= 0x00 then
                    if memory.readbyte(refresher) ~= 0x00 then current_item = items.herbs end
                    item_exists = true
                    break
                else
                    current_item = items.silver_armlet
                end
            elseif current_item == items.silver_armlet then
                if memory.readbyte(silver_armlet) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.olgas_ring
                end
            elseif current_item == items.olgas_ring or current_item == items.oaks_ring then
                if memory.readbyte(olgas_ring) ~= 0x00 or memory.readbyte(oaks_ring) ~= 0x00 then
                    if memory.readbyte(oaks_ring) ~= 0x00 then current_item = items.oaks_ring end
                    item_exists = true
                    break
                else
                    current_item = items.spring_bean
                end
            elseif current_item == items.spring_bean then
                if memory.readbyte(spring_bean) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.power_glove
                end
            elseif current_item == items.power_glove then
                if memory.readbyte(power_glove) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.navas_charm
                end
            elseif current_item == items.navas_charm then
                if memory.readbyte(navas_charm) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.aqua_cape
                end
            elseif current_item == items.aqua_cape then
                if memory.readbyte(aqua_cape) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.sand_cape
                end
            elseif current_item == items.sand_cape then
                if memory.readbyte(sand_cape) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.wind_scroll
                end
            elseif current_item == items.wind_scroll or current_item == items.wind_book then
                if memory.readbyte(wind_scroll) ~= 0x00 or memory.readbyte(wind_book) ~= 0x00 then
                    if memory.readbyte(wind_book) ~= 0x00 then current_item = items.wind_book end
                    item_exists = true
                    break
                else
                    current_item = items.fire_scroll
                end
            elseif current_item == items.fire_scroll or current_item == items.fire_book then
                if memory.readbyte(fire_scroll) ~= 0x00 or memory.readbyte(fire_book) ~= 0x00 then
                    if memory.readbyte(fire_book) ~=0x00 then current_item = items.fire_book end
                    item_exists = true
                    break
                else
                    current_item = items.water_scroll
                end
            elseif current_item == items.water_scroll or current_item == items.water_book  then
                if memory.readbyte(water_scroll) ~= 0x00 or memory.readbyte(water_book) ~= 0x00 then
                    if memory.readbyte(water_book) ~= 0x00 then current_item = items.water_book end
                    item_exists = true
                    break
                else
                    current_item = items.earth_scroll
                end
            elseif current_item == items.earth_scroll or current_item == items.earth_book then
                if memory.readbyte(earth_scroll) ~= 0x00 or memory.readbyte(earth_book) ~= 0x00 then
                    if memory.readbyte(earth_book) ~= 0x00 then current_item = items.earth_book end
                    item_exists = true
                    break
                else
                    current_item = items.mining_bomb
                end
            elseif current_item == items.mining_bomb then
                if memory.readbyte(mining_bomb) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.wonder_essence
                end
            elseif current_item == items.wonder_essence then
                if memory.readbyte(wonder_essence) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.magic_elixir
                end
            elseif current_item == items.magic_elixir then
                if memory.readbyte(magic_elixir) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.strength_elixir
                end
            elseif current_item == items.strength_elixir then
                if memory.readbyte(strength_elixir) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.strength_tonic
                end
            elseif current_item == items.strength_tonic then
                if memory.readbyte(strength_tonic) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.herbs
                end
            elseif current_item == items.herbs then
                if memory.readbyte(herbs) ~= 0x00 then
                    item_exists = true
                    break
                else
                    current_item = items.refresher
                end
            end
            
            if item_exists then
                local address = item_slot
                memory.writebyte(address, swap_value)
                break
            end
        end
    end

    if item_message_timer == 0 then
        item_message = popupMessage
    end

    -- Give items
    if content == "StrengthTonic+" then give_item(strength_tonic) end
    if content == "StrengthElixir+" then give_item(strength_elixir) end
    if content == "MagicElixir+" then give_item(magic_elixir) end
    if content == "WonderEssence+" then give_item(wonder_essence) end
    if content == "MiningBomb+" then give_item(mining_bomb) end
    if content == "IronFlail+" then give_item(iron_flail) end
    if content == "HuntersBow+" then give_item(hunters_bow) end
    if content == "FireWand+" then give_item(fire_wand) end
    if content == "IceWand+" then give_item(ice_wand) end
    if content == "EarthScroll+" then give_item(earth_scroll) end
    if content == "WaterScroll+" then give_item(water_scroll) end
    if content == "FireScroll+" then give_item(fire_scroll) end
    if content == "WindScroll+" then give_item(wind_scroll) end
    if content == "EarthBook+" then give_item(earth_book) end
    if content == "WaterBook+" then give_item(water_book) end
    if content == "FireBook+" then give_item(fire_book) end
    if content == "WindBook+" then give_item(wind_book) end
    if content == "SandCape+" then give_item(sand_cape) end
    if content == "AquaCape+" then give_item(aqua_cape) end
    if content == "NavasCharm+" then give_item(navas_charm) end
    if content == "PowerGlove+" then give_item(power_glove) end
    if content == "SpringBean+" then give_item(spring_bean) end
    if content == "OlgasRing+" then give_item(olgas_ring) end
    if content == "SilverArmlet+" then give_item(silver_armlet) end
    if content == "RecoveryRing+" then give_item(recovery_ring) end
    if content == "Refresher+" then give_item(refresher) end
    if content == "SpiritWand+" then give_item(spirit_wand) end
    if content == "LegendSword+" then give_item(legend_sword) end
    if content == "SteelFlail+" then give_item(steel_flail) end
    if content == "OaksRing+" then give_item(oaks_ring) end
    if content == "RecoverRing+" then give_item(recovery_ring) end
    if content == "SecretPass+" then give_item(secret_pass) end
    if content == "ElevatorKey+" then give_item(elevator_key) end
    if content == "RubyCrest+" then give_item(ruby_crest) end
    if content == "SapphireCrest+" then give_item(sapphire_crest) end
    if content == "TopazCrest+" then give_item(topaz_crest) end
    if content == "AgateCrest+" then give_item(agate_crest) end
    if content == "GarnetCrest+" then give_item(garnet_crest) end
    if content == "EmeraldCrest+" then give_item(emerald_crest) end
    if content == "DiamondCrest+" then give_item(diamond_crest) end
    if content == "Bouquet+" then give_item(bouquet) end
    if content == "LeatherArmor+" then give_item(leather_armor) end
    if content == "AncientArmor+" then give_item(ancient_armor) end
    if content == "SilverArmor+" then give_item(silver_armor) end
    if content == "LongBoots+" then give_item(long_boots) end
    if content == "MermanBoots+" then give_item(merman_boots) end
    if content == "CharmBoots+" then give_item(charm_boots) end
    if content == "BrokenArmor+" then give_item(broken_armor) end
    if content == "Sword+" then give_item(sword) end
    if content == "FiendBlade+" then give_item(fiend_blade) end
    if content == "HolySword+" then give_item(holy_sword) end
    if content == "GildedFalcon+" then give_falcon() end
    if content == "WillowBow+" then give_item(willow_bow) end
    if content == "Dagger+" then give_item(dagger) end
    if content == "ProtoFlail+" then give_item(proto_flail) end
    if content == "ProtoFireWand+" then give_item(proto_fire_wand) end
    if content == "MP+" then give_mp() end
    if content == "Key+" then give_key() end
    if content == "TreeGem+" then give_item(tree_gem) end
    if content == "JessLetter+" then give_item(jess_letter) end
    if content == "ZolistStone+" then give_item(zolist_stone) end
    if content == "BookOfElna+" then give_item(book_of_elna) end
    if content == "BookOfRunes+" then give_item(book_of_runes) end

    -- Take Items
    if content == "StrengthTonic-" then take_item(strength_tonic) end
    if content == "StrengthElixir-" then take_item(strength_elixir) end
    if content == "MagicElixir-" then take_item(magic_elixir) end
    if content == "WonderEssesence-" then take_item(wonder_essence) end
    if content == "MiningBomb-" then take_item(mining_bomb) end
    if content == "IronFlail-" then take_item(iron_flail) end
    if content == "HuntersBow-" then take_item(hunters_bow) end
    if content == "FireWand-" then take_item(fire_wand) end
    if content == "IceWand-" then take_item(ice_wand) end
    if content == "EarthScroll-" then take_item(earth_scroll) end
    if content == "WaterScroll-" then take_item(water_scroll) end
    if content == "FireScroll-" then take_item(fire_scroll) end
    if content == "WindScroll-" then take_item(wind_scroll) end
    if content == "EarthBook-" then take_item(earth_book) end
    if content == "WaterBook-" then take_item(water_book) end
    if content == "FireBook-" then take_item(fire_book) end
    if content == "WindBook-" then take_item(wind_book) end
    if content == "SandCape-" then take_item(sand_cape) end
    if content == "AquaCape-" then take_item(aqua_cape) end
    if content == "NavasCharm-" then take_item(navas_charm) end
    if content == "PowerGlove-" then take_item(power_glove) end
    if content == "SpringBean-" then take_item(spring_bean) end
    if content == "OlgasRing-" then take_item(olgas_ring) end
    if content == "SilverArmlet-" then take_item(silver_armlet) end
    if content == "RecoveryRing-" then take_item(recovery_ring) end
    if content == "Refresher-" then take_item(refresher) end
    if content == "SpiritWand-" then take_item(spirit_wand) end
    if content == "LegendSword-" then take_item(legend_sword) end
    if content == "SteelFlail-" then take_item(steel_flail) end
    if content == "OaksRing-" then take_item(oaks_ring) end
    if content == "RecoverRing-" then take_item(recovery_ring) end
    if content == "SecretPass-" then take_item(secret_pass) end
    if content == "ElevatorKey-" then take_item(elevator_key) end
    if content == "RubyCrest-" then take_item(ruby_crest) end
    if content == "SapphireCrest-" then take_item(sapphire_crest) end
    if content == "TopazCrest-" then take_item(topaz_crest) end
    if content == "AgateCrest-" then take_item(agate_crest) end
    if content == "GarnetCrest-" then take_item(garnet_crest) end
    if content == "EmeraldCrest-" then take_item(emerald_crest) end
    if content == "DiamondCrest-" then give_item(diamond_crest) end
    if content == "Bouquet-" then take_item(bouquet) end
    if content == "LeatherArmor-" then take_item(leather_armor) end
    if content == "AncientArmor-" then take_item(ancient_armor) end
    if content == "SilverArmor-" then take_item(silver_armor) end
    if content == "LongBoots-" then take_item(long_boots) end
    if content == "MermanBoots-" then take_item(merman_boots) end
    if content == "CharmBoots-" then take_item(charm_boots) end
    if content == "BrokenArmor-" then take_item(broken_armor) end
    if content == "Sword-" then take_item(sword) end
    if content == "FiendBlade-" then take_item(fiend_blade) end
    if content == "HolySword-" then take_item(holy_sword) end
    if content == "GildedFalcon-" then take_falcon() end
    if content == "WillowBow-" then take_item(willow_bow) end
    if content == "Dagger-" then take_item(dagger) end
    if content == "ProtoFlail-" then take_item(proto_flail) end
    if content == "ProtoFireWand-" then take_item(proto_fire_wand) end
    if content == "MP-" then take_mp() end
    if content == "Key-" then take_key() end
    if content == "TreeGem-" then take_item(tree_gem) end
    if content == "JessLetter-" then take_item(jess_letter) end
    if content == "ZolistStone-" then take_item(zolist_stone) end
    if content == "BookOfElna-" then take_item(book_of_elna) end
    if content == "BookOfRunes-" then take_item(book_of_runes) end

    -- Swap weapon
    if content == "SwapSword" then swap_wpn(0x01, dagger) end
    if content == "SwapFlail" then swap_wpn(0x03, iron_flail) end
    if content == "SwapBow" then swap_wpn(0x02, hunters_bow) end
    if content == "SwapFireWand" then swap_wpn(0x05, fire_wand) end
    if content == "SwapIceWand" then swap_wpn(0x04, ice_wand) end
    if content == "SwapSpiritWand" then swap_wpn(0x06, spirit_wand) end

    -- Force weapon
    if content == "ForceSword" then force_wpn(0x01, dagger) end
    if content == "ForceFlail" then force_wpn(0x03, iron_flail) end
    if content == "ForceBow" then force_wpn(0x02, hunters_bow) end
    if content == "ForceFireWand" then force_wpn(0x05, fire_wand) end
    if content == "ForceIceWand" then force_wpn(0x04, ice_wand) end
    if content == "ForceSpiritWand" then force_wpn(0x06, spirit_wand) end

    -- Swap item
    if content == "SwapHerbs" then swap_item(items.herbs, herbs) end
    if content == "SwapStrengthTonic" then swap_item(items.strength_tonic, strength_tonic) end
    if content == "SwapStrengthElixir" then swap_item(items.strength_elixir, strength_elixir) end
    if content == "SwapMagicElixir" then swap_item(items.magic_elixir, magic_elixir) end
    if content == "SwapWonderEssence" then swap_item(items.wonder_essence, wonder_essence) end
    if content == "SwapMiningBomb" then swap_item(items.mining_bomb, mining_bomb) end
    if content == "SwapSandCape" then swap_item(items.sand_cape, sand_cape) end
    if content == "SwapAquaCape" then swap_item(items.aqua_cape, aqua_cape) end
    if content == "SwapEarthScroll" then swap_item(items.earth_magic, earth_scroll) end
    if content == "SwapEarthBook" then swap_item(items.earth_magic, earth_book) end
    if content == "SwapWaterScroll" then swap_item(items.water_magic, water_scroll) end
    if content == "SwapWaterBook" then swap_item(items.water_magic, water_book) end
    if content == "SwapFireScroll" then swap_item(items.fire_magic, fire_scroll) end
    if content == "SwapFireBook" then swap_item(items.fire_magic, fire_book) end
    if content == "SwapWindScroll" then swap_item(items.wind_magic, wind_scroll) end
    if content == "SwapWindBook" then swap_item(items.wind_magic, wind_book) end
    if content == "SwapOlgasRing" then swap_item(items.olgas_ring, olgas_ring) end
    if content == "SwapOaksRing" then swap_item(items.olgas_ring, olgas_ring) end
    if content == "SwapSilverArmlet" then swap_item(items.silver_armlet, silver_armlet) end
    if content == "SwapNavasCharm" then swap_item(items.navas_charm, navas_charm) end
    if content == "SwapPowerGlove" then swap_item(items.power_glove, power_glove) end
    if content == "SwapSpringBean" then swap_item(items.spring_bean, spring_bean) end
    if content == "SwapRecoveryRing" then swap_item(items.recovery_ring, recovery_ring) end
    if content == "SwapRefresher" then swap_item(items.recovery_ring, recovery_ring) end

    -- Lock commands
    if content == "LockWeapon" then lock_wpn() end
    if content == "LockItem" then lock_itm() end

    -- Force item
    if content == "ForceHerbs" then force_itm(herbs) end
    if content == "ForceStrengthTonic" then force_itm(strength_tonic) end
    if content == "ForceStrengthElixir" then force_itm(strength_elixir) end
    if content == "ForceMagicElixir" then force_itm(magic_elixir) end
    if content == "ForceWonderEssence" then force_itm(wonder_essence) end
    if content == "ForceMiningBomb" then force_itm(mining_bomb) end
    if content == "ForceSandCape" then force_itm(sand_cape) end
    if content == "ForceAquaCape" then force_itm(aqua_cape) end
    if content == "ForceEarthScroll" then force_itm(earth_scroll) end
    if content == "ForceEarthBook" then force_itm(earth_book) end
    if content == "ForceWaterScroll" then force_itm(water_scroll) end
    if content == "ForceWaterBook" then force_itm(water_book) end
    if content == "ForceFireScroll" then force_itm(fire_scroll) end
    if content == "ForceFireBook" then force_itm(fire_book) end
    if content == "ForceWindScroll" then force_itm(wind_scroll) end
    if content == "ForceWindBook" then force_itm(wind_book) end
    if content == "ForceOlgasRing" then force_itm(olgas_ring) end
    if content == "ForceOaksRing" then force_itm(oaks_ring) end
    if content == "ForceSilverArmlet" then force_itm(silver_armlet) end
    if content == "ForceNavasCharm" then force_itm(navas_charm) end
    if content == "ForcePowerGlove" then force_itm(power_glove) end
    if content == "ForceSpringBean" then force_itm(spring_bean) end
    if content == "ForceRecoveryRing" then force_itm(recovery_ring) end
    if content == "ForceRefresher" then force_itm(refresher) end

    -- Spawn enemy (Alundra PC only)
    if content == "SpawnEnemy" then spawn_enemy("Enemy") end
    if content == "SpawnPuku" then spawn_enemy("Puku") end
    if content == "SpawnSlime" then spawn_enemy("Slime") end
    if content == "SpawnWasp" then spawn_enemy("Wasp") end
    if content == "SpawnKiller" then spawn_enemy("Killer") end
    if content == "SpawnRoach" then spawn_enemy("Roach") end
    if content == "SpawnMurgg" then spawn_enemy("Murgg") end
    if content == "SpawnGragg" then spawn_enemy("Gragg") end
    if content == "SpawnSandWorm" then spawn_enemy("SandWorm") end
    if content == "SpawnSludge" then spawn_enemy("Sludge") end
    if content == "SpawnMiming" then spawn_enemy("Miming") end
    if content == "SpawnReaper" then spawn_enemy("Reaper") end
    if content == "SpawnShadow" then spawn_enemy("Shadow") end
    if content == "SpawnLizardman" then spawn_enemy("Lizardman") end
    if content == "SpawnZombie" then spawn_enemy("Zombie") end
    if content == "SpawnTurtle" then spawn_enemy("Turtle") end
    if content == "SpawnMimic" then spawn_enemy("Mimic") end
    if content == "SpawnMudMan" then spawn_enemy("MudMan") end
    if content == "SpawnMushroom" then spawn_enemy("Mushroom") end
    if content == "SpawnMummy" then spawn_enemy("Mummy") end
    if content == "SpawnRedTurtle" then spawn_enemy("RedTurtle") end
    if content == "SpawnRockFace" then spawn_enemy("RockFace") end
    if content == "SpawnTreant" then spawn_enemy("Treant") end
    if content == "SpawnFirebird" then spawn_enemy("Firebird") end
    if content == "SpawnShrineMummy" then spawn_enemy("ShrineMummy") end
    if content == "SpawnRoper" then spawn_enemy("Roper") end
    if content == "SpawnShrineDemon" then spawn_enemy("ShrineDemon") end
    if content == "BuffSpawnEnemy" then spawn_enemy("Enemy", true) end
    if content == "BuffSpawnPuku" then spawn_enemy("Puku", true) end
    if content == "BuffSpawnSlime" then spawn_enemy("Slime", true) end
    if content == "BuffSpawnWasp" then spawn_enemy("Wasp", true) end
    if content == "BuffSpawnKiller" then spawn_enemy("Killer", true) end
    if content == "BuffSpawnRoach" then spawn_enemy("Roach", true) end
    if content == "BuffSpawnMurgg" then spawn_enemy("Murgg", true) end
    if content == "BuffSpawnGragg" then spawn_enemy("Gragg", true) end
    if content == "BuffSpawnSandWorm" then spawn_enemy("SandWorm", true) end
    if content == "BuffSpawnSludge" then spawn_enemy("Sludge", true) end
    if content == "BuffSpawnMiming" then spawn_enemy("Miming", true) end
    if content == "BuffSpawnReaper" then spawn_enemy("Reaper", true) end
    if content == "BuffSpawnShadow" then spawn_enemy("Shadow", true) end
    if content == "BuffSpawnLizardman" then spawn_enemy("Lizardman", true) end
    if content == "BuffSpawnZombie" then spawn_enemy("Zombie", true) end
    if content == "BuffSpawnTurtle" then spawn_enemy("Turtle", true) end
    if content == "BuffSpawnMimic" then spawn_enemy("Mimic", true) end
    if content == "BuffSpawnMudMan" then spawn_enemy("MudMan", true) end
    if content == "BuffSpawnMushroom" then spawn_enemy("Mushroom", true) end
    if content == "BuffSpawnMummy" then spawn_enemy("Mummy", true) end
    if content == "BuffSpawnRedTurtle" then spawn_enemy("RedTurtle", true) end
    if content == "BuffSpawnRockFace" then spawn_enemy("RockFace", true) end
    if content == "BuffSpawnTreant" then spawn_enemy("Treant", true) end
    if content == "BuffSpawnFirebird" then spawn_enemy("Firebird", true) end
    if content == "BuffSpawnShrineMummy" then spawn_enemy("ShrineMummy", true) end
    if content == "BuffSpawnRoper" then spawn_enemy("Roper", true) end
    if content == "BuffSpawnShrineDemon" then spawn_enemy("ShrineDemon", true) end
    
    -- Give Falcon
    function give_falcon()
        clearFile()
        local falcons = memory.readbyte(gilded_falcon)
        local new_falcon_value = math.min(falcons + 1, 50)
        item_message_timer = item_display_duration
        memory.writebyte(gilded_falcon, new_falcon_value)
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    -- Take Falcon
    function take_falcon()
        clearFile()
        local falcons = memory.readbyte(gilded_falcon)
        if falcons > 0 then
            local new_falcon_value = math.min(falcons - 1, 50)
            item_message_timer = item_display_duration
            memory.writebyte(gilded_falcon, new_falcon_value)
            item_message = popupMessage
            print(popupMessage .. "!")
        end
    end

    -- Give Key
    function give_key()
        clearFile()
        local keys = memory.readbyte(key)
        local new_key_value = math.min(keys + 1, 99)
        item_message_timer = item_display_duration
        memory.writebyte(key, new_key_value)
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    -- Take Key
    function take_key()
        clearFile()
        local keys = memory.readbyte(key)
        -- if keys > 0 then
            local new_key_value = math.min(keys - 1, 99)
            item_message_timer = item_display_duration
            memory.writebyte(key, new_key_value)
            item_message = popupMessage
            print(popupMessage .. "!")
        -- end
    end

    -- Give MP
    function give_mp()
        clearFile()
        local current_mp = memory.readbyte(current_magic_address)
        local current_max_mp = memory.readbyte(max_magic_address)
        local new_mp_value = math.min(current_mp + 1, current_max_mp)
        item_message_timer = item_display_duration
        memory.writebyte(current_magic_address, new_mp_value)
        item_message = popupMessage
        print(popupMessage .. "!")
    end
    
    -- Take MP
    function take_mp()
        clearFile()
        local current_mp = memory.readbyte(current_magic_address)
        local new_mp_value = math.min(current_mp - 1, 0)
        if new_mp_value < 0 then new_mp_value = 0 end
        item_message_timer = item_display_duration
        memory.writebyte(current_magic_address, new_mp_value)
        item_message = popupMessage
        print(popupMessage .. "!")
    end

    -- Invincibility
    if content == "Invincibility" then
        clearFile()
        if not debounce_invincibility then
            cheat_active = not cheat_active -- Toggle the cheat state
            debounce_invincibility = true -- Prevent multiple toggles per press

            if invincibility_length < item_display_duration then
                item_message_timer = invincibility_length
            else
                item_message_timer = item_display_duration
            end

            item_message = string.gsub(item_message, " ", "")

            if cheat_active then
                print("Invincibility Activated!")
                invincibility_timer = 0 -- Reset the timer immediately when activated
            else
                print("Invincibility Deactivated!")
                invincibility_timer = 0 -- Reset the timer immediately when turned off
            end
        end
    else
        debounce_invincibility = false -- Reset debounce when the keys are released
    end

    -- No I Frames
    if content == "NoIFrames" then
        clearFile()
        if not debounce_iFrame then
            iFrame_cheat_active = not iFrame_cheat_active -- Toggle iFrame cheat state
            debounce_iFrame = true -- Prevent multiple toggles per press

            if no_iframes_length < item_display_duration then
                item_message_timer = no_iframes_length
            else
                item_message_timer = item_display_duration
            end

            item_message = string.gsub(item_message, " ", "")

            if iFrame_cheat_active then
                print("No iFrames Cheat Activated!")
                iFrame_timer = 0 -- Reset the timer immediately when activated
            else
                print("No iFrames Cheat Deactivated!")
                iFrame_timer = 0 -- Reset the timer immediately when turned off
            end
        end
    else
        debounce_iFrame = false -- Reset debounce when the keys are released
    end

    -- Give Gilder 
    if content == "Gilder+" then
        clearFile()
        if not debounce_gilder then
            debounce_gilder = true -- Activate debounce for Gilder cheat

            -- Read the current 16-bit Gilder value from memory
            local lower_byte = memory.readbyte(gilder_address)
            local upper_byte = memory.readbyte(gilder_address + 1)
            local current_gilder_value = (upper_byte << 8) | lower_byte  -- Combine bytes into a 16-bit value

            -- Add 50 to the current Gilder value and cap it at 9999
            local new_gilder_value = math.min(current_gilder_value + gilder_give, 9999)
            item_message_timer = item_display_duration

            -- Write the updated 16-bit value back to memory
            memory.writebyte(gilder_address, new_gilder_value & 0xFF)           -- Write lower byte
            memory.writebyte(gilder_address + 1, (new_gilder_value >> 8) & 0xFF)  -- Write upper byte

            -- Print the updated Gilder value
            print("Gilder increased! New amount: " .. new_gilder_value)
        end
    else
        debounce_gilder = false -- Reset debounce when the keys are released
    end

    -- Take Gilder 
    if content == "Gilder-" then
        clearFile()
        if not debounce_gilder then
            debounce_gilder = true -- Activate debounce for Gilder cheat

            -- Read the current 16-bit Gilder value from memory
            local lower_byte = memory.readbyte(gilder_address)
            local upper_byte = memory.readbyte(gilder_address + 1)
            local current_gilder_value = (upper_byte << 8) | lower_byte  -- Combine bytes into a 16-bit value

            -- Add 50 to the current Gilder value and cap it at 9999
            local new_gilder_value = math.max(current_gilder_value - gilder_take, 0)
            item_message_timer = item_display_duration

            -- Write the updated 16-bit value back to memory
            memory.writebyte(gilder_address, new_gilder_value & 0xFF)           -- Write lower byte
            memory.writebyte(gilder_address + 1, (new_gilder_value >> 8) & 0xFF)  -- Write upper byte

            -- Print the updated Gilder value
            print("Gilder decreased! New amount: " .. new_gilder_value)
        end
    else
        debounce_gilder = false -- Reset debounce when the keys are released
    end

    -- Give Herbs
    if content == "Herbs+" then
        clearFile()
        if not debounce_herb then
            debounce_herb = true -- Prevent multiple increments per press
            local current_herb_value = memory.readbyte(herbs) -- Read current herb value
            item_message_timer = item_display_duration

            if current_herb_value < max_herb_value then
                local new_herb_value = current_herb_value + 1
                memory.writebyte(herbs, new_herb_value) -- Increment herb value
                item_message = "Herbs Obtained! Amount: " .. tostring(new_herb_value) .. popupMessage -- Show herb value as decimal
            else
                item_message = "Herbs is already at maximum!" .. popupMessage -- Show herb value as decimal
            end

            print(item_message)
        end
    else
        debounce_herb = false
    end

    -- Take Herbs
    if content == "Herbs-" then
        clearFile()
        if not debounce_remove_herb then
            debounce_remove_herb = true -- Prevent multiple decrements per press
            local current_herb_value = memory.readbyte(herbs) -- Read current herb value
            item_message_timer = item_display_duration

            if current_herb_value > 0x00 then
                local new_herb_value = current_herb_value - 1
                memory.writebyte(herbs, new_herb_value) -- Decrement herb value
                item_message = "Herbs Lost! Amount: " .. tostring(new_herb_value) .. popupMessage-- Show herb value as decimal
            else
                item_message = "Herbs is already at Zero!" .. popupMessage -- Show herb value as decimal
            end

            print(item_message)
        end
    else
        debounce_remove_herb = false
    end

    -- No Jump
    if content == "NoJump" then
        clearFile()
        if not debounce_no_jump then
            no_jump_active = not no_jump_active -- Toggle No Jump cheat state
            debounce_no_jump = true -- Prevent multiple toggles per press

            if no_jump_length < item_display_duration then
                item_message_timer = invincibility_length
            else
                item_message_timer = item_display_duration
            end

            item_message = string.gsub(item_message, " ", "")

            if no_jump_active then
                print("No Jump Cheat Activated!")
                no_jump_timer = 0 -- Reset the timer immediately when activated
            else
                print("No Jump Cheat Deactivated!")
                no_jump_timer = 0 -- Reset the timer immediately when turned off
            end
        end
    else
        debounce_no_jump = false -- Reset debounce when the keys are released
    end

    -- Slow Motion
    if content == "SlowMotion" then
        clearFile()
        if not debounce_slow_motion then
            slow_motion_active = not slow_motion_active -- Toggle Slow Motion cheat state
            debounce_slow_motion = true -- Prevent multiple toggles per press

            if slow_motion_length < item_display_duration then
                item_message_timer = slow_motion_length
            else
                item_message_timer = item_display_duration
            end

            item_message = string.gsub(item_message, " ", "")

            if slow_motion_active then
                print("Slow Motion Cheat Activated!")
                slow_motion_timer = 0 -- Reset the timer immediately when activated
            else
                print("Slow Motion Cheat Deactivated!")
                slow_motion_timer = 0 -- Reset the timer immediately when turned off
            end
        end
    else
        debounce_slow_motion = false -- Reset debounce when the keys are released
    end

    -- Moon Jump
    if content == "MoonJump" then
        clearFile()
        if not debounce_moon_jump then
            moon_jump_active = not moon_jump_active -- Toggle Moon Jump state
            debounce_moon_jump = true -- Prevent multiple toggles per press

            if moon_jump_length < item_display_duration then
                item_message_timer = moon_jump_length
            else
                item_message_timer = item_display_duration
            end

            if moon_jump_active then
                print("Moon Jump Activated!")
                moon_jump_timer = 0 -- Reset the timer immediately when activated
            else
                print("Moon Jump Deactivated!")
                moon_jump_timer = 0 -- Reset the timer immediately when turned off
            end
        end
    else
        debounce_moon_jump = false -- Reset debounce when the keys are released
    end

    -- Anti Grav
    if content == "AntiGrav" then
        clearFile()
        -- Add later
    end

    -- Increase Health Cheat
    if content == "LifeVessel+" then
        clearFile()
        if not debounce_health_increase then
            debounce_health_increase = true -- Prevent multiple increments per press

            -- Read current health value
            local current_max_health_value = memory.readbyte(max_health_address) -- Read 16-bit value from address
            item_message_timer = item_display_duration

            if current_health_value < 50 then
                -- Increment health, but not beyond the max value
                local new_health_value = math.min(current_max_health_value + 1, 50)
                memory.writebyte(max_health_address, new_health_value) -- Set new health value
                print("Health Increased! New Amount: " .. tostring(new_health_value))
            else
                print("Health is already at maximum!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_increase then
            debounce_duration_increase = debounce_duration_increase + 1
            if debounce_duration_increase >= debounce_reset_duration then
                debounce_health_increase = false
                debounce_duration_increase = 0 -- Reset debounce duration
            end
        end
    end

    -- Decrease Health Cheat
    if content == "LifeVessel-" then
        clearFile()
        if not debounce_health_decrease then
            debounce_health_decrease = true -- Prevent multiple decrements per press

            -- Read current health value
            local current_max_health_value = memory.readbyte(max_health_address) -- Read 16-bit value from address
            item_message_timer = item_display_duration

            if current_max_health_value > 1 then
                -- Decrement health, but not below 0
                local new_health_value = math.max(current_max_health_value - 1, 0)
                memory.writebyte(max_health_address, new_health_value) -- Set new health value
                print("Health Decreased! New Amount: " .. tostring(new_health_value))
            else
                print("Health is already at minimum!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_decrease then
            debounce_duration_decrease = debounce_duration_decrease + 1
            if debounce_duration_decrease >= debounce_reset_duration then
                debounce_health_decrease = false
                debounce_duration_decrease = 0 -- Reset debounce duration
            end
        end
    end

    -- Increase Current Health
    if content == "HP+" then
        clearFile()
        if not debounce_health_increase then
            debounce_health_increase = true -- Prevent multiple increments per press

            -- Read current health value
            local current_health_value = memory.readbyte(current_health_address) -- Read 8-bit value from address
            local current_max_health_value = memory.readbyte(max_health_address)

            item_message_timer = item_display_duration

            if current_health_value < current_max_health_value then
                -- Increment health, but not beyond the max value
                local new_health_value = math.min(current_health_value + hp_change, current_max_health_value)
                memory.writebyte(current_health_address, new_health_value) -- Set new health value
                print("Health Increased! New Amount: " .. tostring(new_health_value))
            else
                print("Health is already at maximum!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_increase then
            debounce_duration_increase = debounce_duration_increase + 1
            if debounce_duration_increase >= debounce_reset_duration then
                debounce_health_increase = false
                debounce_duration_increase = 0 -- Reset debounce duration
            end
        end
    end

    -- Decrease Current Health
    if content == "HP-" then
        clearFile()
        if not debounce_health_decrease then
            debounce_health_decrease = true -- Prevent multiple decrements per press

            -- Read current health value
            local current_health_value = memory.readbyte(current_health_address) -- Read 8-bit value from address
            item_message_timer = item_display_duration

            if current_health_value > 1 then
                -- Decrement health, but not below 0
                local new_health_value = math.max(current_health_value - hp_change, 1)
                memory.writebyte(current_health_address, new_health_value) -- Set new health value
                print("Health Decreased! New Amount: " .. tostring(new_health_value))
            else
                print("Health is already at 1!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_decrease then
            debounce_duration_decrease = debounce_duration_decrease + 1
            if debounce_duration_decrease >= debounce_reset_duration then
                debounce_health_decrease = false
                debounce_duration_decrease = 0 -- Reset debounce duration
            end
        end
    end

    -- Regen cheat
    if content == "Regen" then
        clearFile()
        regen_active = true
        item_message_timer = item_display_duration
    end

    -- Poison cheat
    if content == "Poison" then
        clearFile()
        poison_active = true
        item_message_timer = item_display_duration
    end

    -- Increase Max Magic
    if content == "MagicSeed+" then
        clearFile()
        if not debounce_health_increase then
            debounce_health_increase = true -- Prevent multiple increments per press
            
            -- Read current Magic value
            local current_max_magic_value = memory.readbyte(max_magic_address) -- Read 16-bit value from address
            local current_magic_value = memory.readbyte(current_magic_address)

            item_message_timer = item_display_duration

            if current_magic_value < 4 then
                -- Increment health, but not beyond the max value
                local new_magic_value = math.min(current_max_magic_value + 1, 4)
                memory.writebyte(max_magic_address, new_magic_value) -- Set new health value
                print("Magic Increased! New Amount: " .. tostring(new_magic_value))
            else
                print("Magic is already at maximum!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_increase then
            debounce_duration_increase = debounce_duration_increase + 1
            if debounce_duration_increase >= debounce_reset_duration then
                debounce_health_increase = false
                debounce_duration_increase = 0 -- Reset debounce duration
            end
        end
    end

    -- Decrease Max Magic
    if content == "MagicSeed-" then
        clearFile()
        if not debounce_health_decrease then
            debounce_health_decrease = true -- Prevent multiple decrements per press

            -- Read current Magic value
            local current_max_magic_value = memory.readbyte(max_magic_address) -- Read 16-bit value from address

            item_message_timer = item_display_duration

            if current_max_magic_value > -1 then
                -- Decrement health, but not below 0
                local new_magic_value = math.max(current_max_magic_value - 1, 0)
                memory.writebyte(max_magic_address, new_magic_value) -- Set new health value
                print("Magic Decreased! New Amount: " .. tostring(new_magic_value))
            else
                print("Magic is already at Zero!")
            end
        end
    else
        -- Reset debounce after a small delay when keys are released
        if debounce_health_decrease then
            debounce_duration_decrease = debounce_duration_decrease + 1
            if debounce_duration_decrease >= debounce_reset_duration then
                debounce_health_decrease = false
                debounce_duration_decrease = 0 -- Reset debounce duration
            end
        end
    end

    -- Take return: what the command gave or took; earned things taken come back on their timer
    if ledger_before ~= nil then ledger_after(ledger_before, ledger_kind) end
    ledger_tick(menu_closed and not LR_check)

    -- Timer-based toggling for No Jump (only if cheat is active)
    if no_jump_active and menu_closed and not LR_check then
        no_jump_timer = no_jump_timer + 1 -- Increment the No Jump timer

        if no_jump_timer >= no_jump_length then
            -- Automatically toggle No Jump off after the interval
            no_jump_active = false
            no_jump_timer = 0 -- Reset the No Jump timer
            print("No Jump Cheat Deactivated!")
        end
    end

    -- Timer-based toggling for Invincibility
    if cheat_active and menu_closed and not LR_check then
        invincibility_timer = invincibility_timer + 1 -- Increment the timer

        if invincibility_timer >= invincibility_length then
            -- Automatically toggle invincibility off after the interval
            cheat_active = false
            invincibility_timer = 0 -- Reset the timer
            print("Invincibility Deactivated!")
        end
    end

    -- Timer-based toggling for No iFrames
    if iFrame_cheat_active and menu_closed and not LR_check then
        iFrame_timer = iFrame_timer + 1 -- Increment the iFrame timer

        if iFrame_timer >= no_iframes_length then
            -- Automatically toggle No iFrames off after the interval
            iFrame_cheat_active = false
            iFrame_timer = 0 -- Reset the iFrame timer
            print("No iFrames Cheat Deactivated!")
        end
    end

    -- Timer-based toggling for Slow Motion
    if slow_motion_active then
        slow_motion_timer = slow_motion_timer + 1 -- Increment the Slow Motion timer

        if slow_motion_timer >= slow_motion_length then
            -- Automatically toggle Slow Motion off after the interval
            slow_motion_active = false
            slow_motion_timer = 0 -- Reset the Slow Motion timer
            print("Slow Motion Cheat Deactivated!")
        end
    end

    -- Timer-based toggling for Moon Jump
    if moon_jump_active then
        moon_jump_timer = moon_jump_timer + 1 -- Increment the Moon Jump timer

        if moon_jump_timer >= moon_jump_length then
            -- Automatically toggle Moon Jump off after the interval
            moon_jump_active = false
            moon_jump_timer = 0 -- Reset the timer
            print("Moon Jump Deactivated!")
        end
    end

    -- Timer-based toggling for Force Weapon
    if force_swap_active then

        if menu_closed and not LR_check then 
            swap_timer = swap_timer + 1 
        end
        memory.writebyte(weapon_slot, swap_to)

        if swap_timer >= swap_length then
            force_swap_active = false

            if return_weapon then 
                memory.writebyte(give_weapon, 0x00)
                swap_wpn(0x01, dagger)
                return_weapon = false
            end
            
            swap_timer = 0 -- Reset the timer
            print("Forced Weapon Deactivated!")
        end
    end

    if force_item_active then

        if menu_closed and not LR_check then 
        lock_item_timer = lock_item_timer + 1
        end
        memory.writebyte(item_slot, locked_item)

        if lock_item_timer >= lock_item_length then
            force_item_active = false         
            lock_item_timer = 0 -- Reset the timer
            print("Item Lock Deactivated!")
        end
    end

    -- Apply Slow Motion cheat based on the current state
    if slow_motion_active then
        memory.write_u16_be(slow_motion_address, slow_motion_value)
    end

    -- Apply Moon Jump based on the current state
    if moon_jump_active then
        memory.writebyte(moon_jump_address1, moon_jump_value1)
        memory.writebyte(moon_jump_address2, moon_jump_value2)
    end

    -- Apply Invincibility based on the current state
    if cheat_active then
        memory.writebyte(invincibility_cheat_address, cheat_value)
    end

    -- Apply iFrame cheat based on the current state
    if iFrame_cheat_active then
        memory.writebyte(iFrame_cheat_address, iFrame_cheat_value_on)
    end

    -- Apply No Jump cheat based on the current state
    if no_jump_active then
        memory.writebyte(no_jump_address, no_jump_value)
    end

    if regen_active and menu_closed and not LR_check then
        -- Read current health value
        local current_health_value = memory.readbyte(current_health_address)
        local current_max_health_value = memory.readbyte(max_health_address)

        regen_timer = regen_timer + 1
        regen_ttimer = regen_ttimer + 1

        if regen_ttimer > regen_tick then 
            if current_health_value < current_max_health_value then
                -- Increment health, but not beyond the max value
                local new_health_value = math.min(current_health_value + 1, current_max_health_value)
                memory.writebyte(current_health_address, new_health_value) -- Set new health value
                print("Health Increased! New Amount: " .. tostring(new_health_value))
            end
            regen_ttimer = 0
        end

        if regen_timer > regen_length then 
            regen_timer = 0
            regen_active = false 
        end
    end

    if poison_active and menu_closed and not LR_check then
        -- Read current health value
        local current_health_value = memory.readbyte(current_health_address)

        poison_timer = poison_timer + 1
        poison_ttimer = poison_ttimer + 1

        if poison_ttimer > poison_tick then 
            if current_health_value > 1 then
                -- Decrement health, but not below 0
                local new_health_value = math.max(current_health_value - 1, 1)
                memory.writebyte(current_health_address, new_health_value) -- Set new health value
                print("Health Decreased! New Amount: " .. tostring(new_health_value))
            end
            poison_ttimer = 0
        end

        if poison_timer > poison_length then 
            poison_timer = 0
            poison_active = false 
        end
    end

    -- Display cheat statuses
    if cheat_active then
        drawOutlinedText(base_x, base_y + line_spacing, "Invincibility", textColor, outlineColor)
    else
        drawOutlinedText(base_x, base_y + line_spacing, "", textColor, outlineColor)
    end

    if iFrame_cheat_active then
        drawOutlinedText(base_x, base_y, "No I Frames", textColor, outlineColor)
    else
        drawOutlinedText(base_x, base_y, "", textColor, outlineColor)
    end

    if no_jump_active then
        drawOutlinedText(base_x, base_y - line_spacing, "No Jump", textColor, outlineColor)
    else
        drawOutlinedText(base_x, base_y - line_spacing, "", textColor, outlineColor)
    end

    if slow_motion_active then
        drawOutlinedText(base_x, base_y - 2 * line_spacing, "Slow Motion", textColor, outlineColor)
    else
        drawOutlinedText(base_x, base_y - 2 * line_spacing, "", textColor, outlineColor)
    end

    if force_swap_active and not force_item_active then
        drawOutlinedText(base_x, 0, "Weapon Locked", textColor, outlineColor)
    else
        drawOutlinedText(base_x, 0, "", textColor, outlineColor)
    end

    if force_item_active and not force_swap_active then
        drawOutlinedText(base_x, 0, "Item Locked", textColor, outlineColor)
    else
        drawOutlinedText(base_x, 0, "", textColor, outlineColor)
    end

    if force_item_active and force_swap_active then
        drawOutlinedText(base_x, 0, "Weapon & Item Locked", textColor, outlineColor)
    else
        drawOutlinedText(base_x, 0, "", textColor, outlineColor)
    end

    if poison_active and not regen_active then
        drawOutlinedText(base_x + 116, 0, "Poisoned", textColor, outlineColor)
    else
        drawOutlinedText(base_x + 116, 0, "", textColor, outlineColor)
    end

    if regen_active and not poison_active then
        drawOutlinedText(base_x + 116, 0, "Regen", textColor, outlineColor)
    else
        drawOutlinedText(base_x + 116, 0, "", textColor, outlineColor)
    end

    if regen_active and poison_active then
        drawOutlinedText(base_x + 116, 0, "Regen & Poison", textColor, outlineColor)
    else
        drawOutlinedText(base_x + 116, 0, "", textColor, outlineColor)
    end

    -- Display item message if timer is active
    if item_message_timer > 0 then
        drawOutlinedText(base_x, base_y + 2 * line_spacing, item_message, textColor, outlineColor)
        item_message_timer = item_message_timer - 1
    end

    -- Advance to the next frame
    emu.frameadvance()
end