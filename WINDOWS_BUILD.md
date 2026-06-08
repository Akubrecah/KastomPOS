# Windows Build & Installation Guide for KastomPOS

This guide explains how to build the standalone Windows application and create an installer for KastomPOS.

## CI/CD Automated Build (Recommended for macOS Users)

Since PyInstaller does not support cross-compilation (you cannot build a Windows `.exe` on macOS), we have set up an automated **GitHub Actions** CI/CD pipeline.

### How to trigger the automated build:
1. **Manual Trigger**: Go to the **Actions** tab in your GitHub repository, select **Build Windows Application**, and click **Run workflow**.
2. **Auto Trigger on Push**: Any push to the `main` or `master` branches will trigger a build.
3. **Release Trigger**: Pushing a version tag (e.g., `v1.0.0`) will automatically compile the executable and build the installer.

### Downloading the artifacts:
Once the GitHub Action completes successfully, you can download the **KastomPOS-Windows-Installer** artifact from the run details. It contains:
- `KastomPOS_Setup.exe` (Production Setup Wizard Installer)
- `KastomPOS.exe` (Standalone Portable Executable)

---

## Local Build (Requires Windows OS)

If you have a physical Windows machine or a Windows Virtual Machine (VM), you can build the application locally.

### Prerequisites
1. **Windows OS**: You must perform these steps on a Windows environment.
2. **Python 3.10+**: Ensure Python is installed and added to your PATH.
3. **Inno Setup**: For compiling the `Setup.exe` installer. Download it from [jrsoftware.org](https://jrsoftware.org/isdl.php).

### Step 1: Install Build Dependencies
Open PowerShell or Command Prompt in the project root directory and run:
```bash
pip install -r requirements_win.txt
```

### Step 2: Build the Standalone Executable
Run the build script to bundle the application:
```bash
python build_exe.py
```
- This cleans up old builds and compiles the project into `dist/KastomPOS.exe`.
- You can run `dist/KastomPOS.exe` immediately to launch the app locally.

### Step 3: Create the Windows Installer
If you have Inno Setup installed:
1. Right-click on `installer.iss` and select **Compile**.
2. Or, open the Inno Setup Compiler application, load `installer.iss`, and press `F9`.
3. The installer wizard `KastomPOS_Setup.exe` will be generated in the `dist/` folder.

---

## Database Initialization & Credentials

When the packaged application runs for the first time on a user's machine, it detects that the database is empty and automatically initializes and seeds the SQLite database.

- **Seeded Admin Credentials**:
  - **Username**: `admin`
  - **Password**: `password123`
- **Seeded Cashier Credentials**:
  - **Username**: `cashier1`
  - **Password**: `password123`
- **Seeded Waiter Credentials**:
  - **Username**: `waiter1`
  - **Password**: `password123`

### Technical Details
- **Launcher**: The app uses PyQt6 `QWebEngineView` to wrap the FastAPI backend in a native web view, providing a premium desktop application experience.
- **Database Location**: When frozen inside the PyInstaller package, the database (`pos.db`) is automatically redirected to the user's roaming directory: `%APPDATA%/KastomPOS/pos.db`. This prevents data loss when updating or uninstalling the app.
- **App Styling & Branding**: KastomPOS maintains clean teal-based branding (`#00817a`) throughout the setup, window wrappers, and app interface.

## Troubleshooting
- **Antivirus Flags**: Freshly compiled PyInstaller `.exe` binaries are sometimes flagged by Windows Defender or antivirus tools because they lack a digital signature. To bypass this, add an exception in your antivirus or sign the binary with a trusted certificate.
- **Missing DLLs**: If the application crashes on start, make sure you have the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) installed on your system.
