# UnifiedHub - Multi-Purpose Dashboard App

A powerful, feature-rich Tkinter-based dashboard that integrates Google services, Discord, AI, weather, news, search engines, and much more—all in one intuitive interface.

## Downloads

- Latest release (Linux/macOS/Windows): visit GitHub Releases
  - Direct link: [github.com/your-org/UnifiedHub/releases/latest](https://github.com/your-org/UnifiedHub/releases/latest)
    - Download the artifact for your platform from the Releases page
- Local builds (after running `python build.py`):
  - **Linux**: [`distr/linux/UnifiedHub/UnifiedHub`](distr/linux/UnifiedHub)
    - **macOS**: [`distr/macos/UnifiedHub.app`](distr/macos/UnifiedHub)
    - **Windows**: [`distr/windows/UnifiedHub/UnifiedHub.exe`](distr/windows/UnifiedHub/UnifiedHub)

Note: On some systems, clicking local links may open the folder rather than execute the app. Prefer running from terminal or your file explorer.

- Portable builds are located under `dists/` when you build locally (see Installation & Running)

## Features

### Google Integration

- **Gmail**: Read, compose, filter emails; manage labels and view unread count
- **Calendar**: View and create events; 7-day agenda view
- **Drive**: Browse, preview, download, and upload files
- **Tasks**: Create and manage task lists
- **Contacts**: View your Google Contacts
- **Google Keep**: Create notes
- **YouTube**: View subscriptions
- **Profile**: View your Google account info
- **Translation**: Translate text to 10+ languages
- **Maps**: Search locations and open in browser

### Discord Integration

- View servers and member lists
- Send direct messages (requires bot token)
- Browse server details and member info

### Web Search (Multi-Engine)

- **Engines**: Google, DuckDuckGo, Bing, Wikipedia
- **In-App Results**: Clickable links with HTML preview
- **Smart Fallbacks**: JSON APIs, text scraping, jina.ai proxy
- **Link Decoding**: Auto-unwrap Bing/DuckDuckGo redirects
- **Bypass Blocks**: Multiple endpoints + 10s timeouts + retry logic

### AI & Chat

- **Mistral AI**: Chat mode or Agent mode
- Model selection and conversation history
- Real-time streaming responses

### News & Information

- **News**: Latest headlines by category
- **Quotes**: Daily inspirational quotes with API fallbacks
- **Weather**: City weather forecast
- **Dictionary**: Word definitions
- **Crypto**: Real-time cryptocurrency prices
- **Website Viewer**: Preview websites in-app with HTML rendering

### Utilities

- **System Monitor**: Live CPU, memory, disk, network stats
- **Todo/Tasks**: Local task management with persistence
- **Notes**: Save and load personal notes
- **Code Snippets**: Store code samples by language
- **QR Code**: Generate QR codes from text/URLs

### Settings & Customization

- **Dark Mode**: Full recursive UI dark theme (all widgets)
- **Font Size**: Adjustable text size (8-16pt)
- **Search Defaults**: Default engine, result limits (5-50)
- **SSL Control**: Toggle certificate verification
- **Persistent Settings**: Auto-save to `settings.json`

## Prerequisites

- Python 3.8+
- Tkinter (included with Python)
- Dependencies (see `requirements.txt`)
- API keys (optional, for Google, Discord, Mistral)

## Installation & Running

### Quick Start (Python Required)

```bash
# 1. Clone/Download
cd ~/Documents/Dashboard

# 2. Create Virtual Environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install Dependencies
pip install -r requirements.txt

# 4. Configure .env
# Create .env file with your API keys (see OAuth Setup section)

# 5. Run
python unifiedhub.py
```

### Build Standalone Executables (No Python Required)

Convert UnifiedHub to a standalone app for Windows, macOS, or Linux:

```bash
# Install PyInstaller
pip install pyinstaller

# Build for your platform (automatic detection)
python build.py

# Or build for specific platform
python build.py linux    # For Linux
python build.py macos    # For macOS
python build.py windows  # For Windows
```

**Output locations:**

- **Linux**: `dist/linux/UnifiedHub/UnifiedHub`
- **macOS**: `dist/macos/UnifiedHub.app`
- **Windows**: `dist/windows/UnifiedHub/UnifiedHub.exe`

See **BUILD_GUIDE.md** for detailed build instructions, customization, and distribution packaging.

## OAuth Setup

### Google

1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable APIs: Gmail, Calendar, Drive, Tasks, YouTube, Contacts
4. Create OAuth 2.0 credentials (Desktop)
5. Set redirect URI: `http://localhost:8080/callback`
6. Copy Client ID & Secret to `.env`

### Discord

1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application
3. Add OAuth2 redirect: `http://localhost:8080/callback`
4. Copy Client ID & Secret to `.env`

## Usage

### Launch

```bash
python unifiedhub.py
```

### Main Tabs

| Tab | Features |
|-----|----------|
| Google | Gmail, Calendar, Drive, Tasks, Contacts, etc. |
| Discord | Servers, DMs, member info |
| AI | Mistral chat & agent mode |
| Search | Multi-engine search with in-app results |
| Basics | System monitor, weather, todos, notes, QR, crypto, dict |
| News | News headlines by category |
| Quotes | Daily quotes & author search |
| Website | Preview websites in-app |
| Settings | Dark mode, font size, search defaults |

### Control Bar

- **Connect Google/Discord**: OAuth login
- **Refresh All**: Reload all data
- **Clear Tokens**: Logout from all services
- **Exit**: Close app gracefully
- Per-account logout buttons

## Settings

Auto-saved to `settings.json`:

- **Default Search Engine**: Google, DuckDuckGo, Bing, Wikipedia
- **Dark Mode**: Full UI theme toggle
- **Font Size**: 8-16pt
- **Verify SSL**: Toggle certificate verification
- **Results Limit**: 5-50 results per query

## File Structure

```bash
Dashboard/
├── unifiedhub.py          # Main application (3700+ lines)
├── requirements.txt       # Dependencies
├── build.py              # Universal build script (all platforms)
├── build.spec            # PyInstaller configuration
├── build-linux.sh        # Linux build script
├── build-macos.sh        # macOS build script
├── build-windows.bat     # Windows build script
├── BUILD_GUIDE.md        # Detailed build documentation
├── settings.json         # User settings (auto-generated)
├── templates.json        # Email templates (auto-generated)
├── .env                  # API keys (create this, not in repo)
├── .tokens.json          # OAuth tokens (auto-generated)
├── dist/                 # Built executables (after running build.py)
│   ├── linux/
│   ├── macos/
│   └── windows/
├── build/                # Build artifacts (can be deleted)
├── qr_codes/             # Generated QR codes
└── README.md             # This file
```

## Advanced Features

### Dark Mode

- Recursive widget theming
- Separate colors for text inputs, buttons, frames
- Applies to ALL widgets (no white boxes in dark mode)
- Persists across sessions

### Search Engine Intelligence

- BeautifulSoup HTML parsing
- JSON fallback (ddg-webapp-aagd.vercel.app)
- jina.ai text proxy scraping
- Bing `/url?r=` redirect decoding
- DuckDuckGo `uddg=` parameter unwrapping
- Multi-endpoint retries with 10s timeout

### Network Resilience

- SSL warning suppression
- Browser-like User-Agent headers
- `verify=False` for restricted networks
- Automatic proxy fallbacks
- Graceful error handling with browser open button

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Search blocked | Toggle "Verify SSL" in Settings or use browser fallback |
| OAuth fails | Check `.env` credentials and port 8080 availability |
| Dark mode not applied | Toggle in Settings or restart app |
| Website preview blank | Try "Open in Browser" or check site's bot policy |
| Slow Gmail load | Reduce email limit in Gmail settings |

## Performance Tips

1. Disable live system monitor when not in use
2. Limit search results to 10-20 for speed
3. Clear old data before refreshing large lists
4. DuckDuckGo is fastest search engine

## Contributing

Fork, modify, and submit improvements!

## License

MIT License - Free for personal and commercial use

## Support

Report issues or request features via GitHub

---

Built with Python, Tkinter, Google APIs, Discord API, and Mistral AI

Last updated: December 14, 2025 | Version: 1.0
