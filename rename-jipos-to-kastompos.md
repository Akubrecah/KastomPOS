# Rename JiPOS to KastomPOS

This plan outlines the steps to completely rename the project from **JiPOS** to **KastomPOS**. This includes updating UI text, code variables, slugs, and potentially file/directory names.

## Success Criteria
- [x] No occurrences of "JiPOS" remain in the codebase (case-insensitive).
- [x] UI displays "KastomPOS" in titles, headers, and labels.
- [x] Slugs and internal IDs updated to "kastompos".
- [x] Application starts and runs successfully (`uvicorn main:app`).
- [x] Navigation and routes remain functional.

## Tech Stack
- **Backend**: Python (FastAPI)
- **Frontend**: HTML (Jinja2 Templates) + AdminLTE (CSS/JS)
- **Database**: SQLAlchemy models (Store names, etc.)

---

## 📋 Task List

### Phase 1: Identification & Mapping
- **Name**: Map all occurrences of JiPOS
- **Goal**: Find all files containing the old brand name.
- **Agent**: `Explorer`
- **OUTPUT**: List of files and line numbers containing "JiPOS" or "jipos"
- **VERIFY**: Run `grep -ri "jipos" .` and capture output.
- **Status**: [x] DONE

### Phase 2: Template Updates
- **Name**: Replace JiPOS in templates
- **Goal**: Update all HTML files in `/templates/` folder.
- **Files**: `layout.html`, `pos.html`, `rooms.html`, `dashboard.html`, `bookings_calendar.html`, `rooms_dashboard.html`, `purchases.html`
- **Agent**: `frontend-specialist`
- **VERIFY**: Check branding in sidebar, title, and footer.
- **Status**: [x] DONE

### Phase 3: Backend Logic Updates
- **Name**: Replace JiPOS in backend code
- **Goal**: Update `main.py` and any other python files.
- **Agent**: `backend-specialist`
- **Actions**:
    - Update default business name in settings.
    - Update store names in seed data.
- **Status**: [x] DONE

### Phase 4: Asset & Style Updates
- **Name**: Rename images, CSS classes, and slugs
- **Goal**: Ensure no brand traces in file names or styles.
- **Actions**:
    - Update external image URLs (e.g., jipos.co links).
    - Update brand-specific CSS classes (e.g., `text-jipos-teal`).
- **Status**: [x] DONE

### Phase 5: Final Audit & Verification
- **Name**: Global Audit
- **Goal**: Final check using search tools.
- **Status**: [x] DONE

---

## 🏁 Final Verification Log
- [x] `grep -ri "jipos" .` (excluding this plan) returns nothing.
- [x] UI looks perfect with new "KastomPOS" branding.
- [x] Server runs without errors.
