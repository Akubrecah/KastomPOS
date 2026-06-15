# KastomPOS Remote Update Checker

Add a secure, modern background remote update system for the KastomPOS desktop application. When a new version tag (e.g., `v1.0.1`) is pushed to GitHub, the GitHub Actions workflow builds a new Windows setup executable (`KastomPOS_Setup.exe`). The desktop application will check for updates on startup, notify the user, show changelogs in a styled PyQt6 dialog, download the update with a progress bar, and launch the installer automatically.

## User Review Required

> [!IMPORTANT]
> **Windows Admin Privilege Requirements**
> The installer (`KastomPOS_Setup.exe`) requires Administrator privileges (`PrivilegesRequired=admin` in `installer.iss`) to write to the local directory (e.g. Program Files). Spawning the downloaded installer will trigger the Windows User Account Control (UAC) prompt, which is expected. The app must terminate immediately after launching the installer to avoid file locks.

> [!WARNING]
> **Offline Graceful Handling**
> Since KastomPOS is offline-first, the update check MUST run in a background thread and fail silently if there is no internet connection, DNS resolution fails, or GitHub API rate-limits are reached. It must never freeze startup or login.

## Open Questions

> [!IMPORTANT]
> **1. Target Repository for Update Checking**
> Currently, the planned source is the GitHub repository `Akubrecah/KastomPOS`. Is this the exact repository where release tags and installers will be pushed? If it's a private repository or a custom host, we need to handle authorization tokens or query a custom hosted JSON metadata URL.

> [!IMPORTANT]
> **2. Auto-Check vs Manual Check Trigger**
> The planned approach is to automatically check for updates right after login succeeds and the main window opens. Would you also like to add a manual "Check for Updates" button in the admin/settings page of the web UI?

> [!IMPORTANT]
> **3. Client OS Fallbacks**
> If a client runs KastomPOS on macOS or Linux (where `.exe` setup installers cannot run), how should the updater respond? The current design will download the asset but show a notice to manually download the appropriate source or binary, rather than trying to execute the Windows `.exe` setup.

---

## Proposed Changes

### Centralized Version Management

#### [NEW] [app/__init__.py](file:///Users/Akubrecah/Desktop/KastomPOS/app/__init__.py)
Define a central application version constant:
```python
__version__ = "1.0.0"
```

#### [MODIFY] [layout.html](file:///Users/Akubrecah/Desktop/KastomPOS/templates/layout.html)
Render the application version dynamically using Jinja2:
```diff
- <b>KastomPOS Version 1.0 | Copyright &copy; 2026</b>
+ <b>KastomPOS Version {{ app_version|default('1.0.0') }} | Copyright &copy; 2026</b>
```

#### [MODIFY] [main_fastapi.py](file:///Users/Akubrecah/Desktop/KastomPOS/main_fastapi.py)
Import and expose the centralized version to the Jinja2 context global namespace:
```python
from app import __version__ as APP_VERSION
templates.env.globals["app_version"] = APP_VERSION
```

---

### PyQt6 Desktop Client Update System

#### [MODIFY] [main.py](file:///Users/Akubrecah/Desktop/KastomPOS/main.py)
Integrate the background update checking thread and updater dialogs into the application.

1. **Version Declaration**: Import version and export to FastAPI configuration.
2. **Background Check Thread (`UpdateCheckerThread`)**:
   - Executes standard library requests using `urllib.request` to `https://api.github.com/repos/Akubrecah/KastomPOS/releases/latest`.
   - Normalizes and compares release tags.
   - Parses assets to extract the download link for `KastomPOS_Setup.exe` (or fallbacks).
3. **Background Download Thread (`FileDownloadThread`)**:
   - Downloads the installer file in chunks, emitting signals for progress updates.
4. **PyQt6 Update Dialog (`UpdateDialog`)**:
   - A modern PyQt6 styled dialog with rounded card layout, using CSS branding matching the KastomPOS teal `#008080`.
   - Lists changelog description/notes.
   - Shows active download progress, speed, and cancel options.
   - Spawns the installer on success using `subprocess.Popen` (on Windows, using `os.startfile` if available) and terminates the running app.

---

## Verification Plan

### Automated Tests
We will add logic verification scripts in the tests folder:
- **`tests/test_updater.py`**:
  - Test version parsing and comparisons (e.g. `1.0.0` vs `1.0.1`, `v1.1` vs `1.0.9`, etc.).
  - Mock GitHub API response structures and test asset parsing/filtering logic.

### Manual Verification
1. **Mock Remote Version Check**: Temporarily set local `__version__ = "0.9.0"` to trigger the update check on startup.
2. **Check Offline Experience**: Disable network adapters or mock a DNS failure to ensure the app boots normally without crashes or hangs.
3. **Simulate Download & Launch**: Verify that the progress dialog updates correctly, download handles cancellation, and the executable is launched on completion.
