# Plugins for MarKusSXCH TagStudio

*English version – [Deutsch](PLUGINS.md) is the source and may be more up to date.*

Plugins extend the new interface with their own functions. Their actions appear in the **tagger** under “Plugins”
and work on the files selected there. They are managed on the **Plugins** page (sidebar): status, on/off, install
missing packages with a button.

> Plugins are ordinary Python code with full rights. Only use plugins from trustworthy sources.

## Where do plugins live?

| Folder | Content |
|---|---|
| `plugins/` in the program folder | built-in plugins (e.g. **Stems**) |
| `~/TagStudio/Plugins/` (Windows: `C:\Users\<name>\TagStudio\Plugins`) | your own plugins – “Open plugin folder” |
| `~/TagStudio/Plugin-Daten/<id>/` | data of a plugin (models, caches) |

Your own plugin with the same `id` as a built-in one replaces it. After copying it in, click **Reload** on the plugin
page.

### Downloading and updating plugins

**Available plugins …** (top of the plugin page) loads the plugin catalog of the newest release in the selected update
channel (“official versions only” or “including beta versions”) and lists all plugins – grouped into updates, new,
installed and incompatible ones, with a category filter. Cards with a newer version show **Update available → Update**. TagStudio only downloads from the official
releases of this project and checks the checksum. The downloaded plugin is then stored in the “Own plugins” folder
(badge “downloaded”) and replaces the built-in version; **More … → Back to built-in version** removes it again. Your
own plugins are never overwritten.

## Structure

```
Plugins/
  my-plugin/
    plugin.json
    plugin.py
```

### plugin.json

```json
{
  "id": "my-plugin",
  "name": "My plugin",
  "version": "1.0",
  "min_app": "4.8.0",
  "category": "online",
  "api": 1,
  "description": "What it does – shown on the plugin page.",
  "author": "Name",
  "requires": [{"module": "numpy", "label": "NumPy"}],
  "install": [{"id": "std", "label": "Install", "packages": ["numpy"], "hint": "optional hint"}],
  "external": [{"cmd": "ffmpeg", "label": "FFmpeg", "hint": "How to install it …"}],
  "notes": "Additional hint when packages are missing",
  "fields": ["TXXX:MY_PLUGIN_*"],
  "i18n": {"en": {"Mein Text": "My text"}}
}
```

- `min_app`: oldest TagStudio version the plugin works with. The plugin catalog only offers the plugin there. When you
  change a plugin, increase its `version`, otherwise no update appears.
- `links` (optional): `[{"label", "url", "desc"}]` – shown under “More …” on the plugin card, e.g. the download
  of an extra app (`https://` only, at most 8).
- `id`: lower-case letters, digits, `-`, `_`.
- `category`: badge on the plugin card – `online` (online API), `local_api` (local API), `import` (takeover from
  tags), `audio` (audio processing) or `other` (default).
- Page actions with the IDs `test`, `keys` or `login` and `settings` appear as fixed buttons “Test”, “Key”/“Sign in”
  and “Settings”; all others under “More …”.
- `requires`: Python modules that must be present. If they are missing, the plugin shows “Packages missing” and
  offers the `install` variants as buttons (`pip install …` with TagStudio's Python).
- `external`: programs that should be on the search path (hint only, does not block).
- `background`: `true` → actions run as a **background job** in a queue (like stems): the dialog closes immediately and
  you can keep working. The plugin gets its own files, freshly read from disk (`ctx.background` is `True`); processes
  via `ctx.run_env` run with low priority. For long actions that create new files – tag changes and suggestions belong
  in foreground actions. Also possible per action (`"background": true` in the ACTIONS entry).
- `fields`: fields the plugin writes (patterns with `*`). For these fields TagStudio shows the origin
  “TagStudio · plugin name” (tagger, comparison), so your own fields stay recognisable.
- `i18n`: translations of the plugin's texts per language (`en`, `gsw-u-sd-chzh`): German text → translation. The
  interface uses them when that language is selected; texts without a translation stay German.

### Own Python environment (`env`) – for heavy packages

```json
"env": {"python": "3.12", "check": ["my_package"]},
"install": [{"id": "cpu", "label": "Install", "packages": ["my-package"],
             "extra_index": ["https://…"]}]
```

With `env` TagStudio does **not** install the packages into its own Python but creates its own environment with
[uv](https://docs.astral.sh/uv/) (`~/TagStudio/Plugin-Daten/<id>/env`). uv downloads the requested Python version by
itself if needed – so packages such as PyTorch also work when TagStudio runs on a newer Python version for which
they do not exist yet. `check` are modules whose import is checked after the installation. Code that needs these
packages runs as its own process:

```python
rc, tail = ctx.run_env([os.path.join(os.path.dirname(__file__), "worker.py"), "job.json"], on_line)
```

`on_line` receives every output line (e.g. JSON progress messages); cancelling ends the process. `ctx.env_info`
contains the installed variant. Template: `plugins/stems/` (plugin.py + worker.py).

**Extra files (`env.files`, #245):** models or program parts that do not come as a Python package are downloaded by
the installation after the packages – only from GitHub (`https://raw.githubusercontent.com/…`, fixed commit) and
always with a SHA-256 checksum. If the checksum does not match, nothing is stored. If a file goes missing later, the
card shows “Data: …” and “Reinstall …” fetches it again (the environment is kept).

```json
"env": {"python": "3.12", "check": ["torch"],
        "files": [{"label": "Model (18 MB)", "path": "engine/model.pt", "size": 18830452,
                   "url": "https://raw.githubusercontent.com/<owner>/<repo>/<commit>/model.pt",
                   "sha256": "<64 hex characters>"}]}
```

The files are stored under `ctx.shared_dir/<path>` (e.g. `~/TagStudio/Plugin-Daten/<id>/engine/model.pt`).

### plugin.py

```python
ACTIONS = [{
    "id": "mark",
    "label": "Mark …",               # button in the tagger
    "where": "tagger",
    "description": "Tooltip / text in the dialog",
    "run_label": "Run",              # text of the start button
    "short": "Short name",           # optional: shorter name for the plugin card (#248)
    "options": [                     # the form is built from this automatically
        {"key": "text",  "type": "text",   "label": "Text", "default": "hello"},
        {"key": "loud",  "type": "check",  "label": "Upper case"},
        {"key": "n",     "type": "number", "label": "Number", "default": 2},
        {"key": "mode",  "type": "select", "label": "Mode", "choices": [["a", "Variant A"], ["b", "B"]], "default": "a"},
        {"key": "target", "type": "folder", "label": "Folder"},
        {"type": "info", "label": "Just a hint text."},
        {"type": "info", "title": "Instructions", "label": "Hint with links (https:// only, open in the browser).",
         "links": [["Example page", "https://example.org"]]},
    ],
}]

def run(action, ctx, files, options):
    for i, f in enumerate(files):
        ctx.progress(i, len(files), f.path)      # progress; raises Cancelled when cancelled
    ctx.edit_tags(files, lambda f: f.set_text("TXXX:Note", options["text"]), "Set note")
    ctx.log("all good")
    return {"message": f"{len(files)} file(s) edited."}
```

More settings per action:

- `"where": "page"` – button on the plugin card instead of in the tagger (e.g. sign in); then usually
  `"needs_selection": false`.
- Additional option types `password` (never stored), `textarea`, `folders` (several folders, one per line, with a
  “+ Folder …” picker button); `"secret": true` prevents remembering for any type. `"show_if": {"method": "login"}`
  only shows a field when another field has this value.
- A function `status(ctx)` in the plugin returns a status text for the card (e.g. “Signed in as …”).

Instead of `ACTIONS` a function `actions(ctx)` that returns the list works too (e.g. for a dynamic choice).
TagStudio remembers the last used values per action.

### The context `ctx`

| | |
|---|---|
| `ctx.progress(i, total, text, frac=None)` | progress bar; checks for cancelling. `frac` (0–1) = share of the element currently running, so the bar keeps moving during long single steps |
| `ctx.status(text)` | status line in the progress window |
| `ctx.cancelled()` / `ctx.check_cancel()` | query cancelling / stop when cancelled |
| `ctx.log(text)` | line in the log (shown after the run) |
| `ctx.output(path)` | report a created file/folder (“Show in Explorer”) |
| `ctx.edit_tags(files, fn, label)` | change tags – with undo, saved as usual with “Save” |
| `ctx.propose(f, key, new, label, note=, checked=)` | **suggest** a change: after the run a preview with tick boxes appears, nothing is taken over before confirmation (with undo). `kind="cover", data=bytes` for covers (without `data` = info row only). `hint=` hint for the field, `show_same=True` also shows unchanged values (grey, not selectable) |
| `importsync.propose(ctx, f, source, name, feature, value)` | suggest an audio feature (0–100) from another source **with matching**: empty field or file unchanged since the last takeover → ticked, otherwise unticked (“ask”). The taken-over value is remembered in `TXXX:TAGSTUDIO`. Examples: plugins *beaTunes* and *Lexicon* |
| `ctx.propose(…, kind="rating")` | suggest a rating of 0–5 stars (`new` = number of stars, POPM) |
| `ctx.propose(…, kind="remote", old=…, data=…)` | suggest a change **outside the file** (e.g. in Lexicon): `old` = current value there, `data` = details for the plugin. After confirmation TagStudio calls the plugin's `apply_remote(ctx, items)` (returns `{"message", "errors"}`) |
| `ctx.djset()` | current DJ set: `{"name", "paths"}` (read only) |
| `ctx.data_dir` | the plugin's own data folder in the current profile (sign-ins, results) |
| `ctx.shared_dir` | shared folder for large data (models, programs) – the same for all profiles |
| `ctx.run_env(args, on_line)` | start the Python of the own environment (only with `env`) |

Logs (installation, errors with details) are in `~/TagStudio/Logs` – “Logs” button on the plugin page.

`files` are the loaded `MP3File` objects (`f.path`, `f.text("TIT2")`, `f.set_text(key, value)`, `f.items`). Only
change tags via `ctx.edit_tags` – then undo, display and saving work.

Return value of `run`: a dict with `message` (required), optionally `log` (list) and `outputs` (list). With
`"open": {"target": "tagger" | "djset" | "djadd", "files": [paths], "label": "…"}` TagStudio loads the files into the
tagger and optionally as a new DJ set or additionally into the DJ set (order kept). Exceptions are shown as an error
message.

More functions a plugin can offer (all optional):

- `on_event(ctx, event, data)` – TagStudio reports `"files_moved"` (`[{"old", "new"}]`: renamed, archived, restored)
  and `"files_added"` (`[path]`: newly taken into the library, Prepare). Runs in the background, errors only go to the
  log.
- `detect_files(ctx, paths)` – Prepare: a status step whose “detection” is the plugin id treats these files as done
  (example: Lexicon – the file is in Lexicon).
- `apply_remote(ctx, items)` – see `kind="remote"` above.
- `playlists(ctx)` → `[{id, name, path, depth, type}]` and `playlist_files(ctx, id)` → `{name, files, missing}` – the
  DJ set then offers “From <plugin> …”: select playlists and load them as lists (example: Lexicon).
- `store_purchases(ctx)` → `{"name", "items": [{id, title, mix, artist, dur, key, bpm, catalog, isrc, label, release,
  genre, url, bought, preorder, dl}]}` and `store_download(ctx, items, dest)` → `{"files": {id: [paths]}, "failed"}` –
  page “Purchases” (#285): collect the bought tracks of a store and download missing ones (example: Beatport).
- `playlist_push(ctx, playlist, options)` – Playlists page › More ▾ › “Send to <plugin> …” (#273). `playlist` =
  `{"name", "folder", "items": [{"path", "artist", "title"}], "remote"}` (`remote` = the id the plugin returned the last
  time, otherwise `None`). Return `{"ok", "id", "message", "missing": [paths], …}`; TagStudio remembers `id` per
  playlist, sending again should update the same playlist. Optional `push_ready(ctx)` → `(ready, hint)`, e.g. when
  writing is switched off in the plugin. Rules: never delete anything, skip and report entries without a file, record
  changes in the plugin's own journal (example: Lexicon – creates the playlist or inserts missing tracks at their
  position, removes nothing).

## Tool: API recorder (for developers)

`python tools/api_recorder.py https://… [--host api.…]` opens the page in Chromium (Playwright), records the page's
JSON calls while you click through it and, after closing, writes `recording.json` and `service.json` – a draft of the
`"service"` section with endpoints like `/tracks/{track_id}`, parameters and response fields (folder
`~/TagStudio/API-Aufnahmen/<host>`). Cookies, sign-ins, tokens, passwords and e-mail addresses are never stored. Only
use it for interfaces you are allowed to use.

## Built in: Key (OpenKeyScan) and OpenKeyScan app

Two ways to detect the key with [OpenKeyScan](https://www.openkeyscan.com) (Rekordcloud) – same result, same
preview (#217):

- **Key (OpenKeyScan)** (`keyscan`, #245) – no extra app, offline. Own environment with Python 3.12, PyTorch,
  librosa and PyAV (variant **processor** or **NVIDIA**, approx. 1 GB). The network and model of the open-source engine
  ([openkeyscan-analyzer](https://github.com/rekordcloud/openkeyscan-analyzer), MIT; model trained on the GiantSteps
  datasets, CC BY-SA 4.0) are downloaded by the installation from a fixed commit and verified with SHA-256.
  Actions: **Detect key (OpenKeyScan) …** (preview) and **Analyse key in the background …** (only remembers the
  result, writes nothing – afterwards the preview appears immediately).
- **OpenKeyScan app** (`openkeyscan`, #244) – via the local API of the desktop app (`http://localhost:58721`,
  Windows and macOS). Up to 20 tracks one by one (`/analyze/single`), more via the queue (`/analyze/add`,
  `/analyze/results`). Only addresses on this computer, never via a proxy; `/analyze/clear` is never called.
  **Switch off “auto-tagging” in the app** – otherwise it writes to the files itself. TagStudio warns if a file
  changes during the analysis. If the server does not respond, TagStudio starts the app itself (option “Start the app
  automatically when needed”, the program is searched for or entered under Options) and waits up to 30 s; if the app
  runs without a server, the message says so. **More …** has download links for Windows and Mac.
- For the plugin “Key (OpenKeyScan)”, **Test** checks the environment (loads the model, reports the device); under
  **Options** you can choose “Always processor”.

Preview (both): `TXXX:OPENKEYSCAN_KEY` (Camelot, e.g. `09A`, origin “OpenKeyScan”) and on request `TKEY` in the
configured notation. TKEY is only ticked when it is empty (option “Also tick a differing key …”). The note compares
with TKEY, Beatport (`TXXX:INITIAL_KEY`) and the Mixed In Key comment: same, related (±1 on the wheel or relative
key) or different; plus the model's confidence (`keyscan` only). Results are cached per file (size + modification
time). Usable as a step in **Prepare** (step type “Plugin”, mode “only fill empty fields”).

## Built in: Stems

Separates tracks into single stems with [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)
(Demucs, BS-RoFormer, Mel-Band-RoFormer). Runs in its own environment with Python 3.12 – independent of the Python
version TagStudio runs on. FFmpeg is installed along with it.

1. **Plugins** page → for “Stems” install a variant: **processor** (runs everywhere), **AMD/Intel graphics
   (DirectML)** (Windows, experimental) or **NVIDIA graphics card**. Download 1–4 GB in total. The variant can be
   changed later under “Reinstall / other variant …”.
2. Select tracks in the tagger → **Plugins → Create stems …** → choose model, stems, format, location.

Result: folder `<title> – Stems` next to the track (or in the chosen folder) with `<title> (Vocals).flac` etc. For MP3,
tags and cover are copied and the title gets the suffix “(Vocals)”. The models end up in
`~/TagStudio/Plugin-Daten/stems/modelle` and are downloaded only once.

## Built in: Beatport

Fetches BPM, key (in your notation), genre/subgenre, label, catalogue number, date, ISRC, remixer, cover and
optionally title/artist/album from Beatport, plus Beatport playlists and the Purchases page. Uses the **official
Beatport API v4** – all endpoints with their status are listed under Plugins › Beatport › “Integration …”. Only the
fallback sign-in and downloading bought files are unofficial (Beatport does not offer downloads officially).

1. **Plugins** page → Beatport → **Sign in …**
   - *Own API access* (default, recommended): client ID, client secret, user name, password – see below.
   - *User name and password* (unofficial fallback, like the beets plugin “beatport4” via the docs page's ID): the
     password is only used for signing in and **never stored**.
   - *Token from the browser*: sign in on api.beatport.com/v4/docs, developer tools (F12) → Network → request
     “token” → copy the response (JSON) and paste it.
   Only the token is stored, on Windows encrypted with DPAPI (only your user account can read it). Expired tokens are
   renewed automatically.
2. Select tracks in the tagger → **Plugins → Fetch Beatport data …** → choose fields, “Fill empty fields only” or
   “Overwrite”.
3. **Preview:** per file the Beatport track found with its certainty in %, below it every field old → new. Uncertain
   matches are not preselected. With “Fill empty fields only”, already filled fields with a different value still
   appear – but **unticked** (“already filled”). **All fields Beatport delivers** appear: identical values grey with
   “=” (not selectable), the same value in a different notation (e.g. key Am = 08A, BPM 124.0 = 124) and fields
   deselected in the options unticked, an available cover as an info row. The log shows per track which fields
   Beatport delivered. “Apply” changes the tags (can be undone); as always they are only written with “Save”.

Matching: first via a stored Beatport ID (`TXXX:BEATPORT_TRACK_ID`), then ISRC, otherwise a search for artist + title
+ mix name; title, artist, length and mix name are rated. At most ~3 requests per second.

**Own API access (#286):** if you have your own API app at Beatport, choose the method “Own API access” under
“Sign in …” and enter client ID, client secret, user name and password (password grant as in the official docs).
Client ID and secret are stored encrypted in the plugin (leave empty = use the stored ones), the password never. The
token is renewed with client ID and secret; “Sign out” revokes it at Beatport.

**Followed artists and labels (#288):** “Add followed artists and labels to Discover …” reads whom you follow on
Beatport (“My Beatport”, `/my/beatport/artists/` and `/labels/`) and adds them to the lists in “Discover”. Existing
ones stay, nothing is changed at Beatport.

**Purchases (#285):** the page “Purchases” uses `store_purchases(ctx)` (all purchases with title, mix, key, BPM,
catalogue number, link, purchase date) and `store_download(ctx, items, dest)` (download missing ones into the inbox).

**Playlists (#284, read only):** after signing in, Playlists › Import ▾ offers **“From Beatport …”**: choose your own
Beatport playlists; they arrive as playlists with entries without a file (artist, title, mix, ISRC, length, link to
Beatport) in the folder “Beatport”; sure matches in the library are linked right away, the rest can be matched or
exported as a shopping list. Fetching again updates the playlist and keeps the links. Unofficial here as well
(`/my/playlists/`): if Beatport returns nothing, the field names of the response are in the log (Plugins › Beatport).

## Built in: Spotify and SoundCloud

Read your playlists and track data at Spotify or SoundCloud – **read only**, nothing in your account is changed. Both
need **your own app** at the service; TagStudio does not ship shared credentials.

- **Spotify:** sign in on [developer.spotify.com](https://developer.spotify.com/dashboard) with your account (Spotify
  Premium required), “Create app”, enter exactly `http://127.0.0.1:8765/callback` as redirect URI, choose “Web API”.
  Paste the client ID under Plugins › Spotify › **Sign in …** (no secret needed, sign-in with PKCE). Development mode:
  at most 5 users per app. Since February 2026 Spotify returns tracks only for own or collaborative playlists, search
  at most 10 results per query and no label on albums.
- **SoundCloud:** register an app in “SoundCloud for Developers” (self-registration with Artist Pro), redirect URI
  `http://127.0.0.1:8766/callback`. Paste client ID **and** client secret under Plugins › SoundCloud › **Sign in …**
  (OAuth 2.1 with PKCE).
- **Sign in …** opens the sign-in page in the browser; TagStudio briefly answers the redirect to `127.0.0.1` itself.
  If that does not work (port in use), choose “Paste address”: after agreeing, paste the address from the address bar.
  Credentials and token are stored encrypted in the plugin's data folder and renewed automatically; “Sign out …”
  deletes the sign-in (optionally also the credentials).
- **Playlists › Import ▾ › “From Spotify …” / “From SoundCloud …”** (appears after signing in): Liked Songs or likes,
  own tracks (SoundCloud) and your playlists as playlists with **entries without a file** (artist, title, mix, ISRC,
  duration, link) in the folder “Spotify” or “SoundCloud” – then “Match with library …” and “Export shopping list …”
  (with link). “↗” in the list opens the track at the service.
- **Online metadata:** sources “Spotify” and “SoundCloud” (off until you tick them) – album, date, ISRC, genre, cover
  and as fields `TXXX:SPOTIFY_TRACK_ID`/`TXXX:SPOTIFY_URL` or `TXXX:SOUNDCLOUD_TRACK_ID`/`TXXX:SOUNDCLOUD_URL`.
- **“Add followed artists to “Discover” …”:** adds the artists (Spotify, optionally also your top 20) or accounts
  (SoundCloud) you follow under Discover › Followed artists.
- The card lists all read endpoints with their implementation state under “endpoints”; the API tester calls them with
  your sign-in (token blacked out).

## Built in: Lexicon

Connects TagStudio with [Lexicon DJ](https://www.lexicondj.com) through its Local API (in Lexicon: Settings ›
Integrations › switch on Local API; default `http://localhost:48624`).

- **Take over from Lexicon …** (tagger): values without an official MP3 field go into **own fields with the origin
  “Lexicon”**, unchanged as in Lexicon (1–10): `TXXX:LEXICON_DANCEABILITY`, `…_ENERGY`, `…_HAPPINESS`, `…_POPULARITY`,
  `…_COLOR`, `…_TAGS` (other tag categories, optionally grouping or comment) and `TXXX:LEXICON_MOOD` (officially `TMOO`
  in ID3v2.4). Rating in `POPM`. The TagStudio fields (ENERGY etc.) stay unchanged. Matched directly by path, otherwise by artist + title. Beatgrid
  and cue points from Lexicon are compared with the file (note in the preview).
- **Open from Lexicon …** (tagger, no selection needed): load the tracks selected in Lexicon, the selected playlist or a
  playlist by its name (`Sets/Friday`) into the tagger or take them over as a DJ set. Folders and smartlists work too.
- **Lexicon values into TagStudio fields …** (tagger): takes the values from the files' `LEXICON_` fields into ENERGY,
  DANCEABILITY, HAPPINESS (×10) and the mood – with preview and matching, without a connection to Lexicon. Taking over
  from Lexicon can do this right away (“Also take over into the TagStudio fields”).
- **DJ set › From Lexicon …:** fetch all playlists (and the queue), tick them; each is saved as a list “Lexicon: …”, the
  first one is loaded.
- **Prepare:** the status step “Lexicon” detects tracks that are in Lexicon.
- **Writing back** (Plugins › Lexicon › Settings, off by default):
  - Update paths when TagStudio renames, archives or restores files.
  - Add tracks newly taken into the library, put them into a playlist (default “TagStudio Neu”) and have Lexicon
    analyse them.
  - **Send to Lexicon …** (tagger): title, artist, album, genre, BPM, key, rating, energy etc. and mood as mood tags –
    with a preview, only Lexicon is changed.
  - **DJ set as Lexicon playlist …** (More …).
  - **Undo last change in Lexicon …** restores values and paths.

  The Lexicon API has no sign-in: TagStudio only writes to Lexicon on this computer (localhost) and never deletes
  anything. Every change is recorded in the journal (`Plugin-Daten/lexicon/journal.json`).
