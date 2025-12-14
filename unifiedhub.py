import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from PIL import ImageTk
import webbrowser
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import socket
from dotenv import load_dotenv
from mistralai import Mistral
import psutil
import urllib3

load_dotenv()

# Suppress insecure request warnings due to verify=False in some network calls
try:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass


class ReuseAddrHTTPServer(HTTPServer):
    """HTTP Server that allows port reuse"""
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        super().server_bind()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles OAuth callback from browser"""
    auth_code = None
    
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            OAuthCallbackHandler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">Authentication Successful!</h1>
                <p>You can close this window and return to the dashboard.</p>
                </body></html>
            ''')
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


class DashboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UnifiedHub")
        self.root.geometry("1150x820")
        self.root.configure(bg='#f0f0f0')
        
        self.tokens = {
            'google': None,
            'google_refresh': None,
            'discord': None
        }
        
        self.discord_servers = []
        self.discord_btn = None
        self.templates_file = os.path.join(os.path.dirname(__file__), 'templates.json')
        self.sysmon_job = None

        self.settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        self.settings = self.load_settings()
        self.dark_mode = self.settings.get('dark_mode', False)
        
        self.setup_ui()
        self.apply_settings_to_widgets()
        self.load_saved_tokens()
    
    def setup_ui(self):
        """Setup the main UI"""
        # Control bar
        control_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        control_frame.pack(fill=tk.X, padx=0, pady=0)
        control_frame.pack_propagate(False)
        
        self.google_btn = tk.Button(control_frame, text="🔗 Connect Google", command=self.connect_google, 
                                   bg='#3498db', fg='white', padx=15, pady=8, font=('Arial', 10, 'bold'))
        self.google_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Discord connect
        self.discord_btn = tk.Button(control_frame, text="🔗 Connect Discord", command=self.connect_discord,
                        bg='#7289da', fg='white', padx=15, pady=8, font=('Arial', 10, 'bold'))
        self.discord_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        refresh_btn = tk.Button(control_frame, text="🔄 Refresh All", command=self.refresh_all_data,
                       bg='#27ae60', fg='white', padx=15, pady=8, font=('Arial', 10, 'bold'))
        refresh_btn.pack(side=tk.LEFT, padx=10, pady=10)
        
        clear_btn = tk.Button(control_frame, text="🗑️ Clear Tokens", command=self.clear_tokens,
                             bg='#e74c3c', fg='white', padx=15, pady=8, font=('Arial', 10, 'bold'))
        clear_btn.pack(side=tk.LEFT, padx=10, pady=10)

        exit_btn = tk.Button(control_frame, text="⏻ Exit", command=self.root.quit,
                     bg='#7f8c8d', fg='white', padx=12, pady=8, font=('Arial', 10, 'bold'))
        exit_btn.pack(side=tk.RIGHT, padx=10, pady=10)
        
        # Per-account logout
        logout_frame = tk.Frame(control_frame, bg='#2c3e50')
        logout_frame.pack(side=tk.LEFT, padx=10)
        tk.Button(logout_frame, text="Logout Google", command=self.logout_google,
              bg='#e67e22', fg='white', padx=10, pady=6, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(logout_frame, text="Logout Discord", command=self.logout_discord,
              bg='#e67e22', fg='white', padx=10, pady=6, font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(control_frame, text="Ready", fg='white', bg='#2c3e50', font=('Arial', 9))
        self.status_label.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.setup_google_tab()
        self.setup_discord_tab()
        self.setup_mistral_tab()
        self.setup_search_engine_tab()
        self.setup_basics_tab()
        self.setup_news_tab()
        self.setup_quotes_tab()
        self.setup_website_viewer_tab()
        self.setup_settings_tab()
    
    def setup_google_tab(self):
        google_frame = ttk.Frame(self.notebook)
        self.notebook.add(google_frame, text="🟦 Google")

        # Inner notebook for selectable sub-tabs
        inner = ttk.Notebook(google_frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Emails tab
        emails_tab = ttk.Frame(inner)
        inner.add(emails_tab, text="Emails")
        emails_controls = tk.Frame(emails_tab)
        emails_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(emails_controls, text="Limit:").pack(side=tk.LEFT, padx=5)
        self.email_limit = tk.Spinbox(emails_controls, from_=1, to=50, width=5)
        self.email_limit.insert(0, 10)
        self.email_limit.pack(side=tk.LEFT, padx=5)
        tk.Button(emails_controls, text="Load", command=self.load_gmail_data).pack(side=tk.LEFT, padx=5)
        tk.Button(emails_controls, text="Compose", command=self.compose_email).pack(side=tk.LEFT, padx=5)
        tk.Button(emails_controls, text="Unread Count", command=self.load_gmail_unread_count).pack(side=tk.LEFT, padx=5)
        tk.Label(emails_controls, text="Filter sender:").pack(side=tk.LEFT, padx=5)
        self.gmail_sender_filter = tk.Entry(emails_controls, width=24)
        self.gmail_sender_filter.pack(side=tk.LEFT)
        tk.Button(emails_controls, text="Apply", command=self.apply_gmail_sender_filter).pack(side=tk.LEFT, padx=5)
        
        email_body = tk.Frame(emails_tab)
        email_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        left_frame = tk.Frame(email_body, width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left_frame, text="Inbox:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        list_scroll = tk.Scrollbar(left_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.gmail_listbox = tk.Listbox(left_frame, yscrollcommand=list_scroll.set)
        self.gmail_listbox.pack(fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.gmail_listbox.yview)
        self.gmail_listbox.bind('<<ListboxSelect>>', self.on_email_select)
        
        right_frame = tk.Frame(email_body)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0))
        tk.Label(right_frame, text="Full Email:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        self.gmail_text = scrolledtext.ScrolledText(right_frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.gmail_text.pack(fill=tk.BOTH, expand=True)
        self.gmail_text.config(state=tk.DISABLED)
        
        self.emails_cache = []

        # Calendar tab
        cal_tab = ttk.Frame(inner)
        inner.add(cal_tab, text="Calendar")
        cal_controls = tk.Frame(cal_tab)
        cal_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(cal_controls, text="Load", command=self.load_calendar_data).pack(side=tk.LEFT, padx=5)
        tk.Button(cal_controls, text="New Event", command=self.create_calendar_event).pack(side=tk.LEFT, padx=5)
        tk.Button(cal_controls, text="Delete Selected", command=self.delete_selected_calendar_event).pack(side=tk.LEFT, padx=5)
        self.calendar_text = scrolledtext.ScrolledText(cal_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.calendar_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.calendar_text.config(state=tk.DISABLED)

        # Tasks tab
        tasks_tab = ttk.Frame(inner)
        inner.add(tasks_tab, text="Tasks")
        tasks_controls = tk.Frame(tasks_tab)
        tasks_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(tasks_controls, text="Load", command=self.load_tasks_data).pack(side=tk.LEFT, padx=5)
        tk.Button(tasks_controls, text="New Task", command=self.create_task).pack(side=tk.LEFT, padx=5)
        tk.Button(tasks_controls, text="Mark Selected Complete", command=self.complete_selected_task).pack(side=tk.LEFT, padx=5)
        self.tasks_text = scrolledtext.ScrolledText(tasks_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.tasks_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tasks_text.config(state=tk.DISABLED)

        # store reference if needed later
        self.google_inner_notebook = inner

        # Profile tab
        profile_tab = ttk.Frame(inner)
        inner.add(profile_tab, text="Profile")
        prof_controls = tk.Frame(profile_tab)
        prof_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(prof_controls, text="Load", command=self.load_google_profile).pack(side=tk.LEFT, padx=5)
        self.profile_text = scrolledtext.ScrolledText(profile_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.profile_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.profile_text.config(state=tk.DISABLED)

        # Drive tab
        drive_tab = ttk.Frame(inner)
        inner.add(drive_tab, text="Drive")
        drive_controls = tk.Frame(drive_tab)
        drive_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(drive_controls, text="Load Files", command=self.load_drive_files).pack(side=tk.LEFT, padx=5)
        tk.Button(drive_controls, text="Find", command=self.search_drive_files).pack(side=tk.LEFT, padx=5)
        tk.Button(drive_controls, text="Open in Browser", command=self.open_selected_drive_in_browser).pack(side=tk.LEFT, padx=5)
        tk.Button(drive_controls, text="Download", command=self.download_selected_drive_file).pack(side=tk.LEFT, padx=5)
        drive_content = tk.Frame(drive_tab)
        drive_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left = tk.Frame(drive_content)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text="Files:").pack(anchor=tk.W)
        dscroll = tk.Scrollbar(left)
        dscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.drive_listbox = tk.Listbox(left, yscrollcommand=dscroll.set)
        self.drive_listbox.pack(fill=tk.BOTH, expand=True)
        dscroll.config(command=self.drive_listbox.yview)
        self.drive_listbox.bind('<<ListboxSelect>>', self.on_drive_file_select)

        right = tk.Frame(drive_content, width=420)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)
        right.pack_propagate(False)
        tk.Label(right, text="Preview:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.drive_text = scrolledtext.ScrolledText(right, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.drive_text.pack(fill=tk.BOTH, expand=True)
        self.drive_text.config(state=tk.DISABLED)

        # Gmail Labels tab
        labels_tab = ttk.Frame(inner)
        inner.add(labels_tab, text="Labels")
        lab_controls = tk.Frame(labels_tab)
        lab_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(lab_controls, text="Load", command=self.load_gmail_labels).pack(side=tk.LEFT, padx=5)
        self.labels_text = scrolledtext.ScrolledText(labels_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.labels_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.labels_text.config(state=tk.DISABLED)

        # YouTube tab
        youtube_tab = ttk.Frame(inner)
        inner.add(youtube_tab, text="YouTube")
        yt_controls = tk.Frame(youtube_tab)
        yt_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(yt_controls, text="Load Subscriptions", command=self.load_youtube_subscriptions).pack(side=tk.LEFT, padx=5)
        self.youtube_text = scrolledtext.ScrolledText(youtube_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.youtube_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.youtube_text.config(state=tk.DISABLED)

        # Contacts tab
        contacts_tab = ttk.Frame(inner)
        inner.add(contacts_tab, text="Contacts")
        contacts_controls = tk.Frame(contacts_tab)
        contacts_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Button(contacts_controls, text="Load Contacts", command=self.load_google_contacts).pack(side=tk.LEFT, padx=5)
        self.contacts_text = scrolledtext.ScrolledText(contacts_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.contacts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.contacts_text.config(state=tk.DISABLED)

        # Keep Notes tab
        keep_tab = ttk.Frame(inner)
        inner.add(keep_tab, text="Keep Notes")
        keep_controls = tk.Frame(keep_tab)
        keep_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(keep_controls, text="Title:").pack(side=tk.LEFT, padx=5)
        self.keep_title = tk.Entry(keep_controls, width=30)
        self.keep_title.pack(side=tk.LEFT, padx=5)
        tk.Button(keep_controls, text="Create Note", command=self.create_keep_note).pack(side=tk.LEFT, padx=5)
        tk.Label(keep_tab, text="Content:").pack(anchor=tk.W, padx=10, pady=(10,0))
        self.keep_content = scrolledtext.ScrolledText(keep_tab, height=15, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.keep_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Translate tab
        translate_tab = ttk.Frame(inner)
        inner.add(translate_tab, text="Translate")
        trans_controls = tk.Frame(translate_tab)
        trans_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(trans_controls, text="To:").pack(side=tk.LEFT, padx=5)
        self.translate_target = ttk.Combobox(trans_controls, width=12, values=['es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh-CN', 'ar'])
        self.translate_target.set('es')
        self.translate_target.pack(side=tk.LEFT, padx=5)
        tk.Button(trans_controls, text="Translate", command=self.translate_text).pack(side=tk.LEFT, padx=5)
        tk.Label(translate_tab, text="Source Text:").pack(anchor=tk.W, padx=10, pady=(10,0))
        self.translate_source = scrolledtext.ScrolledText(translate_tab, height=8, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.translate_source.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(translate_tab, text="Translation:").pack(anchor=tk.W, padx=10)
        self.translate_result = scrolledtext.ScrolledText(translate_tab, height=8, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.translate_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.translate_result.config(state=tk.DISABLED)

        # Drive Upload tab
        drive_tab = ttk.Frame(inner)
        inner.add(drive_tab, text="Drive Upload")
        drive_controls = tk.Frame(drive_tab, bg='#ecf0f1')
        drive_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(drive_controls, text="Select File", command=self.select_drive_file).pack(side=tk.LEFT, padx=5)
        self.drive_upload_path = tk.StringVar()
        self.drive_upload_name = tk.StringVar()
        tk.Label(drive_controls, text="File:").pack(side=tk.LEFT, padx=5)
        tk.Label(drive_controls, textvariable=self.drive_upload_name, width=30).pack(side=tk.LEFT, padx=5)
        tk.Button(drive_controls, text="Upload", command=self.upload_drive_file, bg='#34a853', fg='white').pack(side=tk.LEFT, padx=5)
        self.drive_upload_status = tk.Label(drive_tab, text="Select a file to upload", bg='#ecf0f1', fg='#2c3e50')
        self.drive_upload_status.pack(fill=tk.X, padx=10, pady=4)

        # Calendar Agenda tab
        agenda_tab = ttk.Frame(inner)
        inner.add(agenda_tab, text="Agenda")
        agenda_controls = tk.Frame(agenda_tab, bg='#ecf0f1')
        agenda_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(agenda_controls, text="Load 7-Day Agenda", command=self.load_calendar_agenda).pack(side=tk.LEFT, padx=5)
        self.agenda_text = scrolledtext.ScrolledText(agenda_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.agenda_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.agenda_text.config(state=tk.DISABLED)

        # Templates tab
        templates_tab = ttk.Frame(inner)
        inner.add(templates_tab, text="Templates")
        template_controls = tk.Frame(templates_tab, bg='#ecf0f1')
        template_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(template_controls, text="Template:").pack(side=tk.LEFT, padx=5)
        self.template_name_input = tk.Entry(template_controls, width=40)
        self.template_name_input.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(template_controls, text="Add", command=self.add_template).pack(side=tk.LEFT, padx=5)
        tk.Button(template_controls, text="Delete Selected", command=self.delete_template).pack(side=tk.LEFT, padx=5)
        
        template_body = tk.Frame(templates_tab)
        template_body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(template_body, text="Templates:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        list_scroll = tk.Scrollbar(template_body)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.template_listbox = tk.Listbox(template_body, yscrollcommand=list_scroll.set)
        self.template_listbox.pack(fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.template_listbox.yview)
        self.template_listbox.bind('<<ListboxSelect>>', self.on_template_select)
        
        template_right = tk.Frame(template_body)
        template_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10,0))
        tk.Label(template_right, text="Preview:", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        self.template_preview = scrolledtext.ScrolledText(template_right, height=15, width=50, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.template_preview.pack(fill=tk.BOTH, expand=True)
        tk.Button(template_right, text="Copy to Clipboard", command=self.copy_template_to_clipboard, bg='#3498db', fg='white').pack(fill=tk.X, pady=4)

        # Maps Search tab
        maps_tab = ttk.Frame(inner)
        inner.add(maps_tab, text="Maps")
        maps_controls = tk.Frame(maps_tab)
        maps_controls.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(maps_controls, text="Search:").pack(side=tk.LEFT, padx=5)
        self.maps_query = tk.Entry(maps_controls, width=40)
        self.maps_query.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(maps_controls, text="Find", command=self.search_maps).pack(side=tk.LEFT, padx=5)
        tk.Button(maps_controls, text="Open in Browser", command=self.open_maps_browser).pack(side=tk.LEFT, padx=5)
        self.maps_text = scrolledtext.ScrolledText(maps_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.maps_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.maps_text.config(state=tk.DISABLED)

    def load_settings(self):
        default = {
            'default_search_engine': 'Google',
            'dark_mode': False,
            'font_size': 10,
            'verify_ssl': False,
            'results_limit': 10,
            'theme_accent': '#3498db'
        }
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    default.update(data)
        except Exception:
            pass
        return default

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Settings", f"Failed to save settings: {str(e)}")

    def apply_settings_to_widgets(self):
        try:
            if hasattr(self, 'search_engine'):
                self.search_engine.set(self.settings.get('default_search_engine', 'Google'))
            self.apply_dark_mode(self.settings.get('dark_mode', False), persist=False)
        except Exception:
            pass

    def apply_dark_mode(self, enabled: bool, persist: bool = True):
        self.dark_mode = enabled
        if persist:
            self.settings['dark_mode'] = enabled
            self.save_settings()
        
        if enabled:
            bg = '#1a1a1a'
            fg = '#ecf0f1'
            text_bg = '#2d2d2d'
            text_fg = '#ecf0f1'
            btn_bg = '#3b82f6'
            accent = self.settings.get('theme_accent', '#3498db')
        else:
            bg = '#f0f0f0'
            fg = '#2c3e50'
            text_bg = '#ffffff'
            text_fg = '#2c3e50'
            btn_bg = '#3498db'
            accent = self.settings.get('theme_accent', '#3498db')
        
        try:
            self.root.configure(bg=bg)
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('.', background=bg, foreground=fg)
            style.configure('TFrame', background=bg, foreground=fg)
            style.configure('TNotebook', background=bg, foreground=fg)
            style.configure('TNotebook.Tab', background=bg, foreground=fg)
            style.configure('TLabel', background=bg, foreground=fg)
            style.configure('TButton', background=btn_bg, foreground='white')
            style.configure('TCombobox', fieldbackground=text_bg, background=text_bg, foreground=text_fg)
            style.configure('TCheckbutton', background=bg, foreground=fg)
        except Exception:
            pass
        
        # Recursively apply theme to all widgets
        self._apply_theme_recursive(self.root, bg, fg, text_bg, text_fg, btn_bg)
    
    def _apply_theme_recursive(self, widget, bg, fg, text_bg, text_fg, btn_bg):
        """Recursively apply dark/light theme to all widgets."""
        try:
            wtype = type(widget).__name__
            if wtype in ('Text', 'Entry', 'Spinbox'):
                widget.config(bg=text_bg, fg=text_fg, insertbackground=text_fg)
            elif wtype in ('Frame', 'LabelFrame'):
                widget.config(bg=bg)
            elif wtype in ('Label', 'LabelFrame'):
                widget.config(bg=bg, fg=fg)
            elif wtype == 'Button':
                widget.config(bg=btn_bg, fg='white')
            elif wtype in ('Canvas', 'Listbox'):
                widget.config(bg=text_bg, fg=text_fg)
            elif hasattr(widget, 'configure'):
                try:
                    widget.config(bg=bg, fg=fg)
                except Exception:
                    try:
                        widget.config(bg=bg)
                    except Exception:
                        pass
        except Exception:
            pass
        
        for child in widget.winfo_children():
            self._apply_theme_recursive(child, bg, fg, text_bg, text_fg, btn_bg)

    def setup_settings_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ Settings")

        bg = '#2d2d2d' if self.dark_mode else '#ecf0f1'
        container = tk.Frame(frame, bg=bg)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Default search engine
        lbl_bg = bg
        lbl_fg = '#ecf0f1' if self.dark_mode else '#2c3e50'
        tk.Label(container, text="Default Search Engine:", bg=lbl_bg, fg=lbl_fg).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.settings_default_engine = ttk.Combobox(container, values=['Google', 'DuckDuckGo', 'Bing', 'Wikipedia'], width=20)
        self.settings_default_engine.set(self.settings.get('default_search_engine', 'Google'))
        self.settings_default_engine.grid(row=0, column=1, sticky='w', padx=5, pady=5)

        # Font size
        tk.Label(container, text="Font Size:", bg=lbl_bg, fg=lbl_fg).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.settings_font_size = tk.Spinbox(container, from_=8, to=16, width=5, bg='white', fg='black')
        self.settings_font_size.delete(0, tk.END)
        self.settings_font_size.insert(0, self.settings.get('font_size', 10))
        self.settings_font_size.grid(row=1, column=1, sticky='w', padx=5, pady=5)

        # Verify SSL
        self.verify_ssl_var = tk.BooleanVar(value=self.settings.get('verify_ssl', False))
        tk.Checkbutton(container, text="Verify SSL Certificates", variable=self.verify_ssl_var, bg=lbl_bg, fg=lbl_fg).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        # Results limit
        tk.Label(container, text="Search Results Limit:", bg=lbl_bg, fg=lbl_fg).grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.settings_results_limit = tk.Spinbox(container, from_=5, to=50, width=5, bg='white', fg='black')
        self.settings_results_limit.delete(0, tk.END)
        self.settings_results_limit.insert(0, self.settings.get('results_limit', 10))
        self.settings_results_limit.grid(row=3, column=1, sticky='w', padx=5, pady=5)

        # Dark mode toggle
        self.dark_mode_var = tk.BooleanVar(value=self.settings.get('dark_mode', False))
        dark_cb = tk.Checkbutton(container, text="Enable Dark Mode", variable=self.dark_mode_var, bg=lbl_bg, fg=lbl_fg, command=lambda: self.apply_dark_mode(self.dark_mode_var.get()))
        dark_cb.grid(row=4, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        btns = tk.Frame(container, bg=lbl_bg)
        btns.grid(row=5, column=0, columnspan=2, sticky='w', padx=5, pady=10)
        tk.Button(btns, text="Save Settings", command=self.save_settings_from_ui, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text="Reset Defaults", command=self.reset_settings, bg='#e67e22', fg='white').pack(side=tk.LEFT, padx=5)

        for i in range(2):
            container.columnconfigure(i, weight=1)

    def save_settings_from_ui(self):
        self.settings['default_search_engine'] = self.settings_default_engine.get() or 'Google'
        self.settings['dark_mode'] = bool(self.dark_mode_var.get())
        self.settings['font_size'] = int(self.settings_font_size.get() or 10)
        self.settings['verify_ssl'] = bool(self.verify_ssl_var.get())
        self.settings['results_limit'] = int(self.settings_results_limit.get() or 10)
        self.save_settings()
        self.apply_settings_to_widgets()
        messagebox.showinfo("Settings", "Settings saved and applied")

    def reset_settings(self):
        self.settings = {
            'default_search_engine': 'Google',
            'dark_mode': False,
            'font_size': 10,
            'verify_ssl': False,
            'results_limit': 10,
            'theme_accent': '#3498db'
        }
        self.save_settings()
        if hasattr(self, 'settings_default_engine'):
            self.settings_default_engine.set('Google')
        if hasattr(self, 'settings_font_size'):
            self.settings_font_size.delete(0, tk.END)
            self.settings_font_size.insert(0, 10)
        if hasattr(self, 'settings_results_limit'):
            self.settings_results_limit.delete(0, tk.END)
            self.settings_results_limit.insert(0, 10)
        if hasattr(self, 'verify_ssl_var'):
            self.verify_ssl_var.set(False)
        if hasattr(self, 'dark_mode_var'):
            self.dark_mode_var.set(False)
        self.apply_settings_to_widgets()

    def setup_discord_tab(self):
        discord_frame = ttk.Frame(self.notebook)
        self.notebook.add(discord_frame, text="🟣 Discord")

        # Inner notebook for Discord sub-tabs
        inner = ttk.Notebook(discord_frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Servers tab
        servers_tab = ttk.Frame(inner)
        inner.add(servers_tab, text="Servers")
        
        hdr = tk.Frame(servers_tab, bg='#ecf0f1')
        hdr.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(hdr, text="Load Servers", command=self.load_discord_servers).pack(side=tk.LEFT, padx=5)

        content = tk.Frame(servers_tab)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        list_frame = tk.Frame(content)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(list_frame, text="Servers:").pack(anchor=tk.W)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.discord_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.discord_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.discord_listbox.yview)
        self.discord_listbox.bind('<<ListboxSelect>>', self.on_discord_server_select)

        detail_frame = tk.Frame(content, width=380)
        detail_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)
        detail_frame.pack_propagate(False)
        tk.Label(detail_frame, text="Details:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.discord_details = scrolledtext.ScrolledText(detail_frame, height=25, width=50, wrap=tk.WORD,
                                                         bg='white', fg='#2c3e50', font=('Courier', 9))
        self.discord_details.pack(fill=tk.BOTH, expand=True)
        self.discord_details.config(state=tk.DISABLED)

        # DM tab
        dm_tab = ttk.Frame(inner)
        inner.add(dm_tab, text="Send DMs")
        
        info = tk.Frame(dm_tab, bg='#ecf0f1')
        info.pack(fill=tk.X, padx=10, pady=10)
        msg = (
            "DMs over OAuth are restricted. With a bot token, you can SEND a DM to a user (cannot read existing DMs).\n"
            "Add DISCORD_BOT_TOKEN to .env."
        )
        tk.Label(info, text=msg, bg='#ecf0f1', justify=tk.LEFT, wraplength=700).pack(anchor=tk.W, pady=6)
        tk.Button(info, text="Open Discord DMs in Browser", command=lambda: webbrowser.open('https://discord.com/channels/@me'), bg='#7289da', fg='white').pack(anchor=tk.W, padx=5, pady=4)

        form = tk.Frame(dm_tab)
        form.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(form, text="User ID:").grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.dm_user_id = tk.Entry(form, width=30)
        self.dm_user_id.grid(row=0, column=1, sticky='we', padx=4, pady=4)
        tk.Label(form, text="Message:").grid(row=1, column=0, sticky='nw', padx=4, pady=4)
        self.dm_message = scrolledtext.ScrolledText(form, height=6, width=60, wrap=tk.WORD)
        self.dm_message.grid(row=1, column=1, sticky='we', padx=4, pady=4)
        form.columnconfigure(1, weight=1)
        tk.Button(form, text="Send DM", command=self.send_discord_dm, bg='#5865F2', fg='white').grid(row=2, column=1, sticky='w', padx=4, pady=6)

        self.dm_status = tk.Label(dm_tab, text="Enter user ID and message", bg='#ecf0f1', fg='#2c3e50')
        self.dm_status.pack(fill=tk.X, padx=10, pady=4)

    def setup_mistral_tab(self):
        mistral_frame = ttk.Frame(self.notebook)
        self.notebook.add(mistral_frame, text="🤖 UnifiedHub AI")

        # API Key setup
        key_frame = tk.Frame(mistral_frame, bg='#ecf0f1')
        key_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(key_frame, text="API Key:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.mistral_api_key = tk.Entry(key_frame, width=50, show='*')
        self.mistral_api_key.pack(side=tk.LEFT, padx=5)
        # Load from env if available
        mistral_key = os.getenv('MISTRAL_API_KEY', '')
        if mistral_key:
            self.mistral_api_key.insert(0, mistral_key)
        tk.Button(key_frame, text="Save Key", command=self.save_mistral_key).pack(side=tk.LEFT, padx=5)

        # Mode selection (Chat vs Agent)
        mode_frame = tk.Frame(mistral_frame, bg='#ecf0f1')
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(mode_frame, text="Mode:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.mistral_mode = ttk.Combobox(mode_frame, width=15, values=['Chat', 'Agent'], state='readonly')
        self.mistral_mode.set('Chat')
        self.mistral_mode.pack(side=tk.LEFT, padx=5)
        self.mistral_mode.bind('<<ComboboxSelected>>', lambda e: self.on_mistral_mode_change())
        
        # Agent ID field (hidden by default)
        tk.Label(mode_frame, text="Agent ID:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.mistral_agent_id = tk.Entry(mode_frame, width=30)
        self.mistral_agent_id.pack(side=tk.LEFT, padx=5)
        agent_id = os.getenv('MISTRAL_AI_AGENT_ID', '')
        if agent_id:
            self.mistral_agent_id.insert(0, agent_id)

        # Model selection (for chat mode)
        model_frame = tk.Frame(mistral_frame, bg='#ecf0f1')
        model_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(model_frame, text="Model:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.mistral_model = ttk.Combobox(model_frame, width=40, values=[
            'mistral-small-latest',
            'mistral-medium-latest',
            'mistral-large-latest',
            'open-mistral-7b',
            'open-mixtral-8x7b',
            'open-mixtral-8x22b'
        ])
        self.mistral_model.set('mistral-small-latest')
        self.mistral_model.pack(side=tk.LEFT, padx=5)
        tk.Button(model_frame, text="List Models", command=self.list_mistral_models).pack(side=tk.LEFT, padx=5)
        tk.Button(model_frame, text="Clear Chat", command=self.clear_mistral_chat).pack(side=tk.LEFT, padx=5)

        # Chat display
        self.mistral_chat = scrolledtext.ScrolledText(mistral_frame, height=25, wrap=tk.WORD,
                                                       bg='white', fg='#2c3e50', font=('Courier', 9))
        self.mistral_chat.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.mistral_chat.config(state=tk.DISABLED)

        # Input area
        input_frame = tk.Frame(mistral_frame)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(input_frame, text="Message:").pack(side=tk.LEFT, padx=5)
        self.mistral_input = tk.Entry(input_frame, width=80)
        self.mistral_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.mistral_input.bind('<Return>', lambda e: self.send_mistral_message())
        tk.Button(input_frame, text="Send", command=self.send_mistral_message, bg='#5865F2', fg='white',
                 padx=15, pady=5, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        # Chat history for context (chat mode) and agent conversation ID (agent mode)
        self.mistral_history = []
        self.mistral_agent_conversation_id = None
        
    def on_mistral_mode_change(self):
        """Handle mode change between Chat and Agent"""
        mode = self.mistral_mode.get()
        if mode == 'Chat':
            self.mistral_history = []
            self.mistral_agent_conversation_id = None
        elif mode == 'Agent':
            self.mistral_history = []
            self.mistral_agent_conversation_id = None
        self.clear_mistral_chat()

    def setup_drive_upload_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📤 Drive Upload")

        top = tk.Frame(frame, bg='#ecf0f1')
        top.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(top, text="File:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.drive_upload_path = tk.StringVar()
        path_entry = tk.Entry(top, textvariable=self.drive_upload_path, width=60)
        path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Button(top, text="Choose", command=self.select_drive_file).pack(side=tk.LEFT, padx=5)

        name_row = tk.Frame(frame, bg='#ecf0f1')
        name_row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(name_row, text="Upload As:", bg='#ecf0f1').pack(side=tk.LEFT, padx=5)
        self.drive_upload_name = tk.StringVar()
        tk.Entry(name_row, textvariable=self.drive_upload_name, width=50).pack(side=tk.LEFT, padx=5)
        tk.Button(name_row, text="Upload", command=self.upload_drive_file, bg='#27ae60', fg='white').pack(side=tk.LEFT, padx=5)

        status_row = tk.Frame(frame, bg='#ecf0f1')
        status_row.pack(fill=tk.X, padx=10, pady=5)
        self.drive_upload_status = tk.Label(status_row, text="Select a file to upload", bg='#ecf0f1', fg='#2c3e50')
        self.drive_upload_status.pack(anchor=tk.W)

    def setup_calendar_agenda_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🗓️ Agenda 7d")

        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Load Agenda", command=self.load_calendar_agenda).pack(side=tk.LEFT, padx=5)

        self.calendar_agenda_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.calendar_agenda_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.calendar_agenda_text.config(state=tk.DISABLED)

    def setup_gmail_templates_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📨 Gmail Templates")

        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Add", command=self.add_template).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Delete", command=self.delete_template).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Copy to Clipboard", command=self.copy_template_to_clipboard).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Refresh", command=self.refresh_templates).pack(side=tk.LEFT, padx=5)

        body = tk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = tk.Frame(body, width=240)
        left.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(left, text="Templates:").pack(anchor=tk.W)
        lscroll = tk.Scrollbar(left)
        lscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.template_listbox = tk.Listbox(left, yscrollcommand=lscroll.set, width=30)
        self.template_listbox.pack(fill=tk.BOTH, expand=True)
        lscroll.config(command=self.template_listbox.yview)
        self.template_listbox.bind('<<ListboxSelect>>', lambda e: self.show_template_preview())

        right = tk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        tk.Label(right, text="Preview:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.template_preview = scrolledtext.ScrolledText(right, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.template_preview.pack(fill=tk.BOTH, expand=True)
        self.template_preview.config(state=tk.DISABLED)

        self.refresh_templates()

    def setup_discord_dm_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="💬 Discord DMs")

        info = tk.Frame(frame, bg='#ecf0f1')
        info.pack(fill=tk.X, padx=10, pady=10)
        msg = (
            "DMs over OAuth are restricted. With a bot token, you can SEND a DM to a user (cannot read existing DMs).\n"
            "Add DISCORD_BOT_TOKEN to .env."
        )
        tk.Label(info, text=msg, bg='#ecf0f1', justify=tk.LEFT, wraplength=700).pack(anchor=tk.W, pady=6)
        tk.Button(info, text="Open Discord DMs in Browser", command=lambda: webbrowser.open('https://discord.com/channels/@me'), bg='#7289da', fg='white').pack(anchor=tk.W, padx=5, pady=4)

        form = tk.Frame(frame)
        form.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(form, text="User ID:").grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.dm_user_id = tk.Entry(form, width=30)
        self.dm_user_id.grid(row=0, column=1, sticky='we', padx=4, pady=4)
        tk.Label(form, text="Message:").grid(row=1, column=0, sticky='nw', padx=4, pady=4)
        self.dm_message = scrolledtext.ScrolledText(form, height=6, width=60, wrap=tk.WORD)
        self.dm_message.grid(row=1, column=1, sticky='we', padx=4, pady=4)
        form.columnconfigure(1, weight=1)
        tk.Button(form, text="Send DM", command=self.send_discord_dm, bg='#5865F2', fg='white').grid(row=2, column=1, sticky='w', padx=4, pady=6)

        self.dm_status = tk.Label(frame, text="Enter user ID and message", bg='#ecf0f1', fg='#2c3e50')
        self.dm_status.pack(fill=tk.X, padx=10, pady=4)

    def setup_system_monitor_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🖥️ System Monitor")

        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Refresh", command=lambda: self.refresh_system_monitor(schedule=False)).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Start Live", command=self.start_system_monitor_live).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Stop Live", command=self.stop_system_monitor_live).pack(side=tk.LEFT, padx=5)

        self.sysmon_text = scrolledtext.ScrolledText(frame, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.sysmon_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.sysmon_text.config(state=tk.DISABLED)

        self.refresh_system_monitor(schedule=False)
        
    def refresh_google(self):
        self.load_gmail_data()
        self.load_calendar_data()
        self.load_tasks_data()

    # Drive quick upload
    def select_drive_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.drive_upload_path.set(path)
            self.drive_upload_name.set(os.path.basename(path))
            self.drive_upload_status.config(text="Ready to upload")

    def upload_drive_file(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        path = self.drive_upload_path.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Drive Upload", "Please choose a valid file")
            return
        name = self.drive_upload_name.get().strip() or os.path.basename(path)
        threading.Thread(target=self._upload_drive_file, args=(path, name), daemon=True).start()

    def _upload_drive_file(self, path, name):
        self.update_status("Uploading to Drive...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart'
            with open(path, 'rb') as f:
                files = {
                    'metadata': ('metadata', json.dumps({'name': name}), 'application/json; charset=UTF-8'),
                    'file': (name, f)
                }
                resp = requests.post(url, headers=headers, files=files)
            if resp.status_code in (200, 201):
                self.root.after(0, lambda: self.drive_upload_status.config(text="Upload complete"))
                self.root.after(0, lambda: messagebox.showinfo("Drive", "File uploaded to My Drive"))
            else:
                self.root.after(0, lambda: self.drive_upload_status.config(text=f"Failed: {resp.status_code}"))
                self.root.after(0, lambda: messagebox.showerror("Drive", resp.text))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Drive", f"Upload failed: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.update_status("Ready"))

    # Calendar agenda (next 7 days)
    def load_calendar_agenda(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_calendar_agenda, daemon=True).start()

    def _fetch_calendar_agenda(self):
        self.update_status("Loading agenda...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            time_min = now.isoformat().replace('+00:00', 'Z')
            time_max = (now + timedelta(days=7)).isoformat().replace('+00:00', 'Z')
            url = (
                'https://www.googleapis.com/calendar/v3/calendars/primary/events'
                f'?timeMin={time_min}&timeMax={time_max}&singleEvents=true&orderBy=startTime&maxResults=50'
            )
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                events = resp.json().get('items', [])
                self.root.after(0, lambda: self.display_calendar_agenda(events))
            else:
                self.root.after(0, lambda: self.show_text_error(self.agenda_text, f"Error: {resp.status_code}\n{resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Agenda", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Agenda loaded"))

    def display_calendar_agenda(self, events):
        self.agenda_text.config(state=tk.NORMAL)
        self.agenda_text.delete(1.0, tk.END)
        if not events:
            self.agenda_text.insert(tk.END, "No events in next 7 days")
        else:
            for ev in events:
                title = ev.get('summary', 'Untitled')
                start = ev.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No date'))
                location = ev.get('location', 'No location')
                self.agenda_text.insert(tk.END, f"Title: {title}\nStart: {start_time}\nLocation: {location}\n")
                self.agenda_text.insert(tk.END, f"Event ID: {ev.get('id','')}\n")
                self.agenda_text.insert(tk.END, "-" * 60 + "\n")
        self.agenda_text.config(state=tk.DISABLED)

    # Gmail templates
    def load_templates_from_disk(self):
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def save_templates_to_disk(self, templates):
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Templates", f"Failed to save: {str(e)}")

    def refresh_templates(self):
        self.templates_cache = self.load_templates_from_disk()
        self.template_listbox.delete(0, tk.END)
        for tpl in self.templates_cache:
            self.template_listbox.insert(tk.END, tpl.get('name', 'Untitled'))
        self.show_template_preview()

    def add_template(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("New Template", "Template name:")
        if not name:
            return
        body = simpledialog.askstring("New Template", "Body:")
        if body is None:
            return
        templates = self.load_templates_from_disk()
        templates.append({'name': name, 'body': body})
        self.save_templates_to_disk(templates)
        self.refresh_templates()

    def delete_template(self):
        idxs = self.template_listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        templates = self.load_templates_from_disk()
        if idx < len(templates):
            templates.pop(idx)
            self.save_templates_to_disk(templates)
            self.refresh_templates()

    def show_template_preview(self):
        self.template_preview.config(state=tk.NORMAL)
        self.template_preview.delete(1.0, tk.END)
        idxs = self.template_listbox.curselection()
        if not idxs or not hasattr(self, 'templates_cache'):
            self.template_preview.config(state=tk.DISABLED)
            return
        tpl = self.templates_cache[idxs[0]]
        self.template_preview.insert(tk.END, tpl.get('body', ''))
        self.template_preview.config(state=tk.DISABLED)
    def on_template_select(self, event):
        self.show_template_preview()

    def copy_template_to_clipboard(self):
        idxs = self.template_listbox.curselection()
        if not idxs or not hasattr(self, 'templates_cache'):
            return
        tpl = self.templates_cache[idxs[0]]
        body = tpl.get('body', '')
        self.root.clipboard_clear()
        self.root.clipboard_append(body)
        messagebox.showinfo("Templates", "Copied to clipboard")

    # System monitor
    def refresh_system_monitor(self, schedule=True):
        try:
            cpu_overall = psutil.cpu_percent(interval=0)
            cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            from datetime import datetime
            lines = [
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"CPU Overall: {cpu_overall}%",
                "Per-Core: " + ", ".join([f"{i}:{v}%" for i, v in enumerate(cpu_per_core)]),
                f"Memory: {mem.percent}% ({self._fmt_bytes(mem.used)} / {self._fmt_bytes(mem.total)})",
                f"Disk: {disk.percent}% ({self._fmt_bytes(disk.used)} / {self._fmt_bytes(disk.total)})",
                f"Net: sent {self._fmt_bytes(net.bytes_sent)}, recv {self._fmt_bytes(net.bytes_recv)}"
            ]
            self.sysmon_text.config(state=tk.NORMAL)
            self.sysmon_text.delete(1.0, tk.END)
            self.sysmon_text.insert(tk.END, "\n".join(lines))
            self.sysmon_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("System Monitor", str(e))

        # schedule next update if live
        if schedule and self.sysmon_job:
            self.sysmon_job = self.root.after(2000, lambda: self.refresh_system_monitor(schedule=True))

    def start_system_monitor_live(self):
        self.stop_system_monitor_live()
        self.sysmon_job = True  # mark active
        self.refresh_system_monitor(schedule=True)

    def stop_system_monitor_live(self):
        if self.sysmon_job and isinstance(self.sysmon_job, int):
            self.root.after_cancel(self.sysmon_job)
        self.sysmon_job = None

    # Discord bot-powered DM (send only)
    def send_discord_dm(self):
        bot_token = os.getenv('DISCORD_BOT_TOKEN')
        if not bot_token:
            messagebox.showwarning("Discord DM", "Set DISCORD_BOT_TOKEN in .env (bot must share a server with the user).")
            return
        user_id = self.dm_user_id.get().strip()
        content = self.dm_message.get(1.0, tk.END).strip()
        if not user_id or not content:
            messagebox.showwarning("Discord DM", "User ID and message are required")
            return
        threading.Thread(target=self._send_discord_dm, args=(bot_token, user_id, content), daemon=True).start()

    def _send_discord_dm(self, bot_token, user_id, content):
        self.root.after(0, lambda: self.dm_status.config(text="Sending..."))
        headers = {
            'Authorization': f'Bot {bot_token}',
            'Content-Type': 'application/json'
        }
        try:
            dm_resp = requests.post('https://discord.com/api/v10/users/@me/channels', headers=headers, json={'recipient_id': user_id})
            if dm_resp.status_code not in (200, 201):
                self.root.after(0, lambda: self.dm_status.config(text=f"Failed to open DM: {dm_resp.status_code}"))
                self.root.after(0, lambda: messagebox.showerror("Discord DM", dm_resp.text))
                return
            channel_id = dm_resp.json().get('id')
            msg_resp = requests.post(f'https://discord.com/api/v10/channels/{channel_id}/messages', headers=headers, json={'content': content})
            if msg_resp.status_code in (200, 201):
                self.root.after(0, lambda: self.dm_status.config(text="Sent"))
                self.root.after(0, lambda: messagebox.showinfo("Discord DM", "Message sent"))
            else:
                self.root.after(0, lambda: self.dm_status.config(text=f"Failed: {msg_resp.status_code}"))
                self.root.after(0, lambda: messagebox.showerror("Discord DM", msg_resp.text))
        except Exception as e:
            self.root.after(0, lambda: self.dm_status.config(text="Error"))
            self.root.after(0, lambda: messagebox.showerror("Discord DM", str(e)))

    # Google Keep Notes
    def create_keep_note(self):
        title = self.keep_title.get().strip()
        content = self.keep_content.get(1.0, tk.END).strip()
        if not title or not content:
            messagebox.showwarning("Keep", "Title and content required")
            return
        messagebox.showinfo("Keep Notes", "Google Keep API requires OAuth app verification.\nOpening Keep in browser to create note manually.")
        webbrowser.open(f'https://keep.google.com/u/0/#NOTE/{requests.utils.quote(title)}')

    # Google Translate
    def translate_text(self):
        source_text = self.translate_source.get(1.0, tk.END).strip()
        if not source_text:
            messagebox.showwarning("Translate", "Enter text to translate")
            return
        target_lang = self.translate_target.get()
        threading.Thread(target=self._translate_text, args=(source_text, target_lang), daemon=True).start()

    def _translate_text(self, text, target):
        self.update_status("Translating...")
        try:
            url = 'https://api.mymemory.translated.net/get'
            lang_map = {'es': 'es', 'fr': 'fr', 'de': 'de', 'it': 'it', 'pt': 'pt', 'ru': 'ru', 'ja': 'ja', 'ko': 'ko', 'zh-CN': 'zh-CN', 'ar': 'ar'}
            target_lang = lang_map.get(target, 'es')
            params = {'q': text, 'langpair': f'en|{target_lang}'}
            resp = requests.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                translated = data.get('responseData', {}).get('translatedText', 'No translation')
                self.root.after(0, lambda: self.display_translation(translated))
            else:
                self.root.after(0, lambda: messagebox.showerror("Translate", f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Translate", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_translation(self, text):
        import html
        text = html.unescape(text)
        self.translate_result.config(state=tk.NORMAL)
        self.translate_result.delete(1.0, tk.END)
        self.translate_result.insert(tk.END, text)
        self.translate_result.config(state=tk.DISABLED)

    # Google Maps
    def search_maps(self):
        query = self.maps_query.get().strip()
        if not query:
            messagebox.showwarning("Maps", "Enter a search query")
            return
        threading.Thread(target=self._search_maps, args=(query,), daemon=True).start()

    def _search_maps(self, query):
        self.update_status("Searching maps...")
        try:
            url = 'https://nominatim.openstreetmap.org/search'
            params = {'q': query, 'format': 'json', 'limit': 5}
            headers = {'User-Agent': 'UnifiedHub'}
            resp = requests.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                results = resp.json()
                self.root.after(0, lambda: self.display_maps_results(results))
            else:
                self.root.after(0, lambda: messagebox.showerror("Maps", f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Maps", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_maps_results(self, results):
        self.maps_text.config(state=tk.NORMAL)
        self.maps_text.delete(1.0, tk.END)
        if not results:
            self.maps_text.insert(tk.END, "No results found")
        else:
            for r in results[:5]:
                self.maps_text.insert(tk.END, f"Address: {r.get('display_name', 'N/A')}\n")
                self.maps_text.insert(tk.END, f"Lat: {r.get('lat', 'N/A')}, Lng: {r.get('lon', 'N/A')}\n")
                self.maps_text.insert(tk.END, "-" * 60 + "\n")
        self.maps_text.config(state=tk.DISABLED)

    def open_maps_browser(self):
        query = self.maps_query.get().strip()
        if query:
            webbrowser.open(f'https://www.google.com/maps/search/{requests.utils.quote(query)}')

    def _fmt_bytes(self, num):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024.0:
                return f"{num:.1f} {unit}"
            num /= 1024.0
        return f"{num:.1f} PB"
    
    # Removed Discord tab

    def setup_calendar_tab(self):
        cal_frame = ttk.Frame(self.notebook)
        self.notebook.add(cal_frame, text="📅 Calendar")
        
        control = tk.Frame(cal_frame, bg='#ecf0f1')
        control.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(control, text="Load Events", command=self.load_calendar_data).pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="Create Event", command=self.create_calendar_event).pack(side=tk.LEFT, padx=5)
        
        self.calendar_text = scrolledtext.ScrolledText(cal_frame, height=30, width=100, wrap=tk.WORD,
                                                       bg='white', fg='#2c3e50', font=('Courier', 9))
        self.calendar_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.calendar_text.config(state=tk.DISABLED)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    # OAuth - Google
    def connect_google(self):
        threading.Thread(target=self._connect_google, daemon=True).start()
    
    def _connect_google(self):
        self.update_status("Connecting to Google...")
        
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        if not client_id or not client_secret:
            self.root.after(0, lambda: messagebox.showerror("Error", "Missing GOOGLE_CLIENT_ID/SECRET in .env"))
            self.root.after(0, lambda: self.update_status("Connection failed"))
            return

        scopes = (
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.labels "
            "https://www.googleapis.com/auth/gmail.send "
            "https://www.googleapis.com/auth/calendar "
            "https://www.googleapis.com/auth/tasks "
            "https://www.googleapis.com/auth/drive.metadata.readonly "
            "https://www.googleapis.com/auth/drive.readonly "
            "https://www.googleapis.com/auth/userinfo.profile "
            "https://www.googleapis.com/auth/userinfo.email "
            "https://www.googleapis.com/auth/youtube.readonly "
            "https://www.googleapis.com/auth/contacts.readonly"
        )
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback&"
            "response_type=code&"
            f"scope={requests.utils.quote(scopes)}&"
            "access_type=offline&"
            "prompt=consent"
        )
        
        try:
            server = ReuseAddrHTTPServer(('localhost', 8080), OAuthCallbackHandler)
            server.timeout = 0.5
            
            # Open browser first
            webbrowser.open(auth_url)
            
            # Wait for callback
            while OAuthCallbackHandler.auth_code is None:
                server.handle_request()
            
            auth_code = OAuthCallbackHandler.auth_code
            OAuthCallbackHandler.auth_code = None
            
            # Exchange code for tokens
            token_url = 'https://oauth2.googleapis.com/token'
            data = {
                'code': auth_code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': 'http://localhost:8080/callback',
                'grant_type': 'authorization_code'
            }
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.tokens['google'] = token_data.get('access_token')
                self.tokens['google_refresh'] = token_data.get('refresh_token')
                self.save_tokens()
                self.root.after(0, lambda: self.update_status("Google connected!"))
                self.root.after(0, lambda: self.google_btn.config(text="✓ Google Connected", bg='#2ed573'))
                # Auto-load data
                self.root.after(0, self.refresh_google)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Google auth failed: {response.text}"))
            server.server_close()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"OAuth error: {str(e)}"))
            self.root.after(0, lambda: self.update_status("Connection failed"))

    # OAuth - Discord
    def connect_discord(self):
        threading.Thread(target=self._connect_discord, daemon=True).start()

    def _connect_discord(self):
        self.update_status("Connecting to Discord...")
        client_id = os.getenv('DISCORD_CLIENT_ID')
        if not client_id:
            self.root.after(0, lambda: messagebox.showerror("Error", "Missing DISCORD_CLIENT_ID in .env"))
            self.root.after(0, lambda: self.update_status("Connection failed"))
            return

        scopes = "identify guilds applications.commands applications.builds.read"
        auth_url = (
            "https://discord.com/api/oauth2/authorize?"
            f"client_id={client_id}&"
            "redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback&"
            "response_type=code&"
            f"scope={requests.utils.quote(scopes)}"
        )

        try:
            server = ReuseAddrHTTPServer(('localhost', 8080), OAuthCallbackHandler)
            server.timeout = 0.5
            webbrowser.open(auth_url)
            while OAuthCallbackHandler.auth_code is None:
                server.handle_request()
            auth_code = OAuthCallbackHandler.auth_code
            OAuthCallbackHandler.auth_code = None
            self.handle_discord_callback(auth_code)
            server.server_close()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"OAuth error: {str(e)}"))
            self.root.after(0, lambda: self.update_status("Connection failed"))
    
    def handle_discord_callback(self, auth_code):
        client_id = os.getenv('DISCORD_CLIENT_ID')
        client_secret = os.getenv('DISCORD_CLIENT_SECRET')
        
        token_url = 'https://discord.com/api/oauth2/token'
        data = {
            'code': auth_code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': 'http://localhost:8080/callback',
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.tokens['discord'] = token_data['access_token']
                self.save_tokens()
                self.root.after(0, lambda: self.update_status("Discord connected!"))
                self.root.after(0, lambda: self.discord_btn.config(text="✓ Discord Connected", bg='#43b581'))
                self.root.after(0, self.load_discord_servers)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Discord auth failed: {response.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Connection error: {str(e)}"))
    
    # Gmail
    def load_gmail_data(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_gmail_data, daemon=True).start()
    
    def _fetch_gmail_data(self):
        self.update_status("Loading emails...")
        
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        max_results = self.email_limit.get()
        
        try:
            url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={max_results}'
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                messages = response.json().get('messages', [])
                emails = []
                
                for msg in messages[:int(max_results)]:
                    msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg["id"]}'
                    msg_response = requests.get(msg_url, headers=headers)
                    if msg_response.status_code == 200:
                        emails.append(msg_response.json())
                
                self.root.after(0, lambda: self.display_emails(emails))
            elif response.status_code == 401:
                error_msg = "⚠️ Gmail Token Invalid\n\n1. Click '🗑️ Clear Tokens'\n2. Click '🔗 Connect Google' again"
                self.root.after(0, lambda: self.show_text_error(self.gmail_text, error_msg))
            else:
                error_msg = f"Error: {response.status_code}\n\n{response.text}"
                self.root.after(0, lambda: self.show_text_error(self.gmail_text, error_msg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        
        self.root.after(0, lambda: self.update_status("Emails loaded"))
    
    def display_emails(self, emails):
        self.emails_cache = emails
        self.gmail_listbox.delete(0, tk.END)
        
        if not emails:
            self.gmail_listbox.insert(tk.END, "No emails found")
        else:
            for email in emails:
                headers = email.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                # Extract name/email only
                sender_short = sender.split('<')[0].strip() if '<' in sender else sender[:30]
                self.gmail_listbox.insert(tk.END, f"{sender_short} - {subject[:50]}")
        
        self.gmail_text.config(state=tk.NORMAL)
        self.gmail_text.delete(1.0, tk.END)
        self.gmail_text.insert(tk.END, "Select an email from the list to view")
        self.gmail_text.config(state=tk.DISABLED)

    def on_email_select(self, event):
        selection = self.gmail_listbox.curselection()
        if not selection or not self.emails_cache:
            return
        idx = selection[0]
        if idx >= len(self.emails_cache):
            return
        email = self.emails_cache[idx]
        self.display_full_email(email)

    def display_full_email(self, email):
        headers = email.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), 'No Date')
        to = next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown')
        
        # Extract body
        body = self._extract_email_body(email.get('payload', {}))
        
        self.gmail_text.config(state=tk.NORMAL)
        self.gmail_text.delete(1.0, tk.END)
        self.gmail_text.insert(tk.END, f"From: {sender}\n")
        self.gmail_text.insert(tk.END, f"To: {to}\n")
        self.gmail_text.insert(tk.END, f"Subject: {subject}\n")
        self.gmail_text.insert(tk.END, f"Date: {date}\n")
        self.gmail_text.insert(tk.END, "-" * 80 + "\n\n")
        self.gmail_text.insert(tk.END, body)
        self.gmail_text.config(state=tk.DISABLED)

    def _extract_email_body(self, payload):
        """Extract text body from email payload without marking as read"""
        import base64
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    body += self._extract_email_body(part)
        elif payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return body if body else payload.get('snippet', 'No body content')


    def load_gmail_unread_count(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_gmail_unread_count, daemon=True).start()

    def _fetch_gmail_unread_count(self):
        self.update_status("Loading unread count...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            resp = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/labels/UNREAD', headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                count = data.get('messagesUnread', 0)
                self.root.after(0, lambda: messagebox.showinfo("Unread", f"Unread messages: {count}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Unread count loaded"))

    def apply_gmail_sender_filter(self):
        sender = self.gmail_sender_filter.get().strip()
        if not sender:
            self.load_gmail_data()
            return
        threading.Thread(target=self._fetch_gmail_filtered, args=(sender,), daemon=True).start()

    def compose_email(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        from tkinter import simpledialog
        to = simpledialog.askstring("Compose", "To (email):")
        subject = simpledialog.askstring("Compose", "Subject:")
        body = simpledialog.askstring("Compose", "Body:")
        if not to:
            return
        threading.Thread(target=self._send_email, args=(to, subject or '', body or ''), daemon=True).start()

    def _send_email(self, to, subject, body):
        import base64
        headers = {'Authorization': f'Bearer {self.tokens["google"]}', 'Content-Type': 'application/json'}
        raw = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
        raw_b64 = base64.urlsafe_b64encode(raw.encode()).decode()
        try:
            url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
            resp = requests.post(url, headers=headers, json={'raw': raw_b64})
            if resp.status_code in (200, 202):
                self.root.after(0, lambda: messagebox.showinfo("Compose", "Email sent"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Compose", f"Failed: {resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Compose", f"Error: {str(e)}"))

    def _fetch_gmail_filtered(self, sender):
        self.update_status("Filtering emails...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            # q parameter uses Gmail search syntax
            params = {'q': f'from:{sender}', 'maxResults': int(self.email_limit.get())}
            resp = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/messages', headers=headers, params=params)
            if resp.status_code == 200:
                messages = resp.json().get('messages', [])
                emails = []
                for msg in messages:
                    msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg["id"]}'
                    msg_resp = requests.get(msg_url, headers=headers)
                    if msg_resp.status_code == 200:
                        emails.append(msg_resp.json())
                self.root.after(0, lambda: self.display_emails(emails))
            else:
                self.root.after(0, lambda: self.show_text_error(self.gmail_text, f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Filter applied"))

    # Gmail Labels
    def load_gmail_labels(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_gmail_labels, daemon=True).start()

    def _fetch_gmail_labels(self):
        self.update_status("Loading labels...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            resp = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/labels', headers=headers)
            if resp.status_code == 200:
                labels = resp.json().get('labels', [])
                self.root.after(0, lambda: self.display_labels(labels))
            elif resp.status_code == 401:
                self.root.after(0, lambda: self.show_text_error(self.labels_text, "⚠️ Token Invalid. Clear Tokens and reconnect."))
            else:
                self.root.after(0, lambda: self.show_text_error(self.labels_text, f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Labels loaded"))

    def display_labels(self, labels):
        self.labels_text.config(state=tk.NORMAL)
        self.labels_text.delete(1.0, tk.END)
        if not labels:
            self.labels_text.insert(tk.END, "No labels found")
        else:
            for lab in labels:
                self.labels_text.insert(tk.END, f"{lab.get('name','(no name)')}  [{lab.get('type','user')}]\n")
        self.labels_text.config(state=tk.DISABLED)

    # YouTube Subscriptions
    def load_youtube_subscriptions(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_youtube_subscriptions, daemon=True).start()

    def _fetch_youtube_subscriptions(self):
        self.update_status("Loading YouTube subscriptions...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            url = 'https://www.googleapis.com/youtube/v3/subscriptions?part=snippet&mine=true&maxResults=50'
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                self.root.after(0, lambda: self.display_youtube_subscriptions(items))
            elif resp.status_code == 403:
                msg = (
                    "⚠️ YouTube API 403\n\n"
                    "Steps:\n"
                    "1. Enable API: https://console.cloud.google.com/apis/library/youtube.googleapis.com\n"
                    "2. Click '🗑️ Clear Tokens' then '🔗 Connect Google'\n\n"
                    f"Error: {resp.text}"
                )
                self.root.after(0, lambda: self.show_text_error(self.youtube_text, msg))
            else:
                self.root.after(0, lambda: self.show_text_error(self.youtube_text, f"Error: {resp.status_code}\n{resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("YouTube loaded"))

    def display_youtube_subscriptions(self, items):
        self.youtube_text.config(state=tk.NORMAL)
        self.youtube_text.delete(1.0, tk.END)
        if not items:
            self.youtube_text.insert(tk.END, "No subscriptions found")
        else:
            for item in items:
                snippet = item.get('snippet', {})
                title = snippet.get('title', 'Unknown')
                channel_id = snippet.get('resourceId', {}).get('channelId', '')
                self.youtube_text.insert(tk.END, f"{title}  [ID: {channel_id}]\n")
        self.youtube_text.config(state=tk.DISABLED)

    # Google Contacts
    def load_google_contacts(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_google_contacts, daemon=True).start()

    def _fetch_google_contacts(self):
        self.update_status("Loading Contacts...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            url = 'https://people.googleapis.com/v1/people/me/connections?personFields=names,emailAddresses&pageSize=100'
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                connections = resp.json().get('connections', [])
                self.root.after(0, lambda: self.display_google_contacts(connections))
            elif resp.status_code == 403:
                msg = (
                    "⚠️ People API 403\n\n"
                    "Steps:\n"
                    "1. Enable API: https://console.cloud.google.com/apis/library/people.googleapis.com\n"
                    "2. Click '🗑️ Clear Tokens' then '🔗 Connect Google'\n\n"
                    f"Error: {resp.text}"
                )
                self.root.after(0, lambda: self.show_text_error(self.contacts_text, msg))
            else:
                self.root.after(0, lambda: self.show_text_error(self.contacts_text, f"Error: {resp.status_code}\n{resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Contacts loaded"))

    def display_google_contacts(self, connections):
        self.contacts_text.config(state=tk.NORMAL)
        self.contacts_text.delete(1.0, tk.END)
        if not connections:
            self.contacts_text.insert(tk.END, "No contacts found")
        else:
            for contact in connections:
                names = contact.get('names', [])
                emails = contact.get('emailAddresses', [])
                name = names[0].get('displayName', 'No name') if names else 'No name'
                email = emails[0].get('value', '') if emails else ''
                self.contacts_text.insert(tk.END, f"{name}  <{email}>\n")
        self.contacts_text.config(state=tk.DISABLED)

    # Tasks
    def setup_tasks_tab(self):
        tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(tasks_frame, text="✓ Tasks")
        
        control = tk.Frame(tasks_frame, bg='#ecf0f1')
        control.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(control, text="Load Tasks", command=self.load_tasks_data).pack(side=tk.LEFT, padx=5)
        tk.Button(control, text="Create Task", command=self.create_task).pack(side=tk.LEFT, padx=5)
        
        self.tasks_text = scrolledtext.ScrolledText(tasks_frame, height=30, width=100, wrap=tk.WORD,
                                                    bg='white', fg='#2c3e50', font=('Courier', 9))
        self.tasks_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.tasks_text.config(state=tk.DISABLED)
    
    def load_tasks_data(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_tasks_data, daemon=True).start()
    
    def _fetch_tasks_data(self):
        self.update_status("Loading tasks...")
        
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        
        try:
            lists_url = 'https://tasks.googleapis.com/tasks/v1/users/@me/lists'
            response = requests.get(lists_url, headers=headers)
            
            if response.status_code == 200:
                task_lists = response.json().get('items', [])
                all_tasks = []
                
                for task_list in task_lists:
                    tasks_url = f'https://tasks.googleapis.com/tasks/v1/lists/{task_list["id"]}/tasks'
                    tasks_response = requests.get(tasks_url, headers=headers)
                    if tasks_response.status_code == 200:
                        tasks = tasks_response.json().get('items', [])
                        all_tasks.append({'list_name': task_list['title'], 'tasks': tasks, 'list_id': task_list['id']})
                
                self.root.after(0, lambda: self.display_tasks(all_tasks))
            elif response.status_code == 401:
                error_msg = "⚠️ Tasks Token Invalid\n\n1. Click '🗑️ Clear Tokens'\n2. Reconnect Google"
                self.root.after(0, lambda: self.show_text_error(self.tasks_text, error_msg))
            elif response.status_code == 403:
                error_msg = (
                    "⚠️ Tasks API 403\n\n"
                    "Possible causes:\n"
                    "- API not enabled in the same project as your OAuth client\n"
                    "- Missing scope grant (requires https://www.googleapis.com/auth/tasks)\n\n"
                    "Fix:\n"
                    "1) Enable API: https://console.cloud.google.com/apis/library/tasks.googleapis.com\n"
                    "2) Click Clear Tokens, then Connect Google to re-consent scopes."
                )
                self.root.after(0, lambda: self.show_text_error(self.tasks_text, error_msg))
            else:
                self.root.after(0, lambda: self.show_text_error(self.tasks_text, f"Error: {response.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        
        self.root.after(0, lambda: self.update_status("Tasks loaded"))
    
    def display_tasks(self, task_lists):
        self.tasks_text.config(state=tk.NORMAL)
        self.tasks_text.delete(1.0, tk.END)
        
        if not task_lists:
            self.tasks_text.insert(tk.END, "No tasks found")
        else:
            for task_list in task_lists:
                self.tasks_text.insert(tk.END, f"\n📋 {task_list['list_name']}\n")
                self.tasks_text.insert(tk.END, "=" * 80 + "\n")
                
                tasks = task_list.get('tasks', [])
                if not tasks:
                    self.tasks_text.insert(tk.END, "  No tasks in this list\n")
                else:
                    for task in tasks:
                        title = task.get('title', 'Untitled')
                        status = task.get('status', 'needsAction')
                        due = task.get('due', 'No due date')
                        checkbox = "✓" if status == 'completed' else "☐"
                        self.tasks_text.insert(tk.END, f"  {checkbox} {title} (Due: {due})  [Task ID: {task.get('id','')}] [List ID: {task_list.get('list_id','')}]\n")
                
                self.tasks_text.insert(tk.END, "\n")
        
        self.tasks_text.config(state=tk.DISABLED)

    def complete_selected_task(self):
        from tkinter import simpledialog
        task_id = simpledialog.askstring("Complete Task", "Enter Task ID:")
        list_id = simpledialog.askstring("Complete Task", "Enter List ID:")
        if not task_id or not list_id:
            return
        threading.Thread(target=self._complete_task, args=(list_id, task_id), daemon=True).start()

    def _complete_task(self, list_id, task_id):
        headers = {
            'Authorization': f'Bearer {self.tokens["google"]}',
            'Content-Type': 'application/json'
        }
        try:
            # tasks.update requires the task body; fetch then update status
            get_url = f'https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks/{task_id}'
            resp = requests.get(get_url, headers=headers)
            if resp.status_code == 200:
                body = resp.json()
                body['status'] = 'completed'
                upd_url = f'https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks/{task_id}'
                resp2 = requests.put(upd_url, headers=headers, json=body)
                if resp2.status_code == 200:
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Task marked completed"))
                    self.root.after(0, self.load_tasks_data)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {resp2.text}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
    
    def create_task(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        
        from tkinter import simpledialog
        title = simpledialog.askstring("New Task", "Task title:")
        if not title:
            return
        
        threading.Thread(target=self._create_task, args=(title,), daemon=True).start()
    
    def _create_task(self, title):
        headers = {
            'Authorization': f'Bearer {self.tokens["google"]}',
            'Content-Type': 'application/json'
        }
        
        try:
            lists_url = 'https://tasks.googleapis.com/tasks/v1/users/@me/lists'
            response = requests.get(lists_url, headers=headers)
            
            if response.status_code == 200:
                task_lists = response.json().get('items', [])
                if task_lists:
                    list_id = task_lists[0]['id']
                    task_data = {'title': title}
                    
                    task_url = f'https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks'
                    response = requests.post(task_url, headers=headers, json=task_data)
                    
                    if response.status_code == 200:
                        self.root.after(0, lambda: messagebox.showinfo("Success", "Task created!"))
                        self.root.after(0, self.load_tasks_data)
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {response.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    # Calendar
    def load_calendar_data(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_calendar_data, daemon=True).start()
    
    def _fetch_calendar_data(self):
        self.update_status("Loading calendar...")
        
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        
        try:
            from datetime import timezone, datetime
            now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            url = f'https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={now}&maxResults=20&singleEvents=true&orderBy=startTime'
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                events = response.json().get('items', [])
                self.root.after(0, lambda: self.display_calendar_events(events))
            elif response.status_code == 401:
                error_msg = "⚠️ Calendar Token Invalid\n\n1. Click '🗑️ Clear Tokens'\n2. Reconnect Google"
                self.root.after(0, lambda: self.show_text_error(self.calendar_text, error_msg))
            elif response.status_code == 403:
                error_msg = (
                    "⚠️ Calendar API 403\n\n"
                    "Possible causes:\n"
                    "- API not enabled in the same project as your OAuth client\n"
                    "- Missing scope grant (requires https://www.googleapis.com/auth/calendar)\n\n"
                    "Fix:\n"
                    "1) Ensure API enabled: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com\n"
                    "2) Click Clear Tokens, then Connect Google to re-consent scopes."
                )
                self.root.after(0, lambda: self.show_text_error(self.calendar_text, error_msg))
            else:
                self.root.after(0, lambda: self.show_text_error(self.calendar_text, f"Error: {response.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        
        self.root.after(0, lambda: self.update_status("Calendar loaded"))
    
    def display_calendar_events(self, events):
        self.calendar_events_cache = events
        self.calendar_text.config(state=tk.NORMAL)
        self.calendar_text.delete(1.0, tk.END)
        
        if not events:
            self.calendar_text.insert(tk.END, "No upcoming events")
        else:
            for event in events:
                title = event.get('summary', 'Untitled')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No date'))
                location = event.get('location', 'No location')
                description = event.get('description', 'No description')
                
                self.calendar_text.insert(tk.END, f"Title: {title}\n")
                self.calendar_text.insert(tk.END, f"Start: {start_time}\n")
                self.calendar_text.insert(tk.END, f"Location: {location}\n")
                self.calendar_text.insert(tk.END, f"Description: {description}\n")
                self.calendar_text.insert(tk.END, f"Event ID: {event.get('id','')}\n")
                self.calendar_text.insert(tk.END, "-" * 80 + "\n\n")
        
        self.calendar_text.config(state=tk.DISABLED)

    def delete_selected_calendar_event(self):
        # expects user to select ID text manually; simple prompt
        from tkinter import simpledialog
        event_id = simpledialog.askstring("Delete Event", "Enter Event ID:")
        if not event_id:
            return
        threading.Thread(target=self._delete_calendar_event, args=(event_id,), daemon=True).start()

    def _delete_calendar_event(self, event_id):
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            resp = requests.delete(f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}', headers=headers)
            if resp.status_code in (200, 204):
                self.root.after(0, lambda: messagebox.showinfo("Success", "Event deleted"))
                self.root.after(0, self.load_calendar_data)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
    
    def create_calendar_event(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        
        from tkinter import simpledialog
        from datetime import datetime, timedelta
        title = simpledialog.askstring("New Event", "Event title:")
        if not title:
            return
        
        date_str = simpledialog.askstring("New Event", "Date (YYYY-MM-DD) or leave empty for tomorrow:")
        if date_str:
            try:
                event_date = datetime.strptime(date_str, '%Y-%m-%d')
            except:
                messagebox.showerror("Error", "Invalid date format")
                return
        else:
            event_date = datetime.now() + timedelta(days=1)
        
        time_str = simpledialog.askstring("New Event", "Time (HH:MM) or leave empty for all-day:")
        
        threading.Thread(target=self._create_event, args=(title, event_date, time_str), daemon=True).start()
    
    def _create_event(self, title, event_date, time_str):
        headers = {
            'Authorization': f'Bearer {self.tokens["google"]}',
            'Content-Type': 'application/json'
        }
        from datetime import timedelta
        
        if time_str:
            try:
                hour, minute = map(int, time_str.split(':'))
                start_dt = event_date.replace(hour=hour, minute=minute)
                end_dt = start_dt + timedelta(hours=1)
                
                event = {
                    'summary': title,
                    'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
                    'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'}
                }
            except:
                self.root.after(0, lambda: messagebox.showerror("Error", "Invalid time format"))
                return
        else:
            event = {
                'summary': title,
                'start': {'date': event_date.strftime('%Y-%m-%d')},
                'end': {'date': event_date.strftime('%Y-%m-%d')}
            }
        
        try:
            response = requests.post(
                'https://www.googleapis.com/calendar/v3/calendars/primary/events',
                headers=headers,
                json=event
            )
            if response.status_code == 200:
                self.root.after(0, lambda: messagebox.showinfo("Success", "Event created!"))
                self.root.after(0, self.load_calendar_data)
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {response.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
    
    # Discord Servers
    def load_discord_servers(self):
        if not self.tokens.get('discord'):
            messagebox.showwarning("Warning", "Please connect Discord first")
            return
        threading.Thread(target=self._fetch_discord_servers, daemon=True).start()
    
    def _fetch_discord_servers(self):
        self.update_status("Loading Discord servers...")
        
        headers = {'Authorization': f'Bearer {self.tokens["discord"]}'}
        
        try:
            response = requests.get('https://discord.com/api/v10/users/@me/guilds', headers=headers)
            
            if response.status_code == 200:
                guilds = response.json()
                
                # Filter to only servers you own
                owned_servers = [g for g in guilds if g.get('owner', False)]
                
                # Get member counts for owned servers
                for server in owned_servers:
                    server['online_count'] = self._fetch_guild_members(server['id'])
                
                self.discord_servers = owned_servers
                self.root.after(0, lambda: self.display_discord_servers(owned_servers))
            else:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load servers: {response.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        
        self.root.after(0, lambda: self.update_status("Discord servers loaded"))
    
    def _fetch_guild_members(self, guild_id):
        """Get online member count for a guild"""
        headers = {'Authorization': f'Bot {os.getenv("DISCORD_BOT_TOKEN")}'}
        
        try:
            response = requests.get(
                f'https://discord.com/api/v10/guilds/{guild_id}?with_counts=true',
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('approximate_presence_count', 0)
        except:
            pass
        
        return 0
    
    def display_discord_servers(self, servers):
        self.discord_listbox.delete(0, tk.END)
        
        if not servers:
            self.discord_listbox.insert(tk.END, "No owned servers found")
        else:
            for server in servers:
                name = server.get('name', 'Unknown')
                online = server.get('online_count', 0)
                display_text = f"{name} ({online} online)" if online > 0 else name
                self.discord_listbox.insert(tk.END, display_text)
    
    def on_discord_server_select(self, event):
        selection = self.discord_listbox.curselection()
        if selection and self.discord_servers:
            server = self.discord_servers[selection[0]]
            
            self.discord_details.config(state=tk.NORMAL)
            self.discord_details.delete(1.0, tk.END)
            
            details = f"Name: {server.get('name', 'N/A')}\n"
            details += f"ID: {server.get('id', 'N/A')}\n"
            details += f"Owner: Yes\n"
            details += f"Members Online: {server.get('online_count', 0)}\n"
            
            self.discord_details.insert(tk.END, details)
            self.discord_details.config(state=tk.DISABLED)

    # Discord Applications
    def load_discord_apps(self):
        if not self.tokens.get('discord'):
            messagebox.showwarning("Warning", "Please connect Discord first")
            return
        threading.Thread(target=self._fetch_discord_apps, daemon=True).start()
    
    def _fetch_discord_apps(self):
        self.update_status("Loading Discord apps...")
        
        headers = {'Authorization': f'Bearer {self.tokens["discord"]}'}
        try:
            response = requests.get('https://discord.com/api/v10/oauth2/applications/@me', headers=headers)
            if response.status_code == 200:
                app = response.json()
                apps = [app] if isinstance(app, dict) else app
                self.root.after(0, lambda: self.display_discord_apps(apps))
            else:
                # Capture 401 specifically and advise reconnect
                if response.status_code == 401:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Discord Apps",
                        "401 Unauthorized.\n\nFixes:\n- Click '🗑️ Clear Tokens' then '🔗 Connect Discord' to re-consent scopes.\n- Ensure redirect URI matches exactly http://localhost:8080/callback in Developer Portal.\n- Verify you own at least one application."
                    ))
                response2 = requests.get('https://discord.com/api/v10/applications', headers=headers)
                if response2.status_code == 200:
                    apps = response2.json()
                    if isinstance(apps, list):
                        self.root.after(0, lambda: self.display_discord_apps(apps))
                    else:
                        self.root.after(0, lambda: self.display_discord_apps([apps]))
                else:
                    err = f"{response.status_code}: {response.text}\n{response2.status_code}: {response2.text}"
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Discord Apps",
                        f"Could not load applications.\n\nCommon fixes:\n- Ensure you own at least one application\n- Reconnect with scopes: applications.commands\n- Try again later\n\nError: {err}"
                    ))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        
        self.root.after(0, lambda: self.update_status("Discord apps loaded"))
    
    def display_discord_apps(self, apps):
        self.discord_listbox.delete(0, tk.END)
        for app in apps:
            name = app.get('name', 'Unknown')
            self.discord_listbox.insert(tk.END, name)
        
        # Store temporarily for selection handling
        self.discord_apps_cache = apps
        self.discord_listbox.bind('<<ListboxSelect>>', self.on_discord_app_select)
    
    def on_discord_app_select(self, event):
        selection = self.discord_listbox.curselection()
        if selection and getattr(self, 'discord_apps_cache', None):
            app = self.discord_apps_cache[selection[0]]
            
            self.discord_details.config(state=tk.NORMAL)
            self.discord_details.delete(1.0, tk.END)
            
            details = f"Name: {app.get('name', 'N/A')}\n"
            details += f"ID: {app.get('id', 'N/A')}\n"
            details += f"Description: {app.get('description', 'N/A')}\n"
            owner = app.get('owner', {})
            details += f"Owner: {owner.get('username', 'N/A')}\n"
            details += f"Public: {app.get('public', False)}\n"
            details += f"Verified: {app.get('verified', False)}\n"
            
            self.discord_details.insert(tk.END, details)
            self.discord_details.config(state=tk.DISABLED)
    
    # Token management
    def refresh_google_token(self):
        if not self.tokens.get('google_refresh'):
            return False
        
        try:
            client_id = os.getenv('GOOGLE_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
            
            token_url = 'https://oauth2.googleapis.com/token'
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': self.tokens['google_refresh'],
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.tokens['google'] = token_data['access_token']
                self.save_tokens()
                return True
        except:
            pass
        
        return False
    
    def save_tokens(self):
        with open('.tokens.json', 'w') as f:
            json.dump(self.tokens, f)
    
    def load_saved_tokens(self):
        if os.path.exists('.tokens.json'):
            try:
                with open('.tokens.json', 'r') as f:
                    self.tokens = json.load(f)
                    if self.tokens.get('google'):
                        self.google_btn.config(text="✓ Google Connected", bg='#2ed573')
                    if self.tokens.get('discord') and self.discord_btn:
                        self.discord_btn.config(text="✓ Discord Connected", bg='#43b581')
            except:
                pass
    
    def clear_tokens(self):
        if messagebox.askyesno("Confirm", "Clear all tokens?"):
            self.tokens = {'google': None, 'google_refresh': None, 'discord': None}
            if os.path.exists('.tokens.json'):
                os.remove('.tokens.json')
            
            self.google_btn.config(text="🔗 Connect Google", bg='#3498db')
            if self.discord_btn:
                self.discord_btn.config(text="🔗 Connect Discord", bg='#7289da')
            self.update_status("Tokens cleared")
    
    def force_reconnect_google(self):
        self.tokens['google'] = None
        self.tokens['google_refresh'] = None
        self.save_tokens()
        self.google_btn.config(text="🔗 Connect Google", bg='#3498db')
        self.connect_google()
    
    def force_reconnect_discord(self):
        self.tokens['discord'] = None
        self.save_tokens()
        if self.discord_btn:
            self.discord_btn.config(text="🔗 Connect Discord", bg='#7289da')
        # Discord connect disabled

    def logout_google(self):
        self.tokens['google'] = None
        self.tokens['google_refresh'] = None
        self.save_tokens()
        self.google_btn.config(text="🔗 Connect Google", bg='#3498db')
        self.update_status("Logged out Google")
    
    def logout_discord(self):
        self.tokens['discord'] = None
        self.save_tokens()
        if self.discord_btn:
            self.discord_btn.config(text="🔗 Connect Discord", bg='#7289da')
        self.update_status("Logged out Discord")
    
    def refresh_all_data(self):
        # Refresh Google data
        self.load_gmail_data()
        self.load_calendar_data()
        self.load_calendar_agenda()
        self.load_tasks_data()
        self.load_google_profile()
        self.load_drive_files()
        self.load_gmail_labels()
        self.load_youtube_subscriptions()
        self.load_google_contacts()
        self.refresh_system_monitor(schedule=False)
    
    def show_text_error(self, text_widget, error_msg):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, error_msg)
        text_widget.config(state=tk.DISABLED)

    # Google Profile
    def load_google_profile(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_google_profile, daemon=True).start()

    def _fetch_google_profile(self):
        self.update_status("Loading profile...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            resp = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                self.root.after(0, lambda: self.display_profile(data))
            elif resp.status_code == 401:
                self.root.after(0, lambda: self.show_text_error(self.profile_text, "⚠️ Token Invalid. Clear Tokens and reconnect."))
            else:
                self.root.after(0, lambda: self.show_text_error(self.profile_text, f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Profile loaded"))

    def display_profile(self, data):
        self.profile_text.config(state=tk.NORMAL)
        self.profile_text.delete(1.0, tk.END)
        lines = [
            f"Name: {data.get('name', 'N/A')}",
            f"Email: {data.get('email', 'N/A')}",
            f"Verified: {data.get('email_verified', False)}",
            f"Picture: {data.get('picture', 'N/A')}",
            f"Sub (ID): {data.get('sub', 'N/A')}"
        ]
        self.profile_text.insert(tk.END, "\n".join(lines))
        self.profile_text.config(state=tk.DISABLED)

    # Google Drive Files
    def load_drive_files(self):
        if not self.tokens.get('google'):
            messagebox.showwarning("Warning", "Please connect Google first")
            return
        threading.Thread(target=self._fetch_drive_files, daemon=True).start()

    def _fetch_drive_files(self):
        self.update_status("Loading Drive files...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            url = 'https://www.googleapis.com/drive/v3/files?pageSize=20&fields=files(id,name,mimeType,modifiedTime,owners)'
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                files = resp.json().get('files', [])
                self.root.after(0, lambda: self.display_drive_files(files))
            elif resp.status_code == 401:
                self.root.after(0, lambda: self.show_text_error(self.drive_text, "⚠️ Token Invalid. Clear Tokens and reconnect."))
            elif resp.status_code == 403:
                msg = (
                    "⚠️ Drive API 403\n\n"
                    "Enable API: https://console.cloud.google.com/apis/library/drive.googleapis.com\n"
                    "Re-consent with scope https://www.googleapis.com/auth/drive.metadata.readonly"
                )
                self.root.after(0, lambda: self.show_text_error(self.drive_text, msg))
            else:
                msg = f"Error: {resp.status_code}\n{resp.text}"
                self.root.after(0, lambda: self.show_text_error(self.drive_text, msg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Drive loaded"))

    def display_drive_files(self, files):
        # cache for selection
        self.drive_cache = files
        self.drive_listbox.delete(0, tk.END)
        if not files:
            self.drive_listbox.insert(tk.END, "No files found")
        else:
            for f in files:
                self.drive_listbox.insert(tk.END, f.get('name', '(no name)'))
        # clear preview
        self.drive_text.config(state=tk.NORMAL)
        self.drive_text.delete(1.0, tk.END)
        self.drive_text.config(state=tk.DISABLED)

    def on_drive_file_select(self, event):
        sel = self.drive_listbox.curselection()
        if not sel or not getattr(self, 'drive_cache', None):
            return
        file = self.drive_cache[sel[0]]
        threading.Thread(target=self._preview_drive_file, args=(file,), daemon=True).start()

    def _preview_drive_file(self, file):
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        file_id = file.get('id')
        mime = file.get('mimeType', '')
        content = None
        try:
            if mime.startswith('application/vnd.google-apps.document'):
                # Export Google Docs to text
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/plain'
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    content = resp.text
            elif mime.startswith('application/vnd.google-apps.spreadsheet'):
                # Export Google Sheets to CSV
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/csv'
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    content = resp.text
            elif mime.startswith('application/vnd.google-apps.presentation'):
                # Export Google Slides to plain text (notes)
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType=text/plain'
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    content = resp.text
            else:
                # Try direct download (text-like only)
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media'
                resp = requests.get(url, headers=headers, stream=True)
                if resp.status_code == 200:
                    # Attempt to decode small text files
                    chunk = resp.raw.read(200000, decode_content=True)
                    try:
                        content = chunk.decode('utf-8', errors='replace')
                    except Exception:
                        content = None
        except Exception as e:
            content = f"Error fetching content: {str(e)}"

        def _render():
            self.drive_text.config(state=tk.NORMAL)
            self.drive_text.delete(1.0, tk.END)
            if content:
                self.drive_text.insert(tk.END, content)
            else:
                self.drive_text.insert(tk.END, "Preview not available for this file type.")
            self.drive_text.config(state=tk.DISABLED)
        self.root.after(0, _render)

    def search_drive_files(self):
        query = self.drive_search.get().strip()
        threading.Thread(target=self._search_drive_files, args=(query,), daemon=True).start()

    def _search_drive_files(self, query):
        self.update_status("Searching Drive...")
        if self.tokens.get('google_refresh'):
            self.refresh_google_token()
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        try:
            q = f"name contains '{query.replace("'", "\'")}'" if query else None
            params = {
                'pageSize': 50,
                'fields': 'files(id,name,mimeType,modifiedTime,owners)'
            }
            if q:
                params['q'] = q
            resp = requests.get('https://www.googleapis.com/drive/v3/files', headers=headers, params=params)
            if resp.status_code == 200:
                files = resp.json().get('files', [])
                self.root.after(0, lambda: self.display_drive_files(files))
            else:
                msg = f"Error: {resp.status_code}\n{resp.text}"
                self.root.after(0, lambda: self.show_text_error(self.drive_text, msg))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Drive search done"))

    def download_selected_drive_file(self):
        sel = getattr(self, 'drive_listbox', None).curselection() if hasattr(self, 'drive_listbox') else []
        if not sel or not getattr(self, 'drive_cache', None):
            messagebox.showwarning("Drive", "Select a file first")
            return
        file = self.drive_cache[sel[0]]
        threading.Thread(target=self._download_drive_file, args=(file,), daemon=True).start()

    def _download_drive_file(self, file):
        headers = {'Authorization': f'Bearer {self.tokens["google"]}'}
        file_id = file.get('id')
        name = file.get('name', 'download')
        try:
            url = f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media'
            resp = requests.get(url, headers=headers, stream=True)
            if resp.status_code == 200:
                path = os.path.join(os.getcwd(), name)
                with open(path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                self.root.after(0, lambda: messagebox.showinfo("Drive", f"Downloaded to {path}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Drive", f"Failed: {resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Drive", f"Error: {str(e)}"))

    def open_selected_drive_in_browser(self):
        sel = getattr(self, 'drive_listbox', None).curselection() if hasattr(self, 'drive_listbox') else []
        if not sel or not getattr(self, 'drive_cache', None):
            messagebox.showwarning("Drive", "Select a file first")
            return
        file = self.drive_cache[sel[0]]
        file_id = file.get('id')
        url = f"https://drive.google.com/file/d/{file_id}/view"
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Drive", f"Failed to open: {str(e)}")

    # Mistral AI
    def save_mistral_key(self):
        key = self.mistral_api_key.get().strip()
        if not key:
            messagebox.showwarning("Mistral", "Please enter an API key")
            return
        # Save to .env
        env_path = os.path.join(os.getcwd(), '.env')
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
            # Update existing key
            for i, line in enumerate(lines):
                if line.startswith('MISTRAL_API_KEY='):
                    lines[i] = f'MISTRAL_API_KEY={key}\n'
                    found = True
                    break
        if not found:
            lines.append(f'MISTRAL_API_KEY={key}\n')
        with open(env_path, 'w') as f:
            f.writelines(lines)
        os.environ['MISTRAL_API_KEY'] = key
        messagebox.showinfo("Mistral", "API key saved to .env")

    def list_mistral_models(self):
        key = self.mistral_api_key.get().strip() or os.getenv('MISTRAL_API_KEY')
        if not key:
            messagebox.showwarning("Mistral", "Please enter API key first")
            return
        threading.Thread(target=self._fetch_mistral_models, args=(key,), daemon=True).start()

    def _fetch_mistral_models(self, key):
        self.update_status("Loading Mistral models...")
        headers = {'Authorization': f'Bearer {key}'}
        try:
            resp = requests.get('https://api.mistral.ai/v1/models', headers=headers)
            if resp.status_code == 200:
                models = resp.json().get('data', [])
                model_ids = [m['id'] for m in models]
                self.root.after(0, lambda: self.mistral_model.config(values=model_ids))
                self.root.after(0, lambda: messagebox.showinfo("Mistral", f"Found {len(model_ids)} models"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Mistral", f"Error: {resp.status_code}\n{resp.text}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Mistral", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Models loaded"))

    def clear_mistral_chat(self):
        self.mistral_history = []
        self.mistral_chat.config(state=tk.NORMAL)
        self.mistral_chat.delete(1.0, tk.END)
        self.mistral_chat.config(state=tk.DISABLED)

    def send_mistral_message(self):
        message = self.mistral_input.get().strip()
        if not message:
            return
        key = self.mistral_api_key.get().strip() or os.getenv('MISTRAL_API_KEY')
        if not key:
            messagebox.showwarning("Mistral", "Please enter API key first")
            return
        
        mode = self.mistral_mode.get()
        
        if mode == 'Agent':
            agent_id = self.mistral_agent_id.get().strip() or os.getenv('MISTRAL_AI_AGENT_ID')
            if not agent_id:
                messagebox.showwarning("Mistral", "Please enter Agent ID for Agent mode")
                return
            self.mistral_input.delete(0, tk.END)
            # Show user message
            self.mistral_chat.config(state=tk.NORMAL)
            self.mistral_chat.insert(tk.END, f"You: {message}\n\n")
            self.mistral_chat.config(state=tk.DISABLED)
            self.mistral_chat.see(tk.END)
            threading.Thread(target=self._send_mistral_agent, args=(key, agent_id, message), daemon=True).start()
        else:
            model = self.mistral_model.get()
            self.mistral_input.delete(0, tk.END)
            # Show user message
            self.mistral_chat.config(state=tk.NORMAL)
            self.mistral_chat.insert(tk.END, f"You: {message}\n\n")
            self.mistral_chat.config(state=tk.DISABLED)
            self.mistral_chat.see(tk.END)
            threading.Thread(target=self._send_mistral_chat, args=(key, model, message), daemon=True).start()

    def _send_mistral_agent(self, key, agent_id, message):
        """Send message to Mistral AI Agent"""
        self.update_status("Agent thinking...")
        try:
            from mistralai.models import MessageInputEntry
            
            client = Mistral(api_key=key)
            
            if self.mistral_agent_conversation_id is None:
                # Start new conversation
                response = client.beta.conversations.start(
                    agent_id=agent_id,
                    inputs=[MessageInputEntry(role="user", content=message)]
                )
                self.mistral_agent_conversation_id = response.conversation_id
            else:
                # Continue existing conversation
                response = client.beta.conversations.append(
                    conversation_id=self.mistral_agent_conversation_id,
                    inputs=[MessageInputEntry(role="user", content=message)]
                )
            
            # Extract assistant response
            assistant_msg = "No response"
            if getattr(response, "outputs", None):
                for output in reversed(response.outputs):
                    role = getattr(output, "role", None)
                    if role == "assistant":
                        content = getattr(output, "content", "")
                        if isinstance(content, list):
                            parts = []
                            for item in content:
                                text = getattr(item, "text", None)
                                parts.append(text if text is not None else str(item))
                            assistant_msg = "".join(parts)
                        else:
                            assistant_msg = str(content)
                        break
            
            def _display():
                self.mistral_chat.config(state=tk.NORMAL)
                self.mistral_chat.insert(tk.END, f"Agent: {assistant_msg}\n\n")
                self.mistral_chat.config(state=tk.DISABLED)
                self.mistral_chat.see(tk.END)
            self.root.after(0, _display)
        except Exception as e:
            error_msg = f"Agent Error: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Mistral Agent", error_msg))
        self.root.after(0, lambda: self.update_status("Ready"))

    def _send_mistral_chat(self, key, model, message):
        self.update_status("Thinking...")
        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json'
        }
        # Add message to history
        self.mistral_history.append({'role': 'user', 'content': message})
        payload = {
            'model': model,
            'messages': self.mistral_history,
            'temperature': 0.7,
            'max_tokens': 1024
        }
        try:
            resp = requests.post('https://api.mistral.ai/v1/chat/completions', headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                assistant_msg = data['choices'][0]['message']['content']
                self.mistral_history.append({'role': 'assistant', 'content': assistant_msg})
                def _display():
                    self.mistral_chat.config(state=tk.NORMAL)
                    self.mistral_chat.insert(tk.END, f"Mistral: {assistant_msg}\n\n")
                    self.mistral_chat.config(state=tk.DISABLED)
                    self.mistral_chat.see(tk.END)
                self.root.after(0, _display)
            else:
                error = f"Error: {resp.status_code}\n{resp.text}"
                self.root.after(0, lambda: messagebox.showerror("Mistral", error))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Mistral", f"Failed: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Ready"))

    # Weather Tab
    def setup_weather_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🌤️ Weather")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="City:").pack(side=tk.LEFT, padx=5)
        self.weather_city = tk.Entry(controls, width=30)
        self.weather_city.pack(side=tk.LEFT, padx=5)
        self.weather_city.insert(0, "New York")
        tk.Button(controls, text="Get Weather", command=self.get_weather).pack(side=tk.LEFT, padx=5)
        
        self.weather_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.weather_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.weather_text.config(state=tk.DISABLED)

    def get_weather(self):
        city = self.weather_city.get().strip()
        if not city:
            messagebox.showwarning("Weather", "Enter a city name")
            return
        threading.Thread(target=self._fetch_weather, args=(city,), daemon=True).start()

    def _fetch_weather(self, city):
        self.update_status("Fetching weather...")
        try:
            url = f'https://wttr.in/{city}?format=j1'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                current = data['current_condition'][0]
                forecast = data['weather']
                self.root.after(0, lambda: self.display_weather(current, forecast))
            else:
                self.root.after(0, lambda: messagebox.showerror("Weather", f"City not found: {city}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Weather", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_weather(self, current, forecast):
        self.weather_text.config(state=tk.NORMAL)
        self.weather_text.delete(1.0, tk.END)
        self.weather_text.insert(tk.END, f"Current Weather:\n{'='*50}\n")
        self.weather_text.insert(tk.END, f"Temp: {current['temp_C']}°C ({current['temp_F']}°F)\n")
        self.weather_text.insert(tk.END, f"Condition: {current['weatherDesc'][0]['value']}\n")
        self.weather_text.insert(tk.END, f"Humidity: {current['humidity']}%\n")
        self.weather_text.insert(tk.END, f"Wind: {current['windspeedKmph']} km/h\n")
        self.weather_text.insert(tk.END, f"Feels Like: {current['FeelsLikeC']}°C\n\n")
        self.weather_text.insert(tk.END, f"5-Day Forecast:\n{'='*50}\n")
        for day in forecast[:5]:
            date = day['date']
            max_temp = day['maxtempC']
            min_temp = day['mintempC']
            desc = day['hourly'][0]['weatherDesc'][0]['value'] if day['hourly'] else 'N/A'
            self.weather_text.insert(tk.END, f"{date}: {min_temp}°C - {max_temp}°C | {desc}\n")
        self.weather_text.config(state=tk.DISABLED)

    # Todo/Tasks Tab
    def setup_todo_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="✓ Todo List")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Task:").pack(side=tk.LEFT, padx=5)
        self.todo_input = tk.Entry(controls, width=50)
        self.todo_input.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Add", command=self.add_todo).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Delete Selected", command=self.delete_todo).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Mark Done", command=self.mark_todo_done).pack(side=tk.LEFT, padx=5)
        
        self.todo_listbox = tk.Listbox(frame, bg='white', fg='#2c3e50', font=('Arial', 10))
        self.todo_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.todos = []
        self.load_todos_from_disk()

    def add_todo(self):
        task = self.todo_input.get().strip()
        if not task:
            messagebox.showwarning("Todo", "Enter a task")
            return
        self.todos.append({'task': task, 'done': False})
        self.todo_input.delete(0, tk.END)
        self.save_todos_to_disk()
        self.refresh_todo_list()

    def delete_todo(self):
        sel = self.todo_listbox.curselection()
        if not sel:
            messagebox.showwarning("Todo", "Select a task")
            return
        del self.todos[sel[0]]
        self.save_todos_to_disk()
        self.refresh_todo_list()

    def mark_todo_done(self):
        sel = self.todo_listbox.curselection()
        if not sel:
            messagebox.showwarning("Todo", "Select a task")
            return
        self.todos[sel[0]]['done'] = True
        self.save_todos_to_disk()
        self.refresh_todo_list()

    def refresh_todo_list(self):
        self.todo_listbox.delete(0, tk.END)
        for t in self.todos:
            prefix = "✓ " if t['done'] else "○ "
            self.todo_listbox.insert(tk.END, f"{prefix}{t['task']}")

    def load_todos_from_disk(self):
        try:
            if os.path.exists('todos.json'):
                with open('todos.json', 'r') as f:
                    self.todos = json.load(f)
                self.refresh_todo_list()
        except:
            self.todos = []

    def save_todos_to_disk(self):
        try:
            with open('todos.json', 'w') as f:
                json.dump(self.todos, f, indent=2)
        except:
            pass

    # Notes Tab
    def setup_notes_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📝 Notes")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Title:").pack(side=tk.LEFT, padx=5)
        self.note_title = tk.Entry(controls, width=40)
        self.note_title.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Save", command=self.save_note).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Load", command=self.load_note).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="List", command=self.list_notes).pack(side=tk.LEFT, padx=5)
        
        self.note_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.note_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def save_note(self):
        title = self.note_title.get().strip()
        content = self.note_text.get(1.0, tk.END).strip()
        if not title or not content:
            messagebox.showwarning("Notes", "Enter title and content")
            return
        try:
            os.makedirs('notes', exist_ok=True)
            with open(f'notes/{title}.txt', 'w') as f:
                f.write(content)
            messagebox.showinfo("Notes", f"Note '{title}' saved")
        except Exception as e:
            messagebox.showerror("Notes", str(e))

    def load_note(self):
        title = self.note_title.get().strip()
        if not title:
            messagebox.showwarning("Notes", "Enter note title")
            return
        try:
            with open(f'notes/{title}.txt', 'r') as f:
                content = f.read()
            self.note_text.delete(1.0, tk.END)
            self.note_text.insert(tk.END, content)
        except FileNotFoundError:
            messagebox.showerror("Notes", f"Note '{title}' not found")
        except Exception as e:
            messagebox.showerror("Notes", str(e))

    def list_notes(self):
        try:
            if not os.path.exists('notes'):
                messagebox.showinfo("Notes", "No notes yet")
                return
            notes = [f[:-4] for f in os.listdir('notes') if f.endswith('.txt')]
            if not notes:
                messagebox.showinfo("Notes", "No notes yet")
                return
            self.note_text.delete(1.0, tk.END)
            self.note_text.insert(tk.END, "Available Notes:\n" + "="*50 + "\n")
            for note in sorted(notes):
                self.note_text.insert(tk.END, f"• {note}\n")
        except Exception as e:
            messagebox.showerror("Notes", str(e))

    # Code Snippet Tab
    def setup_code_snippet_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="</> Code")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Language:").pack(side=tk.LEFT, padx=5)
        self.code_lang = ttk.Combobox(controls, values=['python', 'javascript', 'java', 'cpp', 'sql', 'html', 'css'], width=15)
        self.code_lang.set('python')
        self.code_lang.pack(side=tk.LEFT, padx=5)
        tk.Label(controls, text="Name:").pack(side=tk.LEFT, padx=5)
        self.code_name = tk.Entry(controls, width=30)
        self.code_name.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Save", command=self.save_code).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Load", command=self.load_code).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="List", command=self.list_codes).pack(side=tk.LEFT, padx=5)
        
        self.code_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9))
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def save_code(self):
        lang = self.code_lang.get()
        name = self.code_name.get().strip()
        code = self.code_text.get(1.0, tk.END).strip()
        if not name or not code:
            messagebox.showwarning("Code", "Enter name and code")
            return
        try:
            os.makedirs(f'snippets/{lang}', exist_ok=True)
            with open(f'snippets/{lang}/{name}.txt', 'w') as f:
                f.write(code)
            messagebox.showinfo("Code", f"Snippet '{name}' saved")
        except Exception as e:
            messagebox.showerror("Code", str(e))

    def load_code(self):
        lang = self.code_lang.get()
        name = self.code_name.get().strip()
        if not name:
            messagebox.showwarning("Code", "Enter snippet name")
            return
        try:
            with open(f'snippets/{lang}/{name}.txt', 'r') as f:
                code = f.read()
            self.code_text.delete(1.0, tk.END)
            self.code_text.insert(tk.END, code)
        except FileNotFoundError:
            messagebox.showerror("Code", f"Snippet '{name}' not found")
        except Exception as e:
            messagebox.showerror("Code", str(e))

    def list_codes(self):
        lang = self.code_lang.get()
        try:
            path = f'snippets/{lang}'
            if not os.path.exists(path):
                messagebox.showinfo("Code", f"No {lang} snippets yet")
                return
            snippets = [f[:-4] for f in os.listdir(path) if f.endswith('.txt')]
            if not snippets:
                messagebox.showinfo("Code", f"No {lang} snippets yet")
                return
            self.code_text.delete(1.0, tk.END)
            self.code_text.insert(tk.END, f"Available {lang.upper()} Snippets:\n" + "="*50 + "\n")
            for snippet in sorted(snippets):
                self.code_text.insert(tk.END, f"• {snippet}\n")
        except Exception as e:
            messagebox.showerror("Code", str(e))

    # QR Code Tab
    def setup_qr_code_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📲 QR Code")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Data:").pack(side=tk.LEFT, padx=5)
        self.qr_input = tk.Entry(controls, width=50)
        self.qr_input.pack(side=tk.LEFT, padx=5)
        self.qr_input.insert(0, "https://example.com")
        tk.Button(controls, text="Generate", command=self.generate_qr).pack(side=tk.LEFT, padx=5)
        
        self.qr_display = tk.Label(frame, text="QR Code will appear here", bg='white', fg='#2c3e50', font=('Arial', 12))
        self.qr_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def generate_qr(self):
        data = self.qr_input.get().strip()
        if not data:
            messagebox.showwarning("QR Code", "Enter data")
            return
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.thumbnail((400, 400))
            self.qr_photo = ImageTk.PhotoImage(img)
            self.qr_display.config(image=self.qr_photo, text="")
            try:
                os.makedirs('qr_codes', exist_ok=True)
                img.save(f'qr_codes/{len(os.listdir("qr_codes"))}.png')
            except:
                pass
        except ImportError:
            messagebox.showerror("QR Code", "Install qrcode: pip install qrcode[pil]")
        except Exception as e:
            messagebox.showerror("QR Code", str(e))

    # Crypto Prices Tab
    def setup_crypto_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="₿ Crypto")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Bitcoin", command=lambda: self.get_crypto('bitcoin')).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Ethereum", command=lambda: self.get_crypto('ethereum')).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Cardano", command=lambda: self.get_crypto('cardano')).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Ripple", command=lambda: self.get_crypto('ripple')).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Litecoin", command=lambda: self.get_crypto('litecoin')).pack(side=tk.LEFT, padx=5)
        tk.Label(controls, text="Custom:").pack(side=tk.LEFT, padx=5)
        self.crypto_input = tk.Entry(controls, width=20)
        self.crypto_input.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Search", command=self.search_crypto).pack(side=tk.LEFT, padx=5)
        
        self.crypto_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.crypto_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.crypto_text.config(state=tk.DISABLED)

    def get_crypto(self, crypto_id):
        threading.Thread(target=self._fetch_crypto, args=(crypto_id,), daemon=True).start()

    def search_crypto(self):
        crypto = self.crypto_input.get().strip().lower()
        if not crypto:
            messagebox.showwarning("Crypto", "Enter a cryptocurrency name")
            return
        self.get_crypto(crypto)

    def _fetch_crypto(self, crypto_id):
        self.update_status("Fetching crypto data...")
        try:
            url = f'https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd,eur,gbp&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if crypto_id in data:
                    self.root.after(0, lambda: self.display_crypto(crypto_id, data[crypto_id]))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Crypto", f"Cryptocurrency '{crypto_id}' not found"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Crypto", f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Crypto", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_crypto(self, name, data):
        self.crypto_text.config(state=tk.NORMAL)
        self.crypto_text.delete(1.0, tk.END)
        self.crypto_text.insert(tk.END, f"{name.upper()} Prices\n{'='*50}\n\n")
        self.crypto_text.insert(tk.END, f"USD: ${data.get('usd', 'N/A')}\n")
        self.crypto_text.insert(tk.END, f"EUR: €{data.get('eur', 'N/A')}\n")
        self.crypto_text.insert(tk.END, f"GBP: £{data.get('gbp', 'N/A')}\n\n")
        self.crypto_text.insert(tk.END, f"24h Change: {data.get('usd_24h_change', 'N/A')}%\n")
        self.crypto_text.insert(tk.END, f"Market Cap (USD): ${data.get('usd_market_cap', 'N/A')}\n")
        self.crypto_text.insert(tk.END, f"24h Volume (USD): ${data.get('usd_24h_vol', 'N/A')}\n")
        self.crypto_text.config(state=tk.DISABLED)

    # News Tab
    def setup_news_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📰 News")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Category:").pack(side=tk.LEFT, padx=5)
        self.news_category = ttk.Combobox(controls, values=['general', 'business', 'technology', 'health', 'science', 'sports', 'entertainment'], width=15)
        self.news_category.set('general')
        self.news_category.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Load News", command=self.load_news).pack(side=tk.LEFT, padx=5)
        
        self.news_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 8))
        self.news_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.news_text.config(state=tk.DISABLED)

    def load_news(self):
        category = self.news_category.get()
        threading.Thread(target=self._fetch_news, args=(category,), daemon=True).start()

    def _fetch_news(self, category):
        self.update_status("Fetching news...")
        try:
            # Use demo API key - limited requests per day
            api_key = os.getenv('NEWS_API_KEY', 'demo')
            url = f'https://newsapi.org/v2/top-headlines?category={category}&language=en&pageSize=10&apiKey={api_key}'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                articles = resp.json().get('articles', [])
                self.root.after(0, lambda: self.display_news(articles))
            elif resp.status_code == 426:
                # Upgrade required - demo key exhausted, use fallback
                self.root.after(0, lambda: self.display_fallback_news(category))
            else:
                self.root.after(0, lambda: messagebox.showerror("News", f"Error: {resp.status_code}\nTry setting NEWS_API_KEY in .env"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("News", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_news(self, articles):
        self.news_text.config(state=tk.NORMAL)
        self.news_text.delete(1.0, tk.END)
        if not articles:
            self.news_text.insert(tk.END, "No news available")
        else:
            for i, article in enumerate(articles, 1):
                self.news_text.insert(tk.END, f"{i}. {article.get('title', 'N/A')}\n")
                self.news_text.insert(tk.END, f"   {article.get('description', 'N/A')}\n")
                self.news_text.insert(tk.END, f"   Source: {article.get('source', {}).get('name', 'N/A')} | {article.get('publishedAt', 'N/A')[:10]}\n")
                self.news_text.insert(tk.END, f"   URL: {article.get('url', 'N/A')}\n\n")
        self.news_text.config(state=tk.DISABLED)

    def display_fallback_news(self, category):
        self.news_text.config(state=tk.NORMAL)
        self.news_text.delete(1.0, tk.END)
        self.news_text.insert(tk.END, f"News API demo key exhausted.\n\n")
        self.news_text.insert(tk.END, f"To get real news, sign up for free at:\nhttps://newsapi.org/register\n\n")
        self.news_text.insert(tk.END, f"Then add to .env file:\nNEWS_API_KEY=your_key_here\n\n")
        self.news_text.insert(tk.END, f"Placeholder {category} news:\n" + "="*50 + "\n\n")
        self.news_text.insert(tk.END, f"1. Latest updates in {category}\n")
        self.news_text.insert(tk.END, f"   Get your free API key to see real news headlines\n\n")
        self.news_text.config(state=tk.DISABLED)

    # Quotes Tab
    def setup_quotes_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="💬 Quotes")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Random Quote", command=self.get_random_quote).pack(side=tk.LEFT, padx=5)
        tk.Label(controls, text="Author:").pack(side=tk.LEFT, padx=5)
        self.quote_author = tk.Entry(controls, width=30)
        self.quote_author.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Search Author", command=self.search_author_quotes).pack(side=tk.LEFT, padx=5)
        
        self.quote_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='#f9f9f9', fg='#2c3e50', font=('Georgia', 11))
        self.quote_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.quote_text.config(state=tk.DISABLED)
        self.get_random_quote()

    def get_random_quote(self):
        threading.Thread(target=self._fetch_random_quote, daemon=True).start()

    def _fetch_random_quote(self):
        self.update_status("Fetching quote...")
        # Show custom quote first
        custom_quote = "Embrace the Unknown, Unravel the Future"
        custom_author = "Kirill Zaikin"
        if not hasattr(self, '_custom_quote_shown'):
            self._custom_quote_shown = True
            self.root.after(0, lambda: self.display_quote(custom_quote, custom_author))
            self.root.after(0, lambda: self.update_status("Ready"))
            return
        
        try:
            url = 'https://api.quotable.io/random?minLength=100&maxLength=300'
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                quote = data.get('content', 'No quote')
                author = data.get('author', 'Unknown').replace(', type.fit', '')
                self.root.after(0, lambda: self.display_quote(quote, author))
            else:
                self.root.after(0, lambda: self.fetch_fallback_quote())
        except Exception as e:
            self.root.after(0, lambda: self.fetch_fallback_quote())
        self.root.after(0, lambda: self.update_status("Ready"))

    def fetch_fallback_quote(self):
        try:
            resp = requests.get('https://zenquotes.io/api/random', timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()[0]
                quote = data.get('q', 'No quote')
                author = data.get('a', 'Unknown').replace(', type.fit', '')
                self.display_quote(quote, author)
        except:
            self.quote_text.config(state=tk.NORMAL)
            self.quote_text.delete(1.0, tk.END)
            self.quote_text.insert(tk.END, '"Embrace the Unknown, Unravel the Future"\n\n— Kirill Zaikin')
            self.quote_text.config(state=tk.DISABLED)

    def search_author_quotes(self):
        author = self.quote_author.get().strip()
        if not author:
            messagebox.showwarning("Quotes", "Enter author name")
            return
        threading.Thread(target=self._fetch_author_quotes, args=(author,), daemon=True).start()

    def _fetch_author_quotes(self, author):
        self.update_status("Fetching quotes...")
        try:
            url = f'https://api.quotable.io/quotes?author={requests.utils.quote(author)}&limit=20'
            resp = requests.get(url, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('results'):
                    quotes = data['results']
                    self.root.after(0, lambda q=quotes: self.display_author_quotes(q))
                else:
                    msg = f"No quotes found for '{author}'"
                    self.root.after(0, lambda m=msg: messagebox.showerror("Quotes", m))
            else:
                msg = f"Error: {resp.status_code}"
                self.root.after(0, lambda m=msg: messagebox.showerror("Quotes", m))
        except Exception as e:
            error = str(e)
            self.root.after(0, lambda er=error: messagebox.showerror("Quotes", er))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_quote(self, quote, author):
        self.quote_text.config(state=tk.NORMAL)
        self.quote_text.delete(1.0, tk.END)
        self.quote_text.insert(tk.END, f'"{quote}"\n\n')
        self.quote_text.insert(tk.END, f"— {author}\n")
        self.quote_text.config(state=tk.DISABLED)

    def display_author_quotes(self, quotes):
        self.quote_text.config(state=tk.NORMAL)
        self.quote_text.delete(1.0, tk.END)
        for q in quotes[:10]:
            self.quote_text.insert(tk.END, f'"{q["content"]}"\n\n')
            self.quote_text.insert(tk.END, f"— {q['author']}\n\n")
            self.quote_text.insert(tk.END, "-" * 60 + "\n\n")
        self.quote_text.config(state=tk.DISABLED)

    # Dictionary Tab
    def setup_dictionary_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="📖 Dictionary")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Word:").pack(side=tk.LEFT, padx=5)
        self.dict_input = tk.Entry(controls, width=30)
        self.dict_input.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Search", command=self.search_dictionary).pack(side=tk.LEFT, padx=5)
        
        self.dict_text = scrolledtext.ScrolledText(frame, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.dict_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.dict_text.config(state=tk.DISABLED)

    def search_dictionary(self):
        word = self.dict_input.get().strip()
        if not word:
            messagebox.showwarning("Dictionary", "Enter a word")
            return
        threading.Thread(target=self._fetch_dictionary, args=(word,), daemon=True).start()

    def _fetch_dictionary(self, word):
        self.update_status("Searching dictionary...")
        try:
            resp = requests.get(f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}', timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.root.after(0, lambda: self.display_dictionary(data[0] if isinstance(data, list) else data))
            elif resp.status_code == 404:
                self.root.after(0, lambda: messagebox.showerror("Dictionary", f"Word '{word}' not found"))
            else:
                self.root.after(0, lambda: messagebox.showerror("Dictionary", f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Dictionary", str(e)))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_dictionary(self, data):
        self.dict_text.config(state=tk.NORMAL)
        self.dict_text.delete(1.0, tk.END)
        word = data.get('word', 'N/A')
        phonetic = data.get('phonetic', '')
        self.dict_text.insert(tk.END, f"{word} {phonetic}\n{'='*50}\n\n")
        
        meanings = data.get('meanings', [])
        for meaning in meanings[:3]:
            pos = meaning.get('partOfSpeech', 'N/A')
            self.dict_text.insert(tk.END, f"{pos}\n")
            definitions = meaning.get('definitions', [])
            for i, defi in enumerate(definitions[:3], 1):
                self.dict_text.insert(tk.END, f"  {i}. {defi.get('definition', 'N/A')}\n")
                example = defi.get('example')
                if example:
                    self.dict_text.insert(tk.END, f"     Ex: {example}\n")
            self.dict_text.insert(tk.END, "\n")
        
        antonyms = data.get('antonyms', [])
        if antonyms:
            self.dict_text.insert(tk.END, f"Antonyms: {', '.join(antonyms[:5])}\n")
        
        self.dict_text.config(state=tk.DISABLED)

    # Website Viewer Tab
    # Search Engine Tab
    def setup_search_engine_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🔍 Search")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="Query:").pack(side=tk.LEFT, padx=5)
        self.search_query = tk.Entry(controls, width=50)
        self.search_query.pack(side=tk.LEFT, padx=5)
        
        tk.Label(controls, text="Engine:").pack(side=tk.LEFT, padx=5)
        engines = ['Google', 'DuckDuckGo', 'Bing', 'Wikipedia']
        self.search_engine = ttk.Combobox(controls, values=engines, width=15)
        self.search_engine.set(self.settings.get('default_search_engine', 'Google') if hasattr(self, 'settings') else 'Google')
        self.search_engine.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=5)
        
        # Container for HTML search results (clickable links)
        self.search_results_container = tk.Frame(frame, bg='white')
        self.search_results_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Lazy initialize HtmlFrame when needed
        self.search_html_frame = None

    def perform_search(self):
        query = self.search_query.get().strip()
        if not query:
            messagebox.showwarning("Search", "Enter a search query")
            return
        engine = self.search_engine.get()
        threading.Thread(target=self._perform_search, args=(query, engine), daemon=True).start()

    def _perform_search(self, query, engine):
        self.update_status(f"Searching {engine}...")
        try:
            if engine == 'Wikipedia':
                headers = {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36',
                    'Accept': 'application/json'
                }
                resp = requests.get('https://en.wikipedia.org/w/api.php', params={
                    'action': 'query',
                    'list': 'search',
                    'srsearch': query,
                    'format': 'json'
                }, headers=headers, timeout=10, verify=False)
                if resp.status_code == 200:
                    results = resp.json().get('query', {}).get('search', [])
                    self.root.after(0, lambda r=results, q=query: self.display_wikipedia_results(r, q))
                else:
                    msg = f"Error: {resp.status_code}"
                    self.root.after(0, lambda m=msg: messagebox.showerror("Search", m))
            else:
                # Render DuckDuckGo HTML results in-app with clickable links
                self.root.after(0, lambda q=query, e=engine: self.render_duckduckgo_results(q, e))
        except Exception as e:
            error = str(e)
            self.root.after(0, lambda er=error: messagebox.showerror("Search", er))
        self.root.after(0, lambda: self.update_status("Ready"))

    def render_duckduckgo_results(self, query, engine_label):
        # Load DuckDuckGo HTML results page inside the app for clickable links
        for widget in self.search_results_container.winfo_children():
            widget.destroy()
        try:
            from tkinterweb import HtmlFrame
            from bs4 import BeautifulSoup
            if self.search_html_frame is None or not isinstance(self.search_html_frame, HtmlFrame):
                self.search_html_frame = HtmlFrame(self.search_results_container, messages_enabled=False)
                self.search_html_frame.pack(fill=tk.BOTH, expand=True)
            # Use multiple endpoints for simpler rendering and to avoid blocks
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            html = None
            from urllib.parse import urlparse, parse_qs, unquote, urljoin

            def normalize_href(href_value, engine):
                """Decode engine-specific redirect/query wrappers to real URLs."""
                href = href_value
                # DuckDuckGo wrapped redirect
                if href and 'uddg=' in href:
                    try:
                        qs = parse_qs(urlparse(href).query)
                        if 'uddg' in qs:
                            href = unquote(qs.get('uddg')[0])
                    except Exception:
                        pass
                # Bing sometimes returns relative /url? r=... or /ck/a links
                if engine == 'Bing' and href:
                    if href.startswith('/url?') or href.startswith('/ck/a'):
                        try:
                            qs = parse_qs(urlparse(href).query)
                            cand = qs.get('r') or qs.get('u')
                            if cand:
                                href = unquote(cand[0])
                        except Exception:
                            pass
                    if href.startswith('/'):
                        href = urljoin('https://www.bing.com', href)
                return href
            endpoints = []
            if engine_label == 'Bing':
                endpoints = [f"https://www.bing.com/search?q={requests.utils.quote(query)}&setlang=en-us&FORM=HDRSC1"]
            else:
                endpoints = [
                    f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}",
                    f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}",
                    f"https://duckduckgo.com/?q={requests.utils.quote(query)}&t=h_&ia=web",
                    f"https://lite.duckduckgo.com/lite/?q={requests.utils.quote(query)}"
                ]
            for url in endpoints:
                try:
                    resp = requests.get(url, headers=headers, timeout=10, verify=False)
                    if resp.status_code == 200 and ('result__a' in resp.text or '<a' in resp.text or 'b_algo' in resp.text):
                        html = resp.text
                        break
                except Exception:
                    continue
            if html:
                # Parse quick summary links to show immediately at the top
                summary_frame = tk.Frame(self.search_results_container, bg='white')
                summary_frame.pack(fill=tk.X, padx=4, pady=4)
                summary = scrolledtext.ScrolledText(summary_frame, height=10, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
                summary.pack(fill=tk.BOTH, expand=True)
                summary.tag_config('link', foreground='#1a73e8', underline=True)
                links = []
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    anchors = []
                    if engine_label == 'Bing':
                        anchors = soup.select('li.b_algo h2 a')
                    if not anchors:
                        anchors = soup.select('a.result__a')
                    if not anchors:
                        anchors = soup.select('a[href]')
                    for a in anchors:
                        title = a.get_text(strip=True)
                        href = normalize_href(a.get('href'), engine_label)
                        if href and title and href.startswith(('http://', 'https://')):
                            links.append((title, href))
                        if len(links) >= 10:
                            break
                except Exception:
                    pass
                if not links:
                    # Try a JSON fallback endpoint to still surface something
                    try:
                        json_resp = requests.get(f"https://ddg-webapp-aagd.vercel.app/search?q={requests.utils.quote(query)}", timeout=10)
                        if json_resp.status_code == 200:
                            data = json_resp.json()
                            for item in data.get('results', [])[:10]:
                                title = item.get('title') or item.get('heading')
                                href = item.get('url') or item.get('link')
                                if title and href:
                                    links.append((title, href))
                    except Exception:
                        pass
                summary.insert(tk.END, f"{engine_label} quick links for: {query}\n{'='*70}\n\n")
                if links:
                    def make_link(u):
                        def _open(event, url=u):
                            webbrowser.open(url)
                        return _open
                    for i, (title, href) in enumerate(links, 1):
                        summary.insert(tk.END, f"{i}. {title}\n")
                        start = summary.index(tk.INSERT)
                        summary.insert(tk.END, f"   {href}\n\n")
                        end = summary.index(tk.INSERT)
                        summary.tag_add('link', start, end)
                        summary.tag_bind('link', '<Button-1>', make_link(href))
                else:
                    summary.insert(tk.END, "No summary links found. Scroll below for full HTML view.\n")
                summary.config(state=tk.DISABLED)

                # Full HTML view below
                self.search_html_frame.load_html(html.replace('DuckDuckGo', engine_label))
            else:
                raise Exception("No HTML results")
        except Exception:
            try:
                from bs4 import BeautifulSoup
                results = []

                def ddg_json_fallback(q):
                    tmp = []
                    try:
                        json_resp = requests.get(
                            f"https://ddg-webapp-aagd.vercel.app/search?q={requests.utils.quote(q)}",
                            timeout=10,
                            headers={'User-Agent': headers['User-Agent'], 'Accept': 'application/json'}
                        )
                        if json_resp.status_code == 200:
                            data = json_resp.json()
                            for item in data.get('results', [])[:10]:
                                title = item.get('title') or item.get('heading')
                                href = item.get('url') or item.get('link')
                                if title and href:
                                    tmp.append((title, href))
                    except Exception:
                        pass
                    return tmp

                def jina_scrape(engine):
                    tmp = []
                    try:
                        if engine.lower() == 'duckduckgo':
                            jina_url = f"https://r.jina.ai/https://lite.duckduckgo.com/lite/?q={requests.utils.quote(query)}"
                        else:
                            jina_url = f"https://r.jina.ai/https://www.{engine.lower()}.com/search?q={requests.utils.quote(query)}"
                        jr = requests.get(jina_url, timeout=10, headers={'User-Agent': headers['User-Agent']})
                        if jr.status_code == 200:
                            lines = jr.text.splitlines()
                            for ln in lines:
                                if 'http' in ln and len(ln) < 400 and not ln.lower().startswith('data:'):
                                    for p in ln.split(' '):
                                        if p.startswith('http') and 'google.com' not in p and 'bing.com/search' not in p:
                                            tmp.append((ln.strip()[:80], p))
                                            if len(tmp) >= 10:
                                                return tmp
                    except Exception:
                        pass
                    return tmp

                for ddg_url in endpoints:
                    try:
                        resp = requests.get(ddg_url, headers=headers, timeout=10, verify=False)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            anchors = []
                            if engine_label == 'Bing':
                                anchors = soup.select('li.b_algo h2 a')
                            if not anchors:
                                anchors = soup.select('a.result__a')
                            if not anchors:
                                anchors = soup.select('a[href]')
                            for r in anchors:
                                title = r.get_text(strip=True)
                                href = normalize_href(r.get('href'), engine_label)
                                if href and title and href.startswith(('http://', 'https://')):
                                    results.append((title, href))
                                if len(results) >= 10:
                                    break
                            if results:
                                break
                    except Exception:
                        continue

                if not results:
                    results = ddg_json_fallback(query)
                if not results and engine_label in ('Google', 'Bing', 'DuckDuckGo'):
                    results = jina_scrape(engine_label)

                text = scrolledtext.ScrolledText(self.search_results_container, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
                text.pack(fill=tk.BOTH, expand=True)
                text.tag_config('link', foreground='#1a73e8', underline=True)

                def make_link(url):
                    def _open(event, u=url):
                        webbrowser.open(u)
                    return _open

                text.insert(tk.END, f"{engine_label} Results for: {query}\n{'='*70}\n\n")
                if not results:
                    text.insert(tk.END, "No results found or blocked")
                else:
                    for i, (title, href) in enumerate(results[:10], 1):
                        text.insert(tk.END, f"{i}. {title}\n")
                        start = text.index(tk.INSERT)
                        text.insert(tk.END, f"   {href}\n\n")
                        end = text.index(tk.INSERT)
                        text.tag_add('link', start, end)
                        text.tag_bind('link', '<Button-1>', make_link(href))
                text.config(state=tk.DISABLED)
            except Exception:
                lbl = tk.Label(self.search_results_container, text="Search results could not be loaded. Please try again or open in browser.", bg='white', fg='#c0392b')
                lbl.pack(fill=tk.BOTH, expand=True)
                open_btn = tk.Button(self.search_results_container, text=f"Open {engine_label} in browser", command=lambda: webbrowser.open(f"https://duckduckgo.com/?q={requests.utils.quote(query)}"))
                open_btn.pack(pady=6)

    def display_wikipedia_results(self, results, query):
        # Fallback simple text rendering for Wikipedia (with clickable links)
        for widget in self.search_results_container.winfo_children():
            widget.destroy()
        text = scrolledtext.ScrolledText(self.search_results_container, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        text.pack(fill=tk.BOTH, expand=True)
        text.tag_config('link', foreground='#1a73e8', underline=True)
        
        def make_link(url):
            def _open(event, u=url):
                webbrowser.open(u)
            return _open
        
        text.insert(tk.END, f"Wikipedia Results for: {query}\n{'='*70}\n\n")
        if not results:
            text.insert(tk.END, "No results found")
        else:
            for i, result in enumerate(results[:10], 1):
                title = result.get('title', 'N/A')
                snippet = result.get('snippet', 'N/A').replace('<span class="searchmatch">', '').replace('</span>', '')
                url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                text.insert(tk.END, f"{i}. {title}\n")
                text.insert(tk.END, f"   {snippet}\n")
                start = text.index(tk.INSERT)
                text.insert(tk.END, f"   {url}\n\n")
                end = text.index(tk.INSERT)
                text.tag_add('link', start, end)
                text.tag_bind('link', '<Button-1>', make_link(url))
        text.config(state=tk.DISABLED)

    def update_search_results(self, message):
        self.search_results_text.config(state=tk.NORMAL)
        self.search_results_text.delete(1.0, tk.END)
        self.search_results_text.insert(tk.END, message)
        self.search_results_text.config(state=tk.DISABLED)

    # Basics Tab - Collection of utilities
    def setup_basics_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="⚙️ Basics")
        
        # Inner notebook for basic utilities
        inner = ttk.Notebook(frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System Monitor
        sysmon_tab = ttk.Frame(inner)
        inner.add(sysmon_tab, text="🖥️ System")
        controls = tk.Frame(sysmon_tab, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(controls, text="Refresh", command=lambda: self.refresh_system_monitor(schedule=False)).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Start Live", command=self.start_system_monitor_live).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Stop Live", command=self.stop_system_monitor_live).pack(side=tk.LEFT, padx=5)
        self.sysmon_text = scrolledtext.ScrolledText(sysmon_tab, height=20, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.sysmon_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.sysmon_text.config(state=tk.DISABLED)
        self.refresh_system_monitor(schedule=False)
        
        # Weather
        weather_tab = ttk.Frame(inner)
        inner.add(weather_tab, text="🌤️ Weather")
        weather_controls = tk.Frame(weather_tab, bg='#ecf0f1')
        weather_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(weather_controls, text="City:").pack(side=tk.LEFT, padx=5)
        self.weather_city = tk.Entry(weather_controls, width=30)
        self.weather_city.pack(side=tk.LEFT, padx=5)
        self.weather_city.insert(0, "New York")
        tk.Button(weather_controls, text="Get Weather", command=self.get_weather).pack(side=tk.LEFT, padx=5)
        self.weather_text = scrolledtext.ScrolledText(weather_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.weather_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.weather_text.config(state=tk.DISABLED)
        
        # Todo List
        todo_tab = ttk.Frame(inner)
        inner.add(todo_tab, text="✓ Todo")
        todo_controls = tk.Frame(todo_tab, bg='#ecf0f1')
        todo_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(todo_controls, text="Task:").pack(side=tk.LEFT, padx=5)
        self.todo_input = tk.Entry(todo_controls, width=50)
        self.todo_input.pack(side=tk.LEFT, padx=5)
        tk.Button(todo_controls, text="Add", command=self.add_todo).pack(side=tk.LEFT, padx=5)
        tk.Button(todo_controls, text="Delete Selected", command=self.delete_todo).pack(side=tk.LEFT, padx=5)
        tk.Button(todo_controls, text="Mark Done", command=self.mark_todo_done).pack(side=tk.LEFT, padx=5)
        self.todo_listbox = tk.Listbox(todo_tab, bg='white', fg='#2c3e50', font=('Arial', 10))
        self.todo_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.load_todos_from_disk()
        
        # Notes
        notes_tab = ttk.Frame(inner)
        inner.add(notes_tab, text="📝 Notes")
        notes_controls = tk.Frame(notes_tab, bg='#ecf0f1')
        notes_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(notes_controls, text="Title:").pack(side=tk.LEFT, padx=5)
        self.note_title = tk.Entry(notes_controls, width=40)
        self.note_title.pack(side=tk.LEFT, padx=5)
        tk.Button(notes_controls, text="Save", command=self.save_note).pack(side=tk.LEFT, padx=5)
        tk.Button(notes_controls, text="Load", command=self.load_note).pack(side=tk.LEFT, padx=5)
        tk.Button(notes_controls, text="List", command=self.list_notes).pack(side=tk.LEFT, padx=5)
        self.note_text = scrolledtext.ScrolledText(notes_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.note_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Code Snippets
        code_tab = ttk.Frame(inner)
        inner.add(code_tab, text="</> Code")
        code_controls = tk.Frame(code_tab, bg='#ecf0f1')
        code_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(code_controls, text="Language:").pack(side=tk.LEFT, padx=5)
        self.code_lang = ttk.Combobox(code_controls, values=['python', 'javascript', 'java', 'cpp', 'sql', 'html', 'css'], width=15)
        self.code_lang.set('python')
        self.code_lang.pack(side=tk.LEFT, padx=5)
        tk.Label(code_controls, text="Name:").pack(side=tk.LEFT, padx=5)
        self.code_name = tk.Entry(code_controls, width=30)
        self.code_name.pack(side=tk.LEFT, padx=5)
        tk.Button(code_controls, text="Save", command=self.save_code).pack(side=tk.LEFT, padx=5)
        tk.Button(code_controls, text="Load", command=self.load_code).pack(side=tk.LEFT, padx=5)
        tk.Button(code_controls, text="List", command=self.list_codes).pack(side=tk.LEFT, padx=5)
        self.code_text = scrolledtext.ScrolledText(code_tab, height=25, wrap=tk.WORD, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9))
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # QR Code
        qr_tab = ttk.Frame(inner)
        inner.add(qr_tab, text="📲 QR")
        qr_controls = tk.Frame(qr_tab, bg='#ecf0f1')
        qr_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(qr_controls, text="Data:").pack(side=tk.LEFT, padx=5)
        self.qr_input = tk.Entry(qr_controls, width=50)
        self.qr_input.pack(side=tk.LEFT, padx=5)
        self.qr_input.insert(0, "https://example.com")
        tk.Button(qr_controls, text="Generate", command=self.generate_qr).pack(side=tk.LEFT, padx=5)
        self.qr_display = tk.Label(qr_tab, text="QR Code will appear here", bg='white', fg='#2c3e50', font=('Arial', 12))
        self.qr_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crypto
        crypto_tab = ttk.Frame(inner)
        inner.add(crypto_tab, text="₿ Crypto")
        crypto_controls = tk.Frame(crypto_tab, bg='#ecf0f1')
        crypto_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(crypto_controls, text="Bitcoin", command=lambda: self.get_crypto('bitcoin')).pack(side=tk.LEFT, padx=5)
        tk.Button(crypto_controls, text="Ethereum", command=lambda: self.get_crypto('ethereum')).pack(side=tk.LEFT, padx=5)
        tk.Button(crypto_controls, text="Cardano", command=lambda: self.get_crypto('cardano')).pack(side=tk.LEFT, padx=5)
        tk.Label(crypto_controls, text="Custom:").pack(side=tk.LEFT, padx=5)
        self.crypto_input = tk.Entry(crypto_controls, width=20)
        self.crypto_input.pack(side=tk.LEFT, padx=5)
        tk.Button(crypto_controls, text="Search", command=self.search_crypto).pack(side=tk.LEFT, padx=5)
        self.crypto_text = scrolledtext.ScrolledText(crypto_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.crypto_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.crypto_text.config(state=tk.DISABLED)
        
        # Dictionary
        dict_tab = ttk.Frame(inner)
        inner.add(dict_tab, text="📖 Dict")
        dict_controls = tk.Frame(dict_tab, bg='#ecf0f1')
        dict_controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(dict_controls, text="Word:").pack(side=tk.LEFT, padx=5)
        self.dict_input = tk.Entry(dict_controls, width=30)
        self.dict_input.pack(side=tk.LEFT, padx=5)
        tk.Button(dict_controls, text="Search", command=self.search_dictionary).pack(side=tk.LEFT, padx=5)
        self.dict_text = scrolledtext.ScrolledText(dict_tab, height=25, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Courier', 9))
        self.dict_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.dict_text.config(state=tk.DISABLED)

    def setup_website_viewer_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="🌐 Website")
        
        controls = tk.Frame(frame, bg='#ecf0f1')
        controls.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(controls, text="URL:").pack(side=tk.LEFT, padx=5)
        self.website_url = tk.Entry(controls, width=60)
        self.website_url.insert(0, "https://takirus6524.github.io/ChronoLink-Technologies/index.html")
        self.website_url.pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Open in Browser", command=self.open_in_browser).pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Preview", command=self.preview_website).pack(side=tk.LEFT, padx=5)
        
        self.website_frame = tk.Frame(frame, bg='white')
        self.website_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.website_info = tk.Label(self.website_frame, text="For full website experience with styles & JavaScript:\nClick 'Open in Browser' button\n\nPreview shows basic HTML structure", 
                                    bg='white', fg='#7f8c8d', font=('Arial', 10))
        self.website_info.pack(fill=tk.BOTH, expand=True)

    def open_in_browser(self):
        url = self.website_url.get().strip()
        if not url:
            messagebox.showwarning("Website", "Enter a URL")
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        webbrowser.open(url)

    def preview_website(self):
        url = self.website_url.get().strip()
        if not url:
            messagebox.showwarning("Website", "Enter a URL")
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.website_url.delete(0, tk.END)
            self.website_url.insert(0, url)
        threading.Thread(target=self._preview_website, args=(url,), daemon=True).start()

    def _preview_website(self, url):
        self.update_status(f"Loading {url}...")
        try:
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                html = resp.text
                self.root.after(0, lambda h=html, u=url: self.display_website_preview(h, u))
            else:
                self.root.after(0, lambda: messagebox.showerror("Website", f"Error: {resp.status_code}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Website", f"Failed to load: {str(e)}"))
        self.root.after(0, lambda: self.update_status("Ready"))

    def display_website_preview(self, html, url):
        # Clear existing widgets
        for widget in self.website_frame.winfo_children():
            widget.destroy()
        
        try:
            # Try using tkinterweb for HTML rendering
            from tkinterweb import HtmlFrame
            html_frame = HtmlFrame(self.website_frame, messages_enabled=False)
            html_frame.load_html(html)
            html_frame.pack(fill=tk.BOTH, expand=True)
        except ImportError:
            # Fallback to scrolledtext if tkinterweb not available
            import html as html_lib
            from html.parser import HTMLParser
            
            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                    self.in_script = False
                    self.in_style = False
                
                def handle_starttag(self, tag, attrs):
                    if tag == 'script':
                        self.in_script = True
                    elif tag == 'style':
                        self.in_style = True
                
                def handle_endtag(self, tag):
                    if tag == 'script':
                        self.in_script = False
                    elif tag == 'style':
                        self.in_style = False
                
                def handle_data(self, data):
                    if not self.in_script and not self.in_style:
                        self.text.append(data.strip())
            
            extractor = TextExtractor()
            extractor.feed(html)
            text_content = '\n'.join([t for t in extractor.text if t])
            
            text_widget = scrolledtext.ScrolledText(self.website_frame, wrap=tk.WORD, bg='white', fg='#2c3e50', font=('Arial', 10))
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert(tk.END, f"Website: {url}\n{'='*70}\n\n")
            text_widget.insert(tk.END, f"Rendered Content (text only):\n\n{text_content}\n\n")
            text_widget.insert(tk.END, "\nNote: For full CSS/JS rendering, click 'Open in Browser'")
            text_widget.config(state=tk.DISABLED)

    # Removed obsolete duplicate preview code block


if __name__ == "__main__":
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
