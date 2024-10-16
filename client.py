import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from ttkbootstrap import Style
import socketio
import json
import os
import random
from datetime import datetime

with open("userinfo.json", "r") as file:
    user_info = json.load(file)

username = user_info["username"]
email = user_info["email"]
secret_key = user_info["secret_key"]

server_url = "http://127.0.0.1:5000"
sio = socketio.Client()

current_room = None
last_message_id = -1

if not os.path.exists("messages"):
    os.makedirs("messages")

def save_message_to_file(room_name, message):
    with open(f"messages/{room_name}.txt", "a") as file:
        file.write(f"{message}\n")

def read_messages_from_file(room_name):
    if os.path.exists(f"messages/{room_name}.txt"):
        with open(f"messages/{room_name}.txt", "r") as file:
            return file.readlines()
    return []

def generate_user_color(username):
    random.seed(username)
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def send_chat_message():
    global current_room
    message = chat_message_entry.get()
    if current_room and message:
        timestamp = datetime.now().strftime("%H:%M")
        date = datetime.now().strftime("%Y-%m-%d")
        sio.emit("send_message", {"username": username, "room_name": current_room, "message": message, "timestamp": timestamp, "date": date})
        chat_message_entry.delete(0, tk.END)
    elif message:
        messagebox.showerror("Error", "Select a room first.")

def load_rooms():
    for widget in rooms_canvas_frame.winfo_children():
        widget.destroy()
    sio.emit("get_rooms")

def select_room(room_name):
    global current_room, last_message_id
    if current_room == room_name:
        return
    current_room = room_name
    last_message_id = -1
    room_label.config(text=f"Current Room: {room_name}")
    sio.emit("join_room_route", {"username": username, "room_name": room_name})
    load_chat_history_from_file(room_name)
    check_for_new_messages()

def leave_room():
    global current_room, last_message_id
    if current_room:
        sio.emit("leave_room_route", {"username": username, "room_name": current_room})
        chat_text.config(state=tk.NORMAL)
        chat_text.insert(tk.END, f"User: {username} left room {current_room} successfully.\n", "system_message")
        chat_text.tag_config("system_message", foreground="red")
        current_room = None
        last_message_id = -1
        room_label.config(text="Select a room or talk to yourself")
        chat_text.config(state=tk.DISABLED)
        user_list.delete(0, tk.END)

def load_users_in_room(room_name):
    sio.emit("get_users_in_room_route", {"room_name": room_name})

def load_chat_history_from_file(room_name):
    global last_message_id
    chat_text.config(state=tk.NORMAL)
    chat_text.delete(1.0, tk.END)
    chat_text.insert(tk.END, f"Current User: {username}\n", "current_user")
    chat_text.tag_config("current_user", foreground="cyan")
    messages = read_messages_from_file(room_name)
    last_date = None
    for message in messages:
        try:
            date, timestamp, username_in_msg, msg_text = message.split(" | ", 3)
        except ValueError:
            continue  # Skip improperly formatted messages
        if last_date != date:
            if last_date is not None:
                chat_text.insert(tk.END, "\n")
            chat_text.insert(tk.END, f"----- {datetime.strptime(date, '%Y-%m-%d').strftime('%d %B')} -----\n", "date_separator")
            chat_text.tag_config("date_separator", foreground="green")
            last_date = date
        user_color = generate_user_color(username_in_msg.strip())
        formatted_message = f"[{timestamp}] {username_in_msg.strip()}: {msg_text.strip()}"
        chat_text.insert(tk.END, f"{formatted_message}\n", ("username",))
        chat_text.tag_config("username", foreground=user_color)
    last_message_id = -1
    chat_text.config(state=tk.DISABLED)
    chat_text.see(tk.END)

def check_for_new_messages():
    global last_message_id
    if current_room:
        sio.emit("get_new_messages", {"room_name": current_room, "last_message_id": last_message_id})
        root.after(1700, check_for_new_messages)

def refresh_user_list():
    if current_room:
        load_users_in_room(current_room)
    root.after(2000, refresh_user_list)

def create_new_room():
    new_room_name = simpledialog.askstring("Create New Room", "Enter the name for the new room:")
    if new_room_name:
        sio.emit("create_room", {"username": username, "room_name": new_room_name})

def on_connect():
    load_rooms()

def on_room_list(rooms):
    for room in rooms:
        room_button = tk.Button(
            rooms_canvas_frame,
            text=room,
            command=lambda r=room: select_room(r),
            bg="blue",
            fg="white",
        )
        room_button.pack(fill=tk.X, pady=2)

def on_room_created(data):
    load_rooms()

def on_joined_room(data):
    load_users_in_room(current_room)

def on_left_room(data):
    leave_room()

def on_room_users(users):
    user_list.delete(0, tk.END)
    for user in users:
        user_list.insert(tk.END, user)

def on_new_messages(new_messages):
    global last_message_id
    if new_messages:
        chat_text.config(state=tk.NORMAL)
        last_date = None
        for msg in new_messages:
            date = msg.get('date', datetime.now().strftime('%Y-%m-%d'))
            if last_date != date:
                if last_date is not None:
                    chat_text.insert(tk.END, "\n")
                chat_text.insert(tk.END, f"----- {datetime.strptime(date, '%Y-%m-%d').strftime('%d %B')} -----\n", "date_separator")
                chat_text.tag_config("date_separator", foreground="green")
                last_date = date
            formatted_message = f"[{msg['timestamp']}] {msg['username']}: {msg['message']}"
            save_message_to_file(current_room, f"{date} | {msg['timestamp']} | {msg['username']} | {msg['message']}")
            user_color = generate_user_color(msg["username"])
            chat_text.insert(tk.END, f"{formatted_message}\n", ("username",))
            chat_text.tag_config("username", foreground=user_color)
            last_message_id = msg["id"]
        chat_text.config(state=tk.DISABLED)
        chat_text.see(tk.END)

sio.on("connect", on_connect)
sio.on("room_list", on_room_list)
sio.on("room_created", on_room_created)
sio.on("joined_room", on_joined_room)
sio.on("left_room", on_left_room)
sio.on("room_users", on_room_users)
sio.on("new_messages", on_new_messages)

root = tk.Tk()
root.title("Chat App")

style = Style(theme="cyborg")

main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

left_frame = tk.Frame(main_frame)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

room_label = tk.Label(left_frame, text="Select a room or talk to yourself", bg="black", fg="cyan")
room_label.pack(fill=tk.X)

chat_text = scrolledtext.ScrolledText(left_frame, state=tk.DISABLED, bg="black", fg="white")
chat_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

chat_message_frame = tk.Frame(left_frame)
chat_message_frame.pack(fill=tk.X, padx=10, pady=10)
chat_message_entry = tk.Entry(chat_message_frame, bg="black", fg="white")
chat_message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
send_button = tk.Button(chat_message_frame, text="Send", command=send_chat_message, bg="black", fg="cyan")
send_button.pack(side=tk.RIGHT)

leave_room_button = tk.Button(left_frame, text="Leave Room", command=leave_room, bg="black", fg="red")
leave_room_button.pack(fill=tk.X, padx=10, pady=(5, 10))

right_frame = tk.Frame(main_frame, bg="#222")
right_frame.pack(side=tk.RIGHT, fill=tk.Y)

rooms_label = tk.Label(right_frame, text="Rooms", bg="black", fg="cyan")
rooms_label.pack(fill=tk.X, pady=(10, 5))

rooms_canvas = tk.Canvas(right_frame, bg="#222")
rooms_canvas.pack(side=tk.LEFT, fill=tk.Y, expand=True)
rooms_scrollbar = tk.Scrollbar(right_frame, orient="vertical", command=rooms_canvas.yview)
rooms_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
rooms_canvas_frame = tk.Frame(rooms_canvas, bg="#222")
rooms_canvas.create_window((0, 0), window=rooms_canvas_frame, anchor="nw")
rooms_canvas.config(yscrollcommand=rooms_scrollbar.set)
rooms_canvas.bind("<Configure>", lambda e: rooms_canvas.configure(scrollregion=rooms_canvas.bbox("all")))

users_label = tk.Label(right_frame, text="Users", bg="black", fg="cyan")
users_label.pack(fill=tk.X, pady=(20, 5))
user_list = tk.Listbox(right_frame, bg="#222", fg="white")
user_list.pack(fill=tk.Y, expand=True)

create_room_button = tk.Button(right_frame, text="Create New Room", command=create_new_room, bg="black", fg="cyan")
create_room_button.pack(side=tk.BOTTOM, padx=10, pady=10)

sio.connect(server_url)

refresh_user_list()
check_for_new_messages()

root.mainloop()
