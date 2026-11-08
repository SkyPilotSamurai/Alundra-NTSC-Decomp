import concurrent.futures
import time
import TwitchPlays_Connection
import os

# Replace this with your Twitch username. Must be all lowercase.
TWITCH_CHANNEL = 'skypilotsamurai'

# Bot allowed to give points to users. Must be all lowercase.
BOT_ACCOUNT = 'botname'

# If streaming on Youtube, set this to False
STREAMING_ON_TWITCH = True

# Replace this with your Youtube's Channel ID
YOUTUBE_CHANNEL_ID = "YOUTUBE_CHANNEL_ID_HERE"

# If you're using an Unlisted stream to test on Youtube, replace "None" below with your stream's URL in quotes.
# Otherwise you can leave this as "None"
YOUTUBE_STREAM_URL = None

# Points name, to give points use !give"pointsname" user amount eg, givegilder user 1000
POINTS_NAME = 'gilder'

# Intial points given to users 
INITIAL_POINTS = 1000

# Show username in game when command redeemed
show_username = True

# Define if you want commands that modify certain items (Note having these True can lead to softlocks)
# Allow changes to Weapons, Bombs, Bean etc.
important_equipment_commands = True

# Allow changes to Crests, Tree gem, Bouquet etc. (Broken Armor, Gilded Falcons and secret pass included for rando)
progression_item_commands = True

# Other commands, safe to change
# Allow Spirit Wand to be given and taken from the player
spirit_wand = True

# Allow changes to max HP and MP, eg. give vessel, give magic seed
max_hp_mp_commands = True

# Allow changes to current HP and MP, eg. give hp, poison
current_hp_mp_commands = True

# Allow Swap Commands, eg. swap sword, swap herbs
swap_commands = True

# Allow Buffed Spawn Commands (Alundra PC: Randomizer > Seeds > Buffed spawns)
buffed_spawns = True

# Allow Force Swap Commands, eg. force sword, force bow
force_commands = True

# Allow Lock Commands, eg. lock weapon, lock item
lock_commands = True

# Command prefix, recommended not to change
cmd = "!"

# Shortcut for giving items, eg. !give bomb is also !g bomb (can even have empty, eg. give = "")
give = "g"

# Shortcut for taking items, eg. !take bomb is also !t bomb
take = "t"

# Shortcut for weapon swap eg. !swap bow is also !s bow
swap = "s"

# Shortcut for weapon forcing eg. !force bow is also !f bow
force = "f"

# Shortcut for weapon lock eg. !lock weapon is also !l weapon
lock = "l"

# You can change command names and costs here, (important no gaps in command name change) 
# commands by default work with spaces and caps eg. !give bomb, !take Power Glove etc.
commands = {
    # Gameplay
    f"{cmd}invincibility {cmd}invulnerable {cmd}nodamage {cmd}inv": 100,
    f"{cmd}noiframes {cmd}noframes {cmd}nf": 80,
    f"{cmd}moonjump {cmd}nogravity {cmd}gravity {cmd}moon {cmd}mj": 20,
    f"{cmd}nojump {cmd}antijump {cmd}nj": 50,
    f"{cmd}slowmotion {cmd}slowmo {cmd}slow {cmd}sm": 40,
    # Character Give
    f"{cmd}{give}lifevessel {cmd}{give}vessel {cmd}{give}maxhp": 80,
    f"{cmd}heal {cmd}cure {cmd}{give}hp {cmd}healhp": 20,
    f"{cmd}{give}magicseed {cmd}{give}seed": 200,
    # Character Take
    f"{cmd}{take}lifevessel {cmd}{take}vessel {cmd}{take}maxhp": 80,
    f"{cmd}hurt {cmd}damage {cmd}{take}hp {cmd}losehp": 20,
    f"{cmd}{take}magicseed {cmd}{take}seed": 200,
    # Equipment Give
    f"{cmd}{give}miningbomb {cmd}{give}bomb {cmd}{give}mining {cmd}{give}boom": 150,
    f"{cmd}{give}ironflail {cmd}{give}flail {cmd}{give}iron": 150,
    f"{cmd}{give}huntersbow {cmd}{give}bow {cmd}{give}arrow": 125,
    f"{cmd}{give}firewand {cmd}{give}fwand {cmd}{give}wand {cmd}{give}lighter": 300,
    f"{cmd}{give}icewand {cmd}{give}iwand {cmd}{give}ice {cmd}{give}freezer": 250,
    f"{cmd}{give}leatherarmor {cmd}{give}leatherarmour {cmd}{give}leather": 200,
    f"{cmd}{give}anchientarmor {cmd}{give}anchientarmour {cmd}{give}anchient": 300,
    f"{cmd}{give}silverarmor {cmd}{give}silverarmour {cmd}{give}silver": 400,
    f"{cmd}{give}longboots {cmd}{give}longboot {cmd}{give}long {cmd}{give}wellies {cmd}{give}crocs": 150,
    f"{cmd}{give}mermanboots {cmd}{give}mermanboot {cmd}{give}merman {cmd}{give}swim {cmd}{give}filpflops {cmd}{give}flippers": 200,
    f"{cmd}{give}charmboots {cmd}{give}charmboot {cmd}{give}charmb {cmd}{give}docmartens": 100,
    f"{cmd}{give}earthscroll {cmd}{give}escroll {cmd}{give}earths {cmd}{give}earth": 100,
    f"{cmd}{give}waterscroll {cmd}{give}wscroll {cmd}{give}waters {cmd}{give}water": 100,
    f"{cmd}{give}firescroll {cmd}{give}fscroll {cmd}{give}fires {cmd}{give}fire {cmd}{give}bestscroll": 100,
    f"{cmd}{give}windscroll {cmd}{give}wscroll {cmd}{give}winds {cmd}{give}wind {cmd}{give}thunder {cmd}{give}lightning": 100,
    f"{cmd}{give}earthbook {cmd}{give}ebook {cmd}{give}earthb {cmd}{give}earth2 {cmd}{give}meatballs": 200,
    f"{cmd}{give}waterbook {cmd}{give}wbook {cmd}{give}waterb {cmd}{give}water2 {cmd}{give}crystals": 200,
    f"{cmd}{give}firebook {cmd}{give}fbook {cmd}{give}fireb {cmd}{give}fire2 {cmd}{give}nuke": 250,
    f"{cmd}{give}windbook {cmd}{give}wbook {cmd}{give}windb {cmd}{give}wind2 {cmd}{give}tornado": 220,
    f"{cmd}{give}sandcape {cmd}{give}scape {cmd}{give}cape {cmd}{give}curtain {cmd}{give}curtains": 100,
    f"{cmd}{give}aquacape {cmd}{give}acape {cmd}{give}aqua {cmd}{give}showercurtain {cmd}{give}showercurtains": 50,
    f"{cmd}{give}navascharm {cmd}{give}ncharm {cmd}{give}charm {cmd}{give}nava": 50,
    f"{cmd}{give}powerglove {cmd}{give}pglove {cmd}{give}power {cmd}{give}glove": 50,
    f"{cmd}{give}springbean {cmd}{give}spring {cmd}{give}bean {cmd}{give}hotdog": 200,
    f"{cmd}{give}olgaring {cmd}{give}oring {cmd}{give}olga {cmd}{give}ring": 100,
    f"{cmd}{give}silverarmlet {cmd}{give}sarmlet {cmd}{give}armlet {cmd}{give}bracers": 50,
    f"{cmd}{give}recoveryring {cmd}{give}rring {cmd}{give}recovery": 40,
    f"{cmd}{give}refresher {cmd}{give}fresh" : 40,
    # Equipment Take
    f"{cmd}{take}miningbomb {cmd}{take}bomb {cmd}{take}mining {cmd}{take}boom": 150,
    f"{cmd}{take}ironflail {cmd}{take}flail {cmd}{take}iron": 150,
    f"{cmd}{take}huntersbow {cmd}{take}bow {cmd}{take}arrow": 120,
    f"{cmd}{take}firewand {cmd}{take}fwand {cmd}{take}wand {cmd}{take}lighter": 300,
    f"{cmd}{take}icewand {cmd}{take}iwand {cmd}{take}ice {cmd}{take}freezer": 250,
    f"{cmd}{take}leatherarmor {cmd}{take}leatherarmour {cmd}{take}leather": 200,
    f"{cmd}{take}anchientarmor {cmd}{take}anchientarmour {cmd}{take}anchient": 300,
    f"{cmd}{take}silverarmor {cmd}{take}silverarmour {cmd}{take}silver": 400,
    f"{cmd}{take}longboots {cmd}{take}longboot {cmd}{take}long {cmd}{take}wellies {cmd}{take}crocs": 150,
    f"{cmd}{take}mermanboots {cmd}{take}mermanboot {cmd}{take}merman {cmd}{take}swim {cmd}{take}filpflops {cmd}{take}flippers": 200,
    f"{cmd}{take}charmboots {cmd}{take}charmboot {cmd}{take}charmb {cmd}{take}docmartens": 100,
    f"{cmd}{take}earthscroll {cmd}{take}escroll {cmd}{take}earths {cmd}{take}earth": 100,
    f"{cmd}{take}waterscroll {cmd}{take}wscroll {cmd}{take}waters {cmd}{take}water": 100,
    f"{cmd}{take}firescroll {cmd}{take}fscroll {cmd}{take}fires {cmd}{take}fire {cmd}{take}bestscroll": 100,
    f"{cmd}{take}windscroll {cmd}{take}wscroll {cmd}{take}winds {cmd}{take}wind {cmd}{take}thunder {cmd}{take}lightning": 100,
    f"{cmd}{take}earthbook {cmd}{take}ebook {cmd}{take}earthb {cmd}{take}earth2 {cmd}{take}meatballs": 200,
    f"{cmd}{take}waterbook {cmd}{take}waterbook {cmd}{take}waterb {cmd}{take}water2 {cmd}{take}crystals": 200,
    f"{cmd}{take}firebook {cmd}{take}fbook {cmd}{take}fireb {cmd}{take}fire2 {cmd}{take}nuke": 250,
    f"{cmd}{take}windbook {cmd}{take}wbook {cmd}{take}windb {cmd}{take}wind2 {cmd}{take}tornado": 220,
    f"{cmd}{take}sandcape {cmd}{take}scape {cmd}{take}cape {cmd}{take}curtain {cmd}{take}curtains": 100,
    f"{cmd}{take}aquacape {cmd}{take}acape {cmd}{take}aqua {cmd}{take}showercurtain {cmd}{take}showercurtains": 50,
    f"{cmd}{take}navascharm {cmd}{take}ncharm {cmd}{take}charm {cmd}{take}nava": 50,
    f"{cmd}{take}powerglove {cmd}{take}pglove {cmd}{take}power {cmd}{take}glove": 50,
    f"{cmd}{take}springbean {cmd}{take}spring {cmd}{take}bean {cmd}{take}hotdog": 200,
    f"{cmd}{take}olgaring {cmd}{take}oring {cmd}{take}olga {cmd}{take}ring": 100,
    f"{cmd}{take}silverarmlet {cmd}{take}sarmlet {cmd}{take}armlet {cmd}{take}bracers": 50,
    f"{cmd}{take}recoveryring {cmd}{take}rring {cmd}{take}recovery": 40,
    f"{cmd}{take}refresher {cmd}{take}fresh": 40,
    # Item Give
    f"{cmd}{give}herbs {cmd}{give}herb": 10,
    f"{cmd}{give}strengthtonic {cmd}{give}tonic {cmd}{give}potion": 20,
    f"{cmd}{give}strengthelixyr {cmd}{give}strengthelixir {cmd}{give}elixyr {cmd}{give}elixir": 40,
    f"{cmd}{give}magicelixyr {cmd}{give}magicelixir {cmd}{give}melixir {cmd}{give}melixyr {cmd}{give}magictonic {cmd}{give}mtonic {cmd}{give}magicpotion {cmd}{give}mpotion": 60,
    f"{cmd}{give}wonderessence {cmd}{give}wonderessense {cmd}{give}wonder {cmd}{give}essence {cmd}{give}essense {cmd}{give}revive": 200,
    # Item Take
    f"{cmd}{take}herbs {cmd}{take}herb": 10,
    f"{cmd}{take}strengthtonic {cmd}{take}tonic {cmd}{take}potion": 20,
    f"{cmd}{take}strengthelixyr {cmd}{take}strengthelixir {cmd}{take}elixyr {cmd}{take}elixir": 40,
    f"{cmd}{take}magicelixyr {cmd}{take}magicelixir {cmd}{take}melixir {cmd}{take}melixyr {cmd}{give}magictonic {cmd}{give}mtonic {cmd}{take}magicpotion {cmd}{take}mpotion": 60,
    f"{cmd}{take}wonderessence {cmd}{take}wonderessense {cmd}{take}wonder {cmd}{take}essence {cmd}{take}essense {cmd}{take}revive": 200,
    # Progression Give
    f"{cmd}{give}bouquet {cmd}{give}flowers": 100,
    f"{cmd}{give}elevatorkey {cmd}{give}ekey {cmd}{give}elevator": 50,
    f"{cmd}{give}rubycrest {cmd}{give}ruby": 500,
    f"{cmd}{give}sapphirecrest {cmd}{give}sapphire": 600,
    f"{cmd}{give}topazcrest {cmd}{give}topaz": 700,
    f"{cmd}{give}agatecrest {cmd}{give}agate": 800,
    f"{cmd}{give}garnetcrest {cmd}{give}garnet": 900,
    f"{cmd}{give}emeraldcrest {cmd}{give}emerald": 1000,
    f"{cmd}{give}diamondcrest {cmd}{give}diamond": 1100,
    # Progression Take
    f"{cmd}{take}bouquet {cmd}{take}flowers": 100,
    f"{cmd}{take}elevatorkey {cmd}{take}ekey {cmd}{take}elevator": 50,
    f"{cmd}{take}rubycrest {cmd}{take}ruby": 500,
    f"{cmd}{take}sapphirecrest {cmd}{take}sapphire": 600,
    f"{cmd}{take}topazcrest {cmd}{take}topaz": 700,
    f"{cmd}{take}agatecrest {cmd}{take}agate": 800,
    f"{cmd}{take}garnetcrest {cmd}{take}garnet": 900,
    f"{cmd}{take}emeraldcrest {cmd}{take}emerald": 1000,
    f"{cmd}{take}diamondcrest {cmd}{take}diamond": 1100,
    # Misc Give
    f"{cmd}{give}secretpass {cmd}{give}secret {cmd}{give}pass": 150,
    f"{cmd}{give}brokenarmour {cmd}{give}brokenarmor {cmd}{give}broken": 20,
    f"{cmd}{give}key": 150,
    # Misc Take
    f"{cmd}{take}secretpass {cmd}{take}secret {cmd}{take}pass": 150,
    f"{cmd}{take}brokenarmour {cmd}{take}brokenarmor {cmd}{take}broken": 20,
    f"{cmd}{take}key": 150,
    # Money
    f"{cmd}{give}money {cmd}{give}gilder {cmd}{give}cash {cmd}{give}coin": 50,
    f"{cmd}{take}money {cmd}{take}gilder {cmd}{take}cash {cmd}{take}coin": 50,
    # Swords {give} - Added these last lol
    f"{cmd}{give}sword": 150,
    f"{cmd}{give}fiendblade {cmd}{give}fiend {cmd}{give}blade": 250,
    f"{cmd}{give}holysword {cmd}{give}holy": 350,
    f"{cmd}{give}legendsword {cmd}{give}legsword  {cmd}{give}legend": 500,
    # Swords Take
    f"{cmd}{take}sword": 150,
    f"{cmd}{take}fiendblade {cmd}{take}fiend {cmd}{take}blade": 250,
    f"{cmd}{take}holysword {cmd}{take}holy": 350,
    f"{cmd}{take}legendsword {cmd}{take}legsword {cmd}{take}legend": 500,
    # Falcons
    f"{cmd}{give}gildedfalcon {cmd}{give}falcon": 20,
    f"{cmd}{take}gildedfalcon {cmd}{take}falcon": 20,
    # Upgrades
    f"{cmd}{give}steelflail {cmd}{give}sflail {cmd}{give}steel": 200,
    f"{cmd}{take}steelflail {cmd}{take}sflail {cmd}{take}steel": 200,
    # Magic Healing
    f"{cmd}{give}mp {cmd}healmp {cmd}{give}magic {cmd}{give}healmagic {cmd}{give}restoremp": 20,
    f"{cmd}{take}mp {cmd}losemp {cmd}{take}magic {cmd}{take}losemagic {cmd}{take}removemp": 20,
    # Sprit Wand
    f"{cmd}{give}spiritwand {cmd}{give}spiritwand {cmd}{give}spiritw {cmd}{give}swand {cmd}{give}spirit": 1000,
    f"{cmd}{take}spiritwand {cmd}{take}spiritwand {cmd}{take}spiritw {cmd}{take}swand {cmd}{take}spirit": 400,
    # Other Items
    f"{cmd}{give}oaksring {cmd}{give}oakring {cmd}{give}oak": 100,
    f"{cmd}{take}oaksring {cmd}{take}oakring {cmd}{take}oak": 100,
    f"{cmd}{give}willowbow {cmd}{give}wbow {cmd}{give}willow {cmd}{give}bow2": 200,
    f"{cmd}{take}willowbow {cmd}{take}wbow {cmd}{take}willow {cmd}{take}bow2": 200,
    f"{cmd}{give}dagger {cmd}{give}knife": 100,
    f"{cmd}{take}dagger {cmd}{take}knife": 100,
    f"{cmd}{give}protoflail {cmd}{give}protofail {cmd}{give}pflail {cmd}{give}pfail": 50,
    f"{cmd}{take}protoflail {cmd}{take}protofail {cmd}{take}pflail {cmd}{take}pfail": 50,
    f"{cmd}{give}protofirewand {cmd}{give}protofirew {cmd}{give}protofwand {cmd}{give}protowand": 20,
    f"{cmd}{take}protofirewand {cmd}{take}protofirew {cmd}{take}protofwand {cmd}{take}protowand": 20,
    f"{cmd}{give}key": 150,
    f"{cmd}{take}key": 150,
    f"{cmd}{give}smallkey {cmd}{give}skey": 50,
    f"{cmd}{take}smallkey {cmd}{take}skey": 50,
    # Weapon Swap Commands
    f"{cmd}{swap}sword":20,
    f"{cmd}{swap}flail" :20,
    f"{cmd}{swap}bow {cmd}arrow" :20,
    f"{cmd}{swap}firewand {cmd}{swap}fwand {cmd}{swap}firew {cmd}{swap}wand {cmd}{swap}lighter" :20,
    f"{cmd}{swap}icewand {cmd}{swap}iwand {cmd}{swap}icew {cmd}{swap}ice {cmd}{swap}freezer" :20,
    f"{cmd}{swap}spiritwand {cmd}{swap}spiritwand {cmd}{swap}spiritw {cmd}{swap}spirit": 20,
    f"{cmd}{force}sword {cmd}{force}swd {cmd}{force}dagger {cmd}{force}knife {cmd}{force}fiendblade {cmd}{force}blade {cmd}{force}legendsword {cmd}{force}legend":100,
    f"{cmd}{force}flail, {cmd}{force}ironflail {cmd}{force}iron {cmd}{force}steelflail {cmd}{force}steel" :100,
    f"{cmd}{force}bow {cmd}{force}arrow {cmd}{force}huntersbow {cmd}{force}hunters {cmd}{force}willowbow {cmd}{force}willow" :100,
    f"{cmd}{force}firewand {cmd}{force}fwand {cmd}{force}firew {cmd}{force}wand {cmd}{force}lighter" :100,
    f"{cmd}{force}icewand {cmd}{force}iwand {cmd}{force}icew {cmd}{force}ice {cmd}{force}freezer" :100,
    f"{cmd}{force}spiritwand {cmd}{force}spiritwand {cmd}{force}spiritw {cmd}{force}spirit": 100,
    # Misc Items
    f"{cmd}{give}treegem {cmd}{give}tree {cmd}{give}gem": 100,
    f"{cmd}{take}treegem {cmd}{take}tree {cmd}{take}gem": 100,
    f"{cmd}{give}jess_letter {cmd}{give}letter": 20,
    f"{cmd}{take}jess_letter {cmd}{take}letter": 20,
    f"{cmd}{give}zolist_stone {cmd}{give}zloist, {cmd}{give}stone": 50,
    f"{cmd}{take}zolist_stone {cmd}{take}zloist, {cmd}{take}stone": 50,
    f"{cmd}{give}book_of_elna {cmd}{give}elna": 20,
    f"{cmd}{take}book_of_elna {cmd}{take}elna": 20,
    f"{cmd}{give}book_of_runes {cmd}{give}runes": 20,
    f"{cmd}{take}book_of_runes {cmd}{take}runes": 20,
    f"{cmd}{give}curious_key {cmd}{give}ckey {cmd}{give}curious": 50,
    f"{cmd}{take}curious_key {cmd}{take}ckey {cmd}{take}curious": 50,
    # Item Swap Commands
    f"{cmd}{swap}herbs {cmd}{swap}herb": 20,
    f"{cmd}{swap}strengthtonic {cmd}{swap}tonic {cmd}{swap}potion": 20,
    f"{cmd}{swap}strengthelixyr {cmd}{swap}strengthelixir {cmd}{swap}elixyr {cmd}{swap}elixir": 20,
    f"{cmd}{swap}magicelixyr {cmd}{swap}magicelixir {cmd}{swap}melixir {cmd}{swap}melixyr {cmd}{swap}magictonic {cmd}{swap}mtonic {cmd}{swap}magicpotion {cmd}{swap}mpotion": 20,
    f"{cmd}{swap}wonderessence {cmd}{swap}wonderessense {cmd}{swap}wonder {cmd}{swap}essence {cmd}{swap}essense {cmd}{swap}revive": 20,
    f"{cmd}{swap}earthscroll {cmd}{swap}escroll {cmd}{swap}earth": 20,
    f"{cmd}{swap}waterscroll {cmd}{swap}wscroll {cmd}{swap}water": 20,
    f"{cmd}{swap}firescroll {cmd}{swap}fscroll {cmd}{swap}fire {cmd}{swap}bestscroll": 20,
    f"{cmd}{swap}windscroll {cmd}{swap}wscroll {cmd}{swap}wind {cmd}{swap}thunder {cmd}{swap}lightning": 20,
    f"{cmd}{swap}earthbook {cmd}{swap}ebook {cmd}{swap}earth2 {cmd}{swap}meatballs": 20,
    f"{cmd}{swap}waterbook {cmd}{swap}waterbook {cmd}{swap}water2 {cmd}{swap}crystals": 20,
    f"{cmd}{swap}firebook {cmd}{swap}fbook {cmd}{swap}fire2 {cmd}{swap}nuke": 20,
    f"{cmd}{swap}windbook {cmd}{swap}wbook {cmd}{swap}wind2 {cmd}{swap}tornado": 20,
    f"{cmd}{swap}sandcape {cmd}{swap}scape {cmd}{swap}cape {cmd}{swap}curtain {cmd}{swap}curtains": 20,
    f"{cmd}{swap}aquacape {cmd}{swap}acape {cmd}{swap}aqua {cmd}{swap}showercurtain {cmd}{swap}showercurtains": 20,
    f"{cmd}{swap}navascharm {cmd}{swap}ncharm {cmd}{swap}charm {cmd}{swap}nava": 20,
    f"{cmd}{swap}powerglove {cmd}{swap}pglove {cmd}{swap}power {cmd}{swap}glove": 20,
    f"{cmd}{swap}springbean {cmd}{swap}spring {cmd}{swap}bean {cmd}{swap}hotdog": 20,
    f"{cmd}{swap}olgaring {cmd}{swap}oring {cmd}{swap}olga {cmd}{swap}ring": 20,
    f"{cmd}{swap}oaksring {cmd}{swap}oakring {cmd}{swap}oak": 20,
    f"{cmd}{swap}silverarmlet {cmd}{swap}sarmlet {cmd}{swap}armlet {cmd}{swap}bracers": 20,
    f"{cmd}{swap}recoveryring {cmd}{swap}rring {cmd}{swap}recovery": 20,
    f"{cmd}{swap}refresher {cmd}{swap}fresh" : 20,
    f"{cmd}{swap}miningbomb {cmd}{swap}bomb {cmd}{swap}boom": 20,
    # Lock Commands
    f"{cmd}{lock}weapons {cmd}{lock}weapon {cmd}{lock}wpn": 100,
    f"{cmd}{lock}items {cmd}{lock}item {cmd}{lock}itm": 100,
    # Other Effects 
    f"{cmd}regen {cmd}reg {cmd}rgn" : 80,
    f"{cmd}poison {cmd}poi {cmd}psn": 100,
    f"{cmd}{POINTS_NAME}": 0,
    # Force Item Commands
    f"{cmd}{force}herbs {cmd}{force}herb": 100,
    f"{cmd}{force}strengthtonic {cmd}{force}tonic {cmd}{force}potion": 100,
    f"{cmd}{force}strengthelixyr {cmd}{force}strengthelixir {cmd}{force}elixyr {cmd}{force}elixir": 100,
    f"{cmd}{force}magicelixyr {cmd}{force}magicelixir {cmd}{force}melixir {cmd}{force}melixyr {cmd}{force}magictonic {cmd}{force}mtonic {cmd}{force}magicpotion {cmd}{force}mpotion": 100,
    f"{cmd}{force}wonderessence {cmd}{force}wonderessense {cmd}{force}wonder {cmd}{force}essence {cmd}{force}essense {cmd}{force}revive": 100,
    f"{cmd}{force}earthscroll {cmd}{force}escroll {cmd}{force}earth": 100,
    f"{cmd}{force}waterscroll {cmd}{force}wscroll {cmd}{force}water": 100,
    f"{cmd}{force}firescroll {cmd}{force}fscroll {cmd}{force}fire {cmd}{force}bestscroll": 100,
    f"{cmd}{force}windscroll {cmd}{force}wscroll {cmd}{force}wind {cmd}{force}thunder {cmd}{force}lightning": 100,
    f"{cmd}{force}earthbook {cmd}{force}ebook {cmd}{force}earth2 {cmd}{force}meatballs": 100,
    f"{cmd}{force}waterbook {cmd}{force}water2 {cmd}{force}crystals": 100,
    f"{cmd}{force}firebook {cmd}{force}fbook {cmd}{force}fire2 {cmd}{force}nuke": 100,
    f"{cmd}{force}windbook {cmd}{force}wbook {cmd}{force}wind2 {cmd}{force}tornado": 100,
    f"{cmd}{force}sandcape {cmd}{force}scape {cmd}{force}cape {cmd}{force}curtain {cmd}{force}curtains": 100,
    f"{cmd}{force}aquacape {cmd}{force}acape {cmd}{force}aqua {cmd}{force}showercurtain {cmd}{force}showercurtains": 100,
    f"{cmd}{force}navascharm {cmd}{force}ncharm {cmd}{force}charm {cmd}{force}nava": 100,
    f"{cmd}{force}powerglove {cmd}{force}pglove {cmd}{force}power {cmd}{force}glove": 100,
    f"{cmd}{force}springbean {cmd}{force}spring {cmd}{force}bean {cmd}{force}hotdog": 100,
    f"{cmd}{force}olgaring {cmd}{force}oring {cmd}{force}olga {cmd}{force}ring": 100,
    f"{cmd}{force}oaksring {cmd}{force}oakring {cmd}{force}oak": 100,
    f"{cmd}{force}silverarmlet {cmd}{force}sarmlet {cmd}{force}armlet {cmd}{force}bracers": 100,
    f"{cmd}{force}recoveryring {cmd}{force}rring {cmd}{force}recovery": 100,
    f"{cmd}{force}refresher {cmd}{force}fresh": 100,
    f"{cmd}{force}miningbomb {cmd}{force}bomb {cmd}{force}boom": 100,
    # Spawn Enemy (Alundra PC only): a random enemy of the map, or one of a family
    f"{cmd}spawn {cmd}spawnenemy {cmd}spawnrandom {cmd}spn {cmd}spnenemy {cmd}spnrandom": 15,
    f"{cmd}spawnpuku {cmd}spawnslimegel {cmd}spawngel {cmd}spawnblob {cmd}spnpuku {cmd}spnslimegel {cmd}spngel {cmd}spnblob": 15,
    f"{cmd}spawnslime {cmd}spawnbeannoid {cmd}spawngoo {cmd}spnslime {cmd}spnbeannoid {cmd}spngoo": 15,
    f"{cmd}spawnwasp {cmd}spawnbee {cmd}spawnhornet {cmd}spnwasp {cmd}spnbee {cmd}spnhornet": 15,
    f"{cmd}spawnkiller {cmd}spnkiller": 15,
    f"{cmd}spawnroach {cmd}spawncockroach {cmd}spnroach {cmd}spncockroach": 15,
    f"{cmd}spawnmurgg {cmd}spawnmuruta {cmd}spawnmurg {cmd}spawngoblin {cmd}spawnmonkey {cmd}spnmurgg {cmd}spnmuruta {cmd}spnmurg {cmd}spngoblin {cmd}spnmonkey": 20,
    f"{cmd}spawngragg {cmd}spawnorc {cmd}spawngrag {cmd}spawnpig {cmd}spngragg {cmd}spnorc {cmd}spngrag {cmd}spnpig": 20,
    f"{cmd}spawnsandworm {cmd}spawnworm {cmd}spnsandworm {cmd}spnworm": 20,
    f"{cmd}spawnsludge {cmd}spawnooze {cmd}spawnmud {cmd}spnsludge {cmd}spnooze {cmd}spnmud": 20,
    f"{cmd}spawnmiming {cmd}spawnmimming {cmd}spawndwarf {cmd}spnmiming {cmd}spnmimming {cmd}spndwarf": 20,
    f"{cmd}spawnreaper {cmd}spawnghost {cmd}spnreaper {cmd}spnghost": 20,
    f"{cmd}spawnshadow {cmd}spawnshadowman {cmd}spnshadow {cmd}spnshadowman": 20,
    f"{cmd}spawnlizardman {cmd}spawnlizard {cmd}spnlizardman {cmd}spnlizard": 25,
    f"{cmd}spawnzombie {cmd}spnzombie": 25,
    f"{cmd}spawnturtle {cmd}spawnrockturtle {cmd}spnturtle {cmd}spnrockturtle": 25,
    f"{cmd}spawnmimic {cmd}spawnchest {cmd}spnmimic {cmd}spnchest": 25,
    f"{cmd}spawnmudman {cmd}spawninsectman {cmd}spawninsect {cmd}spawnbug {cmd}spnmudman {cmd}spninsectman {cmd}spninsect {cmd}spnbug": 30,
    f"{cmd}spawnmushroom {cmd}spawnshroom {cmd}spnmushroom {cmd}spnshroom": 30,
    f"{cmd}spawnmummy {cmd}spawnmummyman {cmd}spnmummy {cmd}spnmummyman": 35,
    f"{cmd}spawnredturtle {cmd}spawnrockturtle2 {cmd}spawnturtle2 {cmd}spnredturtle {cmd}spnrockturtle2 {cmd}spnturtle2": 40,
    f"{cmd}spawnrockface {cmd}spawnface {cmd}spnrockface {cmd}spnface": 40,
    f"{cmd}spawntreant {cmd}spawnwoodman {cmd}spawntree {cmd}spawnent {cmd}spntreant {cmd}spnwoodman {cmd}spntree {cmd}spnent": 50,
    f"{cmd}spawnfirebird {cmd}spawnphoenix {cmd}spawnbird {cmd}spnfirebird {cmd}spnphoenix {cmd}spnbird": 50,
    f"{cmd}spawnshrinemummy {cmd}spawnmummy2 {cmd}spawnbigmummy {cmd}spnshrinemummy {cmd}spnmummy2 {cmd}spnbigmummy": 50,
    f"{cmd}spawnroper {cmd}spawntentacle {cmd}spnroper {cmd}spntentacle": 50,
    f"{cmd}spawnshrinedemon {cmd}spawndemon {cmd}spnshrinedemon {cmd}spndemon": 50,
    # Buffed Spawn (Alundra PC only): double cost
    f"{cmd}spawnbuff {cmd}spawnbuffenemy {cmd}spawnbuffrandom {cmd}spnbuff {cmd}spnbuffenemy {cmd}spnbuffrandom {cmd}buffspawn {cmd}buffspawnenemy {cmd}buffspawnrandom {cmd}buffspn {cmd}buffspnenemy {cmd}buffspnrandom {cmd}buff {cmd}buffenemy {cmd}buffrandom": 30,
    f"{cmd}spawnbuffpuku {cmd}spawnbuffslimegel {cmd}spawnbuffgel {cmd}spawnbuffblob {cmd}spnbuffpuku {cmd}spnbuffslimegel {cmd}spnbuffgel {cmd}spnbuffblob {cmd}buffspawnpuku {cmd}buffspawnslimegel {cmd}buffspawngel {cmd}buffspawnblob {cmd}buffspnpuku {cmd}buffspnslimegel {cmd}buffspngel {cmd}buffspnblob {cmd}buffpuku {cmd}buffslimegel {cmd}buffgel {cmd}buffblob": 30,
    f"{cmd}spawnbuffslime {cmd}spawnbuffbeannoid {cmd}spawnbuffgoo {cmd}spnbuffslime {cmd}spnbuffbeannoid {cmd}spnbuffgoo {cmd}buffspawnslime {cmd}buffspawnbeannoid {cmd}buffspawngoo {cmd}buffspnslime {cmd}buffspnbeannoid {cmd}buffspngoo {cmd}buffslime {cmd}buffbeannoid {cmd}buffgoo": 30,
    f"{cmd}spawnbuffwasp {cmd}spawnbuffbee {cmd}spawnbuffhornet {cmd}spnbuffwasp {cmd}spnbuffbee {cmd}spnbuffhornet {cmd}buffspawnwasp {cmd}buffspawnbee {cmd}buffspawnhornet {cmd}buffspnwasp {cmd}buffspnbee {cmd}buffspnhornet {cmd}buffwasp {cmd}buffbee {cmd}buffhornet": 30,
    f"{cmd}spawnbuffkiller {cmd}spnbuffkiller {cmd}buffspawnkiller {cmd}buffspnkiller {cmd}buffkiller": 30,
    f"{cmd}spawnbuffroach {cmd}spawnbuffcockroach {cmd}spnbuffroach {cmd}spnbuffcockroach {cmd}buffspawnroach {cmd}buffspawncockroach {cmd}buffspnroach {cmd}buffspncockroach {cmd}buffroach {cmd}buffcockroach": 30,
    f"{cmd}spawnbuffmurgg {cmd}spawnbuffmuruta {cmd}spawnbuffmurg {cmd}spawnbuffgoblin {cmd}spawnbuffmonkey {cmd}spnbuffmurgg {cmd}spnbuffmuruta {cmd}spnbuffmurg {cmd}spnbuffgoblin {cmd}spnbuffmonkey {cmd}buffspawnmurgg {cmd}buffspawnmuruta {cmd}buffspawnmurg {cmd}buffspawngoblin {cmd}buffspawnmonkey {cmd}buffspnmurgg {cmd}buffspnmuruta {cmd}buffspnmurg {cmd}buffspngoblin {cmd}buffspnmonkey {cmd}buffmurgg {cmd}buffmuruta {cmd}buffmurg {cmd}buffgoblin {cmd}buffmonkey": 40,
    f"{cmd}spawnbuffgragg {cmd}spawnbufforc {cmd}spawnbuffgrag {cmd}spawnbuffpig {cmd}spnbuffgragg {cmd}spnbufforc {cmd}spnbuffgrag {cmd}spnbuffpig {cmd}buffspawngragg {cmd}buffspawnorc {cmd}buffspawngrag {cmd}buffspawnpig {cmd}buffspngragg {cmd}buffspnorc {cmd}buffspngrag {cmd}buffspnpig {cmd}buffgragg {cmd}bufforc {cmd}buffgrag {cmd}buffpig": 40,
    f"{cmd}spawnbuffsandworm {cmd}spawnbuffworm {cmd}spnbuffsandworm {cmd}spnbuffworm {cmd}buffspawnsandworm {cmd}buffspawnworm {cmd}buffspnsandworm {cmd}buffspnworm {cmd}buffsandworm {cmd}buffworm": 40,
    f"{cmd}spawnbuffsludge {cmd}spawnbuffooze {cmd}spawnbuffmud {cmd}spnbuffsludge {cmd}spnbuffooze {cmd}spnbuffmud {cmd}buffspawnsludge {cmd}buffspawnooze {cmd}buffspawnmud {cmd}buffspnsludge {cmd}buffspnooze {cmd}buffspnmud {cmd}buffsludge {cmd}buffooze {cmd}buffmud": 40,
    f"{cmd}spawnbuffmiming {cmd}spawnbuffmimming {cmd}spawnbuffdwarf {cmd}spnbuffmiming {cmd}spnbuffmimming {cmd}spnbuffdwarf {cmd}buffspawnmiming {cmd}buffspawnmimming {cmd}buffspawndwarf {cmd}buffspnmiming {cmd}buffspnmimming {cmd}buffspndwarf {cmd}buffmiming {cmd}buffmimming {cmd}buffdwarf": 40,
    f"{cmd}spawnbuffreaper {cmd}spawnbuffghost {cmd}spnbuffreaper {cmd}spnbuffghost {cmd}buffspawnreaper {cmd}buffspawnghost {cmd}buffspnreaper {cmd}buffspnghost {cmd}buffreaper {cmd}buffghost": 40,
    f"{cmd}spawnbuffshadow {cmd}spawnbuffshadowman {cmd}spnbuffshadow {cmd}spnbuffshadowman {cmd}buffspawnshadow {cmd}buffspawnshadowman {cmd}buffspnshadow {cmd}buffspnshadowman {cmd}buffshadow {cmd}buffshadowman": 40,
    f"{cmd}spawnbufflizardman {cmd}spawnbufflizard {cmd}spnbufflizardman {cmd}spnbufflizard {cmd}buffspawnlizardman {cmd}buffspawnlizard {cmd}buffspnlizardman {cmd}buffspnlizard {cmd}bufflizardman {cmd}bufflizard": 50,
    f"{cmd}spawnbuffzombie {cmd}spnbuffzombie {cmd}buffspawnzombie {cmd}buffspnzombie {cmd}buffzombie": 50,
    f"{cmd}spawnbuffturtle {cmd}spawnbuffrockturtle {cmd}spnbuffturtle {cmd}spnbuffrockturtle {cmd}buffspawnturtle {cmd}buffspawnrockturtle {cmd}buffspnturtle {cmd}buffspnrockturtle {cmd}buffturtle {cmd}buffrockturtle": 50,
    f"{cmd}spawnbuffmimic {cmd}spawnbuffchest {cmd}spnbuffmimic {cmd}spnbuffchest {cmd}buffspawnmimic {cmd}buffspawnchest {cmd}buffspnmimic {cmd}buffspnchest {cmd}buffmimic {cmd}buffchest": 50,
    f"{cmd}spawnbuffmudman {cmd}spawnbuffinsectman {cmd}spawnbuffinsect {cmd}spawnbuffbug {cmd}spnbuffmudman {cmd}spnbuffinsectman {cmd}spnbuffinsect {cmd}spnbuffbug {cmd}buffspawnmudman {cmd}buffspawninsectman {cmd}buffspawninsect {cmd}buffspawnbug {cmd}buffspnmudman {cmd}buffspninsectman {cmd}buffspninsect {cmd}buffspnbug {cmd}buffmudman {cmd}buffinsectman {cmd}buffinsect {cmd}buffbug": 60,
    f"{cmd}spawnbuffmushroom {cmd}spawnbuffshroom {cmd}spnbuffmushroom {cmd}spnbuffshroom {cmd}buffspawnmushroom {cmd}buffspawnshroom {cmd}buffspnmushroom {cmd}buffspnshroom {cmd}buffmushroom {cmd}buffshroom": 60,
    f"{cmd}spawnbuffmummy {cmd}spawnbuffmummyman {cmd}spnbuffmummy {cmd}spnbuffmummyman {cmd}buffspawnmummy {cmd}buffspawnmummyman {cmd}buffspnmummy {cmd}buffspnmummyman {cmd}buffmummy {cmd}buffmummyman": 70,
    f"{cmd}spawnbuffredturtle {cmd}spawnbuffrockturtle2 {cmd}spawnbuffturtle2 {cmd}spnbuffredturtle {cmd}spnbuffrockturtle2 {cmd}spnbuffturtle2 {cmd}buffspawnredturtle {cmd}buffspawnrockturtle2 {cmd}buffspawnturtle2 {cmd}buffspnredturtle {cmd}buffspnrockturtle2 {cmd}buffspnturtle2 {cmd}buffredturtle {cmd}buffrockturtle2 {cmd}buffturtle2": 80,
    f"{cmd}spawnbuffrockface {cmd}spawnbuffface {cmd}spnbuffrockface {cmd}spnbuffface {cmd}buffspawnrockface {cmd}buffspawnface {cmd}buffspnrockface {cmd}buffspnface {cmd}buffrockface {cmd}buffface": 80,
    f"{cmd}spawnbufftreant {cmd}spawnbuffwoodman {cmd}spawnbufftree {cmd}spawnbuffent {cmd}spnbufftreant {cmd}spnbuffwoodman {cmd}spnbufftree {cmd}spnbuffent {cmd}buffspawntreant {cmd}buffspawnwoodman {cmd}buffspawntree {cmd}buffspawnent {cmd}buffspntreant {cmd}buffspnwoodman {cmd}buffspntree {cmd}buffspnent {cmd}bufftreant {cmd}buffwoodman {cmd}bufftree {cmd}buffent": 100,
    f"{cmd}spawnbufffirebird {cmd}spawnbuffphoenix {cmd}spawnbuffbird {cmd}spnbufffirebird {cmd}spnbuffphoenix {cmd}spnbuffbird {cmd}buffspawnfirebird {cmd}buffspawnphoenix {cmd}buffspawnbird {cmd}buffspnfirebird {cmd}buffspnphoenix {cmd}buffspnbird {cmd}bufffirebird {cmd}buffphoenix {cmd}buffbird": 100,
    f"{cmd}spawnbuffshrinemummy {cmd}spawnbuffmummy2 {cmd}spawnbuffbigmummy {cmd}spnbuffshrinemummy {cmd}spnbuffmummy2 {cmd}spnbuffbigmummy {cmd}buffspawnshrinemummy {cmd}buffspawnmummy2 {cmd}buffspawnbigmummy {cmd}buffspnshrinemummy {cmd}buffspnmummy2 {cmd}buffspnbigmummy {cmd}buffshrinemummy {cmd}buffmummy2 {cmd}buffbigmummy": 100,
    f"{cmd}spawnbuffroper {cmd}spawnbufftentacle {cmd}spnbuffroper {cmd}spnbufftentacle {cmd}buffspawnroper {cmd}buffspawntentacle {cmd}buffspnroper {cmd}buffspntentacle {cmd}buffroper {cmd}bufftentacle": 100,
    f"{cmd}spawnbuffshrinedemon {cmd}spawnbuffdemon {cmd}spnbuffshrinedemon {cmd}spnbuffdemon {cmd}buffspawnshrinedemon {cmd}buffspawndemon {cmd}buffspnshrinedemon {cmd}buffspndemon {cmd}buffshrinedemon {cmd}buffdemon": 100,
}

##################### MESSAGE QUEUE VARIABLES #####################

MESSAGE_RATE = 0.5
MAX_QUEUE_LENGTH = 20
MAX_WORKERS = 100  # Maximum number of threads you can process at a time 

last_time = time.time()
message_queue = []
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
active_tasks = []

# Count down before starting, so you have time to load up the game
countdown = 0
while countdown > 0:
    print(countdown)
    countdown -= 1
    time.sleep(1)

if STREAMING_ON_TWITCH:
    t = TwitchPlays_Connection.Twitch()
    t.twitch_connect(TWITCH_CHANNEL)
else:
    t = TwitchPlays_Connection.YouTube()
    t.youtube_connect(YOUTUBE_CHANNEL_ID, YOUTUBE_STREAM_URL)

# Get the directory of the current script
script_directory = os.path.dirname(os.path.abspath(__file__))

# Directory for user files
user_files_directory = os.path.join(script_directory, 'user_points')
os.makedirs(user_files_directory, exist_ok=True)

user_points = {}

def initialize_user_points(username):
    # Path to the user's file
    user_file = os.path.join(user_files_directory, f"{username}_points.txt")
    
    # Check if the file exists
    if os.path.exists(user_file):
        try:
            with open(user_file, "r") as file:
                # Read the points from the file
                for line in file:
                    if line.startswith("Points:"):
                        return int(line.split(":")[1].strip())
        except Exception as e:
            print(f"Error reading points for {username}: {e}")
            return INITIAL_POINTS  # Fallback to default if there's an error
    else:
        return INITIAL_POINTS  # Default points if no file exists

def handle_message(message):
    try:
        org_msg = msg = message['message'].strip().lower()
        msg = message['message'].strip().lower()
        username = message['username'].strip().lower()
        org_username = message['username'].strip()

        # Ensure the user is in the points system
        if username != BOT_ACCOUNT: 
            if username not in user_points: user_points[username] = initialize_user_points(username)

        # Handle when give command is entered fully
        msg = msg.replace(f"{cmd}give ",f"{cmd}{give}")
        msg = msg.replace(f"{cmd}give",f"{cmd}{give}")
        msg = msg.replace(f"{cmd}take ",f"{cmd}{take}")
        msg = msg.replace(f"{cmd}take",f"{cmd}{take}")
        msg = msg.replace(f"{cmd}{give} ",f"{cmd}{give}")
        msg = msg.replace(f"{cmd}{take} ",f"{cmd}{take}")
        
        # Check for !givepoints command and handle it
        if (username == TWITCH_CHANNEL or BOT_ACCOUNT in username) and msg.startswith(f"{cmd}{give}{POINTS_NAME}"):
            parts = msg.split()  # Split the message into parts
            if len(parts) == 3:
                target_user = parts[1].strip().lower()  # The username to give points to
                try:
                    points_to_give = int(parts[2])  # The number of points to give
                    if points_to_give > 0:
                        # Ensure target user is in the system and give points
                        if target_user not in user_points:
                            user_points[target_user] = INITIAL_POINTS  # Initialize points if needed
                        user_points[target_user] += points_to_give
                        print(f"{username} gave {points_to_give} points to {target_user}")
                        
                        # Write updated points to the target user's file
                        user_file = os.path.join(user_files_directory, f"{target_user}_points.txt")
                        with open(user_file, "w") as file:
                            file.write(f"Points: {user_points[target_user]}\n")
                            file.write(f"Last Command: {cmd}{give}{POINTS_NAME} {points_to_give}\n")
                            file.write(f"#Get {points_to_give} {POINTS_NAME.capitalize()}\n")
                    else:
                        print("Points must be a positive number.")
                except ValueError:
                    print("Invalid points value. It must be a number.")
            else:
                print(f"Usage: {cmd}givepoints <username> <amount>")
        if (username == TWITCH_CHANNEL or username == BOT_ACCOUNT) and msg.startswith(f"{cmd}{take}{POINTS_NAME}"):
            parts = msg.split()  # Split the message into parts
            if len(parts) == 3:
                target_user = parts[1].strip().lower()  # The username to take points from
                try:
                    points_to_take = int(parts[2])  # The number of points to take
                    if points_to_take > 0:
                        # Ensure target user is in the system
                        if target_user not in user_points:
                            user_points[target_user] = INITIAL_POINTS  # Initialize points if needed
                        
                        # Deduct points but prevent negative balance
                        if user_points[target_user] < points_to_take:
                            points_taken = user_points[target_user]  # Maximum points that can be taken
                            user_points[target_user] = 0
                        else:
                            points_taken = points_to_take
                            user_points[target_user] -= points_to_take
                        
                        print(f"{username} took {points_taken} points from {target_user}")
                        
                        # Write updated points to the target user's file
                        user_file = os.path.join(user_files_directory, f"{target_user}_points.txt")
                        with open(user_file, "w") as file:
                            file.write(f"Points: {user_points[target_user]}\n")
                            file.write(f"Last Command: {cmd}{take}{POINTS_NAME} {points_taken}\n")
                            file.write(f"#Remove {points_taken} {POINTS_NAME.capitalize()}\n")
                    else:
                        print("Points must be a positive number.")
                except ValueError:
                    print("Invalid points value. It must be a number.")
            else:
                print(f"Usage: {cmd}takepoints <username> <amount>")
                
        # Handle when command is entered fully
        msg = msg.replace(" ", "")  # Ensure no spaces in the message
        msg = msg.replace(f"{cmd}swap",f"{cmd}{swap}")
        msg = msg.replace(f"{cmd}force",f"{cmd}{force}")
        msg = msg.replace(f"{cmd}lock",f"{cmd}{lock}")
        org_msg = org_msg.replace(" ","")

        # Preprocess commands to handle individual matches
        command_map = {}
        for key, cost in commands.items():
            for command in key.split():  # Split multiple commands
                command_map[command] = cost  # Map each command to the cost

        # Get the command cost
        command_cost = command_map.get(msg)

        if command_cost is not None:  # Check if the command exists
            # Check if the user has enough points for the command
            if user_points[username] >= command_cost:

                # Check specific command and perform its unique behavior
                with open(os.path.join(script_directory, '_internal/command.txt'), "w") as file:
                    command_map = {}
                    for idx, key in enumerate(commands.keys()):
                        for command in key.split():  # Split each key into individual commands
                            command_map[command.strip()] = idx  # Map each command to its original index     

                    if msg in command_map:
                        index = command_map[msg]  # Get the index associated with the matched command

                        # Gameplay
                        if index == 0: file.write("Invincibility\n")
                        if index == 1: file.write("NoIFrames\n")
                        if index == 2: file.write("MoonJump\nMoon Jump")
                        if index == 3: file.write("NoJump\n")
                        if index == 4: file.write("SlowMotion\n")

                        # Character Give
                        if max_hp_mp_commands:
                            if index == 5: file.write("LifeVessel+\nObtained A Life Vessel")
                            
                        if current_hp_mp_commands:
                            if index == 6: file.write("HP+\nHealed HP")

                        if max_hp_mp_commands:
                            if index == 7: file.write("MagicSeed+\nObtained A Magic Seed")

                        # Character Take
                        if max_hp_mp_commands:
                            if index == 8: file.write("LifeVessel-\nLost A Life Vessel")

                        if current_hp_mp_commands:
                            if index == 9: file.write("HP-\nLost HP")

                        if max_hp_mp_commands:
                            if index == 10: file.write("MagicSeed-\nLost A Magic Seed")

                        # Equipment Give
                        if important_equipment_commands:
                            if index == 11: file.write("MiningBomb+\nObtained Mining Bomb")
                            if index == 12: file.write("IronFlail+\nObtained Iron Flail")
                            if index == 13: file.write("HuntersBow+\nObtained Hunter's Bow")
                            if index == 14: file.write("FireWand+\nObtained Fire Wand")
                            if index == 15: file.write("IceWand+\nObtained Ice Wand")
                        if index == 16: file.write("LeatherArmor+\nObtained Leather Armor")
                        if index == 17: file.write("AncientArmor+\nObtained Ancient Armor")
                        if index == 18: file.write("SilverArmor+\nObtained Silver Armor")
                        if important_equipment_commands:
                            if index == 19: file.write("LongBoots+\nObtained Long Boots")
                            if index == 20: file.write("MermanBoots+\nObtained Merman Boots")
                            if index == 21: file.write("CharmBoots+\nObtained Charm Boots")
                        if index == 22: file.write("EarthScroll+\nObtained Earth Scroll")
                        if index == 23: file.write("WaterScroll+\nObtained Water Scroll")
                        if index == 24: file.write("FireScroll+\nObtained Fire Scroll")
                        if index == 25: file.write("WindScroll+\nObtained Wind Scroll")
                        if index == 26: file.write("EarthBook+\nObtained Earth Book")
                        if index == 27: file.write("WaterBook+\nObtained Water Book")
                        if index == 28: file.write("FireBook+\nObtained Fire Book")
                        if index == 29: file.write("WindBook+\nObtained Wind Book")
                        if important_equipment_commands:
                            if index == 30: file.write("SandCape+\nObtained Sand Cape")
                            if index == 31: file.write("AquaCape+\nObtained Aqua Cape")
                        if index == 32: file.write("NavasCharm+\nObtained Nava's Charm")
                        if important_equipment_commands:
                            if index == 33: file.write("PowerGlove+\nObtained Power Glove")
                            if index == 34: file.write("SpringBean+\nObtained Hot Dog")
                        if index == 35: file.write("OlgasRing+\nObtained Olga's Ring")
                        if index == 36: file.write("SilverArmlet+\nObtained Silver Armlet")
                        if index == 37: file.write("RecoveryRing+\nObtained Recovery Ring")
                        if index == 38: file.write("Refresher+\nObtained Refresher")

                        # Equipment Take
                        if important_equipment_commands:
                            if index == 39: file.write("MiningBomb-\nLost Mining Bomb")
                            if index == 40: file.write("IronFlail-\nLost Iron Flail")
                            if index == 41: file.write("HuntersBow-\nLost Hunter's Bow")
                            if index == 42: file.write("FireWand-\nLost Fire Wand")
                            if index == 43: file.write("IceWand-\nLost Ice Wand")

                        if index == 44: file.write("LeatherArmor-\nLost Leather Armor")
                        if index == 45: file.write("AncientArmor-\nLost Ancient Armor")
                        if index == 46: file.write("SilverArmor-\nLost Silver Armor")

                        if important_equipment_commands: 
                            if index == 47: file.write("LongBoots-\nLost Long Boots")
                            if index == 48: file.write("MermanBoots-\nLost Merman Boots")
                            if index == 49: file.write("CharmBoots-\nLost Charm Boots")

                        if index == 50: file.write("EarthScroll-\nLost Earth Scroll")
                        if index == 51: file.write("WaterScroll-\nLost Water Scroll")
                        if index == 52: file.write("FireScroll-\nLost Fire Scroll")
                        if index == 53: file.write("WindScroll-\nLost Wind Scroll")
                        if index == 54: file.write("EarthBook-\nLost Earth Book")
                        if index == 55: file.write("WaterBook-\nLost Water Book")
                        if index == 56: file.write("FireBook-\nLost Fire Book")
                        if index == 57: file.write("WindBook-\nLost Wind Book")

                        if important_equipment_commands:
                            if index == 58: file.write("SandCape-\nLost Sand Cape")
                            if index == 59: file.write("AquaCape-\nLost Aqua Cape")

                        if index == 60: file.write("NavasCharm-\nLost Nava's Charm")

                        if important_equipment_commands:
                            if index == 61: file.write("PowerGlove-\nLost Power Glove")
                            if index == 62: file.write("SpringBean-\nLost Hot Dog")

                        if index == 63: file.write("OlgasRing-\nLost Olgas Ring")
                        if index == 64: file.write("SilverArmlet-\nLost Silver Armlet")
                        if index == 65: file.write("RecoveryRing-\nLost Recovery Ring")
                        if index == 66: file.write("Refresher-\nLost Refresher")

                        # Items Give
                        if index == 67: file.write("Herbs+\n")
                        if index == 68: file.write("StrengthTonic+\nObtained Strength Tonic")
                        if index == 69: file.write("StrengthElixir+\nObtained Strength Elixir")
                        if index == 70: file.write("MagicElixir+\nObtained Magic Elixir")
                        if index == 71: file.write("WonderEssence+\nObtained Wonder Essence")

                        # Items Take
                        if index == 72: file.write("Herbs-\n")
                        if index == 73: file.write("StrengthTonic-\nLost Strength Tonic")
                        if index == 74: file.write("StrengthElixir-\nLost Strength Elixir")
                        if index == 75: file.write("MagicElixir-\nLost Magic Elixir")
                        if index == 76: file.write("WonderEssence-\nLost Wonder Essence")

                        # Progression Give
                        if progression_item_commands: 
                            if index == 77: file.write("Bouquet+\nObtained Bouquet")
                            if index == 78: file.write("ElevatorKey+\nObtained Elevator Key")
                            if index == 79: file.write("RubyCrest+\nObtained Ruby Crest")
                            if index == 80: file.write("SapphireCrest+\nObtained Sapphire Crest")
                            if index == 81: file.write("TopazCrest+\nObtained Topaz Crest")
                            if index == 82: file.write("AgateCrest+\nObtained Agate Crest")
                            if index == 83: file.write("GarnetCrest+\nObtained Garnet Crest")
                            if index == 84: file.write("EmeraldCrest+\nObtained Emerald Crest")
                            if index == 85: file.write("DiamondCrest+\nObtained Diamond Crest")

                        # Progression Take
                        if progression_item_commands:
                            if index == 86: file.write("Bouquet-\nLost Bouquet")
                            if index == 87: file.write("ElevatorKey-\nLost Elevator Key")
                            if index == 88: file.write("RubyCrest-\nLost Ruby Crest")
                            if index == 89: file.write("SapphireCrest-\nLost Sapphire Crest")
                            if index == 90: file.write("TopazCrest-\nLost Topaz Crest")
                            if index == 91: file.write("AgateCrest-\nLost Agate Crest")
                            if index == 92: file.write("GarnetCrest-\nLost Garnet Crest")
                            if index == 93: file.write("EmeraldCrest-\nLost Emerald Crest")
                            if index == 94: file.write("DiamondCrest-\nLost Diamond Crest")

                        # Misc Give
                        if progression_item_commands:
                            if index == 95: file.write("SecretPass+\nObtained Secret Pass")
                            if index == 96: file.write("BrokenArmor+\nObtained Broken Armor")
                            if index == 97: file.write("Key+\nObtained Key")

                        # Misc Take
                        if progression_item_commands:
                            if index == 98: file.write("SecretPass-\nLost Secret Pass")
                            if index == 99: file.write("BrokenArmor-\nLost Broken Armor")
                            if index == 100: file.write("Key-\nLost Key")

                        # Money Give
                        if index == 101: file.write("Gilder+\nObtained Gilder")

                        # Money Take
                        if index == 102: file.write("Gilder-\nLost Gilder")

                        # Swords Give
                        if index == 103: file.write("Sword+\nObtained Sword")
                        if index == 104: file.write("FiendBlade+\nObtained Fiend Blade")
                        if index == 105: file.write("HolySword+\nObtained Holy Sword")
                        if index == 106: file.write("LegendSword+\nObtained Legend Sword")

                        # Swords Take
                        if index == 107: file.write("Sword-\nLost Sword")
                        if index == 108: file.write("FiendBlade-\nLost Fiend Blade")
                        if index == 109: file.write("HolySword-\nLost Holy Sword")
                        if index == 110: file.write("LegendSword-\nLost Legend Sword")

                        # Falcons
                        if progression_item_commands:
                            if index == 111: file.write("GildedFalcon+\nObtained Gilded Falcon")
                            if index == 112: file.write("GildedFalcon-\nLost Gilded Falcon")

                        # Upgrades
                        if important_equipment_commands:
                            if index == 113: file.write("SteelFlail+\nObatined Steel Flail")
                            if index == 114: file.write("SteelFlail-\nLost Steel Flail")

                        # Magic Healing
                        if current_hp_mp_commands:
                            if index == 115: file.write("MP+\nGained MP")
                            if index == 116: file.write("MP-\nLost MP")

                        # Spirit Wand
                        if spirit_wand:
                            if index == 117: file.write("SpiritWand+\nObatined Spirit Wand")
                            if index == 118: file.write("SpiritWand-\nLost Spirit Wand")

                        # Other Things
                        if index == 119: file.write("OaksRing+\nObtained Oak's Ring")
                        if index == 120: file.write("OaksRing-\nLost Oak's Ring")
                        
                        if important_equipment_commands:
                            if index == 121: file.write("WillowBow+\nObtained Willow Bow")
                            if index == 122: file.write("WillowBow-\nLost Willow Bow")
                            if index == 123: file.write("Dagger+\nObtained Dagger")
                            if index == 124: file.write("Dagger-\nLost Dagger")

                        if important_equipment_commands:
                            if index == 125: file.write("ProtoFlail+\nObtained (Proto) Flail")
                            if index == 126: file.write("ProtoFlail-\nLost (Proto) Flail")
                        if index == 127: file.write("ProtoFireWand+\nObtained (Proto) Fire Wand")
                        if index == 128: file.write("ProtoFireWand-\nLost (Proto) Wand")

                        if progression_item_commands:
                            if index == 129: file.write("SmallKey+\nObtained Small Key")
                            if index == 130: file.write("SmallKey-\nLost Small Key")

                        if swap_commands:
                            if index == 131: file.write("SwapSword\nSwap to Sword")
                            if index == 132: file.write("SwapFlail\nSwap to Flail")
                            if index == 133: file.write("SwapBow\nSwap to Bow")
                            if index == 134: file.write("SwapFireWand\nSwap to Fire Wand")
                            if index == 135: file.write("SwapIceWand\nSwap to Ice Wand")
                            if index == 136: file.write("SwapSpiritWand\nSwap to Spirit Wand")

                        if force_commands:
                            if index == 137: file.write("ForceSword\nForce Sword")
                            if index == 138: file.write("ForceFlail\nForce Flail")
                            if index == 139: file.write("ForceBow\nForce Bow")
                            if index == 140: file.write("ForceFireWand\nForce Fire Wand")
                            if index == 141: file.write("ForceIceWand\nForce Ice Wand")
                            if index == 142: file.write("ForceSpiritWand\nForce Spirit Wand")
                        
                        if index == 143: file.write("TreeGem+\nObatined Tree Gem")
                        if index == 144: file.write("TreeGem-\nLost Tree Gem")
                        if index == 145: file.write("JessLetter+\nObatined Jess's Letter")
                        if index == 146: file.write("JessLetter-\nLost Jess's Letter")
                        if index == 147: file.write("ZolistStone+\nObtained Zolist Stone")
                        if index == 148: file.write("ZolistStone-\nLost Zolist Stone")
                        if index == 149: file.write("BookOfElna+\nObtained Book of Elna")
                        if index == 150: file.write("BookOfElna-\nLost Book of Elna")
                        if index == 151: file.write("BookOfRunes+\nObtained Book of Runes")
                        if index == 152: file.write("BookOfRunes-\nLost Book of Runes")
                        if index == 153: file.write("CuriousKey+\nObtained Curious Key")
                        if index == 154: file.write("CuriousKey-\nLost Curious Key")
                        if swap_commands:
                            if index == 155: file.write("SwapHerbs\nSwap to Herbs")
                            if index == 156: file.write("SwapStrengthTonic\nSwap to Strength Tonic")
                            if index == 157: file.write("SwapStrengthElixir\nSwap to Strength Elixir")
                            if index == 158: file.write("SwapMagicElixir\nSwap to Magic Elixir")
                            if index == 159: file.write("SwapWonderEssence\nSwap to Wonder Essence")
                            if index == 160: file.write("SwapEarthScroll\nSwap to Earth Scroll")
                            if index == 161: file.write("SwapWaterScroll\nSwap to Water Scroll")
                            if index == 162: file.write("SwapFireScroll\nSwap to Fire Scroll")
                            if index == 163: file.write("SwapWindScroll\nSwap to Wind Scroll")
                            if index == 164: file.write("SwapEarthBook\nSwap to Earth Book")
                            if index == 165: file.write("SwapWaterBook\nSwap to Water Book")
                            if index == 166: file.write("SwapFireBook\nSwap to Fire Book")
                            if index == 167: file.write("SwapWindBook\nSwap to Wind Book")
                            if index == 168: file.write("SwapSandCape\nSwap to Sand Cape")
                            if index == 169: file.write("SwapAquaCape\nSwap to Aqua Cape")
                            if index == 170: file.write("SwapNavasCharm\nSwap to Navas Charm")
                            if index == 171: file.write("SwapPowerGlove\nSwap to Power Glove")
                            if index == 172: file.write("SwapSpringBean\nSwap to Hot Dog")
                            if index == 173: file.write("SwapOlgasRing\nSwap to Olgas Ring")
                            if index == 174: file.write("SwapOaksRing\nSwap to Oaks Ring")
                            if index == 175: file.write("SwapSilverArmlet\nSwap to Silver Armlet")
                            if index == 176: file.write("SwapRecoveryRing\nSwap to Recovery Ring")
                            if index == 177: file.write("SwapRefresher\nSwap to Refresher")
                            if index == 178: file.write("SwapMiningBomb\nSwap to Mining Bomb")
                            
                        if lock_commands:
                            if index == 179: file.write("LockWeapon\nLock Weapon")
                            if index == 180: file.write("LockItem\nLock Item")
                        
                        if current_hp_mp_commands:
                            if index == 181: file.write("Regen\nHP Regen")
                            if index == 182: file.write("Poison\nPoisoned")

                        if force_commands:
                            if index == 184: file.write("ForceHerbs\nForce Herbs")
                            if index == 185: file.write("ForceStrengthTonic\nForce Strength Tonic")
                            if index == 186: file.write("ForceStrengthElixir\nForce Strength Elixir")
                            if index == 187: file.write("ForceMagicElixir\nForce Magic Elixir")
                            if index == 188: file.write("ForceWonderEssence\nForce Wonder Essence")
                            if index == 189: file.write("ForceEarthScroll\nForce Earth Scroll")
                            if index == 190: file.write("ForceWaterScroll\nForce Water Scroll")
                            if index == 191: file.write("ForceFireScroll\nForce Fire Scroll")
                            if index == 192: file.write("ForceWindScroll\nForce Wind Scroll")
                            if index == 193: file.write("ForceEarthBook\nForce Earth Book")
                            if index == 194: file.write("ForceWaterBook\nForce Water Book")
                            if index == 195: file.write("ForceFireBook\nForce Fire Book")
                            if index == 196: file.write("ForceWindBook\nForce Wind Book")
                            if index == 197: file.write("ForceSandCape\nForce Sand Cape")
                            if index == 198: file.write("ForceAquaCape\nForce Aqua Cape")
                            if index == 199: file.write("ForceNavasCharm\nForce Navas Charm")
                            if index == 200: file.write("ForcePowerGlove\nForce Power Glove")
                            if index == 201: file.write("ForceSpringBean\nForce Hot Dog")
                            if index == 202: file.write("ForceOlgasRing\nForce Olgas Ring")
                            if index == 203: file.write("ForceOaksRing\nForce Oaks Ring")
                            if index == 204: file.write("ForceSilverArmlet\nForce Silver Armlet")
                            if index == 205: file.write("ForceRecoveryRing\nForce Recovery Ring")
                            if index == 206: file.write("ForceRefresher\nForce Refresher")
                            if index == 207: file.write("ForceMiningBomb\nForce Mining Bomb")

                        if index == 208: file.write("SpawnEnemy\nSpawn Enemy")
                        if index == 209: file.write("SpawnPuku\nSpawn Puku")
                        if index == 210: file.write("SpawnSlime\nSpawn Slime")
                        if index == 211: file.write("SpawnWasp\nSpawn Wasp")
                        if index == 212: file.write("SpawnKiller\nSpawn Killer")
                        if index == 213: file.write("SpawnRoach\nSpawn Roach")
                        if index == 214: file.write("SpawnMurgg\nSpawn Murgg")
                        if index == 215: file.write("SpawnGragg\nSpawn Gragg")
                        if index == 216: file.write("SpawnSandWorm\nSpawn Sand Worm")
                        if index == 217: file.write("SpawnSludge\nSpawn Sludge")
                        if index == 218: file.write("SpawnMiming\nSpawn Miming")
                        if index == 219: file.write("SpawnReaper\nSpawn Reaper")
                        if index == 220: file.write("SpawnShadow\nSpawn Shadow")
                        if index == 221: file.write("SpawnLizardman\nSpawn Lizardman")
                        if index == 222: file.write("SpawnZombie\nSpawn Zombie")
                        if index == 223: file.write("SpawnTurtle\nSpawn Turtle")
                        if index == 224: file.write("SpawnMimic\nSpawn Mimic")
                        if index == 225: file.write("SpawnMudMan\nSpawn Mud Man")
                        if index == 226: file.write("SpawnMushroom\nSpawn Mushroom")
                        if index == 227: file.write("SpawnMummy\nSpawn Mummy")
                        if index == 228: file.write("SpawnRedTurtle\nSpawn Red Turtle")
                        if index == 229: file.write("SpawnRockFace\nSpawn Rock Face")
                        if index == 230: file.write("SpawnTreant\nSpawn Treant")
                        if index == 231: file.write("SpawnFirebird\nSpawn Firebird")
                        if index == 232: file.write("SpawnShrineMummy\nSpawn Shrine Mummy")
                        if index == 233: file.write("SpawnRoper\nSpawn Roper")
                        if index == 234: file.write("SpawnShrineDemon\nSpawn Shrine Demon")
                        if index == 235: file.write("BuffSpawnEnemy\nSpawn Buffed Enemy")
                        if index == 236: file.write("BuffSpawnPuku\nSpawn Buffed Puku")
                        if index == 237: file.write("BuffSpawnSlime\nSpawn Buffed Slime")
                        if index == 238: file.write("BuffSpawnWasp\nSpawn Buffed Wasp")
                        if index == 239: file.write("BuffSpawnKiller\nSpawn Buffed Killer")
                        if index == 240: file.write("BuffSpawnRoach\nSpawn Buffed Roach")
                        if index == 241: file.write("BuffSpawnMurgg\nSpawn Buffed Murgg")
                        if index == 242: file.write("BuffSpawnGragg\nSpawn Buffed Gragg")
                        if index == 243: file.write("BuffSpawnSandWorm\nSpawn Buffed Sand Worm")
                        if index == 244: file.write("BuffSpawnSludge\nSpawn Buffed Sludge")
                        if index == 245: file.write("BuffSpawnMiming\nSpawn Buffed Miming")
                        if index == 246: file.write("BuffSpawnReaper\nSpawn Buffed Reaper")
                        if index == 247: file.write("BuffSpawnShadow\nSpawn Buffed Shadow")
                        if index == 248: file.write("BuffSpawnLizardman\nSpawn Buffed Lizardman")
                        if index == 249: file.write("BuffSpawnZombie\nSpawn Buffed Zombie")
                        if index == 250: file.write("BuffSpawnTurtle\nSpawn Buffed Turtle")
                        if index == 251: file.write("BuffSpawnMimic\nSpawn Buffed Mimic")
                        if index == 252: file.write("BuffSpawnMudMan\nSpawn Buffed Mud Man")
                        if index == 253: file.write("BuffSpawnMushroom\nSpawn Buffed Mushroom")
                        if index == 254: file.write("BuffSpawnMummy\nSpawn Buffed Mummy")
                        if index == 255: file.write("BuffSpawnRedTurtle\nSpawn Buffed Red Turtle")
                        if index == 256: file.write("BuffSpawnRockFace\nSpawn Buffed Rock Face")
                        if index == 257: file.write("BuffSpawnTreant\nSpawn Buffed Treant")
                        if index == 258: file.write("BuffSpawnFirebird\nSpawn Buffed Firebird")
                        if index == 259: file.write("BuffSpawnShrineMummy\nSpawn Buffed Shrine Mummy")
                        if index == 260: file.write("BuffSpawnRoper\nSpawn Buffed Roper")
                        if index == 261: file.write("BuffSpawnShrineDemon\nSpawn Buffed Shrine Demon")

                        # Index above last is points checking

                        remove_cmd = False

                        if important_equipment_commands == False:
                            if index in range(11, 16): remove_cmd = True
                            if index in range(19, 22): remove_cmd = True
                            if index in range(31, 33): remove_cmd = True
                            if index in range(33, 35): remove_cmd = True
                            if index in range(39, 44): remove_cmd = True
                            if index in range(47, 50): remove_cmd = True
                            if index in range(58, 60): remove_cmd = True
                            if index in range(61, 63): remove_cmd = True
                            if index in range(113, 115): remove_cmd = True
                            if index in range(121, 123): remove_cmd = True
                            if index in range(129, 131): remove_cmd = True

                        if progression_item_commands == False:
                            if index in range(77, 101): remove_cmd = True
                            if index in range(129, 131): remove_cmd = True
                            if index in range(143, 145): remove_cmd = True
                            if index in range(147, 149): remove_cmd = True
                            if index in range(153, 155): remove_cmd = True

                        if max_hp_mp_commands == False:
                            if index == 4: remove_cmd = True
                            if index == 6: remove_cmd = True
                            if index == 7: remove_cmd = True
                            if index == 9: remove_cmd = True

                        if current_hp_mp_commands == False:
                            if index == 5: remove_cmd = True
                            if index == 8: remove_cmd = True
                            if index == 115: remove_cmd = True
                            if index == 116: remove_cmd = True
                            if index in range(181, 183): remove_cmd = True

                        if swap_commands == False:
                            if index in range(131, 136): remove_cmd = True
                            if index in range(155, 179): remove_cmd = True

                        if force_commands == False:
                            if index in range(137, 142): remove_cmd = True
                            if index in range(184, 208): remove_cmd = True

                        if buffed_spawns == False:
                            if index in range(235, 262):
                                remove_cmd = True
                                file.seek(0); file.truncate()   # (off: nothing reaches the game)

                        if spirit_wand == False:
                            if index == 117: remove_cmd = True

                        if lock_commands == False:
                            if index in range(179, 181): remove_cmd = True

                        sprite = ""
                        
                        if index == 0: sprite = "Invincibility"
                        if index == 1: sprite = "No_I_Frames"
                        if index == 2: sprite = "Moon_Jump"
                        if index == 3: sprite = "No_Jump"
                        if index == 4: sprite = "Slow_Motion"
                        if index == 5: sprite = "Life_Vessel"
                        if index == 6: sprite = "HP"
                        if index == 7: sprite = "Magic_Seed"
                        if index == 8: sprite = "Life_Vessel-"
                        if index == 9: sprite = "HP-"
                        if index == 10: sprite = "Magic_Seed-"
                        if index == 11: sprite = "Mining_Bomb"
                        if index == 12: sprite = "Iron_Flail"
                        if index == 13: sprite = "Hunters_Bow"
                        if index == 14: sprite = "Fire_Wand"
                        if index == 15: sprite = "Ice_Wand"
                        if index == 16: sprite = "Leather_Armor"
                        if index == 17: sprite = "Ancient_Armor"
                        if index == 18: sprite = "Silver_Armor"
                        if index == 19: sprite = "Long_Boots"
                        if index == 20: sprite = "Merman_Boots"
                        if index == 21: sprite = "Charm_Boots"
                        if index == 22: sprite = "Earth_Scroll"
                        if index == 23: sprite = "Water_Scroll"
                        if index == 24: sprite = "Fire_Scroll"
                        if index == 25: sprite = "Wind_Scroll"
                        if index == 26: sprite = "Earth_Book"
                        if index == 27: sprite = "Water_Book"
                        if index == 28: sprite = "Fire_Book"
                        if index == 29: sprite = "Wind_Book"
                        if index == 30: sprite = "Sand_Cape"
                        if index == 31: sprite = "Aqua_Cape"
                        if index == 32: sprite = "Navas_Charm"
                        if index == 33: sprite = "Power_Glove"
                        if index == 34: sprite = "Spring_Bean"
                        if index == 35: sprite = "Olgas_Ring"
                        if index == 36: sprite = "Silver_Armlet"
                        if index == 37: sprite = "Recovery_Ring"
                        if index == 38: sprite = "Refresher"
                        if index == 39: sprite = "Mining_Bomb-"
                        if index == 40: sprite = "Iron_Flail-"
                        if index == 41: sprite = "Hunters_Bow-"
                        if index == 42: sprite = "Fire_Wand-"
                        if index == 43: sprite = "Ice_Wand-"
                        if index == 44: sprite = "Leather_Armor-"
                        if index == 45: sprite = "Ancient_Armor-"
                        if index == 46: sprite = "Silver_Armor-"
                        if index == 47: sprite = "Long_Boots-"
                        if index == 48: sprite = "Merman_Boots-"
                        if index == 49: sprite = "Charm_Boots-"
                        if index == 50: sprite = "Earth_Scroll-"
                        if index == 51: sprite = "Water_Scroll-"
                        if index == 52: sprite = "Fire_Scroll-"
                        if index == 53: sprite = "Wind_Scroll-"
                        if index == 54: sprite = "Earth_Book-"
                        if index == 55: sprite = "Water_Book-"
                        if index == 56: sprite = "Fire_Book-"
                        if index == 57: sprite = "Wind_Book-"
                        if index == 58: sprite = "Sand_Cape-"
                        if index == 59: sprite = "Aqua_Cape-"
                        if index == 60: sprite = "Navas_Charm-"
                        if index == 61: sprite = "Power_Glove-"
                        if index == 62: sprite = "Spring_Bean-"
                        if index == 63: sprite = "Olgas_Ring-"
                        if index == 64: sprite = "Silver_Armlet-"
                        if index == 65: sprite = "Recovery_Ring-"
                        if index == 66: sprite = "Refresher-"
                        if index == 67: sprite = "Herbs"
                        if index == 68: sprite = "Strength_Tonic"
                        if index == 69: sprite = "Strength_Elixir"
                        if index == 70: sprite = "Magic_Elixir"
                        if index == 71: sprite = "Wonder_Essence"
                        if index == 72: sprite = "Herbs-"
                        if index == 73: sprite = "Strength_Tonic-"
                        if index == 74: sprite = "Strength_Elixir-"
                        if index == 75: sprite = "Magic_Elixir-"
                        if index == 76: sprite = "Wonder_Essence-"
                        if index == 77: sprite = "Bouquet"
                        if index == 78: sprite = "Elevator_Key"
                        if index == 79: sprite = "Ruby_Crest"
                        if index == 80: sprite = "Sapphire_Crest"
                        if index == 81: sprite = "Topaz_Crest"
                        if index == 82: sprite = "Agate_Crest"
                        if index == 83: sprite = "Garnet_Crest"
                        if index == 84: sprite = "Emerald_Crest"
                        if index == 85: sprite = "Diamond_Crest"
                        if index == 86: sprite = "Bouquet-"
                        if index == 87: sprite = "Elevator_Key-"
                        if index == 88: sprite = "Ruby_Crest-"
                        if index == 89: sprite = "Sapphire_Crest-"
                        if index == 90: sprite = "Topaz_Crest-"
                        if index == 91: sprite = "Agate_Crest-"
                        if index == 92: sprite = "Garnet_Crest-"
                        if index == 93: sprite = "Emerald_Crest-"
                        if index == 94: sprite = "Diamond_Crest-"
                        if index == 95: sprite = "Secret_Pass"
                        if index == 96: sprite = "Broken_Armor"
                        if index == 97: sprite = "Key"
                        if index == 98: sprite = "Secret_Pass-"
                        if index == 99: sprite = "Broken_Armor-"
                        if index == 100: sprite = "Key-"
                        if index == 101: sprite = "Gilder"
                        if index == 102: sprite = "Gilder-"
                        if index == 103: sprite = "Sword"
                        if index == 104: sprite = "Fiend_Blade"
                        if index == 105: sprite = "Holy_Sword"
                        if index == 106: sprite = "Legend_Sword"
                        if index == 107: sprite = "Sword-"
                        if index == 108: sprite = "Fiend_Blade-"
                        if index == 109: sprite = "Holy_Sword-"
                        if index == 110: sprite = "Legend_Sword-"
                        if index == 111: sprite = "Gilded_Falcon"
                        if index == 112: sprite = "Gilded_Falcon-"
                        if index == 113: sprite = "Steel_Flail"
                        if index == 114: sprite = "Steel_Flail-"
                        if index == 115: sprite = "MP"
                        if index == 116: sprite = "MP-"
                        if index == 117: sprite = "Spirit_Wand"
                        if index == 118: sprite = "Spirit_Wand-"
                        if index == 119: sprite = "Oaks_Ring"
                        if index == 120: sprite = "Oaks_Ring-"
                        if index == 121: sprite = "Willow_Bow"
                        if index == 122: sprite = "Willow_Bow-"
                        if index == 123: sprite = "Dagger"
                        if index == 124: sprite = "Dagger-"
                        if index == 125: sprite = "Proto_Flail"
                        if index == 126: sprite = "Proto_Flail-"
                        if index == 127: sprite = "Proto_Fire_Wand"
                        if index == 128: sprite = "Proto_Fire_Wand-"
                        if index == 129: sprite = "Small_Key"
                        if index == 130: sprite = "Small_Key-"
                        if index == 131: sprite = "Swap_Sword"
                        if index == 132: sprite = "Swap_Flail"
                        if index == 133: sprite = "Swap_Bow"
                        if index == 134: sprite = "Swap_Fire_Wand"
                        if index == 135: sprite = "Swap_Ice_Wand"
                        if index == 136: sprite = "Swap_Spirit_Wand"
                        if index == 137: sprite = "Force_Sword"
                        if index == 138: sprite = "Force_Flail"
                        if index == 139: sprite = "Force_Bow"
                        if index == 140: sprite = "Force_Fire_Wand"
                        if index == 141: sprite = "Force_Ice_Wand"
                        if index == 142: sprite = "Force_Spirit_Wand"
                        if index == 143: sprite = "Tree_Gem"
                        if index == 144: sprite = "Tree_Gem-"
                        if index == 145: sprite = "Jess's_Letter"
                        if index == 146: sprite = "Jess's_Letter-"
                        if index == 147: sprite = "Zolist_Stone"
                        if index == 148: sprite = "Zolist_Stone-"
                        if index == 149: sprite = "Book_of_Elna"
                        if index == 150: sprite = "Book_of_Elna-"
                        if index == 151: sprite = "Book_of_Runes"
                        if index == 152: sprite = "Book_of_Runes-"
                        if index == 153: sprite = "Curious_Key"
                        if index == 154: sprite = "Curious_Key-"
                        if index == 155: sprite = "Swap_Herbs"
                        if index == 156: sprite = "Swap_Strength_Tonic"
                        if index == 157: sprite = "Swap_Strength_Elixir"
                        if index == 158: sprite = "Swap_Magic_Elixir"
                        if index == 159: sprite = "Swap_Wonder_Essence"
                        if index == 160: sprite = "Swap_Earth_Scroll"
                        if index == 161: sprite = "Swap_Water_Scroll"
                        if index == 162: sprite = "Swap_Fire_Scroll"
                        if index == 163: sprite = "Swap_Wind_Scroll"
                        if index == 164: sprite = "Swap_Earth_Book"
                        if index == 165: sprite = "Swap_Water_Book"
                        if index == 166: sprite = "Swap_Fire_Book"
                        if index == 167: sprite = "Swap_Wind_Book"
                        if index == 168: sprite = "Swap_Sand_Cape"
                        if index == 169: sprite = "Swap_Aqua_Cape"
                        if index == 170: sprite = "Swap_Navas_Charm"
                        if index == 171: sprite = "Swap_Power_Glove"
                        if index == 172: sprite = "Swap_Spring_Bean"
                        if index == 173: sprite = "Swap_Olgas_Ring"
                        if index == 174: sprite = "Swap_Oaks_Ring"
                        if index == 175: sprite = "Swap_Silver_Armlet"
                        if index == 176: sprite = "Swap_Recovery_Ring"
                        if index == 177: sprite = "Swap_Refresher"
                        if index == 178: sprite = "Swap_Mining_Bomb"
                        if index == 179: sprite = "Lock_Weapon"
                        if index == 180: sprite = "Lock_Item"
                        if index == 181: sprite = "Regen"
                        if index == 182: sprite = "Poison"
                        if index > 182: sprite = "Check_Points"
                        if index == 184: sprite = "Swap_Herbs"
                        if index == 185: sprite = "Swap_Strength_Tonic"
                        if index == 186: sprite = "Swap_Strength_Elixir"
                        if index == 187: sprite = "Swap_Magic_Elixir"
                        if index == 188: sprite = "Swap_Wonder_Essence"
                        if index == 189: sprite = "Swap_Earth_Scroll"
                        if index == 190: sprite = "Swap_Water_Scroll"
                        if index == 191: sprite = "Swap_Fire_Scroll"
                        if index == 192: sprite = "Swap_Wind_Scroll"
                        if index == 193: sprite = "Swap_Earth_Book"
                        if index == 194: sprite = "Swap_Water_Book"
                        if index == 195: sprite = "Swap_Fire_Book"
                        if index == 196: sprite = "Swap_Wind_Book"
                        if index == 197: sprite = "Swap_Sand_Cape"
                        if index == 198: sprite = "Swap_Aqua_Cape"
                        if index == 199: sprite = "Swap_Navas_Charm"
                        if index == 200: sprite = "Swap_Power_Glove"
                        if index == 201: sprite = "Swap_Spring_Bean"
                        if index == 202: sprite = "Swap_Olgas_Ring"
                        if index == 203: sprite = "Swap_Oaks_Ring"
                        if index == 204: sprite = "Swap_Silver_Armlet"
                        if index == 205: sprite = "Swap_Recovery_Ring"
                        if index == 206: sprite = "Swap_Refresher"
                        if index == 207: sprite = "Swap_Mining_Bomb"
                        if index == 208: sprite = "Spawn_Enemy"
                        if index == 209: sprite = "Spawn_Puku"
                        if index == 210: sprite = "Spawn_Slime"
                        if index == 211: sprite = "Spawn_Wasp"
                        if index == 212: sprite = "Spawn_Killer"
                        if index == 213: sprite = "Spawn_Roach"
                        if index == 214: sprite = "Spawn_Murgg"
                        if index == 215: sprite = "Spawn_Gragg"
                        if index == 216: sprite = "Spawn_Sand_Worm"
                        if index == 217: sprite = "Spawn_Sludge"
                        if index == 218: sprite = "Spawn_Miming"
                        if index == 219: sprite = "Spawn_Reaper"
                        if index == 220: sprite = "Spawn_Shadow"
                        if index == 221: sprite = "Spawn_Lizardman"
                        if index == 222: sprite = "Spawn_Zombie"
                        if index == 223: sprite = "Spawn_Turtle"
                        if index == 224: sprite = "Spawn_Mimic"
                        if index == 225: sprite = "Spawn_Mud_Man"
                        if index == 226: sprite = "Spawn_Mushroom"
                        if index == 227: sprite = "Spawn_Mummy"
                        if index == 228: sprite = "Spawn_Red_Turtle"
                        if index == 229: sprite = "Spawn_Rock_Face"
                        if index == 230: sprite = "Spawn_Treant"
                        if index == 231: sprite = "Spawn_Firebird"
                        if index == 232: sprite = "Spawn_Shrine_Mummy"
                        if index == 233: sprite = "Spawn_Roper"
                        if index == 234: sprite = "Spawn_Shrine_Demon"
                        if index == 235: sprite = "Spawn_Buffed_Enemy"
                        if index == 236: sprite = "Spawn_Buffed_Puku"
                        if index == 237: sprite = "Spawn_Buffed_Slime"
                        if index == 238: sprite = "Spawn_Buffed_Wasp"
                        if index == 239: sprite = "Spawn_Buffed_Killer"
                        if index == 240: sprite = "Spawn_Buffed_Roach"
                        if index == 241: sprite = "Spawn_Buffed_Murgg"
                        if index == 242: sprite = "Spawn_Buffed_Gragg"
                        if index == 243: sprite = "Spawn_Buffed_Sand_Worm"
                        if index == 244: sprite = "Spawn_Buffed_Sludge"
                        if index == 245: sprite = "Spawn_Buffed_Miming"
                        if index == 246: sprite = "Spawn_Buffed_Reaper"
                        if index == 247: sprite = "Spawn_Buffed_Shadow"
                        if index == 248: sprite = "Spawn_Buffed_Lizardman"
                        if index == 249: sprite = "Spawn_Buffed_Zombie"
                        if index == 250: sprite = "Spawn_Buffed_Turtle"
                        if index == 251: sprite = "Spawn_Buffed_Mimic"
                        if index == 252: sprite = "Spawn_Buffed_Mud_Man"
                        if index == 253: sprite = "Spawn_Buffed_Mushroom"
                        if index == 254: sprite = "Spawn_Buffed_Mummy"
                        if index == 255: sprite = "Spawn_Buffed_Red_Turtle"
                        if index == 256: sprite = "Spawn_Buffed_Rock_Face"
                        if index == 257: sprite = "Spawn_Buffed_Treant"
                        if index == 258: sprite = "Spawn_Buffed_Firebird"
                        if index == 259: sprite = "Spawn_Buffed_Shrine_Mummy"
                        if index == 260: sprite = "Spawn_Buffed_Roper"
                        if index == 261: sprite = "Spawn_Buffed_Shrine_Demon"

                        # For gui display message, displays message before redeem name, eg. Heal HP, Give Herbs

                        if sprite == "HP": sprite += "\nHeal"
                        elif sprite == "HP-": sprite += "\nLose"
                        elif sprite == "MP": sprite += "\nGive"
                        elif sprite == "MP-": sprite += "\nLose"
                        else: sprite += "\n"
                        if index in range(184, 208): sprite += "Force"

                        if index not in range(0, 4) and index < 182:
                            if "HP" not in sprite and "MP" not in sprite:
                                if "-" in sprite: sprite += "Take"
                                if "Swap" in sprite: sprite += "Swap to"
                                if "Swap" not in sprite and "-" not in sprite and "Force" not in sprite and "Lock" not in sprite: sprite += "Give"

                    if remove_cmd == False:
                        user_points[username] -= command_cost  # Deduct points
                        
                        if show_username: file.write(f" ({username})")

                        print(f"{username} used: {org_msg} [cost: {command_cost}] [points left: {user_points[username]}]")

                        # Write the message and points to the user's file
                        user_file = os.path.join(user_files_directory, f"{username}_points.txt")

                        with open(user_file, "w") as file:
                            file.write(f"Points: {user_points[username]}\n")
                            file.write(f"Last Command: {org_msg}\n")
                            file.write(f"{sprite}\n")
                            file.write(f"{command_cost}")
                    else:
                        print(f"{username} used: {msg} Restricted Command")

                        # Write the message and points to the user's file
                        user_file = os.path.join(user_files_directory, f"{username}_points.txt")
                        with open(user_file, "w") as file:
                            file.write(f"Points: {user_points[username]}\n")
                            file.write(f"Last Command: Locked command\nLocked Command")
                    remove_cmd = False
            else:
                # Notify user of insufficient points
                print(f"{username} does not have enough points for {org_msg}")
                user_file = os.path.join(user_files_directory, f"{username}_points.txt")
                with open(user_file, "w") as file:
                    file.write(f"Points: {user_points[username]}\n")
                    file.write(f"Last Command: not enough {POINTS_NAME}\n")
        else:
            user_file = os.path.join(user_files_directory, f" {username}_points.txt")
            if(msg == f"{cmd}{give}{POINTS_NAME}"):
                with open(user_file, "w") as file:
                    file.write(f"Points: {user_points[username]}\n")
                    file.write(f"Last Command: {org_msg}\n")
                    file.write(f"Give {POINTS_NAME}\n")
            if(msg == f"{cmd}{take}{POINTS_NAME}"):
                with open(user_file, "w") as file:
                    file.write(f"Points: {user_points[username]}\n")
                    file.write(f"Last Command: {org_msg}\n")
                    file.write(f"Take {POINTS_NAME}\n")

    except Exception as e:
        print(f"Encountered exception: {str(e)}")
        raise


while True:
    active_tasks = [t for t in active_tasks if not t.done()]

    # Check for new messages
    new_messages = t.twitch_receive_messages()
    if new_messages:
        message_queue += new_messages  # New messages are added to the back of the queue
        message_queue = message_queue[-MAX_QUEUE_LENGTH:]  # Shorten the queue to only the most recent X messages

    messages_to_handle = []
    if not message_queue:
        # No messages in the queue
        last_time = time.time()
    else:
        # Determine how many messages we should handle now
        r = 1 if MESSAGE_RATE == 0 else (time.time() - last_time) / MESSAGE_RATE
        n = int(r * len(message_queue))
        if n > 0:
            # Pop the messages we want off the front of the queue
            messages_to_handle = message_queue[0:n]
            del message_queue[0:n]
            last_time = time.time()

    if not messages_to_handle:
        continue
    else:
        for message in messages_to_handle:
            if len(active_tasks) <= MAX_WORKERS:
                active_tasks.append(thread_pool.submit(handle_message, message))
            else:
                print(f'WARNING: active tasks ({len(active_tasks)}) exceeds number of workers ({MAX_WORKERS}). ({len(message_queue)} messages in the queue)')
