import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import base64
import urllib.parse
from urllib.parse import urlparse, parse_qs
import subprocess
import os
import time
import requests
import socket
import random
import concurrent.futures
from tqdm import tqdm
import threading
import queue
import sys
from datetime import datetime
import platform
if platform.system() == "Windows":
    import winreg
import qrcode
import zipfile
import shutil
import io
from PIL import ImageTk, Image

if sys.platform == 'win32':
    from subprocess import CREATE_NO_WINDOW


def kill_xray_processes():
    """Kill any existing Xray processes (cross-platform)"""
    try:
        if sys.platform == 'win32':
            # Windows implementation
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == 'xray.exe':
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # Linux/macOS implementation
            subprocess.run(['pkill', '-f', 'xray'], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        pass


class VPNConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VPN Config Manager")
        self.root.geometry("600x600+620+20")
        
        # Configure dark theme
        self.setup_dark_theme()
        
        # Kill any existing Xray processes
        self.kill_existing_xray_processes()
        
        self.stop_event = threading.Event()
        self.thread_lock = threading.Lock()
        self.active_threads = []
        self.is_fetching = False
        
        self.XRAY_CORE_URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-windows-64.zip"
        self.GEOIP_URL = "https://github.com/v2fly/geoip/releases/latest/download/geoip.dat"
        self.GEOSITE_URL = "https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat"

        # Configuration - now using a dictionary of mirrors
        self.MIRRORS = {
            "config_proxy": "https://raw.githubusercontent.com/proco2024/channel/main/Telegram%3A%40config_proxy-14040412-006.txt",
            "MRK": "https://raw.githubusercontent.com/mrkkami/MRK/refs/heads/main/MRK-MRK.TXT",
            "barry-far": "https://raw.githubusercontent.com/barry-far/V2ray-Config/refs/heads/main/All_Configs_Sub.txt",
            "SoliSpirit": "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/refs/heads/main/all_configs.txt",
            # "mrvcoder": "https://raw.githubusercontent.com/mrvcoder/V2rayCollector/refs/heads/main/mixed_iran.txt",
            # "MatinGhanbari": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt",
            "Local File (configs.txt)": "local_file", # Added local file option
            "Custom URL": "custom_url", # Added custom URL option
            "Paste Configs": "paste_configs", # Added paste configs option
        }
        self.CONFIGS_URL = self.MIRRORS["barry-far"]  # Default mirror
        self.WORKING_CONFIGS_FILE = "working_configs.txt"
        self.BEST_CONFIGS_FILE = "best_configs.txt"
        self.LOCAL_CONFIGS_FILE = "configs.txt" # New file for local configs
        self.PASTE_CONFIGS_TEMP_FILE = "paste_configs_temp.txt" # New temporary file for pasted configs
        self.TEMP_CONFIG_FILE = "temp_config.json"
        
        self.TEMP_FOLDER = os.path.join(os.getcwd(), "temp")
        self.TEMP_CONFIG_FILE = os.path.join(self.TEMP_FOLDER, "temp_config.json")
        
        self.XRAY_PATH = os.path.join(os.getcwd(), "xray.exe" if sys.platform == 'win32' else "xray")
        
        self.TEST_TIMEOUT = 10
        self.SOCKS_PORT = 1080
        self.PING_TEST_URL = "https://old-queen-f906.mynameissajjad.workers.dev/login" # Updated URL
        self.LATENCY_WORKERS = 100 # Kept original 100 as per freenet5.pyw, freenet6 had 20 but user asked to keep other functions
        
        # Create temp folder if it doesn't exist
        if not os.path.exists(self.TEMP_FOLDER):
            os.makedirs(self.TEMP_FOLDER)
        
        # Variables
        self.best_configs = []
        self.selected_config = None
        self.connected_config = None  # Track the currently connected config
        self.xray_process = None
        self.is_connected = False
        self.log_queue = queue.Queue()
        self.total_configs = 0
        self.tested_configs = 0
        self.working_configs = 0
        
        self.setup_ui()
        self.setup_logging()
        
        # Load best configs if file exists
        if os.path.exists(self.BEST_CONFIGS_FILE):
            self.load_best_configs()
        
    def setup_dark_theme(self):
        """Configure dark theme colors"""
        self.root.tk_setPalette(background='#2d2d2d', foreground='#ffffff',
                              activeBackground='#3e3e3e', activeForeground='#ffffff')

        style = ttk.Style()
        style.theme_use('clam')

        # General widget styling
        style.configure('.', background='#2d2d2d', foreground='#ffffff')
        style.configure('TFrame', background='#2d2d2d')
        style.configure('TLabel', background='#2d2d2d', foreground='#ffffff')
        style.configure('TEntry', fieldbackground='#3e3e3e', foreground='#ffffff')
        style.configure('TScrollbar', background='#3e3e3e')
        
        # Treeview styling
        style.configure('Treeview', 
                       background='#3e3e3e', 
                       foreground='#ffffff', 
                       fieldbackground='#3e3e3e')
        style.configure('Treeview.Heading', 
                       background='#3e3e3e', 
                       foreground='#ffffff')  # Remove button-like appearance
        
        # Remove hover effect on headers
        style.map('Treeview.Heading', 
                  background=[('active', '#3e3e3e')],  # Same as normal background
                  foreground=[('active', '#ffffff')])  # Same as normal foreground
        
        style.map('Treeview', background=[('selected', '#4a6984')])
        style.configure('Vertical.TScrollbar', background='#3e3e3e')
        style.configure('Horizontal.TScrollbar', background='#3e3e3e')
        style.configure('TProgressbar', background='#4a6984', troughcolor='#3e3e3e')

        # Button styling - modified to remove focus highlight
        style.configure('TButton', 
                       background='#3e3e3e', 
                       foreground='#ffffff', 
                       relief='flat',
                       focuscolor='#3e3e3e',  # Same as background
                       focusthickness=0)       # Remove focus thickness
        
        style.map('TButton',
                  background=[('!active', '#3e3e3e'), ('pressed', '#3e3e3e')],
                  foreground=[('disabled', '#888888')])
        
        # Special style for stop button
        style.configure('Stop.TButton', 
                       background='Tomato', 
                       foreground='#ffffff',
                       focuscolor='Tomato',    # Same as background
                       focusthickness=0)      # Remove focus thickness
        
        style.map('Stop.TButton',
                  background=[('!active', 'Tomato'), ('pressed', 'Tomato')],
                  foreground=[('disabled', '#888888')])
        
    def setup_ui(self):
        # --- Top Fixed Frame ---
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, pady=(10, 5), padx=10)

        # Buttons    
        self.fetch_btn = ttk.Button(top_frame, text="Fetch & Test New Configs", command=self.fetch_and_test_configs, cursor='hand2')
        self.fetch_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self.connect_config, state=tk.DISABLED, cursor='hand2')
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.disconnect_btn = ttk.Button(top_frame, text="Disconnect", command=self.click_disconnect_config_button, state=tk.DISABLED, cursor='hand2')
        self.disconnect_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        
        self.reload_btn = ttk.Button(top_frame, text="Reload Best Configs", command=self.reload_and_test_configs, cursor='hand2')
        self.reload_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status label
        self.status_label = ttk.Label(top_frame, text="Disconnected", foreground="Tomato")
        self.status_label.pack(side=tk.RIGHT)
        
        # --- Paned Window ---
        main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashwidth=8, bg="#2d2d2d")
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # --- Middle Treeview Frame ---
        self.middle_frame = ttk.Frame(main_pane)

        columns = ('Index', 'Latency', 'Protocol', 'Server', 'Port' ,'Config')
        self.tree = ttk.Treeview(self.middle_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor='center', minwidth=50)  # Added minwidth parameter

        self.tree.column('Index', width=50, minwidth=50)
        self.tree.column('Latency', width=100, minwidth=100)
        self.tree.column('Protocol', width=80, minwidth=80)
        self.tree.column('Server', width=150, minwidth=150)
        self.tree.column('Port', width=80, minwidth=80)
        self.tree.column('Config', width=400, anchor='w', minwidth=150)

        tree_vscrollbar = ttk.Scrollbar(self.middle_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_vscrollbar.set)
        tree_hscrollbar = ttk.Scrollbar(self.middle_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscrollcommand=tree_hscrollbar.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        tree_vscrollbar.grid(row=0, column=1, sticky='ns')
        tree_hscrollbar.grid(row=1, column=0, sticky='ew')

        self.middle_frame.grid_rowconfigure(0, weight=1)
        self.middle_frame.grid_columnconfigure(0, weight=1)
        
        # Configure tree tags for connected config highlighting
        self.tree.tag_configure('connected', background='#2d5a2d', foreground='#90EE90')
        
        self.tree.bind('<Button-1>', self.on_tree_click)
        
        self.tree.bind("<Button-3>", self.on_right_click)
        
        # Bind double click event
        self.tree.bind('<Double-1>', self.on_config_select)
        
        # Bind Ctrl+V for pasting configs
        self.root.bind('<Control-v>', self.paste_configs)
        
        # Bind Ctrl+C for copying configs
        self.root.bind('<Control-c>', self.copy_selected_configs)
        
        # Bind DEL key for deleting configs
        self.root.bind('<Delete>', self.delete_selected_configs)
        
        # Bind Q/q for QR code generation
        self.root.bind('<q>', self.generate_qrcode)
        self.root.bind('<Q>', self.generate_qrcode)
        

        # --- Bottom Terminal Frame ---
        bottom_frame = ttk.LabelFrame(main_pane, text="Logs")
        bottom_frame.pack_propagate(False)

        counter_frame = ttk.Frame(bottom_frame)
        counter_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.tested_label = ttk.Label(counter_frame, text="Tested: 0")
        self.tested_label.pack(side=tk.LEFT, padx=(0, 10))

        self.total_label = ttk.Label(counter_frame, text="Total: 0")
        self.total_label.pack(side=tk.LEFT)
        
        self.working_label = ttk.Label(counter_frame, text="Working: 0")
        self.working_label.pack(side=tk.LEFT, padx=(10, 0))
        
        self.progress = ttk.Progressbar(counter_frame, mode='determinate')
        self.progress.pack(side=tk.RIGHT, padx=(10, 10), fill=tk.X, expand=True)

        self.terminal = scrolledtext.ScrolledText(bottom_frame, height=2, state=tk.DISABLED)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.terminal.configure(bg='#3e3e3e', fg='#ffffff', insertbackground='white')

        # --- Add to PanedWindow ---
        main_pane.add(self.middle_frame)
        main_pane.add(bottom_frame)
        
        
        # Configure pane constraints
        main_pane.paneconfigure(bottom_frame, minsize=50)  # Absolute minimum height
        main_pane.paneconfigure(self.middle_frame, minsize=200)  # Prevent complete collapse
        
        # Set initial sash position (adjust 300 to your preferred initial height)
        main_pane.sash_place(0, 0, 300)  # This makes bottom frame start taller
        
        # --- Menu Bar ---
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Options menu
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_command(label="Update Xray Core", command=self.update_xray_core)
        options_menu.add_command(label="Update GeoFiles", command=self.update_geofiles)
        menubar.add_cascade(label="Options", menu=options_menu)
        
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Clear Terminal", command=self.clear_terminal)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        self.root.config(menu=menubar)
        
    def clear_terminal(self):
        """Clear the terminal output"""
        self.terminal.config(state=tk.NORMAL)
        self.terminal.delete('1.0', tk.END)
        self.terminal.config(state=tk.DISABLED)
        #self.log("Terminal cleared")
    
    
    def show_mirror_selection(self):
        """Show a popup window to select mirror and thread count"""
        self.mirror_window = tk.Toplevel(self.root)
        self.mirror_window.title("Select Source & Threads")
        self.mirror_window.geometry("300x270")  # Increased height for new control
        self.mirror_window.resizable(False, False)
        
        # Center the window
        window_width = 300
        window_height = 270
        screen_width = self.mirror_window.winfo_screenwidth()
        screen_height = self.mirror_window.winfo_screenheight()
        x = int((screen_width/2) - (window_width/2))
        y = int((screen_height/2) - (window_height/2))
        self.mirror_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Dark theme for the popup
        self.mirror_window.tk_setPalette(background='#2d2d2d', foreground='#ffffff',
                              activeBackground='#3e3e3e', activeForeground='#ffffff')
        
        # Create a custom style for the combobox
        style = ttk.Style()
        style.theme_use('clam')  # Use 'clam' theme as base
        
        # Configure combobox colors
        style.configure('TCombobox', 
                       fieldbackground='#3e3e3e',  # Background of the text field
                       background='#3e3e3e',       # Background of the dropdown
                       foreground='#ffffff',       # Text color
                       selectbackground='#4a6984', # Selection background
                       selectforeground='#ffffff', # Selection text color
                       bordercolor='#3e3e3e',     # Border color
                       lightcolor='#3e3e3e',      # Light part of the border
                       darkcolor='#3e3e3e')       # Dark part of the border
        
        # Configure the dropdown list
        style.map('TCombobox', 
                  fieldbackground=[('readonly', '#3e3e3e')],
                  selectbackground=[('readonly', '#4a6984')],
                  selectforeground=[('readonly', '#ffffff')],
                  background=[('readonly', '#3e3e3e')])
        
        # Source selection
        ttk.Label(self.mirror_window, text="Select config source:").pack(pady=(10, 0))

        self.mirror_combo = ttk.Combobox(
            self.mirror_window, 
            values=list(self.MIRRORS.keys()),
            state="readonly",
            style='TCombobox'
        )
        self.mirror_combo.current(0)
        self.mirror_combo.pack(pady=5, padx=20, fill=tk.X)
        self.mirror_combo.bind("<<ComboboxSelected>>", self._on_source_type_selected) # Bind event

        # Custom URL input field (initially hidden)
        self.custom_url_frame = ttk.Frame(self.mirror_window)
        ttk.Label(self.custom_url_frame, text="Enter Custom URL:").pack(pady=(0, 5))
        self.custom_url_entry = ttk.Entry(self.custom_url_frame)
        self.custom_url_entry.pack(fill=tk.X)
        self.custom_url_frame.pack_forget() # Hide initially

        # Paste Configs input field (initially hidden)
        self.paste_configs_frame = ttk.Frame(self.mirror_window)
        ttk.Label(self.paste_configs_frame, text="Paste Configs Here (one per line):").pack(pady=(0, 5))
        self.paste_configs_text = scrolledtext.ScrolledText(self.paste_configs_frame, height=5, width=30)
        self.paste_configs_text.configure(bg='#3e3e3e', fg='#ffffff', insertbackground='white')
        self.paste_configs_text.pack(fill=tk.BOTH, expand=True)
        self.paste_configs_frame.pack_forget() # Hide initially

        # Explicitly bind paste events to the scrolledtext widget for direct pasting
        self.paste_configs_text.bind("<Control-v>", self._paste_into_text_widget)
        if sys.platform == 'darwin': # macOS
            self.paste_configs_text.bind("<Command-v>", self._paste_into_text_widget) 
        else: # Windows/Linux
            self.paste_configs_text.bind("<<Paste>>", self._paste_into_text_widget)


        # Thread count selection
        ttk.Label(self.mirror_window, text="Select thread count:").pack(pady=(10, 0))
        
        self.thread_combo = ttk.Combobox(
            self.mirror_window,
            values=["10", "20", "50", "100"],
            state="readonly",
            style='TCombobox'
        )
        self.thread_combo.set("100")  # Default to 100
        self.thread_combo.pack(pady=5, padx=20, fill=tk.X)
        
        # Apply dark background to the dropdown lists
        self.mirror_window.option_add('*TCombobox*Listbox.background', '#3e3e3e')
        self.mirror_window.option_add('*TCombobox*Listbox.foreground', '#ffffff')
        self.mirror_window.option_add('*TCombobox*Listbox.selectBackground', '#4a6984')
        self.mirror_window.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        
        # Frame for buttons
        button_frame = ttk.Frame(self.mirror_window)
        button_frame.pack(pady=10)
        
        # OK button
        ttk.Button(
            button_frame, 
            text="OK", 
            command=self.on_mirror_selected
        ).pack(side=tk.LEFT, padx=5)
        
        # Cancel button
        ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.cancel_mirror_selection
        ).pack(side=tk.LEFT, padx=5)
        
        # Handle window close (X button)
        self.mirror_window.protocol("WM_DELETE_WINDOW", self.cancel_mirror_selection)
        
        # Make the window modal
        self.mirror_window.grab_set()
        self.mirror_window.transient(self.root)
        self.mirror_window.wait_window(self.mirror_window)

    def _paste_into_text_widget(self, event):
        """Custom paste function for the scrolledtext widget."""
        try:
            if event.keysym.lower() == 'v' and (event.state & 0x4 or event.state & 0x8): # Control or Command key
                clipboard_content = self.root.clipboard_get()
                self.paste_configs_text.insert(tk.INSERT, clipboard_content)
            elif event.num == 3: # Right-click paste on some systems
                clipboard_content = self.root.clipboard_get()
                self.paste_configs_text.insert(tk.INSERT, clipboard_content)
        except tk.TclError:
            pass
        return "break" # Prevent default handling and propagate to other bindings if necessary
    
    def _on_source_type_selected(self, event):
        """Handle selection change in the source combobox"""
        selected_type = self.mirror_combo.get()
        
        # Hide all optional input frames first
        self.custom_url_frame.pack_forget()
        self.paste_configs_frame.pack_forget()

        # Adjust window size to default for now, then resize if needed
        # Original size for just mirror and threads was 300x200
        # For custom URL, it was 300x250
        # For paste configs, it was 300x350
        current_height = 200 # Base height for mirror and threads
        
        if selected_type == "Custom URL":
            self.custom_url_frame.pack(pady=(10, 0), padx=20, fill=tk.X)
            current_height = 250
        elif selected_type == "Paste Configs":
            self.paste_configs_frame.pack(pady=(10, 0), padx=20, fill=tk.BOTH, expand=True)
            current_height = 350
            self.paste_configs_text.focus_set() # Set focus to the text box
            
        self.mirror_window.geometry(f"300x{current_height}") # Adjust window size
            
    def cancel_mirror_selection(self):
        """Handle cancel or window close without selection"""
        if hasattr(self, 'mirror_window') and self.mirror_window:
            self.mirror_window.destroy()
        
        # Reset the button state
        self.fetch_btn.config(
            text="Fetch & Test New Configs",
            style='TButton',
            state=tk.NORMAL
        )
        self.is_fetching = False

    def on_mirror_selected(self):
        """Handle mirror and thread count selection"""
        selected_source_type = self.mirror_combo.get()
        selected_threads = self.thread_combo.get()
        
        try:
            self.LATENCY_WORKERS = int(selected_threads)
        except ValueError:
            self.LATENCY_WORKERS = 100  # Default if conversion fails
            
        if selected_source_type == "Local File (configs.txt)":
            self.log(f"Selected: Local File ({self.LOCAL_CONFIGS_FILE}), Threads: {self.LATENCY_WORKERS}")
            self.mirror_window.destroy()
            self._start_fetch_and_test(source_type="local_file")
        elif selected_source_type == "Custom URL":
            custom_url = self.custom_url_entry.get().strip()
            if not custom_url:
                messagebox.showwarning("Input Error", "Please enter a Custom URL.")
                return
            self.CONFIGS_URL = custom_url
            self.log(f"Selected: Custom URL ({self.CONFIGS_URL}), Threads: {self.LATENCY_WORKERS}")
            self.mirror_window.destroy()
            self._start_fetch_and_test(source_type="custom_url")
        elif selected_source_type == "Paste Configs":
            pasted_text = self.paste_configs_text.get("1.0", tk.END).strip()
            if not pasted_text:
                messagebox.showwarning("Input Error", "Please paste configs into the text box.")
                return
            configs = [line.strip() for line in pasted_text.splitlines() if line.strip()]
            if not configs:
                messagebox.showwarning("Input Error", "No valid configs found in the pasted text.")
                return

            # Save to temporary paste_configs_temp.txt for testing
            try:
                with open(self.PASTE_CONFIGS_TEMP_FILE, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(configs))
                self.log(f"Saved {len(configs)} pasted configs to {self.PASTE_CONFIGS_TEMP_FILE} for testing.")
            except Exception as e:
                self.log(f"Error saving pasted configs to temp file: {str(e)}")
                messagebox.showerror("Error", f"Failed to save pasted configs: {e}")
                return

            self.log(f"Selected: Paste Configs. Found {len(configs)} configs.")
            self.mirror_window.destroy()
            
            self.fetch_btn.config(state=tk.DISABLED)
            self.log("Testing pasted configs...")
            # Use _test_pasted_configs_worker for these configs, passing the source type
            threading.Thread(target=self._test_pasted_configs_worker, args=(configs, "paste_configs"), daemon=True).start()
            self.is_fetching = True 
            self.fetch_btn.config(text="Stop Testing Configs", style='Stop.TButton')
        elif selected_source_type in self.MIRRORS:
            self.CONFIGS_URL = self.MIRRORS[selected_source_type]
            self.log(f"Selected mirror: {selected_source_type}, Threads: {self.LATENCY_WORKERS}")
            self.mirror_window.destroy()
            self._start_fetch_and_test(source_type="mirror_url")
        else:
            # If somehow no valid selection, treat as cancel
            self.cancel_mirror_selection()
    
    def _start_fetch_and_test(self, source_type):
        """Start the actual fetch and test process after source selection"""
        # Start fetching
        self.is_fetching = True
        self.fetch_btn.config(text="Stop Fetching Configs", style='Stop.TButton')
        
        # Clear any previous stop state
        self.stop_event.clear()
        
        if source_type == "local_file":
            self.log("Starting config test from local file...")
            thread = threading.Thread(target=self._fetch_and_test_worker, args=(source_type,), daemon=True)
        elif source_type == "custom_url":
            self.log(f"Starting config fetch and test from custom URL: {self.CONFIGS_URL}")
            thread = threading.Thread(target=self._fetch_and_test_worker, args=(source_type,), daemon=True)
        elif source_type == "paste_configs": 
            # This branch should not be reached for 'paste_configs' as it's handled in on_mirror_selected
            self.log("Error: _fetch_and_test_worker called with 'paste_configs' source type, which is unexpected here.")
            return 
        else: # mirror_url
            self.log("Starting config fetch and test from mirror URL...")
            thread = threading.Thread(target=self._fetch_and_test_worker, args=(source_type,), daemon=True)
        
        thread.start()
    

    def on_right_click(self, event):
        """Handle right-click event on treeview"""
        item = self.tree.identify_row(event.y)
        if item:
            # Select the item that was right-clicked
            self.tree.selection_set(item)
            self.on_config_highlight(event)  # Update selection
            
            # Show context menu
            try:
                self.generate_qrcode()
            except :
                pass
            finally:
                pass
    
    def load_best_configs(self):
        """Load best configs from file if it exists and test them"""
        try:
            # Change button to stop state
            self.root.after(0, lambda: self.reload_btn.config(
                text="Stop Loading Configs",
                style='Stop.TButton',
                state=tk.NORMAL
            ))
            
            if os.path.exists(self.BEST_CONFIGS_FILE):
                with open(self.BEST_CONFIGS_FILE, 'r', encoding='utf-8') as f:
                    # Use a set to avoid duplicates while reading
                    seen = set() # Changed to set for efficiency
                    config_uris = []
                    for line in f:
                        if self.stop_event.is_set(): # Added stop check
                            break
                            
                        line = line.strip()
                        if line and line not in seen:
                            seen.add(line)
                            config_uris.append(line)
                    
                    if not config_uris:
                        self.root.after(0, lambda: self.reload_btn.config(
                            text="Reload Best Configs",
                            style='TButton',
                            state=tk.NORMAL
                        ))
                        self.log("No configs found in best_configs.txt")
                        self.best_configs = [] # Ensure best_configs is empty if file is empty
                        self.update_treeview() # Update treeview to be empty
                        self.update_counters() # Update counters to zero
                        return
                    
                    if not self.stop_event.is_set(): # Only proceed if not stopped
                        # Initialize with default infinite latency (will be updated when tested)
                        self.best_configs = [(uri, float('inf')) for uri in config_uris]
                        self.total_configs = len(config_uris)
                        self.tested_configs = 0  # Reset to 0 since we need to test them again
                        self.working_configs = 0
                        self.update_counters()
                        self.root.after(0, lambda: self.progress.config(maximum=len(config_uris), value=0))
                        self.log(f"Loaded {len(config_uris)} configs from {self.BEST_CONFIGS_FILE}")
                        
                        # Start testing the loaded configs in a separate thread
                        # Pass "best_configs_reload" to ensure they are re-tested and results updated.
                        thread = threading.Thread(target=self._test_pasted_configs_worker, args=(config_uris, "best_configs_reload"), daemon=True)
                        thread.start()
            else: # If BEST_CONFIGS_FILE does not exist
                self.root.after(0, lambda: self.reload_btn.config(
                    text="Reload Best Configs",
                    style='TButton',
                    state=tk.NORMAL
                ))
                self.log("best_configs.txt not found. No configs to load.")
                self.best_configs = []
                self.update_treeview()
                self.update_counters()
                
        except Exception as e:
            self.log(f"Error loading best configs: {str(e)}")
            self.root.after(0, lambda: self.reload_btn.config(
                text="Reload Best Configs",
                style='TButton',
                state=tk.NORMAL
            ))
            self.stop_event.clear()
    
    def reload_and_test_configs(self):
        """Reload and test configs from best_configs.txt"""
        if self.reload_btn.cget('text') == "Stop Loading Configs":
            self.stop_reloading()
            return
            
        self.reload_btn.config(
            text="Stop Loading Configs",
            style='Stop.TButton',
            state=tk.NORMAL
        )
        self.log("Reloading and testing configs from best_configs.txt...")
        
        # Clear current configs and treeview
        self.best_configs = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Load and test configs from file
        self.load_best_configs()
    
    def delete_selected_configs(self, event=None):
        """Delete selected configs by reading from file, filtering, and saving back"""
        selected_items = self.tree.selection()
        if not selected_items:
            return

        # Get URIs of selected items
        selected_uris = [self.tree.item(item)['values'][5] for item in selected_items]  # Assuming URI is in column 5
        
        try:
            # Read all configs from file
            with open(self.BEST_CONFIGS_FILE, 'r', encoding='utf-8') as f:
                all_configs = [line.strip() for line in f if line.strip()]

            # Filter out selected URIs
            remaining_configs = []
            deleted_count = 0
            
            for config in all_configs:
                if config not in selected_uris:
                    remaining_configs.append(config)
                else:
                    deleted_count += 1

            # Write remaining configs back to file
            with open(self.BEST_CONFIGS_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(remaining_configs))

            # Reload the configs to update both the data and UI
            self.best_configs = []  # Clear current configs
            self.load_best_configs()  # This will reload from file and update the treeview

            
            self.log(f"Deleted {deleted_count} config(s)")

        except Exception as e:
            self.log(f"Error deleting configs: {str(e)}")


    def save_best_configs(self):
        """Save current best configs to file"""
        try:
            with open(self.BEST_CONFIGS_FILE, 'w', encoding='utf-8') as f:
                for config_uri, _ in self.best_configs:  # Only save the URI part
                    f.write(f"{config_uri}\n")
        except Exception as e:
            self.log(f"Error saving best configs: {str(e)}")
    
    def kill_existing_xray_processes(self):
        """Kill any existing Xray processes (cross-platform)"""
        try:
            if sys.platform == 'win32':
                # Windows implementation
                import psutil
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'].lower() == 'xray.exe':
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            else:
                # Linux/macOS implementation
                subprocess.run(['pkill', '-f', 'xray'], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log(f"Error killing existing Xray processes: {str(e)}")
            
    def generate_qrcode(self, event=None):
        """Generate QR code for selected config and display it"""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        item = selected_items[0]
        index = int(self.tree.item(item)['values'][0]) - 1
        
        if 0 <= index < len(self.best_configs):
            config_uri = self.best_configs[index][0]
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(config_uri)
            qr.make(fit=True)
            
            # Keep the original PIL image for resizing
            self.original_img = qr.make_image(fill_color="black", back_color="white")
            
            # Create and show QR code window
            qr_window = tk.Toplevel(self.root)
            qr_window.title("Config QR Code")
            qr_window.geometry("600x620+20+20")
            
            # Convert PIL image to Tkinter PhotoImage
            self.tk_image = ImageTk.PhotoImage(self.original_img)
            
            self.label = ttk.Label(qr_window, image=self.tk_image)
            self.label.image = self.tk_image  # Keep a reference
            self.label.pack(pady=10)
            
            # Set smaller default zoom for VMess configs
            if config_uri.startswith("vmess://"):
                # VMess configs are longer, so use smaller default zoom
                self.zoom_level = 0.7  # 70% of original size
                # Resize the image
                width, height = self.original_img.size
                new_size = (int(width * self.zoom_level), int(height * self.zoom_level))
                resized_img = self.original_img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Update the displayed image
                self.tk_image = ImageTk.PhotoImage(resized_img)
                self.label.configure(image=self.tk_image)
                self.label.image = self.tk_image  # Keep a reference
            else:
                # Other config types can use normal size
                self.zoom_level = 1.0
            
            # Bind mouse wheel event for zooming
            qr_window.bind("<Control-MouseWheel>", self.zoom_qrcode)
            self.label.bind("<Control-MouseWheel>", self.zoom_qrcode)
            
            # Add config preview
            config_preview = ttk.Label(
                qr_window, 
                text=config_uri[:40] + "..." if len(config_uri) > 40 else config_uri,
                wraplength=280
            )
            config_preview.pack(pady=5, padx=10)
            
            # Add close button
            close_btn = ttk.Button(qr_window, text="Close", command=qr_window.destroy)
            close_btn.pack(pady=5)

    def zoom_qrcode(self, event):
        """Handle zooming of QR code with Ctrl + mouse wheel"""
        # Determine zoom direction
        if event.delta > 0:
            self.zoom_level *= 1.1  # Zoom in
        else:
            self.zoom_level *= 0.9  # Zoom out
        
        # Limit zoom levels (optional)
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        
        # Resize the image
        width, height = self.original_img.size
        new_size = (int(width * self.zoom_level), int(height * self.zoom_level))
        resized_img = self.original_img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Update the displayed image
        self.tk_image = ImageTk.PhotoImage(resized_img)
        self.label.configure(image=self.tk_image)
        self.label.image = self.tk_image  # Keep a reference
    
        
    def paste_configs(self, event=None):
        """Handles pasting configs via global Ctrl+V (not for the paste box itself)"""
        try:
            clipboard = self.root.clipboard_get()
            if clipboard.strip():
                configs = [line.strip() for line in clipboard.splitlines() if line.strip()]
                if configs:
                    self.log(f"Pasted {len(configs)} config(s) from clipboard (global paste).")
                    self._test_pasted_configs(configs, "clipboard_paste") 
        except tk.TclError:
            pass
            
    def _test_pasted_configs(self, configs, source_type="clipboard_paste"):
        self.fetch_btn.config(state=tk.DISABLED)
        self.log(f"Testing configs from {source_type}...")
        
        thread = threading.Thread(target=self._test_pasted_configs_worker, args=(configs, source_type), daemon=True)
        thread.start()
        
    def _test_pasted_configs_worker(self, configs, source_type):
        try:
            # Register this thread
            with self.thread_lock:
                self.active_threads.append(threading.current_thread())
                
            self.total_configs = len(configs)
            self.tested_configs = 0
            self.working_configs = 0
            self.root.after(0, self.update_counters)
            
            self.root.after(0, lambda: self.progress.config(maximum=len(configs), value=0))
            
            best_configs_current_session = [] # To store working configs from this test session
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.LATENCY_WORKERS) as executor:
                futures = {executor.submit(self.measure_latency, config): config for config in configs}
                for future in concurrent.futures.as_completed(futures):
                    if self.stop_event.is_set():
                        # Cancel all pending futures
                        for f in futures:
                            f.cancel()
                        break
                        
                    result = future.result()
                    self.tested_configs += 1
                    
                    if result[1] != float('inf'):
                        config_uri = result[0]
                        # Check if this config is already in best_configs_current_session (from this test run)
                        # This prevents adding duplicates *within the current session's results*
                        if not any(x[0] == config_uri for x in best_configs_current_session):
                            best_configs_current_session.append(result)
                            self.working_configs += 1
                            self.log(f"Working config found: {result[1]:.2f}ms")
                            
                    self.root.after(0, lambda: self.progress.config(value=self.tested_configs))
                    self.root.after(0, self.update_counters)
            
            # Only save if not stopped
            if not self.stop_event.is_set():
                # First, get all unique working URIs found in this session
                current_session_working_uris = {uri for uri, latency in best_configs_current_session if latency != float('inf')}

                # Load existing configs from best_configs.txt to merge
                existing_configs_from_file = set()
                if os.path.exists(self.BEST_CONFIGS_FILE):
                    try:
                        with open(self.BEST_CONFIGS_FILE, 'r', encoding='utf-8') as f:
                            existing_configs_from_file = {line.strip() for line in f if line.strip()}
                    except Exception as e:
                        self.log(f"Warning: Could not read existing best_configs.txt for merging: {e}")
                
                # Combine current session's working URIs with existing ones, ensuring uniqueness
                all_unique_working_uris = existing_configs_from_file.union(current_session_working_uris)

                # Overwrite best_configs.txt with the merged and unique working URIs
                try:
                    with open(self.BEST_CONFIGS_FILE, 'w', encoding='utf-8') as f:
                        for uri in sorted(list(all_unique_working_uris)): # Sort for consistent file order
                            f.write(f"{uri}\n")
                    self.log(f"Updated {self.BEST_CONFIGS_FILE} with {len(all_unique_working_uris)} unique working configs.")
                except Exception as e:
                    self.log(f"Error saving to {self.BEST_CONFIGS_FILE}: {e}")

                # Now, re-load self.best_configs from the updated file and update the treeview
                if source_type == "best_configs_reload":
                    # If we are here because load_best_configs called us, we just update the treeview
                    # The data in self.best_configs is already set by load_best_configs (which loaded from file)
                    # We just need to apply the *newly tested latencies* from this run.
                    current_session_latencies = {uri: latency for uri, latency in best_configs_current_session}

                    updated_configs_list = []
                    for config_uri in sorted(list(all_unique_working_uris)): # Iterate through all unique configs
                        latency = current_session_latencies.get(config_uri, float('inf')) # Get latest latency or inf
                        if latency != float('inf'): # Only include working configs
                            updated_configs_list.append((config_uri, latency))
                    
                    self.best_configs = sorted(updated_configs_list, key=lambda x: x[1])
                    self.log(f"Reload and re-test complete! Found {len(self.best_configs)} working configs.")
                    self.root.after(0, self.update_treeview)
                else:
                    # For all other sources (paste, clipboard, mirror, local file), after updating the file,
                    # we want to trigger a full reload cycle to ensure accurate display and sorting.
                    # This will call load_best_configs, which then calls this worker with "best_configs_reload".
                    self.log("Triggering full best configs reload for accurate display...")
                    self.root.after(0, self.load_best_configs)
                
                self.log(f"Test complete! Found {len(best_configs_current_session)} working configs in this session.")
                
        except Exception as e:
            self.log(f"Error in testing configs: {str(e)}")
        finally:
            # Clean up
            with self.thread_lock:
                if threading.current_thread() in self.active_threads:
                    self.active_threads.remove(threading.current_thread())
            
            # Clean up paste_configs_temp.txt if it was used
            if source_type == "paste_configs" and os.path.exists(self.PASTE_CONFIGS_TEMP_FILE):
                try:
                    os.remove(self.PASTE_CONFIGS_TEMP_FILE)
                    self.log(f"Cleaned up temporary file: {self.PASTE_CONFIGS_TEMP_FILE}")
                except Exception as e:
                    self.log(f"Error cleaning up {self.PASTE_CONFIGS_TEMP_FILE}: {str(e)}")
            
            if not self.stop_event.is_set():
                self.root.after(0, lambda: self.fetch_btn.config(
                    text="Fetch & Test New Configs",
                    state=tk.NORMAL,
                    style='TButton'
                ))
                self.root.after(0, lambda: self.reload_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.progress.config(value=0))
                self.is_fetching = False
    
    def stop_reloading(self):
        """Stop the reload operation"""
        self.stop_event.set()
        
        # Wait for active threads to finish (with timeout)
        with self.thread_lock:
            for thread in self.active_threads[:]:  # Create a copy of the list
                if thread.is_alive():
                    thread.join(timeout=1.0)  # Wait up to 1 second for thread to finish
                    if thread.is_alive():  # If still alive after timeout
                        self.log(f"Thread {thread.name} didn't stop gracefully")
        
        # Clear the active threads list
        with self.thread_lock:
            self.active_threads.clear()
        
        # Immediately reset all counters and progress bar
        self.root.after(0, lambda: self.progress.config(value=0))
        self.root.after(0, lambda: self.reload_btn.config(
            text="Reload Best Configs",
            style='TButton',
            state=tk.NORMAL
        ))
        
        # Reset counters
        self.tested_configs = 0
        self.working_configs = 0
        self.total_configs = 0
        self.root.after(0, self.update_counters)
        
        self.log("Stopped reloading configs")
        self.stop_event.clear()  # Clear the stop event for future operations
    
    def copy_selected_configs(self, event=None):
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        configs = []
        for item in selected_items:
            index = int(self.tree.item(item)['values'][0]) - 1
            if 0 <= index < len(self.best_configs):
                configs.append(self.best_configs[index][0])
                
        if configs:
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(configs))
            self.log(f"Copied {len(configs)} config(s) to clipboard")
            
    def update_counters(self):
        self.tested_label.config(text=f"Tested: {self.tested_configs}")
        self.total_label.config(text=f"Total: {self.total_configs}")
        self.working_label.config(text=f"Working: {self.working_configs}")
        
    def setup_logging(self):
        # Start log processing thread
        self.log_thread = threading.Thread(target=self.process_logs, daemon=True)
        self.log_thread.start()
        
    def log(self, message):
        """Add a log message to the queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def process_logs(self):
        """Process log messages from the queue"""
        while True:
            try:
                message = self.log_queue.get(timeout=0.1)
                self.root.after(0, self.update_terminal, message)
            except queue.Empty:
                continue
                
    def update_terminal(self, message):
        """Update the terminal with a new message"""
        self.terminal.config(state=tk.NORMAL)
        self.terminal.insert(tk.END, message + "\n")
        self.terminal.see(tk.END)
        self.terminal.config(state=tk.DISABLED)
        
    def parse_config_info(self, config_uri):
        """Extract basic info from config URI"""
        try:
            if config_uri.startswith("vmess://"):
                base64_str = config_uri[8:]
                padded = base64_str + '=' * (4 - len(base64_str) % 4)
                decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
                vmess_config = json.loads(decoded)
                return "vmess", vmess_config.get("add", "unknown"), vmess_config.get("port", "unknown")
            elif config_uri.startswith("vless://"):
                parsed = urllib.parse.urlparse(config_uri)
                return "vless", parsed.hostname or "unknown", parsed.port or "unknown"
            elif config_uri.startswith("ss://"):
                # Handle Shadowsocks configs
                parts = config_uri[5:].split("#", 1)
                encoded_part = parts[0]
                
                if "@" in encoded_part:
                    # New style SS URI: ss://method:password@server:port
                    userinfo, server_part = encoded_part.split("@", 1)
                    server, port = server_part.split(":", 1) if ":" in server_part else (server_part, "unknown")
                else:
                    # Old style SS URI: ss://base64(method:password)@server:port
                    try:
                        decoded = base64.b64decode(encoded_part + '=' * (-len(encoded_part) % 4)).decode('utf-8')
                        if "@" in decoded:
                            userinfo, server_part = decoded.split("@", 1)
                            server, port = server_part.split(":", 1) if ":" in server_part else (server_part, "unknown")
                        else:
                            # Just method:password without server
                            server, port = "unknown", "unknown"
                    except:
                        server, port = "unknown", "unknown"
                
                return "shadowsocks", server, port
            elif config_uri.startswith("trojan://"):
                parsed = urllib.parse.urlparse(config_uri)
                return "trojan", parsed.hostname or "unknown", parsed.port or "unknown"
        except:
            pass
        return "unknown", "unknown", "unknown"
    
    def clear_temp_folder(self):
        """Clear all files in the temp folder"""
        try:
            for filename in os.listdir(self.TEMP_FOLDER):
                file_path = os.path.join(self.TEMP_FOLDER, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    self.log(f"Failed to delete {file_path}: {e}")
        except Exception as e:
            self.log(f"Error clearing temp folder: {e}")
            
    def stop_fetching(self):
        """Stop all fetching and testing operations"""
        self.is_fetching = False
        self.fetch_btn.config(text="Fetch & Test New Configs", style='TButton')  # Revert to normal style
        self.log("Stopping all operations...")
        
        
        self.stop_event.set()
        
        # Kill all Xray processes
        self.kill_existing_xray_processes()
        
        # Clear temp folder
        self.clear_temp_folder()
        
        # Also clean up the pasted configs temp file if it was used
        if os.path.exists(self.PASTE_CONFIGS_TEMP_FILE):
            try:
                os.remove(self.PASTE_CONFIGS_TEMP_FILE)
                self.log(f"Cleaned up temporary file: {self.PASTE_CONFIGS_TEMP_FILE}")
            except Exception as e:
                    self.log(f"Error cleaning up {self.PASTE_CONFIGS_TEMP_FILE}: {str(e)}")

        # Wait for threads to finish (with timeout)
        with self.thread_lock:
            for thread in self.active_threads[:]:  # Create a copy of the list
                if thread.is_alive():
                    thread.join(timeout=0.5)  # Shorter timeout
                    if thread.is_alive():  # If still alive after timeout
                        self.log(f"Thread {thread.name} didn't stop gracefully")
        
        # Clear the active threads list
        with self.thread_lock:
            self.active_threads.clear()
        
        self.stop_event.clear()
        self.log("All operations stopped")
        self.fetch_btn.config(state=tk.NORMAL)
        self.reload_btn.config(state=tk.NORMAL)
        self.progress.config(value=0)
    
    def fetch_and_test_configs(self):
        kill_xray_processes()
        """Toggle between fetching and stopping"""
        if not self.is_fetching:
            # Start fetching
            self.stop_event.clear()
            self.show_mirror_selection()
            
        else:
            # Stop fetching
            self.stop_fetching()
        
    def _fetch_and_test_worker(self, source_type):
        """Worker thread for fetching and testing configs for URL/File sources"""
        try:
            # Register this thread
            with self.thread_lock:
                self.active_threads.append(threading.current_thread())
            
            configs = []
            if source_type == "local_file":
                configs = self._load_configs_from_file()
            elif source_type == "custom_url":
                configs = self.fetch_configs(custom_url=self.CONFIGS_URL)
            else: # mirror_url
                configs = self.fetch_configs(custom_url=None) # Use default CONFIGS_URL
                
            if not configs or self.stop_event.is_set():
                self.log("Operation stopped or no configs found")
                return
                
            self.total_configs = len(configs)
            self.tested_configs = 0
            self.working_configs = 0
            self.root.after(0, self.update_counters)
            
            self.root.after(0, lambda: self.progress.config(maximum=len(configs), value=0))
            
            # Load existing best configs from file to identify duplicates
            existing_configs_uris_from_file = set()
            if os.path.exists(self.BEST_CONFIGS_FILE):
                with open(self.BEST_CONFIGS_FILE, 'r', encoding='utf-8') as f:
                    existing_configs_uris_from_file = {line.strip() for line in f if line.strip()}
            
            # Test configs for latency
            self.log("Testing configs for latency...")
            newly_found_working_configs = [] # To hold only working configs that are *new* to BEST_CONFIGS_FILE
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.LATENCY_WORKERS) as executor:
                futures = {executor.submit(self.measure_latency, config): config for config in configs}
                for future in concurrent.futures.as_completed(futures):
                    if self.stop_event.is_set():
                        # Cancel all pending futures
                        for f in futures:
                            f.cancel()
                        break
                        
                    result_uri, result_latency = future.result()
                    self.tested_configs += 1
                    
                    if result_latency != float('inf'):
                        # Check if this working config is already in our BEST_CONFIGS_FILE
                        is_already_in_best_file = result_uri in existing_configs_uris_from_file
                        is_already_in_new_finds = any(uri == result_uri for uri, _ in newly_found_working_configs)
                        
                        if not is_already_in_best_file and not is_already_in_new_finds:
                            # If it's a genuinely new working config, add it to our list for appending to file
                            newly_found_working_configs.append((result_uri, result_latency))
                            self.working_configs += 1
                            self.log(f"Working config found: {result_latency:.2f}ms - candidate for best configs")
                        elif is_already_in_best_file:
                            self.log(f"Existing working config found: {result_latency:.2f}ms")

                    # Update progress and counters
                    self.root.after(0, lambda: self.progress.config(value=self.tested_configs))
                    self.root.after(0, self.update_counters)
            
            # Now, process the results for saving to BEST_CONFIGS_FILE and updating treeview
            if not self.stop_event.is_set(): # Only proceed if not stopped
                # Append newly found working configs to BEST_CONFIGS_FILE
                if newly_found_working_configs:
                    with open(self.BEST_CONFIGS_FILE, 'a', encoding='utf-8') as f:
                        for config_uri, _ in newly_found_working_configs:
                            f.write(f"{config_uri}\n")
                    self.log(f"Added {len(newly_found_working_configs)} new working configs to {self.BEST_CONFIGS_FILE}")
                else:
                    self.log("No new working configs found to add to best_configs.txt in this session.")
                
                # Reload all configs from BEST_CONFIGS_FILE to get the most up-to-date sorted list
                self.best_configs = [] # Clear current in-memory list
                # This call to load_best_configs will now correctly re-read the updated file
                # and trigger _test_pasted_configs_worker with "best_configs_reload" source type
                # ensuring the treeview is populated with updated latencies from the re-test.
                self.load_best_configs() 
                
                self.log(f"Testing complete! Current total working configs: {len(self.best_configs)}")
                
        except Exception as e:
            if not self.stop_event.is_set():
                self.log(f"Error in fetch and test: {str(e)}")
        finally:
            # Clean up
            with self.thread_lock:
                if threading.current_thread() in self.active_threads:
                    self.active_threads.remove(threading.current_thread())
                    
            if not self.stop_event.is_set():
                self.root.after(0, lambda: self.fetch_btn.config(
                    text="Fetch & Test New Configs",
                    state=tk.NORMAL,
                    style='TButton'
                ))
                self.root.after(0, lambda: self.reload_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.progress.config(value=0))
                self.is_fetching = False
            
    def update_treeview(self):
        """Update the treeview with best configs"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add best configs (limit to prevent crashes)
        max_configs = min(100, len(self.best_configs))  # Limit to 100 configs
        for i, (config_uri, latency) in enumerate(self.best_configs[:max_configs]):
            protocol, server, port = self.parse_config_info(config_uri)
            config_preview = config_uri
            
            # Check if this is the connected config
            tags = ()
            if self.connected_config and config_uri == self.connected_config:
                tags = ('connected',)
            
            self.tree.insert('', 'end', values=(
                i + 1,
                f"{latency:.2f}",
                protocol,
                server,
                port,
                config_preview
            ), tags=tags)
            
        #self.log(f"Updated treeview with {max_configs} best configs")
        
    def on_tree_click(self, event):
        self.tree.after_idle(lambda: self.on_config_highlight(event))
    
    def on_config_highlight(self, event):
        """Handle single-click on treeview item"""
        selection = self.tree.selection()
        
        if selection:
            item = self.tree.item(selection[0])
            index = int(item['values'][0]) - 1
            
            if 0 <= index < len(self.best_configs):
                self.selected_config = self.best_configs[index][0]
                self.log(f"Selected config: {self.selected_config[:60]}...")
                
                # Update connection status based on current state
                self.connect_btn.config(state=tk.NORMAL)
                self.update_connection_status(self.is_connected)
                
    
    def on_config_select(self, event):
        """Handle double-click on treeview item"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            index = int(item['values'][0]) - 1
            
            if 0 <= index < len(self.best_configs):
                self.selected_config = self.best_configs[index][0]
                self.log(f"Selected config: {self.selected_config[:60]}...")
                #self.connect_btn.config(state=tk.NORMAL)
                self.connect_config()
                
    
    def connect_config(self):
        kill_xray_processes()
        """Connect to the selected config"""
        self.update_connection_status(True)
        
        self.status_label.config(text="Connecting....", foreground="white")
        
        
        if not self.selected_config:
            messagebox.showwarning("Warning", "Please select a config first")
            return
            
        if self.is_connected:
            self.log("Already connected. Disconnecting first...")
            self.disconnect_config()
        
        
        self.set_proxy("127.0.0.1","1080")
        
        self.log("Attempting to connect...")
        
        # Set the connected config before starting the thread
        self.connected_config = self.selected_config
        self.update_treeview()  # Refresh to show the connected config
    
        thread = threading.Thread(target=self._connect_worker, daemon=True)
        thread.start()
        
    def _connect_worker(self):
        """Worker thread for connecting"""
        try:
            config = self.parse_protocol(self.selected_config)
            
            with open(self.TEMP_CONFIG_FILE, "w", encoding='utf-8') as f:
                json.dump(config, f)
                
            self.log("Starting Xray process...")
            
            # Modified to run without console window
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.xray_process = subprocess.Popen(
                [self.XRAY_PATH, "run", "-config", self.TEMP_CONFIG_FILE],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                startupinfo=startupinfo
            )
            
            # Wait a bit for initialization
            time.sleep(2)
            
            # Check if process is still running
            if self.xray_process.poll() is None:
                self.is_connected = True
                self.root.after(0, self.update_connection_status, True)
                self.log("Connected successfully!")
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=self._monitor_xray, daemon=True)
                monitor_thread.start()
            else:
                stderr_output = self.xray_process.stderr.read()
                self.log(f"Failed to start Xray: {stderr_output}")
                self.xray_process = None
                
        except Exception as e:
            self.log(f"Connection error: {str(e)}")
            
    def _monitor_xray(self):
        """Monitor Xray process output"""
        if self.xray_process:
            for line in iter(self.xray_process.stdout.readline, ''):
                if line:
                    self.log(f"Xray: {line.strip()}")
                if self.xray_process.poll() is not None:
                    break
                    
    def update_connection_status(self, connected):
        """Update connection status in GUI"""
        if connected:
            self.status_label.config(text="Connected", foreground="SpringGreen")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
        else:
            self.status_label.config(text="Disconnected", foreground="Tomato")
            self.connect_btn.config(state=tk.NORMAL if self.selected_config else tk.DISABLED)
            self.disconnect_btn.config(state=tk.DISABLED)
    
    def disconnect_config(self, click_button=False):
        """Disconnect from current config"""
        if not self.is_connected:
            messagebox.showinfo("Info", "Not connected")
            return
        
        self.unset_proxy()
        
        self.log("Disconnecting...")
        
        if self.xray_process:
            try:
                self.xray_process.terminate()
                self.xray_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.xray_process.kill()
            except Exception as e:
                self.log(f"Error terminating process: {str(e)}")
            finally:
                self.xray_process = None
                
        self.is_connected = False
        self.connected_config = None  # Clear the connected config
        if click_button :
            self.update_connection_status(False)
        else :
            self.status_label.config(text="Connecting....", foreground="white")
        
        
        # Clean up temp file
        try:
            if os.path.exists(self.TEMP_CONFIG_FILE):
                os.remove(self.TEMP_CONFIG_FILE)
        except:
            pass
            
        self.update_treeview()  # Refresh to remove the connected highlight
        self.log("Disconnected")
        
    def click_disconnect_config_button(self) :
        self.update_connection_status(False)
        self.disconnect_config(True)
    
    def set_proxy(self, proxy_server, port):
        """Set system proxy settings (cross-platform)"""
        try:
            if sys.platform == 'win32':
                # Windows implementation
                import winreg
                key = winreg.HKEY_CURRENT_USER
                subkey = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
                access = winreg.KEY_WRITE

                with winreg.OpenKey(key, subkey, 0, access) as internet_settings_key:
                    winreg.SetValueEx(internet_settings_key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(internet_settings_key, "ProxyServer", 0, winreg.REG_SZ, f"{proxy_server}:{port}")
            
            elif sys.platform == 'darwin':
                # macOS implementation
                networks = subprocess.check_output(["networksetup", "-listallnetworkservices"]).decode('utf-8')
                for service in networks.split('\n')[1:]:  # Skip first line
                    if service.strip():
                        subprocess.run([
                            "networksetup", "-setwebproxy", service.strip(), 
                            proxy_server, str(port)
                        ])
                        subprocess.run([
                            "networksetup", "-setsecurewebproxy", service.strip(), 
                            proxy_server, str(port)
                        ])
                        subprocess.run([
                            "networksetup", "-setsocksfirewallproxy", service.strip(), 
                            proxy_server, str(port)
                        ])
            
            elif sys.platform == 'linux':
                # Linux implementation (GNOME)
                try:
                    subprocess.run([
                        "gsettings", "set", "org.gnome.system.proxy", 
                        "mode", "manual"
                    ])
                    subprocess.run([
                        "gsettings", "set", "org.gnome.system.proxy.socks", 
                        "host", proxy_server
                    ])
                    subprocess.run([
                        "gsettings", "set", "org.gnome.system.proxy.socks", 
                        "port", str(port)
                    ])
                except:
                    self.log("Could not set proxy automatically on Linux. Please set it manually.")
        except Exception as e:
            self.log(f"Error setting proxy: {str(e)}")

    def unset_proxy(self):
        """Unset system proxy settings (cross-platform)"""
        try:
            if sys.platform == 'win32':
                # Windows implementation
                import winreg
                key = winreg.HKEY_CURRENT_USER
                subkey = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
                access = winreg.KEY_WRITE

                with winreg.OpenKey(key, subkey, 0, access) as internet_settings_key:
                    winreg.SetValueEx(internet_settings_key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                    winreg.DeleteValue(internet_settings_key, "ProxyServer")

            elif sys.platform == 'darwin':
                # macOS implementation
                networks = subprocess.check_output(["networksetup", "-listallnetworkservices"]).decode('utf-8')
                for service in networks.split('\n')[1:]:  # Skip first line
                    if service.strip():
                        subprocess.run([
                            "networksetup", "-setwebproxystate", service.strip(), "off"
                        ])
                        subprocess.run([
                            "networksetup", "-setsecurewebproxystate", service.strip(), "off"
                        ])
                        subprocess.run([
                            "networksetup", "-setsocksfirewallproxystate", service.strip(), "off"
                        ])
            
            elif sys.platform == 'linux':
                # Linux implementation (GNOME)
                try:
                    subprocess.run([
                        "gsettings", "set", "org.gnome.system.proxy", 
                        "mode", "none"
                    ])
                except:
                    self.log("Could not unset proxy automatically on Linux. Please unset it manually.")
        except Exception as e:
            self.log(f"Error unsetting proxy: {str(e)}")
    
    # Include all the parsing methods from original script
    def vmess_to_json(self, vmess_url):
        if not vmess_url.startswith("vmess://"):
            raise ValueError("Invalid VMess URL format")
        
        base64_str = vmess_url[8:]
        padded = base64_str + '=' * (4 - len(base64_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        decoded_str = decoded_bytes.decode('utf-8')
        vmess_config = json.loads(decoded_str)
        
        xray_config = {
            "inbounds": [{
                "port": self.SOCKS_PORT,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True}
            }],
            "outbounds": [{
                "protocol": "vmess",
                "settings": {
                    "vnext": [{
                        "address": vmess_config["add"],
                        "port": int(vmess_config["port"]),
                        "users": [{
                            "id": vmess_config["id"],
                            "alterId": int(vmess_config.get("aid", 0)),
                            "security": vmess_config.get("scy", "auto")
                        }]
                    }]
                },
                "streamSettings": {
                    "network": vmess_config.get("net", "tcp"),
                    "security": vmess_config.get("tls", ""),
                    "tcpSettings": {
                        "header": {
                            "type": vmess_config.get("type", "none"),
                            "request": {
                                "path": [vmess_config.get("path", "/")],
                                "headers": {
                                    "Host": [vmess_config.get("host", "")]
                                }
                            }
                        }
                    } if vmess_config.get("net") == "tcp" and vmess_config.get("type") == "http" else None
                }
            }]
        }
        
        if not xray_config["outbounds"][0]["streamSettings"]["security"]:
            del xray_config["outbounds"][0]["streamSettings"]["security"]
        if not xray_config["outbounds"][0]["streamSettings"].get("tcpSettings"):
            xray_config["outbounds"][0]["streamSettings"].pop("tcpSettings", None)
        
        return xray_config

    def parse_vless(self, uri):
        parsed = urllib.parse.urlparse(uri)
        config = {
            "inbounds": [{
                "port": self.SOCKS_PORT,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True}
            }],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": parsed.hostname,
                        "port": parsed.port,
                        "users": [{
                            "id": parsed.username,
                            "encryption": parse_qs(parsed.query).get("encryption", ["none"])[0]
                        }]
                    }]
                },
                "streamSettings": {
                    "network": parse_qs(parsed.query).get("type", ["tcp"])[0],
                    "security": parse_qs(parsed.query).get("security", ["none"])[0]
                }
            }]
        }
        return config

    def parse_shadowsocks(self, uri):
        if not uri.startswith("ss://"):
            raise ValueError("Invalid Shadowsocks URI")
        
        parts = uri[5:].split("#", 1)
        encoded_part = parts[0]
        remark = urllib.parse.unquote(parts[1]) if len(parts) > 1 else "Imported Shadowsocks"

        if "@" in encoded_part:
            userinfo, server_part = encoded_part.split("@", 1)
        else:
            decoded = base64.b64decode(encoded_part + '=' * (-len(encoded_part) % 4)).decode('utf-8')
            if "@" in decoded:
                userinfo, server_part = decoded.split("@", 1)
            else:
                userinfo = decoded
                server_part = ""

        if ":" in server_part:
            server, port = server_part.rsplit(":", 1)
            port = int(port)
        else:
            server = server_part
            port = 443

        try:
            decoded_userinfo = base64.b64decode(userinfo + '=' * (-len(userinfo) % 4)).decode('utf-8')
        except:
            decoded_userinfo = base64.b64decode(encoded_part + '=' * (-len(encoded_part) % 4)).decode('utf-8')
            if "@" in decoded_userinfo:
                userinfo_part, server_part = decoded_userinfo.split("@", 1)
                if ":" in server_part:
                    server, port = server_part.rsplit(":", 1)
                    port = int(port)
                decoded_userinfo = userinfo_part

        if ":" not in decoded_userinfo:
            raise ValueError("Invalid Shadowsocks URI")
        
        method, password = decoded_userinfo.split(":", 1)

        config = {
            "inbounds": [{
                "port": self.SOCKS_PORT,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"udp": True}
            }],
            "outbounds": [
                {
                    "protocol": "shadowsocks",
                    "settings": {
                        "servers": [{
                            "address": server,
                            "port": port,
                            "method": method,
                            "password": password
                        }]
                    },
                    "tag": "proxy"
                },
                {
                    "protocol": "freedom",
                    "tag": "direct"
                }
            ],
            "routing": {
                "domainStrategy": "IPOnDemand",
                "rules": [{
                    "type": "field",
                    "ip": ["geoip:private"],
                    "outboundTag": "direct"
                }]
            },
            "geoip": {
                "path": "geoip.dat",
                "code": "geoip.dat"
            },
            "geosite": {
                "path": "dlc.dat",
                "code": "dlc.dat"
            }
        }
        
        return config

    def parse_trojan(self, uri):
        if not uri.startswith("trojan://"):
            raise ValueError("Invalid Trojan URI")
        
        parsed = urllib.parse.urlparse(uri)
        password = parsed.username
        server = parsed.hostname
        port = parsed.port
        query = parse_qs(parsed.query)
        remark = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "Imported Trojan"
        
        # Extract query parameters with defaults
        network = query.get("type", ["tcp"])[0]
        security = "tls"  # Trojan always uses TLS
        sni = query.get("sni", [""])[0]
        host = query.get("host", [""])[0]
        path = query.get("path", [""])[0]
        header_type = query.get("headerType", ["none"])[0]

        # Configure streamSettings based on network type
        stream_settings = {
            "network": network,
            "security": security,
            "tlsSettings": {
                "serverName": sni,
                "allowInsecure": False  # Always enforce TLS security
            }
        }

        # Add transport-specific settings
        if network == "tcp":
            stream_settings["tcpSettings"] = {
                "header": {
                    "type": header_type,
                    "request": {
                        "headers": {
                            "Host": [host] if host else []
                        }
                    }
                }
            }
        elif network == "ws":
            stream_settings["wsSettings"] = {
                "path": path,
                "headers": {
                    "Host": host
                }
            }
        elif network == "grpc":
            stream_settings["grpcSettings"] = {
                "serviceName": path
            }
        
        config = {
            "inbounds": [{
                "port": self.SOCKS_PORT,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {
                    "udp": True,
                    "auth": "noauth"
                }
            }],
            "outbounds": [
                {
                    "protocol": "trojan",
                    "settings": {
                        "servers": [{
                            "address": server,
                            "port": port,
                            "password": password,
                            "email": remark  # Optional: Use remark as email identifier
                        }]
                    },
                    "streamSettings": stream_settings,
                    "tag": "proxy"
                },
                {
                    "protocol": "freedom",
                    "tag": "direct"
                }
            ],
            "routing": {
                "domainStrategy": "IPOnDemand",
                "rules": [
                    {
                        "type": "field",
                        "ip": ["geoip:private"],
                        "outboundTag": "direct"
                    },
                    {
                        "type": "field",
                        "domain": ["geosite:category-ads-all"],
                        "outboundTag": "block"
                    }
                ]
            }
        }
        
        return config

    def parse_protocol(self, uri):
        if uri.startswith("vmess://"):
            return self.vmess_to_json(uri)
        elif uri.startswith("vless://"):
            return self.parse_vless(uri)
        elif uri.startswith("ss://"):
            return self.parse_shadowsocks(uri)
        elif uri.startswith("trojan://"):
            return self.parse_trojan(uri)
        raise ValueError("Unsupported protocol")

    def is_port_available(self, port):
        """Check if a port is available"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except:
                return False

    def get_available_port(self):
        """Get a random available port"""
        for _ in range(10):
            port = random.randint(49152, 65535)
            if self.is_port_available(port):
                return port
        return 1080

    def measure_latency(self, config_uri):
        if self.stop_event.is_set():
            return (config_uri, float('inf'))
            
        try:
            socks_port = self.get_available_port()
            
            if socks_port is None:
                socks_port = 1080 + random.randint(1, 100)
            
            config = self.parse_protocol(config_uri)
            config['inbounds'][0]['port'] = socks_port
            
            rand_suffix = random.randint(100000, 999999)
            temp_config_file = os.path.join(self.TEMP_FOLDER, f"temp_config_{rand_suffix}.json")
            
            with open(temp_config_file, "w", encoding='utf-8') as f:
                json.dump(config, f)
                
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            xray_process = subprocess.Popen(
                [self.XRAY_PATH, "run", "-config", temp_config_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                startupinfo=startupinfo
            )
            
            # Check stop event before proceeding
            if self.stop_event.is_set():
                xray_process.terminate()
                try:
                    os.remove(temp_config_file)
                except:
                    pass
                return (config_uri, float('inf'))
                
            time.sleep(0.1)
            
            proxies = {
                'http': f'socks5://127.0.0.1:{socks_port}',
                'https': f'socks5://127.0.0.1:{socks_port}'
            }
            
            latency = float('inf')
            try:
                start_time = time.perf_counter()
                response = requests.get(
                    self.PING_TEST_URL,
                    proxies=proxies,
                    timeout=10,
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'close'
                    }
                )
                if response.status_code == 200:
                    latency = (time.perf_counter() - start_time) * 1000
            except requests.RequestException:
                pass
            finally:
                xray_process.terminate()
                try:
                    xray_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    xray_process.kill()
                
                try:
                    os.remove(temp_config_file)
                except:
                    pass
                
                time.sleep(0.1)
            
            return (config_uri, latency)
        
        except Exception as e:
            return (config_uri, float('inf'))

    def _load_configs_from_file(self):
        """Load configs from the local configs.txt file."""
        configs = []
        if os.path.exists(self.LOCAL_CONFIGS_FILE):
            try:
                with open(self.LOCAL_CONFIGS_FILE, 'r', encoding='utf-8') as f:
                    configs = [line.strip() for line in f if line.strip()]
                self.log(f"Loaded {len(configs)} configs from {self.LOCAL_CONFIGS_FILE}")
            except Exception as e:
                self.log(f"Error reading local configs file: {str(e)}")
                messagebox.showerror("Error", f"Could not read configs.txt: {e}")
        else:
            self.log(f"Local configs file not found: {self.LOCAL_CONFIGS_FILE}")
            messagebox.showinfo("Info", f"'{self.LOCAL_CONFIGS_FILE}' not found. Please create it next to the executable.")
        return configs

    def update_xray_core(self):
        """Update Xray core executable"""
        self.log("Starting Xray core update...")
        thread = threading.Thread(target=self._update_xray_core_worker, daemon=True)
        thread.start()

    def _update_xray_core_worker(self):
        """Worker thread for updating Xray core"""
        try:
            # Kill any running Xray processes
            self.kill_existing_xray_processes()
            
            self.log("Downloading latest Xray core...")
            response = requests.get(self.XRAY_CORE_URL, stream=True)
            response.raise_for_status()
            
            # Get the total file size from headers
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Save the downloaded zip file
            zip_path = os.path.join(self.TEMP_FOLDER, "xray_update.zip")
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Calculate progress percentage
                        progress = (downloaded / total_size) * 100
                        # Update log with progress
                        self.log(f"Download progress: {progress:.1f}% ({downloaded}/{total_size} bytes)")
            
            self.log("Extracting Xray core...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get total number of files for progress tracking
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                extracted_files = 0
                
                for file in file_list:
                    zip_ref.extract(file, self.TEMP_FOLDER)
                    extracted_files += 1
                    progress = (extracted_files / total_files) * 100
                    self.log(f"Extraction progress: {progress:.1f}% ({extracted_files}/{total_files} files)")
                    
                    # Check if this is the xray.exe file
                    if file.lower().endswith('xray.exe'):
                        # Move it to the main directory
                        extracted_path = os.path.join(self.TEMP_FOLDER, file)
                        shutil.move(extracted_path, self.XRAY_PATH)
            
            self.log("Xray core updated successfully!")
            messagebox.showinfo("Success", "Xray core updated successfully!")
            
        except Exception as e:
            self.log(f"Error updating Xray core: {str(e)}")
            messagebox.showerror("Error", f"Failed to update Xray core: {str(e)}")
        finally:
            # Clean up
            try:
                os.remove(zip_path)
            except:
                pass

    def update_geofiles(self):
        """Update GeoFiles (geoip.dat and geosite.dat)"""
        self.log("Starting GeoFiles update...")
        thread = threading.Thread(target=self._update_geofiles_worker, daemon=True)
        thread.start()

    def _update_geofiles_worker(self):
        """Worker thread for updating GeoFiles"""
        try:
            # URLs for GeoFiles
            geoip_url = self.GEOIP_URL
            geosite_url = self.GEOSITE_URL
            
            # Download geoip.dat with progress
            self.log("Downloading geoip.dat...")
            response = requests.get(geoip_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open("geoip.dat", 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = (downloaded / total_size) * 100
                        self.log(f"geoip.dat: {progress:.1f}% ({downloaded}/{total_size} bytes)")
            
            self.log("geoip.dat download complete!")
            
            # Download dlc.dat with progress
            self.log("Downloading dlc.dat...")
            response = requests.get(geosite_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open("dlc.dat", 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = (downloaded / total_size) * 100
                        self.log(f"dlc.dat: {progress:.1f}% ({downloaded}/{total_size} bytes)")
            
            self.log("geosite.dat download complete!")
            self.log("GeoFiles updated successfully!")
            messagebox.showinfo("Success", "GeoFiles updated successfully!")
            
        except Exception as e:
            self.log(f"Error updating GeoFiles: {str(e)}")
            self.log("")
            self.log("You can manually download the required files:")
            self.log(f"1. GeoIP file: {geoip_url}")
            self.log(f"2. Geosite file: {geosite_url}")
            self.log("")
            self.log("Instructions:")
            self.log("1. Download both files using the links above")
            self.log("2. Place them in the same directory as this program")
            self.log("3. Make sure they are named exactly:")
            self.log("   - geoip.dat")
            self.log("   - dlc.dat")
            self.log("4. Restart the program if needed")
    
    def fetch_configs(self, custom_url=None):
        """Fetch configs from the specified URL (either mirror or custom)"""
        url_to_fetch = custom_url if custom_url else self.CONFIGS_URL
        try:
            response = requests.get(url_to_fetch)
            response.raise_for_status()
            response.encoding = 'utf-8'  # Explicitly set UTF-8 encoding
            configs = [line.strip() for line in response.text.splitlines() if line.strip()]
            return configs[::-1]  # Reverse the list before returning
        except Exception as e:
            self.log(f"Error fetching configs from {url_to_fetch}: {str(e)}")
            messagebox.showerror("Error", f"Failed to fetch configs from {url_to_fetch}: {e}")
            return []

def main():
    # Kill any existing Xray processes
    kill_xray_processes()
    
    # Create root window
    root = tk.Tk()
    
    # Set window title with platform info
    platform_name = platform.system()
    if platform_name == "Darwin":
        platform_name = "macOS"
    root.title(f"VPN Config Manager ({platform_name})")
    
    # Create and run application
    app = VPNConfigGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
