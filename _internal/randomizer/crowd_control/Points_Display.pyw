import ast
import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk # type: ignore

def get_base_path():
    if getattr(sys, 'frozen', False):  # Check if running as a PyInstaller executable
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

# Directory for user files and item sprites
script_directory = os.path.dirname(os.path.abspath(__file__))
user_files_directory = os.path.join(script_directory, 'user_points')
item_sprites_directory = os.path.join(script_directory, 'item_sprites')
lua_file_name = 'Alundra_CC_Bizhawk.lua'
lua_script_path = os.path.join(script_directory, lua_file_name)
bot_script_path = os.path.join(script_directory, 'Alundra_Crowd_Control.py')

# Ensure the Lua file exists
if not os.path.exists(lua_script_path):
    raise FileNotFoundError(f"Lua file not found at: {lua_script_path}")

# Variables in lua script to pull in
invincibility_length, no_iframes_length, no_jump_length, slow_motion_length, swap_length, poison_length, regen_length = 0, 0, 0, 0, 0, 0, 0   

# Color configuration
def color(color_name):
    colors = {
        "Grey": "#333300", "Red": "#330000", "Blue": "#000033",
        "Green": "#003300", "Purple": "#330033", "Turq": "#003330",
        "Yellow": "#666000", "Orange": "#332000", "Default": "#002033"
    }
    return colors.get(color_name, "Color not found")

bg_color = color("Default")
table_bg_color = "#2E2E2E"
table_title_color = "#1F1F1F"

table_item_font_size = 13
table_title_font_size = 11
redeem_font_size = 12

size_x = 400
size_y = 300

# Font: the game's own (Alundra.ttf, made from the game's menu font) or Helvetica; Font menu, kept in display_settings.json
ALUNDRA_FONT = os.path.join(script_directory, 'Alundra.ttf')
display_settings_path = os.path.join(script_directory, 'display_settings.json')

def load_display_settings():
    try:
        with open(display_settings_path, "r") as file: return dict(json.load(file))
    except Exception: return {}

display_settings = load_display_settings()
alundra_font_loaded = False

def register_alundra_font():
    """Alundra.ttf for this program only (Windows: AddFontResourceEx, FR_PRIVATE)."""
    global alundra_font_loaded
    try:
        if os.name == "nt" and os.path.exists(ALUNDRA_FONT):
            import ctypes
            alundra_font_loaded = ctypes.windll.gdi32.AddFontResourceExW(ALUNDRA_FONT, 0x10, 0) > 0
    except Exception: alundra_font_loaded = False

def use_alundra_font():
    return alundra_font_loaded and display_settings.get("alundra_font", True)

def ui_font(size, bold=False):
    """A font for the display's texts: the Alundra font at its own pixel size, else Helvetica."""
    if use_alundra_font(): return ("Alundra", -16)
    return ("Helvetica", size, "bold") if bold else ("Helvetica", size)

# Other variables for functionality
point_command = False
locked_command = False
not_enough_points = False

def extract_lua_variables(lua_file):
    try:
        with open(lua_file, 'r') as file:
            lua_code = file.read()
    except Exception as e:
        raise Exception(f"Error reading Lua file: {e}")

    pattern = r"local\s+(\w+)\s*=\s*(\d+)"
    matches = re.findall(pattern, lua_code)

    if not matches:
        raise ValueError("No valid variables found in Lua script.")

    return {var_name: int(value) for var_name, value in matches}

try:
    lua_variables = extract_lua_variables(lua_script_path)
    for var_name in lua_variables:
        if var_name in globals():
            globals()[var_name] = lua_variables[var_name]
except Exception as e:
    print(f"Failed to extract or assign Lua variables: {e}")

# File handling

def get_last_edited_files():
    files = []
    for filename in os.listdir(user_files_directory):
        if filename.endswith("_points.txt"):
            file_path = os.path.join(user_files_directory, filename)
            last_modified = os.path.getmtime(file_path)
            files.append((filename, file_path, last_modified))

    files = sorted(files, key=lambda x: x[2], reverse=True)[:8]

    file_data = []
    for filename, file_path, _ in files:
        username = filename.replace("_points.txt", "")
        with open(file_path, "r") as file:
            try:
                lines = file.readlines()
                last_command_line = lines[1].strip().replace("Last Command: ", "").capitalize()
                command_name = lines[2].strip() if len(lines) >= 3 else ""
                command_prefix = lines[3].strip() if len(lines) >= 4 else ""
                command_cost = lines[4].strip() if len(lines) >= 5 else ""

                combined_text = " ".join(filter(None, [command_prefix, command_name.replace("Swap_", "")])).replace("_", " ").replace("-", "")

                if "Invincibility" in command_name:
                    combined_text += f" [{invincibility_length // 60} Seconds]"
                if "Slow" in command_name:
                    combined_text += f" [{slow_motion_length // 60} Seconds]"
                if "Frames" in command_name:
                    combined_text += f" [{no_iframes_length // 60} Seconds]"
                if "Jump" in command_name:
                    combined_text += f" [{no_jump_length // 60} Seconds]"
                if "Force" in command_name or command_prefix == "Force":
                    combined_text += f" [{swap_length // 60} Seconds]"
                if "Posion" in command_name:
                    combined_text += f" [{poison_length // 60} Seconds]"
                if "Regen" in command_name:
                    combined_text += f" [{regen_length // 60} Seconds]"

                global point_command
                global locked_command
                global not_enough_points
                global spawn_cooldown

                point_command = False
                locked_command = False
                not_enough_points = False
                spawn_cooldown = False

                if last_command_line.startswith("Cannot spawn cooldown"):
                    combined_text = "Cooldown " + last_command_line[len("Cannot spawn cooldown "):]
                    spawn_cooldown = True
                elif "Not enough" in last_command_line:
                    combined_text = last_command_line
                    not_enough_points = True
                elif "Locked command" in last_command_line:
                    combined_text = command_name
                    locked_command = True
                elif "#" in command_name: 
                    combined_text = command_name.replace("#", "")
                    point_command = True
                else:
                    combined_text += f" ({command_cost})"

                points_line = next(line for line in lines if line.startswith("Points:"))
                points = int(points_line.split(":")[1].strip())

                commands = [line.split(":", 1)[1].strip() for line in lines if line.startswith("Last Command:")]
                last_command = commands[-1] if commands else "No commands yet"

                file_data.append((username, points, last_command, command_name, combined_text))
            except Exception as e:
                print(f"Error reading file {filename}: {e}")

    return file_data

# Image loading

point_command = locked_command = not_enough_points = spawn_cooldown = False

# The bot's sprite names whose picture has another name; a buffed spawn shows its enemy
SPRITE_NAMES = {"Ancient_Armor": "Ancient_Armour", "Broken_Armor": "Broken_Armour", "Leather_Armor": "Leather_Armour",
                "Silver_Armor": "Silver_Armour", "Hunters_Bow": "Hunter's_Bow", "Jess's_Letter": "Jess'_Letter",
                "Zolist_Stone": "Zolist's_Stone", "Swap_Flail": "Swap_Iron_Flail", "Spawn_Enemy": "Placeholder"}

def sprite_file(image_filename):
    """The picture for a sprite name (any case; SPRITE_NAMES; Spawn_Buffed_X as Spawn_X), else Placeholder.png."""
    try: files = {f.lower(): f for f in os.listdir(item_sprites_directory)}
    except OSError: files = {}
    stem = image_filename[:-4]
    base = stem.rstrip("-"); minus = stem[len(base):]
    base = SPRITE_NAMES.get(base, base).replace("Spawn_Buffed_", "Spawn_")
    for name in (stem + ".png", base + minus + ".png", base + ".png", "Placeholder.png"):
        if name.lower() in files: return os.path.join(item_sprites_directory, files[name.lower()])
    return os.path.join(item_sprites_directory, "Placeholder.png")

def load_image(image_filename):
    if not image_filename:
        return None

    if not image_filename.lower().endswith(".png"):
        image_filename = f"{image_filename}.png"
        
    if image_filename == "Locked Command.png":
        image_filename = "Locked.png"
    if point_command:
        image_filename = "Points.png"
    image_file = sprite_file(image_filename)

    try:
        if os.path.exists(image_file):
            image = Image.open(image_file)
            original_width, original_height = image.size

            if original_width > original_height:
                new_width = 50
                new_height = int((50 / original_width) * original_height)
            else:
                new_height = 50
                new_width = int((50 / original_height) * original_width)

            image = image.resize((new_width, new_height))
            return ImageTk.PhotoImage(image)
        else:
            return None
    except Exception as e:
        print(f"Error loading image {image_filename}: {e}")
        return None

# All user points and the command list (View menu)

def get_all_points():
    rows = []
    if not os.path.isdir(user_files_directory):
        return rows
    for filename in os.listdir(user_files_directory):
        if filename.endswith("_points.txt"):
            try:
                with open(os.path.join(user_files_directory, filename), "r") as file:
                    points_line = next(line for line in file if line.startswith("Points:"))
                rows.append((filename.replace("_points.txt", "").strip(), int(points_line.split(":")[1].strip())))
            except Exception as e:
                print(f"Error reading file {filename}: {e}")
    return sorted(rows, key=lambda row: (-row[1], row[0]))

def get_commands():
    """The bot's commands as (section, [(names, cost)]), without the ones its settings turn off."""
    with open(bot_script_path, "r", encoding="utf-8") as file:
        source = file.read().replace("\r\n", "\n")
    settings = {}
    for name, value in re.findall(r"(?m)^(\w+) = ([^\n#]+?)\s*(?:#.*)?$", source.split("\ncommands = {", 1)[0]):
        try:
            settings[name] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass
    words = dict(settings, cmd=settings.get("cmd", "!"), give="give ", take="take ", swap="swap ", force="force ", lock="lock ")
    removed = set()
    for flag, block in re.findall(r"(?m)^ *if (\w+) == False:\n((?: +(?:if index|remove_cmd|file\.seek)[^\n]*\n)+)", source):
        if settings.get(flag, True) is False:
            for a, b in re.findall(r"index in range\((\d+), (\d+)\)", block):
                removed.update(range(int(a), int(b)))
            removed.update(int(n) for n in re.findall(r"index == (\d+)", block))
    body = source.split("\ncommands = {", 1)[1].split("\n}", 1)[0]
    sections, index, seen = [], 0, {}
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            sections.append((line.lstrip("# ").replace("{give}", "").split(" - ")[0].split(":")[0].strip(), []))
            continue
        found = re.match(r'f?"([^"]*)"\s*:\s*(\d+)', line)
        if not found:
            continue
        if found.group(1) in seen:   # (a repeated key: the bot's dict keeps the first one, with this cost)
            row = seen[found.group(1)]
            if row is not None:
                row[1] = int(found.group(2))
            continue
        seen[found.group(1)] = None
        if index not in removed:
            names = [name.format(**words) for name in found.group(1).split()]
            if sections and "Spawn" in sections[-1][0]:   # (!spawn slime: the bot ignores the space)
                names = [re.sub(r"^(\W*(?:spawnbuff|spnbuff|buffspawn|buffspn|spawn|spn|buff))(.*)$", lambda m: f"{m.group(1)} {m.group(2)}" if m.group(2) else m.group(1), name) for name in names]
            if not sections:
                sections.append(("Commands", []))
            seen[found.group(1)] = [names, int(found.group(2))]
            sections[-1][1].append(seen[found.group(1)])
        index += 1
    for title, rows in sections:   # (a random spawn costs what the enemy it picks costs)
        if "Spawn" in title and len(rows) > 1 and rows[0][0][0].endswith(("spawn", "spawnbuff")):
            costs = [row[1] for row in rows[1:]]
            rows[0][1] = f"{min(costs)}-{max(costs)}"
    return [(title, rows) for title, rows in sections if rows]

def open_all_points(root):
    window = getattr(root, "all_points_window", None)
    if window is not None and window.winfo_exists():
        window.lift()
        return
    window = root.all_points_window = tk.Toplevel(root)
    window.title("All User Points")
    window.geometry("320x420")
    window.configure(bg=bg_color)
    tree = ttk.Treeview(window, columns=("Username", "Gilder"), show="headings")
    tree.heading("Username", text="Username")
    tree.heading("Gilder", text="Gilder")
    tree.column("Username", anchor="center", width=170)
    tree.column("Gilder", anchor="center", width=100)
    bar = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y", pady=10)
    tree.pack(fill="both", expand=True, padx=(10, 0), pady=10)

    def refresh():
        if not tree.winfo_exists():
            return
        rows = get_all_points()
        if [tuple(tree.item(item, "values")) for item in tree.get_children()] != [(name, str(points)) for name, points in rows]:
            tree.delete(*tree.get_children())
            for name, points in rows:
                tree.insert("", "end", values=(name, points))
        tree.after(1000, refresh)
    refresh()

def open_commands(root):
    window = getattr(root, "commands_window", None)
    if window is not None and window.winfo_exists():
        window.lift()
        return
    window = root.commands_window = tk.Toplevel(root)
    window.title("Commands")
    window.geometry("640x520")
    window.configure(bg=bg_color)
    tree = ttk.Treeview(window, columns=("Command", "Cost", "Also"), show="headings")
    tree.heading("Command", text="Command")
    tree.heading("Cost", text="Gilder")
    tree.heading("Also", text="Also")
    tree.column("Command", anchor="w", width=200)
    tree.column("Cost", anchor="center", width=60)
    tree.column("Also", anchor="w", width=340)
    bar = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y", pady=10)
    tree.pack(fill="both", expand=True, padx=(10, 0), pady=10)
    tree.tag_configure("section", background=table_title_color, foreground="lightgray")
    try:
        sections = get_commands()
    except Exception as e:
        sections = []
        tree.insert("", "end", values=(f"Cannot read the commands: {e}", "", ""), tags=("section",))
    for title, rows in sections:
        tree.insert("", "end", values=(title, "", ""), tags=("section",))
        for names, cost in rows:
            tree.insert("", "end", values=(names[0], cost, ", ".join(names[1:])))

# GUI Update

def fit_command_column(tree, texts):
    """The Command column as wide as its longest text (at least 120), the window widened to show it whole."""
    import tkinter.font as tkfont
    font = tkfont.Font(font=ui_font(table_item_font_size))
    width = max([120] + [font.measure(str(t)) + 16 for t in texts])
    if tree.column("Command", "width") != width: tree.column("Command", width=width)
    root = tree.winfo_toplevel(); need = 100 + 70 + width + 24
    if root.winfo_width() > 1 and root.winfo_width() < need: root.geometry(f"{need}x{root.winfo_height()}")

def update_display(tree, image_label, username_label, filename_label):
    last_files = get_last_edited_files()
    tree.delete(*tree.get_children())

    shown = []
    for username, points, last_command, _, _ in last_files:
        if last_command.lower().startswith("cannot spawn cooldown"): last_command = "Cooldown" + last_command[len("cannot spawn cooldown"):]
        tree.insert("", "end", values=(username, points, last_command))
        shown.append(last_command)
    fit_command_column(tree, shown)

    if last_files:
        username, _, _, image_filename, combined_text = last_files[0]
        cap_username = username.capitalize()

        username_label.config(text=f"{cap_username} Redeemed:")
        filename_label.config(text=combined_text)

        if locked_command or not_enough_points: 
            username_label.config(text=f"{cap_username} Cannot Redeem:")
            filename_label.config(text=combined_text)
        if last_files[0][2].lower().startswith("cannot spawn cooldown"):   # (the newest one's own line)
            username_label.config(text=f"{cap_username} Cannot Spawn:")
            filename_label.config(text=combined_text)
        
        image = load_image(image_filename)

        if image:
            image_label.config(image=image)
            image_label.image = image
        else:
            image_label.config(image='')
    else:
        username_label.config(text='')
        filename_label.config(text='')
        image_label.config(image='')

    tree.after(1000, update_display, tree, image_label, username_label, filename_label)

def apply_fonts(root, labels):
    """Every window's texts in the chosen font."""
    style = ttk.Style(root)
    style.configure("Treeview", font=ui_font(table_item_font_size))
    style.configure("Treeview.Heading", font=ui_font(table_title_font_size, True))
    labels[0].config(font=ui_font(redeem_font_size, True)); labels[1].config(font=ui_font(redeem_font_size))

def set_alundra_font(root, labels, on):
    display_settings["alundra_font"] = bool(on)
    try:
        with open(display_settings_path, "w") as file: json.dump(display_settings, file)
    except Exception as e: print(f"Error saving display settings: {e}")
    apply_fonts(root, labels)

def create_gui():
    register_alundra_font()
    root = tk.Tk()
    root.title("Crowd Control Display")
    root.geometry(f"{size_x}x{size_y}")
    root.resizable(False, False)
    root.configure(bg=bg_color)

    menu_bar = tk.Menu(root)
    view_menu = tk.Menu(menu_bar, tearoff=0)
    view_menu.add_command(label="All User Points", command=lambda: open_all_points(root))
    view_menu.add_command(label="Commands", command=lambda: open_commands(root))
    menu_bar.add_cascade(label="View", menu=view_menu)
    font_menu = tk.Menu(menu_bar, tearoff=0)
    font_choice = tk.BooleanVar(root, value=display_settings.get("alundra_font", True))
    labels = []
    font_menu.add_radiobutton(label="Alundra font", variable=font_choice, value=True, command=lambda: set_alundra_font(root, labels, True),
                              state="normal" if alundra_font_loaded else "disabled")
    font_menu.add_radiobutton(label="Normal font", variable=font_choice, value=False, command=lambda: set_alundra_font(root, labels, False))
    menu_bar.add_cascade(label="Font", menu=font_menu)
    root.config(menu=menu_bar)

    tree = ttk.Treeview(root, columns=("Username", "Gilder", "Command"), show="headings", height=5)
    tree.heading("Username", text="Username")
    tree.heading("Gilder", text="Gilder")
    tree.heading("Command", text="Command")
    tree.column("Username", anchor="center", width=100)
    tree.column("Gilder", anchor="center", width=70)
    tree.column("Command", anchor="center", width=120)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    image_label_frame = tk.Frame(root, bg=bg_color)
    image_label_frame.pack(pady=(10, 20))

    image_label = tk.Label(image_label_frame, bg=bg_color)
    image_label.pack(side="left", padx=10)

    text_label_frame = tk.Frame(image_label_frame, bg=bg_color)
    text_label_frame.pack(side="left", fill="y")

    username_label = tk.Label(text_label_frame, text="", bg=bg_color, fg="white", font=("Helvetica", redeem_font_size, "bold"))
    username_label.pack(anchor="w", pady=(0, 5))

    filename_label = tk.Label(text_label_frame, text="", bg=bg_color, fg="white", font=("Helvetica", redeem_font_size))
    filename_label.pack(anchor="w")
    labels += [username_label, filename_label]

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background=table_bg_color, foreground="white", fieldbackground=table_bg_color, rowheight=25, font=("Helvetica", table_item_font_size), borderwidth=0)
    style.configure("Treeview.Heading", background=table_title_color, foreground="lightgray", font=("Helvetica", table_title_font_size, "bold"), borderwidth=0)
    
    # Change the hover effect for the treeview headers
    style.map("Treeview.Heading", background=[("active", "#111111")], foreground=[("active", "lightgray")])
    
    # Change selected row background and text color
    style.map("Treeview", background=[("selected", "#111111")], foreground=[("selected", "white")])
    apply_fonts(root, labels)

    update_display(tree, image_label, username_label, filename_label)

    root.mainloop()

if __name__ == "__main__":
    create_gui()