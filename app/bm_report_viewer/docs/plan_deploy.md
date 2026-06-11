# BM Report Viewer — Static Deployment Plan

## Goal

Deploy the Streamlit dashboard as a fully interactive static web page on GitHub Pages —
no server required. All Python logic, charts, and CSV data are bundled into a single
`dist/index.html` that runs entirely in the visitor's browser.

---

## Mechanism: stlite (Streamlit in WebAssembly)

**stlite** ports Streamlit to run inside the browser via
[Pyodide](https://pyodide.org) (CPython compiled to WebAssembly).

```
Browser
 └─ index.html
     ├─ stlite.js   (loads Pyodide + Streamlit runtime from CDN)
     ├─ stlite.css
     └─ inline JS   (mounts virtual filesystem + entrypoint config)
         ├─ app.py  (embedded as text)
         ├─ pages/  (embedded as text)
         ├─ src/    (embedded as text)
         └─ input/  (CSV data embedded as text)
```

- **No Python server needed** — Streamlit runs in a Pyodide WASM thread
- **No backend calls** — pandas, plotly, all deps downloaded from PyPI by Pyodide at load time
- **Fully interactive** — sidebar filters, charts, multipage navigation all work
- **One file** — everything bundled into `dist/index.html`

> Note: first load is slow (~10–20 s) while Pyodide bootstraps and pulls packages.
> Subsequent visits are fast due to browser/CDN caching.

---

## What Gets Built

### `build.py` (new)

A pure-stdlib Python script placed at `app/bm_report_viewer/build.py`.

**What it does:**
1. Reads every `.py` source file (listed explicitly)
2. Reads all 5 CSV files from `input/`
3. Serialises them as a JSON `files` object
4. Injects into an HTML template that calls `stlite.mount()`
5. Writes `dist/index.html`

```
Input (read from disk)          Output
──────────────────────────      ─────────────
app.py                    ──┐
pages/*.py                  │
src/**/*.py                 ├─► dist/index.html  (~500–800 KB)
src/charts/**/*.py          │
input/*.csv               ──┘
```

Run locally:
```bash
cd app/bm_report_viewer
python build.py          # generates dist/index.html
python build.py --open   # generates + opens in browser
```

---

### `.github/workflows/deploy-bm-viewer.yml` (new)

GitHub Actions workflow that:
1. Checks out the repo
2. Runs `build.py` (no pip install needed — stdlib only)
3. Uploads `dist/` as a GitHub Pages artifact
4. Deploys to GitHub Pages

---

## Trigger Conditions

| Event | Behaviour |
|---|---|
| Push to `main` touching `app/bm_report_viewer/**` | Auto-build and deploy |
| Push to `main` touching `.github/workflows/deploy-bm-viewer.yml` | Auto-build and deploy |
| **Workflow Dispatch** (manual) | Trigger build from GitHub UI → Actions tab → Run workflow |

Manual trigger is useful when you update only the CSV data locally and push,
or when you want to force a redeploy without a code change.

---

## GitHub Pages Setup (one-time, manual)

Before the first deploy, enable GitHub Pages in the repo:

1. Go to **Settings → Pages**
2. Set **Source** to **GitHub Actions** (not a branch)
3. Save

The workflow uses the official `actions/deploy-pages@v4` action which handles
branch/artifact management automatically.

---

## File Plan

```
app/bm_report_viewer/
├── build.py                     ← NEW: build script
├── dist/                        ← NEW: generated output (gitignored)
│   └── index.html
└── docs/
    └── plan_deploy.md           ← this file

.github/
└── workflows/
    └── deploy-bm-viewer.yml     ← NEW: CI/CD workflow
```

Add `dist/` to `.gitignore` — it is generated on CI and published via artifact,
not committed to the branch.

---

## stlite Virtual Filesystem

stlite maps the `files` keys directly onto a virtual POSIX filesystem with
`/work/` as the working directory. The app runs as if `app.py` is at `/work/app.py`.

| Virtual path | Source |
|---|---|
| `/work/app.py` | `app.py` |
| `/work/pages/1_Period_Summary.py` | `pages/1_Period_Summary.py` |
| `/work/src/loader.py` | `src/loader.py` |
| `/work/input/layer1_report.csv` | `input/layer1_report.csv` |
| … | … |

`src/loader.py` resolves CSV paths as:
```python
INPUT_DIR = Path(__file__).parent.parent / "input"
# → /work/src/../input → /work/input   ✓
```
This works as-is — no code changes needed.

---

## Dependency Loading

stlite pulls Python packages at runtime via Pyodide's micropip.
The `requirements` array in `stlite.mount()` controls what is installed:

```javascript
requirements: ["plotly", "pandas"]
```

`streamlit` itself is bundled in stlite and does not need to be listed.

---

## Updating the Live Site

To update data, re-encrypt and push:

```bash
cd app/bm_report_viewer
python sync_input.py                         # pull latest CSVs from bm_analytics
FERNET_KEY="<your-key>" python crypt_data.py --encrypt
cd ../..
git add app/bm_report_viewer/input_enc/
git commit -m "data: refresh CSVs YYYY-MM-DD"
git push origin main                         # triggers redeploy automatically
```

---

## Data Protection: Fernet Encryption + Base64 Obfuscation

### Problem

Two concerns with serving data from a public repo:

| Concern | Root cause |
|---|---|
| CI build fails | `input/` is gitignored → `actions/checkout` gives CI an empty directory → `build.py` aborts |
| Raw CSV readable | Anyone can browse the repo or View Source to extract the data |

A `data` branch was considered but **does not work for public repos** — any branch
is publicly readable, so the raw CSVs would still be accessible.

GitHub Actions Secrets cannot store the files directly either: the total CSV size
is ~1.8 MB, well above the 64 KB per-secret limit.

---

### Solution — Fernet Encryption + Secret Key

CSVs are encrypted with **Fernet** (AES-128-CBC + HMAC) before being committed.
The decryption key is stored only as a GitHub Actions secret and never touches the repo.

```
main branch
├── input_enc/*.enc    ← encrypted blobs (committed, publicly visible but unreadable)
├── input/             ← gitignored; populated by CI at build time via decryption
└── ...
```

**Key generation (one-time, run locally):**

```bash
python app/bm_report_viewer/crypt_data.py --keygen
# prints a key — copy it immediately, store in a password manager
# never paste it into any file, commit, or chat message
```

Add the key to GitHub: repo → **Settings → Secrets and variables → Actions →
New repository secret** → name: `FERNET_KEY`, value: `<key from above>`.

**One-time local setup:**

```bash
cd app/bm_report_viewer
python sync_input.py                          # populate input/ from bm_analytics
FERNET_KEY="<your-key>" python crypt_data.py --encrypt
cd ../..
git add app/bm_report_viewer/input_enc/
git commit -m "feat: add encrypted CSV data for deploy"
git push origin main
```

**How the workflow uses it:**

```yaml
- name: Install cryptography
  run: pip install cryptography --quiet

- name: Decrypt CSV data
  env:
    FERNET_KEY: ${{ secrets.FERNET_KEY }}    # key injected by GitHub, never logged
  run: python app/bm_report_viewer/crypt_data.py --decrypt

- name: Build static site
  run: python app/bm_report_viewer/build.py
```

CI decrypts `input_enc/*.enc` → `input/*.csv` → `build.py` embeds them → deploy.

---

### Base64 Obfuscation in HTML

`build.py` also base64-encodes the CSV content before embedding in `index.html`,
so even a viewer of the built page source sees opaque blobs rather than raw rows:

```
index.html
├── pyFiles  (JSON)   — Python source, plain text
└── dataB64  (JSON)   — CSV content, base64-encoded strings
```

The JS layer decodes `dataB64` into the virtual filesystem before mounting:

```javascript
const dataFiles = Object.fromEntries(
  Object.entries(dataB64).map(([path, b64]) => [
    path,
    new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0)))
  ])
);
stlite.mount({ ..., files: { ...pyFiles, ...dataFiles } }, element);
```

Encoded sizes (base64 is ~33% larger than source):

| File | Raw | Base64 in HTML |
|---|---|---|
| `raw_report.csv` | 575 KB | 784 KB |
| `layer3_timeseries.csv` | 884 KB | 1,207 KB |
| others | ~300 KB total | ~420 KB total |
| **Total HTML** | — | **~2.4 MB** |

> Note: base64 in the HTML is obfuscation only — a determined viewer can decode it
> with browser DevTools. The real protection is Fernet encryption on the repo side.
> For access-controlled viewing, host on a server with authentication instead.

---

### Protection Layers Summary

| Layer | What it stops |
|---|---|
| Fernet-encrypted `.enc` files in repo | Direct CSV download from GitHub |
| Key stored only as Actions secret | Key never in git history or logs |
| `input/` gitignored | Accidental commit of raw CSVs |
| Base64 in HTML | Casual View Source inspection |

---

## Known Limitations

| Limitation | Detail |
|---|---|
| First-load latency | ~10–20 s to download Pyodide + packages (~30 MB) |
| No server-side logic | All computation runs in-browser; fine for this app |
| No file upload/write | `st.file_uploader` works; writing to disk does not persist |
| CDN dependency | stlite JS/CSS loaded from jsDelivr; offline use requires local hosting |
| Browser support | Modern Chromium/Firefox; Safari 15.2+; no IE |
