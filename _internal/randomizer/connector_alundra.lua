local socket = require("socket")
local json = require("json")
require("common")

local STATE_OK = "Ok"
local STATE_NONE = "None"

local state = STATE_NONE
local server = nil
local archSocket = nil
local frame = 0
local current_map_check = 0x1F11FC
local position_x = 0x1D7B40
local position_y = 0x1D7B90
local current_magic_address = 0x1DD820

local items_by_id = {
    [553001] = {"item", "Life Vessel", 0x1AC710, 40},
    [553002] = {"item", "Magic Seed", 0x1DD822, 4},
    [553003] = {"item", "Herbs", 0x1DD8C0, 9},
    [553004] = {"item", "Strength Tonic", 0x1DD8D4, 1},
    [553005] = {"item", "Strength Elixir", 0x1DD8C4, 1},
    [553006] = {"item", "Magic Elixir", 0x1DD8C8, 1},
    [553007] = {"item", "Wonder Essence", 0x1DD8CC, 1},
    [553016] = {"item", "Ice Wand", 0x1DD868, 1},
    [553017] = {"item", "Fire Wand", 0x1DD870, 1},
    [553018] = {"item", "Spirit Wand", 0x1DD84C, 1},
    [553019] = {"item", "Mining Bomb", 0x1DD8BC, 1},
    [553028] = {"item", "Sand Cape", 0x1DD8B0, 1},
    [553029] = {"item", "Aqua Cape", 0x1DD8D0, 1},
    [553030] = {"item", "Nava's Charm", 0x1DD908, 1},
    [553031] = {"item", "Power Glove", 0x1DD91C, 1},
    [553032] = {"item", "Spring Bean", 0x1DD8AC, 1},
    [553033] = {"item", "Olga's Ring", 0x1DD8FC, 1},
    [553034] = {"item", "Silver Armlet", 0x1DD904, 1},
    [553035] = {"item", "Recovery Ring", 0x1DD90C, 1},
    [553036] = {"item", "Long Boots", 0x1DD898, 1},
    [553037] = {"item", "Merman Boots", 0x1DD89C, 1},
    [553038] = {"item", "Charm Boots", 0x1DD8A0, 1},
    [553039] = {"item", "Leather Armor", 0x1DD878, 1},
    [553040] = {"item", "Ancient Armor", 0x1DD87C, 1},
    [553041] = {"item", "Silver Armor", 0x1DD880, 1},
    [553042] = {"item", "Bouquet", 0x1DD958, 1},
    [553043] = {"item", "Tree Gem", 0x1DD964, 1},
    [553044] = {"item", "Secret Pass", 0x1DD914, 1},
    [553045] = {"item", "Small Key", 0x1DD95C, 1},
    [553046] = {"item", "Broken Armor", 0x1DD8B4, 1},
    [553047] = {"item", "Ruby Crest", 0x1DD928, 1},
    [553048] = {"item", "Sapphire Crest", 0x1DD92C, 1},
    [553049] = {"item", "Topaz Crest", 0x1DD930, 1},
    [553050] = {"item", "Agate Crest", 0x1DD934, 1},
    [553051] = {"item", "Garnet Crest", 0x1DD938, 1},
    [553052] = {"item", "Emerald Crest", 0x1DD93C, 1},
    [553053] = {"item", "Diamond Crest", 0x1DD940, 1},
    [553054] = {"item", "Flail Upgrade", 0x1DD854, 1},
    [553055] = {"item", "Flail Upgrade 2", 0x1DD858, 1},
    [553056] = {"item", "Bow Upgrade", 0x1DD844, 1},
    [553057] = {"item", "Bow Upgrade 2", 0x1DD848, 1},
    [553058] = {"item", "Sword Upgrade", 0x1DD838, 1},
    [553059] = {"item", "Sword Upgrade 2", 0x1DD83C, 1},
    [553060] = {"item", "Sword Upgrade 3", 0x1DD840, 1},
    [553061] = {"item", "Sword Upgrade 4", 0x1DD850, 1},
    [553062] = {"item", "Armor Upgrade", 0x1DD878, 1},
    [553063] = {"item", "Armor Upgrade 2", 0x1DD87C, 1},
    [553064] = {"item", "Armor Upgrade 3", 0x1DD880, 1},
    [553065] = {"item", "Earth Magic", 0x1DD8DC, 1},
    [553066] = {"item", "Earth Magic 2", 0x1DD8E0, 1},
    [553067] = {"item", "Water Magic", 0x1DD8E4, 1},
    [553068] = {"item", "Water Magic 2", 0x1DD8E8, 1},
    [553069] = {"item", "Fire Magic", 0x1DD8EC, 1},
    [553070] = {"item", "Fire Magic 2", 0x1DD8F0, 1},
    [553071] = {"item", "Wind Magic", 0x1DD8F4, 1},
    [553072] = {"item", "Wind Magic 2", 0x1DD8F8, 1},
    [553073] = {"item", "Gilded Falcon", 0x1DD82A, 99},
    [553074] = {"item", "30 Gilder", 0x1DD824, 9999},
    [553075] = {"item", "1 Gilder", 0x1DD824, 9999},
    [553076] = {"item", "5 Gilder", 0x1DD824, 9999},
    [553077] = {"item", "10 Gilder", 0x1DD824, 9999},
}

local GILDER_AMOUNTS = {
    ["30 Gilder"] = 30,
    ["5 Gilder"] = 5,
    ["1 Gilder"] = 1,
    ["10 Gilder"] = 10,
}
local GILDER_ADDR = 0x1DD824
local LIFE_VESSEL_ADDR = 0x1AC710

local locations = {
    [553001] = {name="Inoa: Chest in Lutas's house", address=0x1DD404, mask=1},
    [553002] = {name="Inoa: First item in Jess's blue chest", address=0x1DD342, mask=1},
    [553003] = {name="Inoa: Second item in Jess's blue chest", address=0x1DD342, mask=1},
    [553004] = {name="Overworld C2: Chest in Olen's house", address=0x1DD3DC, mask=64},
    [553005] = {name="Overworld C2: First chest in top-left cave", address=0x1DD405, mask=32},
    [553006] = {name="Overworld C2: Chest in graveyard house basement", address=0x1DD40A, mask=2},
    [553007] = {name="Overworld C2: Chest in top-left cave behind springs", address=0x1DD405, mask=64},
    [553008] = {name="Overworld D2: Middle chest", address=0x1DD40B, mask=1},
    [553009] = {name="Overworld D2: Cliff chest", address=0x1DD404, mask=2},
    [553010] = {name="Overworld D2: Pier chest", address=0x1DD3DC, mask=128},
    [553011] = {name="Overworld D2: Chest in cave next to Underground Waterway", address=0x1DD3A5, mask=128},
    [553012] = {name="Overworld D2: Left chest in watermill", address=0x1DD407, mask=8},
    [553013] = {name="Overworld D2: Middle chest in watermill", address=0x1DD407, mask=16},
    [553014] = {name="Overworld D2: Right chest in watermill", address=0x1DD407, mask=32},
    [553015] = {name="Overworld D2 (Cavern): Chest in left half of cavern", address=0x1DD405, mask=4},
    [553016] = {name="Overworld D2 (Cavern): Chest falling after beating all slimes", address=0x1DD405, mask=8},
    [553017] = {name="Overworld D2 (Cavern): Upper chest in right half of cavern", address=0x1DD405, mask=1},
    [553018] = {name="Overworld D2 (Cavern): Lower chest in right half of cavern", address=0x1DD405, mask=2},
    [553019] = {name="Overworld D3: Elevated chest near bridge", address=0x1DD40D, mask=32},
    [553020] = {name="Overworld D3: Elevated chest near left border", address=0x1DD40B, mask=2},
    [553021] = {name="Overworld D3: Leftmost chest in 3-chest group", address=0x1DD40E, mask=16},
    [553022] = {name="Overworld D3: Middle chest in 3-chest group", address=0x1DD40E, mask=8},
    [553023] = {name="Overworld D3: Rightmost chest in 3-chest group", address=0x1DD40E, mask=32},
    [553024] = {name="Overworld D3: 1st chest in 4-chest group", address=0x1DD40D, mask=128},
    [553025] = {name="Overworld D3: 2nd chest in 4-chest group", address=0x1DD40E, mask=1},
    [553026] = {name="Overworld D3: 3rd chest in 4-chest group", address=0x1DD40E, mask=2},
    [553027] = {name="Overworld D3: Rightmost chest in 4-chest group", address=0x1DD40E, mask=4},
    [553028] = {name="Overworld D4: Elevated chest at top-left corner", address=0x1DD40D, mask=64},
    [553029] = {name="Overworld D4: Second chest at top-left corner", address=0x1DD40B, mask=16},
    [553030] = {name="Overworld D4: Chest to the left of the swamp", address=0x1DD40B, mask=4},
    [553031] = {name="Overworld D4: Chest on left swamp island", address=0x1DD3E2, mask=4},
    [553032] = {name="Overworld D4: Right swamp chest", address=0x1DD40B, mask=8},
    [553033] = {name="Overworld C4: Left coast chest", address=0x1DD40E, mask=64},
    [553034] = {name="Overworld C4: Bottom-right cliff upper chest", address=0x1DD3E2, mask=64},
    [553035] = {name="Overworld C4: Bottom-right cliff lower chest", address=0x1DD3DC, mask=2},
    [553036] = {name="Overworld C4: Chest inside forest near the right border", address=0x1DD40E, mask=128},
    [553037] = {name="Overworld C4: Chest hidden among the trees near the middle", address=0x1DD40F, mask=1},
    [553038] = {name="Overworld C4: Right coast chest behind spring", address=0x1DD3E2, mask=128},
    [553039] = {name="Overworld C1: Chest accessible from cave", address=0x1DD3DC, mask=8},
    [553040] = {name="Overworld C1: Chest on cliff accessible from right map", address=0x1DD40D, mask=16},
    [553041] = {name="Overworld C1: Chest in right section", address=0x1DD40F, mask=64},
    [553042] = {name="Overworld C1: Leftmost chest", address=0x1DD40F, mask=128},
    [553043] = {name="Overworld C1: Left chest in two chests group", address=0x1DD40F, mask=16},
    [553044] = {name="Overworld C1: Right chest in two chests group", address=0x1DD40F, mask=32},
    [553045] = {name="Overworld D1: Elevated chest in cliffs labyrinth", address=0x1DD40F, mask=64},
    [553046] = {name="Overworld D1: Left chest in two chests group", address=0x1DD40F, mask=4},
    [553047] = {name="Overworld D1: Right chest in two chests group", address=0x1DD40F, mask=8},
    [553048] = {name="Ice Manor: Reward chest", address=0x1DD3CB, mask=1},
    [553049] = {name="Overworld B4: Chest hidden behind cabins on the pier", address=0x1DD410, mask=16},
    [553050] = {name="Overworld B4: Chest behind the tree stump", address=0x1DD3E1, mask=128},
    [553051] = {name="Overworld B4: Chest accessible from left map", address=0x1DD3E2, mask=1},
    [553052] = {name="Overworld B4: Chest in Nava's cabin", address=0x1DD3EA, mask=1},
    [553053] = {name="Overworld B3: Elevated chest accessible from bottom map", address=0x1DD3DC, mask=32},
    [553054] = {name="Overworld B3: Chest behind vines", address=0x1DD3DC, mask=16},
    [553055] = {name="Overworld B3: King Snow reward for dying a specified amount of times", address=0x1DD413, mask=8},
    [553056] = {name="Riverside Casino: 'Wheel of Fortune' chest", address=0x1DD3F7, mask=16},
    [553057] = {name="Riverside Casino: 'Wheel of Fortune' second reward", address=0x1DD3F7, mask=8},
    [553058] = {name="Riverside Casino: 'Hit Your Mark' chest", address=0x1DD3F6, mask=64},
    [553059] = {name="Riverside Casino: 'Hit Your Mark' second reward", address=0x1DD3F6, mask=32},
    [553060] = {name="Riverside Casino: 'Slime Smash' chest", address=0x1DD3F8, mask=4},
    [553061] = {name="Riverside Casino: 'Slime Smash' second reward", address=0x1DD3F8, mask=2},
    [553062] = {name="Overworld B2: Chest hidden behind musician's house", address=0x1DD410, mask=2},
    [553063] = {name="Overworld B2: Chest near the pond", address=0x1DD410, mask=1},
    [553064] = {name="Overworld B2: First upper mines chest", address=0x1DD407, mask=1},
    [553065] = {name="Overworld B2: Chest falling after beating 50 slimes in upper mines", address=0x1DD406, mask=128},
    [553066] = {name="Overworld B2: Chest in house near Coal Mine", address=0x1DD407, mask=128},
    [553067] = {name="Overworld B2: Chest near Coal Mine back exit", address=0x1DD3E1, mask=64},
    [553068] = {name="Overworld A4: Chest behind Fire Manor", address=0x1DD411, mask=1},
    [553069] = {name="Overworld A4: Chest in cave on the way to Fire Manor rewarded for beating circle of fishes", address=0x1DD412, mask=2},
    [553070] = {name="Overworld A4: Chest in left branch of final cave before Fire Manor", address=0x1DD412, mask=1},
    [553071] = {name="Fire Manor: Reward chest", address=0x1DD3F4, mask=128},
    [553072] = {name="Overworld A3: Elevated chest at top-left corner", address=0x1DD414, mask=4},
    [553073] = {name="Overworld A3: Lower chest in left ruins", address=0x1DD411, mask=64},
    [553074] = {name="Overworld A3: Left chest in 3 chests group", address=0x1DD413, mask=128},
    [553075] = {name="Overworld A3: Middle chest in 3 chests group", address=0x1DD414, mask=1},
    [553076] = {name="Overworld A3: Right chest in 3 chests group", address=0x1DD414, mask=2},
    [553077] = {name="Overworld A3: Left elevated chest in mimics cave", address=0x1DD406, mask=8},
    [553078] = {name="Overworld A3: Right elevated chest in mimics cave", address=0x1DD406, mask=16},
    [553079] = {name="Overworld A3: Left ground chest in mimics cave", address=0x1DD406, mask=2},
    [553080] = {name="Overworld A3: Right ground chest in mimics cave", address=0x1DD406, mask=4},
    [553081] = {name="Overworld A3: Lower chest in right ruins", address=0x1DD411, mask=128},
    [553082] = {name="Overworld A3: Chest behind the trees in right ruins", address=0x1DD3E1, mask=16},
    [553083] = {name="Overworld A3: Elevated chest in middle ruins", address=0x1DD411, mask=2},
    [553084] = {name="Overworld A2: Chest dropped by Murggs", address=0x1DD380, mask=8},
    [553085] = {name="Overworld A2: Chest in circular cave behind vines", address=0x1DD37E, mask=1},
    [553086] = {name="Overworld A2: Left chest in bridge cave with 3 chests", address=0x1DD37E, mask=64},
    [553087] = {name="Overworld A2: Middle chest in bridge cave with 3 chests", address=0x1DD37E, mask=32},
    [553088] = {name="Overworld A2: Right chest in bridge cave with 3 chests", address=0x1DD37E, mask=128},
    [553089] = {name="Overworld A2: Chest near spikeball", address=0x1DD37F, mask=1},
    [553090] = {name="Overworld A2: Upper chest", address=0x1DD410, mask=128},
    [553091] = {name="Overworld A2: Lower chest among trees", address=0x1DD3A3, mask=1},
    [553092] = {name="Overworld A2: Upper chest among trees", address=0x1DD3A2, mask=128},
    [553093] = {name="Overworld A2: Chest after Stone Golem", address=0x1DD380, mask=2},
    [553094] = {name="Overworld B1: Chest on isolated island", address=0x1DD3E1, mask=32},
    [553095] = {name="Overworld E1: Chest near bottom right corner", address=0x1DD40B, mask=32},
    [553096] = {name="Overworld E1: Chest near top right corner", address=0x1DD3E1, mask=8},
    [553097] = {name="Overworld E2: Top chest", address=0x1DD3E2, mask=8},
    [553098] = {name="Overworld E2: Right chest", address=0x1DD40C, mask=4},
    [553099] = {name="Overworld E2: Bottom chest", address=0x1DD40C, mask=2},
    [553100] = {name="Overworld E2: First chest in cave", address=0x1DD3E5, mask=32},
    [553101] = {name="Overworld E2: Chest in cave behind burning pillars", address=0x1DD3E5, mask=16},
    [553102] = {name="Overworld E3: Top-right chest in Sand Cape locked ruins", address=0x1DD3F4, mask=32},
    [553103] = {name="Overworld E3: Left chest in desert", address=0x1DD40C, mask=8},
    [553104] = {name="Overworld E3: Chest on island outside desert", address=0x1DD3D8, mask=1},
    [553105] = {name="Overworld E3: Chest on middle ruins", address=0x1DD3E2, mask=16},
    [553106] = {name="Overworld E3: Chest in cave", address=0x1DD387, mask=8},
    [553107] = {name="Overworld E4: Top-left chest hidden in grass", address=0x1DD3E2, mask=32},
    [553108] = {name="Overworld E4: Chest at mid-level near waterfalls", address=0x1DD40C, mask=16},
    [553109] = {name="Overworld E4: Chest on left cliff", address=0x1DD40C, mask=64},
    [553110] = {name="Overworld E4: Chest in left rocky alcove", address=0x1DD40C, mask=128},
    [553111] = {name="Overworld E4: Left chest in 3 chests group", address=0x1DD40D, mask=1},
    [553112] = {name="Overworld E4: Middle chest in 3 chests group", address=0x1DD40D, mask=2},
    [553113] = {name="Overworld E4: Right chest in 3 chests group", address=0x1DD40D, mask=4},
    [553114] = {name="Overworld E4: Chest between two cliffs", address=0x1DD40D, mask=8},
    [553115] = {name="Overworld E4: Chest on right cliff", address=0x1DD40C, mask=32},
    [553116] = {name="Overworld E4: Lower chest in the well", address=0x1DD406, mask=1},
    [553117] = {name="Overworld E4: Upper chest in the well", address=0x1DD405, mask=128},
    [553118] = {name="Overworld B2: First chest in cave to lake", address=0x1DD404, mask=64},
    [553119] = {name="Overworld B2: Chest behind deep water in cave to lake", address=0x1DD404, mask=128},
    [553120] = {name="Tarn's Manor: Falling chest in dining room after slaying Murggs", address=0x1DD354, mask=32},
    [553121] = {name="Tarn's Manor: Upstairs right chest", address=0x1DD386, mask=4},
    [553122] = {name="Tarn's Manor: First underground chest", address=0x1DD386, mask=2},
    [553123] = {name="Tarn's Manor: Second underground chest", address=0x1DD386, mask=1},
    [553124] = {name="Tarn's Manor: Third underground chest", address=0x1DD385, mask=128},
    [553125] = {name="Tarn's Manor: Chest in watery hallway with spikeball", address=0x1DD386, mask=16},
    [553126] = {name="Tarn's Manor: Chest in right room coming back from the underground", address=0x1DD386, mask=8},
    [553127] = {name="Tarn's Manor: Left chest in final room", address=0x1DD3C9, mask=2},
    [553128] = {name="Tarn's Manor: Right chest in final room", address=0x1DD3C9, mask=4},
    [553129] = {name="Tarn's Manor: Item on table in final room", map=117, x_min=131, x_max=177, y_min=166, y_max=200},
    [553130] = {name="Coal Mine: Chest #1 in room where Lyman dies", address=0x1DD388, mask=8},
    [553131] = {name="Coal Mine: Chest #2 in room where Lyman dies", address=0x1DD388, mask=16},
    [553132] = {name="Coal Mine: Chest #3 in room where Lyman dies", address=0x1DD388, mask=32},
    [553133] = {name="Coal Mine: Chest #4 in room where Lyman dies", address=0x1DD388, mask=64},
    [553134] = {name="Coal Mine: Elevated chest in room with many minecarts", address=0x1DD397, mask=128},
    [553135] = {name="Coal Mine: Lower chest in room with many minecarts", address=0x1DD397, mask=1},
    [553136] = {name="Coal Mine: Elevated chest in last sector", address=0x1DD38E, mask=4},
    [553137] = {name="Coal Mine: Chest on wooden structure in last minecart starting room", address=0x1DD396, mask=4},
    [553138] = {name="Coal Mine: Reward chest for beating the Murggs", address=0x1DD395, mask=64},
    [553139] = {name="Fairy Pond: First chest in spikeballs pit", address=0x1DD3AB, mask=128},
    [553140] = {name="Fairy Pond: Second chest in spikeballs pit", address=0x1DD3AB, mask=32},
    [553141] = {name="Fairy Pond: Chest in bubble jumping room", address=0x1DD3AA, mask=64},
    [553142] = {name="Fairy Pond: Top chest in second chained spikeballs room", address=0x1DD3AB, mask=4},
    [553143] = {name="Fairy Pond: Middle chest in second chained spikeballs room", address=0x1DD3AB, mask=8},
    [553144] = {name="Fairy Pond: Bottom chest in second chained spikeballs room", address=0x1DD3AB, mask=16},
    [553145] = {name="Fairy Pond: Reward chest", address=0x1DD3A8, mask=8},
    [553146] = {name="Ancient Shrine: Chest in left aisle of main entrance room", address=0x1DD385, mask=16},
    [553147] = {name="Ancient Shrine: Chest in right aisle of main entrance room", address=0x1DD385, mask=32},
    [553148] = {name="Ancient Shrine: Chest in room with sandcape holes and jars", address=0x1DD384, mask=16},
    [553149] = {name="Ancient Shrine: Chest near left exterior statue", address=0x1DD3DD, mask=1},
    [553150] = {name="Ancient Shrine: Left reward chest after beating boss", address=0x1DD3CB, mask=4},
    [553151] = {name="Ancient Shrine: Middle reward chest after beating boss", address=0x1DD385, mask=8},
    [553152] = {name="Ancient Shrine: Right reward chest after beating boss", address=0x1DD3D6, mask=16},
    [553153] = {name="Coastal Cave: Chest hidden behind bricks near entrance", address=0x1DD386, mask=64},
    [553154] = {name="Coastal Cave: Chest in 'spiral' room", address=0x1DD355, mask=128},
    [553155] = {name="Coastal Cave: Chest reachable by throwing wood log on water near first key chest", address=0x1DD359, mask=128},
    [553156] = {name="Coastal Cave: Chest on floating wooden structure in 3-buttons hub", address=0x1DD387, mask=4},
    [553157] = {name="Coastal Cave: Chest hidden below bricks in 3-buttons seal room", address=0x1DD35A, mask=4},
    [553158] = {name="Coastal Cave: Chest in buttons arena", address=0x1DD356, mask=128},
    [553159] = {name="Coastal Cave: Chest in room revealed by hitting lever", address=0x1DD35A, mask=8},
    [553160] = {name="Coastal Cave: First chest in room with checkpoint", address=0x1DD387, mask=1},
    [553161] = {name="Coastal Cave: Second chest in room with checkpoint", address=0x1DD35A, mask=32},
    [553162] = {name="Coastal Cave: Chest on small island in room with elevated key chest", address=0x1DD3F8, mask=32},
    [553163] = {name="Coastal Cave: Chest reachable by throwing wood log on water near last key chest", address=0x1DD386, mask=128},
    [553164] = {name="Coastal Cave: Left boss reward chest", address=0x1DD356, mask=64},
    [553165] = {name="Tower of the Great Tree (basement): Bottom chest", address=0x1DD3FC, mask=64},
    [553166] = {name="Tower of the Great Tree (basement): Top-left chest", address=0x1DD3FC, mask=128},
    [553167] = {name="Tower of the Great Tree (basement): Left chest among the two top chests", address=0x1DD3FD, mask=1},
    [553168] = {name="Tower of the Great Tree (basement): Right chest among the two top chests", address=0x1DD3FD, mask=2},
    [553169] = {name="Tower of the Great Tree (ground): Chest in arena", address=0x1DD3FB, mask=16},
    [553170] = {name="Tower of the Great Tree (ground): Chest near left aisle entrance", address=0x1DD366, mask=32},
    [553171] = {name="Tower of the Great Tree (ground): Chest near right aisle entrance", address=0x1DD364, mask=128},
    [553172] = {name="Tower of the Great Tree (1F): Middle chest", address=0x1DD3FB, mask=32},
    [553173] = {name="Tower of the Great Tree (1F): Left chest in top-right room", address=0x1DD3FB, mask=64},
    [553174] = {name="Tower of the Great Tree (1F): Right chest in top-right room", address=0x1DD365, mask=64},
    [553175] = {name="Tower of the Great Tree (2F): Left chest in top row of storage room", address=0x1DD3FC, mask=1},
    [553176] = {name="Tower of the Great Tree (2F): Right chest in top row of storage room", address=0x1DD3FC, mask=2},
    [553177] = {name="Tower of the Great Tree (2F): Left chest in bottom row of storage room", address=0x1DD3FC, mask=4},
    [553178] = {name="Tower of the Great Tree (2F): Right chest in bottom row of storage room", address=0x1DD371, mask=16},
    [553179] = {name="Tower of the Great Tree (2F): Middle chest", address=0x1DD36D, mask=16},
    [553180] = {name="Tower of the Great Tree (2F): Top chest in bottom-right room", address=0x1DD366, mask=128},
    [553181] = {name="Tower of the Great Tree (2F): Left chest in bottom-right room", address=0x1DD367, mask=1},
    [553182] = {name="Tower of the Great Tree (2F): Right chest in bottom-right room", address=0x1DD367, mask=2},
    [553183] = {name="Tower of the Great Tree (3F): Left chest in top-right room", address=0x1DD366, mask=16},
    [553184] = {name="Tower of the Great Tree (3F): Right chest in top-right room", address=0x1DD366, mask=8},
    [553185] = {name="Tower of the Great Tree (4F): Chest in fireball launcher room", address=0x1DD3FC, mask=16},
    [553186] = {name="Tower of the Great Tree (Summit): Left boss reward chest", address=0x1DD371, mask=64},
    [553187] = {name="Tower of the Great Tree (Summit): Right boss reward chest", address=0x1DD972, mask=1},
    [553188] = {name="Tower of the Great Tree (Branches): Left chest on great tree branches", address=0x1DD3D7, mask=2},
    [553189] = {name="Tower of the Great Tree (Branches): Right chest on great tree branches", address=0x1DD3DD, mask=8},
    [553190] = {name="Underground Waterway: First chest in entrance room", address=0x1DD3A5, mask=128},
    [553191] = {name="Underground Waterway: Second chest in entrance room", address=0x1DD3A6, mask=1},
    [553192] = {name="Underground Waterway: Chest on pillar accessible by falling from engine room", address=0x1DD3A6, mask=64},
    [553193] = {name="Underground Waterway: Chest in room behind waterfall", address=0x1DD3A6, mask=2},
    [553194] = {name="Underground Waterway: Chest in last room top-right corner", address=0x1DD3A7, mask=16},
    [553195] = {name="Lars Crypt: Left chest after bridge", address=0x1DD382, mask=64},
    [553196] = {name="Lars Crypt: Right chest after bridge", address=0x1DD382, mask=128},
    [553197] = {name="Lars Crypt: Chest in zombies' pit", address=0x1DD383, mask=1},
    [553198] = {name="Lars Crypt: Corner chest after climbing stairs from zombies' pit", address=0x1DD383, mask=2},
    [553199] = {name="Lars Crypt: Chest in top-left corner of second pit", address=0x1DD383, mask=8},
    [553200] = {name="Lars Crypt: Chest at the bottom of moving platforms vertical room", address=0x1DD383, mask=4},
    [553201] = {name="Lars Crypt: Upper boss reward chest", address=0x1DD382, mask=4},
    [553202] = {name="Lars Crypt: Middle boss reward chest", address=0x1DD382, mask=16},
    [553203] = {name="Lars Crypt: Lower boss reward chest", address=0x1DD382, mask=8},
    [553204] = {name="Lars Crypt: Boss reward chest isolated to the left", address=0x1DD3C9, mask=1},
    [553205] = {name="Magyscar: Left chest in watery triple chest room", address=0x1DD39C, mask=32},
    [553206] = {name="Magyscar: Top-right chest in watery triple chest room", address=0x1DD39C, mask=16},
    [553207] = {name="Magyscar: Bottom-right chest in watery triple chest room", address=0x1DD3F9, mask=4},
    [553208] = {name="Magyscar: Chest behind vines in switchable platforms room", address=0x1DD39C, mask=8},
    [553209] = {name="Magyscar: Chest in room with pillars and smashing spikeballs", address=0x1DD39C, mask=4},
    [553210] = {name="Magyscar: Elevated chest in small room with spinning spikeballs", address=0x1DD3A2, mask=16},
    [553211] = {name="Magyscar: Chest between teleporters", address=0x1DD3F9, mask=8},
    [553212] = {name="Magyscar: Upper chest in room with elevator controlled by switch", address=0x1DD3FB, mask=1},
    [553213] = {name="Magyscar: Lower hidden chest in room with elevator controlled by switch", address=0x1DD39D, mask=8},
    [553214] = {name="Magyscar: Chest behind vines in room with switch giving torch and lowering platforms", address=0x1DD3F9, mask=2},
    [553215] = {name="Magyscar: First chest in vines hallway after room with 4 magic switches", address=0x1DD39F, mask=2},
    [553216] = {name="Magyscar: Second chest in vines hallway after room with 4 magic switches", address=0x1DD39F, mask=4},
    [553217] = {name="Magyscar: Third chest in vines hallway after room with 4 magic switches", address=0x1DD39F, mask=8},
    [553218] = {name="Magyscar: Right boss reward chest", address=0x1DD34E, mask=128},
    [553219] = {name="Reptile Lair: Chest in side cavern accessible from overworld", address=0x1DD395, mask=4},
    [553220] = {name="Reptile Lair: Lower chest in main flooded room", address=0x1DD390, mask=32},
    [553221] = {name="Reptile Lair: Left elevated chest in main flooded room", address=0x1DD390, mask=64},
    [553222] = {name="Reptile Lair: Chest on wooden structure to the right of main flooded room", address=0x1DD390, mask=128},
    [553223] = {name="Reptile Lair: Chest in room with 3 respawning lizard statues", address=0x1DD391, mask=8},
    [553224] = {name="Reptile Lair: Chest next to stairs after leaving main flooded room using right stairs", address=0x1DD392, mask=4},
    [553225] = {name="Reptile Lair: Chest next to stairs after moving fireballs room", address=0x1DD393, mask=8},
    [553226] = {name="Reptile Lair: Chest in room with two wooden bridges", address=0x1DD3D7, mask=16},
    [553227] = {name="Reptile Lair: Chest in room with vibrating spikeballs", address=0x1DD3DD, mask=32},
    [553228] = {name="Reptile Lair: Left chest in boss reward room", address=0x1DD394, mask=16},
    [553229] = {name="Reptile Lair: Right chest in boss reward room", address=0x1DD394, mask=32},
    [553230] = {name="Torla Mountain: Chest bathing in lava", address=0x1DD3EA, mask=128},
    [553231] = {name="Torla Mountain: Chest in stompable flamethrowers hallway", address=0x1DD3EB, mask=1},
    [553232] = {name="Torla Mountain: Chest in top-right corner of room with phoenixes and flamethrowers", address=0x1DD3F3, mask=2},
    [553233] = {name="Torla Mountain: Right chest in checkpoint teleporter room", address=0x1DD3ED, mask=2},
    [553234] = {name="Torla Mountain: Chest in pit below wooden bridge", address=0x1DD3EF, mask=16},
    [553235] = {name="Torla Mountain: Chest before boss", address=0x1DD411, mask=4},
    [553236] = {name="Torla Mountain: Boss reward chest", address=0x1DD408, mask=4},
    [553237] = {name="Nirude's Lair: Chest hidden in passageway behind statue, accessible from outside", address=0x1DD3CF, mask=16},
    [553238] = {name="Nirude's Lair: Chest on left side of cavern hallway with statues", address=0x1DD3DD, mask=64},
    [553239] = {name="Nirude's Lair: Right elevated chest in entrance room", address=0x1DD3CF, mask=2},
    [553240] = {name="Overworld E1: Left chest in two chests group", address=0x1DD40B, mask=128},
    [553241] = {name="Overworld E1: Right chest in two chests group", address=0x1DD40C, mask=1},
    [553242] = {name="Nirude's Lair: Chest in room with spikes and moving platforms", address=0x1DD3D1, mask=32},
    [553243] = {name="Overworld E1: Chest on cliff near top-left corner", address=0x1DD40B, mask=64},
    [553244] = {name="Nirude's Lair: Chest hidden behind moving statue", address=0x1DD3F2, mask=64},
    [553245] = {name="Nirude's Lair: Upper falling chest in elevated arena room", address=0x1DD3D7, mask=32},
    [553246] = {name="Nirude's Lair: Lower falling chest in elevated arena room", address=0x1DD3D5, mask=16},
    [553247] = {name="Nirude's Lair: Boss reward chest", address=0x1DD3D6, mask=1},
    [553248] = {name="Nirude's Lair: Boss reward item given by Miming", address=0x1DD34F, mask=4},
    [553249] = {name="Nava's Keep: Chest buried in ground, raising after beating enemies", address=0x1DD3AD, mask=32},
    [553250] = {name="Nava's Keep: Chest in room with hidden paths", address=0x1DD3AD, mask=64},
    [553251] = {name="Nava's Keep: Elevated chest on Nava's island", address=0x1DD3D7, mask=4},
    [553252] = {name="Nava's Keep: Chest left to the house on Nava's island", address=0x1DD411, mask=8},
    [553253] = {name="Nava's Keep: Falling item revealed using Zolist's Stone", address=0x1DD3AD, mask=128},
    [553254] = {name="Merrick's Shop: Item traded for 15 Gilded Falcons", address=0x1DD3E7, mask=2},
    [553255] = {name="Merrick's Shop: Item traded for 20 Gilded Falcons", address=0x1DD3E7, mask=4},
    [553256] = {name="Merrick's Shop: Item traded for 25 Gilded Falcons", address=0x1DD3E7, mask=8},
    [553257] = {name="Merrick's Shop: Item traded for 30 Gilded Falcons", address=0x1DD3E7, mask=16},
    [553258] = {name="Merrick's Shop: Item traded for 35 Gilded Falcons", address=0x1DD3E7, mask=32},
    [553259] = {name="Merrick's Shop: Item traded for 40 Gilded Falcons", address=0x1DD3E7, mask=64},
    [553260] = {name="Merrick's Shop: Item traded for 45 Gilded Falcons", address=0x1DD3E7, mask=128},
    [553261] = {name="Merrick's Shop: Item traded for 50 Gilded Falcons", address=0x1DD3E8, mask=1},
    [553262] = {name="Lurvy's Shop: Item #5 replacement when bought once", address=0x1DD3B2, mask=2},
    [553263] = {name="Lurvy's Shop: Item #5 replacement when bought twice", address=0x1DD3BE, mask=16},
    [553264] = {name="Lurvy's Shop: Item obtained after repairing Broken Armor", address=0x1DD3BE, mask=32},
    [553265] = {name="Naomi's Shop: Item #4", address=0x1DD38C, mask=16},
    [553266] = {name="Lake Shrine Exterior (garden): Chest to the left of Lake Shrine Interior gate", address=0x1DD411, mask=16},
    [553267] = {name="Lake Shrine Exterior (garden): Chest to the right of Lake Shrine Interior gate", address=0x1DD411, mask=32}
}

local checked_locations = {}
local game_complete = false

local SAVE_FILE = "alundra_checks.json"
local current_seed = nil

local function save_state()
end

local function load_state()
end
local ap_state = {}
local prev_frame = {}
local life_vessel_baseline = nil
local LIFE_VESSEL_BASELINE_FILE = "alundra_life_vessel_baseline.json"

local function load_life_vessel_baseline()
    local f = io.open(LIFE_VESSEL_BASELINE_FILE, "r")
    if not f then return end
    local data = f:read("*a")
    f:close()
    local ok, saved = pcall(json.decode, data)
    if ok and saved and saved.seed == current_seed and saved.baseline ~= nil then
        life_vessel_baseline = saved.baseline
    end
end

local function save_life_vessel_baseline()
    local f = io.open(LIFE_VESSEL_BASELINE_FILE, "w")
    if f then
        f:write(json.encode({seed = current_seed, baseline = life_vessel_baseline}))
        f:close()
    end
end

local function ensure_life_vessel_baseline()
    if life_vessel_baseline == nil then
        load_life_vessel_baseline()
    end
    if life_vessel_baseline == nil then
        local current_ap = ap_state[LIFE_VESSEL_ADDR] or 0
        life_vessel_baseline = mainmemory.read_u8(LIFE_VESSEL_ADDR) - current_ap
        save_life_vessel_baseline()
    end
end

local native_credit = {}

local GILDER_CONFIRMED_FILE = "alundra_gilder_confirmed.json"
local gilder_confirmed_total = nil
local gilder_seen_total = 0

local function load_gilder_confirmed_total()
    local f = io.open(GILDER_CONFIRMED_FILE, "r")
    if not f then return end
    local data = f:read("*a")
    f:close()
    local ok, saved = pcall(json.decode, data)
    if ok and saved and saved.seed == current_seed and saved.confirmed_total ~= nil then
        gilder_confirmed_total = saved.confirmed_total
    end
end

local function save_gilder_confirmed_total()
    local f = io.open(GILDER_CONFIRMED_FILE, "w")
    if f then
        f:write(json.encode({seed = current_seed, confirmed_total = gilder_confirmed_total}))
        f:close()
    end
end

local function ensure_gilder_confirmed_total()
    if gilder_confirmed_total == nil then
        load_gilder_confirmed_total()
    end
    if gilder_confirmed_total == nil then
        gilder_confirmed_total = 0
        save_gilder_confirmed_total()
    end
end

local tracking_initialized = false
local last_item_index = 0
local reconnect_pending = false
local gilder_last_value = nil
local gilder_native_credit = 0
local pending_items = {}
local pending_upgrades = {}

local item_name_to_id = {}
for id, item in pairs(items_by_id) do
    item_name_to_id[item[2]] = id
end

local display_names = {
    ["Flail Upgrade"]   = "Iron Flail",
    ["Flail Upgrade 2"] = "Steel Flail",
    ["Bow Upgrade"]     = "Hunter's Bow",
    ["Bow Upgrade 2"]   = "Willow Bow",
    ["Sword Upgrade"]   = "Sword",
    ["Sword Upgrade 2"] = "Fiend Blade",
    ["Sword Upgrade 3"] = "Holy Sword",
    ["Sword Upgrade 4"] = "Legend Sword",
    ["Earth Magic"]     = "Earth Scroll",
    ["Earth Magic 2"]   = "Earth Book",
    ["Water Magic"]     = "Water Scroll",
    ["Water Magic 2"]   = "Water Book",
    ["Fire Magic"]      = "Fire Scroll",
    ["Fire Magic 2"]    = "Fire Book",
    ["Wind Magic"]      = "Wind Scroll",
    ["Wind Magic 2"]    = "Wind Book",
}

local prerequisites = {
    ["Flail Upgrade 2"]  = "Flail Upgrade",
    ["Bow Upgrade 2"]    = "Bow Upgrade",
    ["Sword Upgrade 2"]  = "Sword Upgrade",
    ["Sword Upgrade 3"]  = "Sword Upgrade 2",
    ["Sword Upgrade 4"]  = "Sword Upgrade 3",
    ["Armor Upgrade 2"]  = "Armor Upgrade",
    ["Armor Upgrade 3"]  = "Armor Upgrade 2",
    ["Earth Magic 2"]    = "Earth Magic",
    ["Water Magic 2"]    = "Water Magic",
    ["Fire Magic 2"]     = "Fire Magic",
    ["Wind Magic 2"]     = "Wind Magic",
}

local upgrade_rollover_next = {
    ["Flail Upgrade"]    = "Flail Upgrade 2",
    ["Bow Upgrade"]      = "Bow Upgrade 2",
    ["Sword Upgrade"]    = "Sword Upgrade 2",
    ["Sword Upgrade 2"]  = "Sword Upgrade 3",
    ["Sword Upgrade 3"]  = "Sword Upgrade 4",
    ["Armor Upgrade"]    = "Armor Upgrade 2",
    ["Armor Upgrade 2"]  = "Armor Upgrade 3",
    ["Earth Magic"]      = "Earth Magic 2",
    ["Water Magic"]      = "Water Magic 2",
    ["Fire Magic"]       = "Fire Magic 2",
    ["Wind Magic"]       = "Wind Magic 2",
}

local message_queue = {}
local current_msg = nil
local msg_expire_frame = 0
local MESSAGE_FRAMES = 180
local fontSize = 11

local GAME_CLEAR_MAP_ID = 347
local GAME_CLEAR_COUNTER_ADDRESS = 0x1D7B90

local MAP_LOCKED_ADDRESSES = {
}

local last_locked_map_id = nil
local map_lock_snapshot = {}

local function update_map_lock(map_id)
    if map_id == last_locked_map_id then return end

    map_lock_snapshot = {}
    local locked = MAP_LOCKED_ADDRESSES[map_id]
    if locked then
        for addr, _ in pairs(locked) do
            local value = mainmemory.read_u8(addr)
            map_lock_snapshot[addr] = value
            prev_frame[addr] = value
            ap_state[addr] = value
        end
    end
    last_locked_map_id = map_id
end

local function enforce_map_lock()
    for addr, value in pairs(map_lock_snapshot) do
        if mainmemory.read_u8(addr) ~= value then
            mainmemory.write_u8(addr, value)
        end
        prev_frame[addr] = value
    end
end

local function get_locked_addresses_for_current_map()
    local map_id = mainmemory.read_u16_le(current_map_check)
    return MAP_LOCKED_ADDRESSES[map_id]
end

local function enforce_life_vessel_sync()
    ensure_life_vessel_baseline()

    local native_count = mainmemory.read_u8(LIFE_VESSEL_ADDR) - life_vessel_baseline
    local known_count = ap_state[LIFE_VESSEL_ADDR] or 0

    if native_count > known_count then
        native_credit[LIFE_VESSEL_ADDR] = (native_credit[LIFE_VESSEL_ADDR] or 0) + (native_count - known_count)
        ap_state[LIFE_VESSEL_ADDR] = native_count
    elseif native_count < known_count then
        ap_state[LIFE_VESSEL_ADDR] = native_count
    end
end

local function enforce_ap_only()
    local locked = get_locked_addresses_for_current_map()
    for addr, expected in pairs(prev_frame) do
        local current = mainmemory.read_u8(addr)
        if current ~= expected then
            if locked and locked[addr] then
                mainmemory.write_u8(addr, expected)
            else
                if current > expected then
                    native_credit[addr] = (native_credit[addr] or 0) + (current - expected)
                end
                prev_frame[addr] = current
                ap_state[addr] = current
            end
        end
    end
end

local function enforce_gilder_sync()
    local current = mainmemory.read_u16_le(GILDER_ADDR)

    if gilder_last_value == nil then
        gilder_last_value = current
        return
    end

    local delta = current - gilder_last_value
    if delta > 0 then
        gilder_native_credit = gilder_native_credit + delta
    end
    gilder_last_value = current
end

local GILDED_FALCON_FLAG_ADDR = 0x1DD3E9
local GILDED_FALCON_FLAG_MIN = 6

local function enforce_falcon_flag_floor()
    if mainmemory.read_u8(GILDED_FALCON_FLAG_ADDR) < GILDED_FALCON_FLAG_MIN then
        mainmemory.write_u8(GILDED_FALCON_FLAG_ADDR, GILDED_FALCON_FLAG_MIN)
    end
end

local function is_in_gameplay()
    local dagger = mainmemory.read_u8(0x1DD834)
    local vessels = mainmemory.read_u8(0x1AC710)
    return dagger == 0x01 and vessels > 0x00 and vessels < 50
end

local function is_game_complete()
    local map_id = mainmemory.read_u16_le(current_map_check)
    return map_id == GAME_CLEAR_MAP_ID and mainmemory.read_u16_le(GAME_CLEAR_COUNTER_ADDRESS) > 910
end

local function format_item_message(display, sender)
    if sender then
        return "Received: "..display.." from "..sender
    end
    return "Obtained: "..display
end

local function give_item(id, sender, is_restore)
    local item = items_by_id[id]
    if not item then return end

    local name = item[2]
    local addr = item[3]

    local gilder_amount = GILDER_AMOUNTS[name]
    if gilder_amount then

        if is_restore and not sender then
            return
        end

        ensure_gilder_confirmed_total()
        gilder_seen_total = gilder_seen_total + gilder_amount

        if gilder_seen_total <= gilder_confirmed_total then
            return
        end

        if not sender and gilder_native_credit >= gilder_amount then
            gilder_native_credit = gilder_native_credit - gilder_amount
        else
            local new_val = mainmemory.read_u16_le(addr) + gilder_amount
            mainmemory.write_u16_le(addr, new_val)
            gilder_last_value = new_val
        end

        gilder_confirmed_total = gilder_seen_total
        save_gilder_confirmed_total()

        if sender or is_restore then
            local display = display_names[name] or name
            local msg = format_item_message(display, sender)
            print(msg)
            table.insert(message_queue, msg)
        end
        return
    end

    local prereq_name = prerequisites[name]
    if prereq_name then
        local prereq_id = item_name_to_id[prereq_name]
        local prereq_item = prereq_id and items_by_id[prereq_id]
        if prereq_item then
            local prereq_given = (ap_state[prereq_item[3]] or 0) >= prereq_item[4]
            if not prereq_given then
                give_item(prereq_id, sender, is_restore)
                table.insert(pending_upgrades, {id=id, sender=sender, is_restore=is_restore})
                return
            end
        end
    end

    local ap_current = ap_state[addr] or 0

    if not sender and (native_credit[addr] or 0) > 0 then
        native_credit[addr] = native_credit[addr] - 1
        if sender or is_restore then
            local display = display_names[name] or name
            local msg = format_item_message(display, sender)
            print(msg)
            table.insert(message_queue, msg)
        end
        return
    end

    if ap_current < item[4] then
        if name == "Life Vessel" and mainmemory.read_u8(addr) == 0 then
            table.insert(pending_items, {id=id, sender=sender, is_restore=is_restore})
            return
        end

        local new_count = ap_current + 1
        ap_state[addr] = new_count

        local new_val
        if name == "Life Vessel" then
            ensure_life_vessel_baseline()
            new_val = life_vessel_baseline + new_count
        else
            new_val = new_count
        end

        mainmemory.write_u8(addr, new_val)
        if name ~= "Life Vessel" then
            prev_frame[addr] = new_val
        end

        if name == "Magic Seed" then
            mainmemory.write_u8(current_magic_address, mainmemory.read_u8(current_magic_address) + 1)
        end

        if sender or is_restore then
            local display = display_names[name] or name
            local msg = format_item_message(display, sender)
            print(msg)
            table.insert(message_queue, msg)
        end
    else
        local next_name = upgrade_rollover_next[name]
        local next_id = next_name and item_name_to_id[next_name]
        if next_id then
            give_item(next_id, sender, is_restore)
            return
        end

        if sender then
            local display = display_names[name] or name
            local msg = format_item_message(display, sender)
            print(msg)
            table.insert(message_queue, msg)
        end
    end

    local to_retry = pending_upgrades
    pending_upgrades = {}
    for _, pending in ipairs(to_retry) do
        local pending_item = items_by_id[pending.id]
        if pending_item then
            local prereq = prerequisites[pending_item[2]]
            local prereq_id = prereq and item_name_to_id[prereq]
            local prereq_item = prereq_id and items_by_id[prereq_id]
            if prereq_item and (ap_state[prereq_item[3]] or 0) >= prereq_item[4] then
                give_item(pending.id, pending.sender, pending.is_restore)
            else
                table.insert(pending_upgrades, pending)
            end
        end
    end
end

local function retry_pending()
    if #pending_items == 0 then return end
    local still_pending = {}
    for _, pending in ipairs(pending_items) do
        local item = items_by_id[pending.id]
        if item and mainmemory.read_u8(item[3]) > 0 then
            give_item(pending.id, pending.sender, pending.is_restore)
        else
            table.insert(still_pending, pending)
        end
    end
    pending_items = still_pending
end

local function receive_items(list, from_index, is_restore)
    if from_index and from_index < last_item_index then
        return
    end
    for _,entry in pairs(list) do
        give_item(entry.id, entry.sender, is_restore)
    end
    if #list > 0 then
        last_item_index = (from_index or last_item_index) + #list
        save_state()
    end
end

local function enforce_checked_locations()
    for id, _ in pairs(checked_locations) do
        local loc = locations[id]
        if loc and loc.address then
            local current = mainmemory.read_u8(loc.address)
            if (current & loc.mask) == 0 then
                mainmemory.write_u8(loc.address, current | loc.mask)
            end
        end
    end
end

local function location_condition_met(loc)
    if loc.map == nil then
        return true
    end

    if mainmemory.read_u16_le(current_map_check) ~= loc.map then
        return false
    end

    if loc.x_min and mainmemory.read_u16_le(position_x) <= loc.x_min then
        return false
    end
    if loc.x_max and mainmemory.read_u16_le(position_x) >= loc.x_max then
        return false
    end
    if loc.y_min and mainmemory.read_u16_le(position_y) <= loc.y_min then
        return false
    end
    if loc.y_max and mainmemory.read_u16_le(position_y) >= loc.y_max then
        return false
    end

    return true
end

local function check_locations()
    local checks = {}

    if mainmemory.read_u16_le(current_map_check) == 0 then
        return checks
    end

    for id,loc in pairs(locations) do
        if not checked_locations[id] then
            local flag_met = true
            if loc.address then
                local value = mainmemory.read_u8(loc.address)
                flag_met = (value & loc.mask) ~= 0
            end

            if flag_met and location_condition_met(loc) then
                print("Checked "..loc.name)

                checks[#checks+1] = {
                    id=id
                }

                checked_locations[id] = true
                save_state()
            end
        end
    end

    return checks
end

local function receive()
    local data, err = archSocket:receive()

    if err == "timeout" then
        return
    elseif err then
        print("Receive error: "..tostring(err))
        state = STATE_NONE
        return
    end

    local is_restore = reconnect_pending
    reconnect_pending = false

    local decoded = json.decode(data)

    if decoded.seed_name and decoded.seed_name ~= "" then
        if current_seed ~= nil and current_seed ~= decoded.seed_name then
            print("New seed detected, clearing saved state")
            checked_locations = {}
            ap_state = {}
            prev_frame = {}
            life_vessel_baseline = nil
            native_credit = {}
            tracking_initialized = false
            gilder_last_value = nil
            gilder_native_credit = 0
            gilder_confirmed_total = nil
            gilder_seen_total = 0
            last_item_index = 0
            save_state()
        end
        current_seed = decoded.seed_name
    end

    if not game_complete and is_game_complete() then
        game_complete = true
        print("Game Complete!")
        local response = {
            player="Alundra",
            locations={},
            game_complete=true
        }
        archSocket:send(json.encode(response).."\n")
        return
    end

    if decoded.checked_locations then
        for _, id in ipairs(decoded.checked_locations) do
            if not checked_locations[id] then
                checked_locations[id] = true
            end
        end
        print("Synced "..#decoded.checked_locations.." checked locations from client")
    end

    if decoded.outgoing_sends then
        for _, msg in ipairs(decoded.outgoing_sends) do
            table.insert(message_queue, msg)
        end
    end

    if decoded.items then
        receive_items(decoded.items, decoded.item_index, is_restore)
    end

    local response = {
        player="Alundra",
        locations=is_in_gameplay() and check_locations() or {},
        game_complete=false
    }

    local ok, senderr = archSocket:send(json.encode(response).."\n")
    if senderr then
        print("Send error: "..tostring(senderr))
    end
end

function drawOutlinedText(x, y, text, textColor, outlineColor)
    gui.drawText(x - 1, y - 1, text, outlineColor, nil, fontSize)
    gui.drawText(x + 1, y - 1, text, outlineColor, nil, fontSize)
    gui.drawText(x - 1, y + 1, text, outlineColor, nil, fontSize)
    gui.drawText(x + 1, y + 1, text, outlineColor, nil, fontSize)
    gui.drawText(x, y - 1, text, outlineColor, nil, fontSize)
    gui.drawText(x, y + 1, text, outlineColor, nil, fontSize)
    gui.drawText(x - 1, y, text, outlineColor, nil, fontSize)
    gui.drawText(x + 1, y, text, outlineColor, nil, fontSize)

    gui.drawText(x, y, text, textColor, nil, fontSize)
end

function main()
    if not checkBizHawkVersion() then
        return
    end

    load_state()

    server = socket.bind("localhost",52980)

    print("Waiting for Archipelago")

    while true do
        frame = frame + 1

        if state == STATE_OK then
            receive()

        elseif state == STATE_NONE then
            server:settimeout(0)

            local client = server:accept()

            if client then
                archSocket = client
                archSocket:settimeout(0)
                state = STATE_OK
                reconnect_pending = true
                print("Archipelago Connected")
            end
        end

        enforce_checked_locations()

        update_map_lock(mainmemory.read_u16_le(current_map_check))
        enforce_map_lock()

        if is_in_gameplay() then
            retry_pending()

            if not tracking_initialized then
                for id, item in pairs(items_by_id) do
                    local addr = item[3]
                    if not GILDER_AMOUNTS[item[2]] and item[2] ~= "Life Vessel" and prev_frame[addr] == nil then
                        prev_frame[addr] = mainmemory.read_u8(addr)
                    end
                end
                tracking_initialized = true
            end
            enforce_ap_only()
            enforce_life_vessel_sync()
            enforce_gilder_sync()
            enforce_falcon_flag_floor()
        else
            if tracking_initialized then
                tracking_initialized = false
                prev_frame = {}
                gilder_last_value = nil
            end
        end

        if current_msg and emu.framecount() >= msg_expire_frame then
            current_msg = nil
        end
        if not current_msg and #message_queue > 0 then
            current_msg = table.remove(message_queue, 1)
            msg_expire_frame = emu.framecount() + MESSAGE_FRAMES
        end
        gui.clearGraphics()
        if current_msg then
            drawOutlinedText(30, 220, current_msg, "white", "black")
        end

        emu.frameadvance()
    end
end

main()