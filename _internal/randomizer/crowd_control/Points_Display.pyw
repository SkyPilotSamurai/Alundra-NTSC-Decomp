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

                point_command = False
                locked_command = False
                not_enough_points = False

                if "Not enough" in last_command_line:
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

def load_image(image_filename):
    if not image_filename:
        return None

    if not image_filename.lower().endswith(".png"):
        image_filename = f"{image_filename}.png"
        
    image_file = os.path.join(item_sprites_directory, image_filename)

    if image_filename == "Locked Command.png":
        image_file = os.path.join(item_sprites_directory, "locked.png")
    if point_command:
        image_file = os.path.join(item_sprites_directory, "points.png")

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

# GUI Update

def update_display(tree, image_label, username_label, filename_label):
    last_files = get_last_edited_files()
    tree.delete(*tree.get_children())

    for username, points, last_command, _, _ in last_files:
        tree.insert("", "end", values=(username, points, last_command))

    if last_files:
        username, _, _, image_filename, combined_text = last_files[0]
        cap_username = username.capitalize()

        username_label.config(text=f"{cap_username} Redeemed:")
        filename_label.config(text=combined_text)

        if locked_command or not_enough_points: 
            username_label.config(text=f"{cap_username} Cannot Redeem:")
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

def create_gui():
    root = tk.Tk()
    root.title("User Points Display")
    root.geometry(f"{size_x}x{size_y}")
    root.resizable(False, False)
    root.configure(bg=bg_color)

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

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background=table_bg_color, foreground="white", fieldbackground=table_bg_color, rowheight=25, font=("Helvetica", table_item_font_size), borderwidth=0)
    style.configure("Treeview.Heading", background=table_title_color, foreground="lightgray", font=("Helvetica", table_title_font_size, "bold"), borderwidth=0)
    
    # Change the hover effect for the treeview headers
    style.map("Treeview.Heading", background=[("active", "#111111")], foreground=[("active", "lightgray")])
    
    # Change selected row background and text color
    style.map("Treeview", background=[("selected", "#111111")], foreground=[("selected", "white")])

    update_display(tree, image_label, username_label, filename_label)

    root.mainloop()

if __name__ == "__main__":
    create_gui()