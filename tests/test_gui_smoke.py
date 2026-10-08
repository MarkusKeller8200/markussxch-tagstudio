"""Rauchtest der Oberfläche: startet das Programm, lädt zwei Ordner, kopiert, macht rückgängig.
Wird übersprungen, wenn kein Bildschirm (bzw. kein tkinter) verfügbar ist."""
import os
import shutil
import tempfile
import time
import unittest

from helpers import write_mp3, text

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_TK = True
except Exception:  # noqa: BLE001 – kein tkinter oder kein Display
    HAVE_TK = False


@unittest.skipUnless(HAVE_TK, "kein tkinter/Display verfügbar")
class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_gui_")
        # Einstellungen, Sicherungen und Cache in den Testordner umleiten
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        import tagstudio
        import thumbs
        self.ts = tagstudio
        tagstudio.CONFIG = os.path.join(self.dir, ".tagstudio.json")
        tagstudio.CONFIG_OLD = os.path.join(self.dir, ".mp3tagcompare.json")
        import core
        core.CONFIG, core.CONFIG_OLD = tagstudio.CONFIG, tagstudio.CONFIG_OLD
        thumbs.CACHE_DIR = os.path.join(self.dir, "cache")
        for m in ("showinfo", "showwarning", "showerror"):
            setattr(tagstudio._messagebox, m, lambda *a, **k: None)
        tagstudio._messagebox.askyesno = lambda *a, **k: True
        tagstudio._messagebox.askyesnocancel = lambda *a, **k: False
        for side, title in (("L", "Links"), ("R", "Rechts")):
            os.makedirs(os.path.join(self.dir, side))
            for i in (1, 2):
                write_mp3(os.path.join(self.dir, side, f"{i}.mp3"),
                          [text("TIT2", f"{title} {i}"), text("TRCK", str(i))])

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_load_copy_undo_save(self):
        app = self.ts.App()
        try:
            app.left_path.set(os.path.join(self.dir, "L"))
            app.right_path.set(os.path.join(self.dir, "R"))
            app.compare(ask=False)
            t0 = time.time()
            while app.loading and time.time() - t0 < 30:
                app.update()
                time.sleep(0.02)
            app.update()
            self.assertEqual(len(app.pairs), 2)
            l, r = app._files()
            self.assertIsNotNone(l)
            app.sel = {"TIT2"}
            app.copy_sel("lr")
            self.assertEqual(r.text("TIT2"), l.text("TIT2"))
            app.do_undo()
            self.assertTrue(r.text("TIT2").startswith("Rechts"))
            app.do_redo()
            self.assertTrue(app.save_all())
            self.assertTrue(r.text("TIT2").startswith("Links"))
            self.assertTrue(any(n.endswith(".zip") for n in os.listdir(app.cfg.get("backup_dir") or
                                                                      self.ts.backup.default_dir())))
        finally:
            app.destroy()

    def test_xml_editor(self):
        from helpers import txxx
        from id3tags import MP3File
        path = os.path.join(self.dir, "xml.mp3")
        write_mp3(path, [text("TIT2", "XML"), txxx("Analyse", '<a x="1"><b>Text</b></a>')])
        app = self.ts.App()
        try:
            f = MP3File(path)
            d = app._xml_dialog(f, "TXXX:Analyse", f.text("TXXX:Analyse"), True)
            app.update()
            self.assertIn("Gültiges", d.xml_status.cget("text"))
            d.xml_tool("format")
            self.assertIn("\n  <b>Text</b>", d.xml_text.get("1.0", "end-1c"))
            d.xml_text.insert("end", "<kaputt>")
            app.update()
            time.sleep(0.4)
            app.update()
            self.assertIn("Zeile", d.xml_status.cget("text"))
            d.xml_text.delete("end-9c", "end-1c")
            d.xml_close(True)
            self.assertTrue(f.text("TXXX:Analyse").startswith("<a x=\"1\">\n"))
            self.assertTrue(f.is_modified())
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
