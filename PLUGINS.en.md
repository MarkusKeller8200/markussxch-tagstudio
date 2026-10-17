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

**Plugin updates …** (top of the plugin page) loads the plugin catalog of the newest release in the selected update
channel (“official versions only” or “including beta versions”) and shows newer versions of built-in plugins and new
plugins. Cards with a newer version show **Update available → Update**. TagStudio only downloads from the official
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

### plugin.py

```python
ACTIONS = [{
    "id": "mark",
    "label": "Mark …",               # button in the tagger
    "where": "tagger",
    "description": "Tooltip / text in the dialog",
    "run_label": "Run",              # text of the start button
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
| `ctx.data_dir` | the plugin's own data folder in the current profile (sign-ins, results) |
| `ctx.shared_dir` | shared folder for large data (models, programs) – the same for all profiles |
| `ctx.run_env(args, on_line)` | start the Python of the own environment (only with `env`) |

Logs (installation, errors with details) are in `~/TagStudio/Logs` – “Logs” button on the plugin page.

`files` are the loaded `MP3File` objects (`f.path`, `f.text("TIT2")`, `f.set_text(key, value)`, `f.items`). Only
change tags via `ctx.edit_tags` – then undo, display and saving work.

Return value of `run`: a dict with `message` (required), optionally `log` (list) and `outputs` (list). Exceptions are
shown as an error message.

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

## Built in: Beatport (unofficial)

Fetches BPM, key (in your notation), genre/subgenre, label, catalogue number, date, ISRC, remixer, cover and
optionally title/artist/album from Beatport. Uses the Beatport API v4 with **your own Beatport account** – the same
way as the beets plugin “beatport4”. Unofficial: Beatport can change access at any time.

1. **Plugins** page → Beatport → **Sign in …**
   - *User name and password*: the password is only used for signing in and **never stored**.
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
