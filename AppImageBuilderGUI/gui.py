"""
Tkinter GUI for the universal AppImage Builder.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from builder import (
    FREEDESKTOP_CATEGORIES,
    DEFAULT_EXCLUDE_LIBS,
    AppImageBuilder,
    AppImageConfig,
)


# ── Colour palette ───────────────────────────────────────────────────────────

BG       = "#1e1e2e"
BG_ALT   = "#262637"
FG       = "#cdd6f4"
FG_DIM   = "#6c7086"
ACCENT   = "#89b4fa"
ACCENT2  = "#a6e3a1"
RED      = "#f38ba8"
SURFACE  = "#313244"
ENTRY_BG = "#2a2a3c"
BTN_BG   = "#45475a"


class AppImageBuilderApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("AppImage Builder")
        self.geometry("820x780")
        self.minsize(720, 680)
        self.configure(bg=BG)

        self.config_obj = AppImageConfig()

        # ─ Style ─
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=ENTRY_BG,
                         borderwidth=0, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Alt.TFrame", background=BG_ALT)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=BG, foreground=ACCENT,
                         font=("Segoe UI", 13, "bold"))
        style.configure("Section.TLabel", background=BG, foreground=ACCENT2,
                         font=("Segoe UI", 11, "bold"))
        style.configure("Dim.TLabel", background=BG, foreground=FG_DIM, font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=FG,
                         insertcolor=FG, padding=5)
        style.configure("TButton", background=BTN_BG, foreground=FG, padding=(10, 5),
                         font=("Segoe UI", 10))
        style.map("TButton", background=[("active", ACCENT)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#11111b",
                         font=("Segoe UI", 11, "bold"), padding=(16, 8))
        style.map("Accent.TButton", background=[("active", ACCENT2)])
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TCombobox", fieldbackground=ENTRY_BG, foreground=FG)
        style.configure("Horizontal.TProgressbar", troughcolor=SURFACE,
                         background=ACCENT, thickness=10)

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        # Scrollable canvas
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))

        pad = {"padx": 14, "pady": 4}
        epad = {"padx": 14, "pady": (0, 8)}

        # ── Title ─
        ttk.Label(self._inner, text="AppImage Builder", style="Header.TLabel").pack(
            pady=(16, 2), **{"padx": 14})
        ttk.Label(self._inner, text="Créer un AppImage à partir de n'importe quel binaire Linux",
                  style="Dim.TLabel").pack(**{"padx": 14, "pady": (0, 12)})

        # ── Section: Binary ─
        self._section("Binaire source")
        frm_bin = ttk.Frame(self._inner)
        frm_bin.pack(fill="x", **epad)
        self.var_binary = tk.StringVar()
        ttk.Entry(frm_bin, textvariable=self.var_binary, width=60).pack(side="left", fill="x", expand=True)
        ttk.Button(frm_bin, text="Parcourir …", command=self._browse_binary).pack(side="left", padx=(6, 0))
        ttk.Button(frm_bin, text="Auto-detect", command=self._auto_detect).pack(side="left", padx=(6, 0))

        # ── Section: App Info ─
        self._section("Informations de l'application")

        self.var_name = self._labeled_entry("Nom", pad)
        self.var_version = self._labeled_entry("Version", pad)
        self.var_comment = self._labeled_entry("Description courte", pad)
        self.var_description = self._labeled_entry("Description longue", pad)
        self.var_homepage = self._labeled_entry("URL page d'accueil", pad)
        self.var_rdns = self._labeled_entry("ID reverse-DNS (optionnel)", pad)

        # Terminal
        self.var_terminal = tk.BooleanVar(value=False)
        ttk.Checkbutton(self._inner, text="Application terminal (pas de GUI)",
                        variable=self.var_terminal).pack(anchor="w", **pad)

        # ── Section: Icon ─
        self._section("Icône")
        frm_icon = ttk.Frame(self._inner)
        frm_icon.pack(fill="x", **epad)
        self.var_icon = tk.StringVar()
        ttk.Entry(frm_icon, textvariable=self.var_icon, width=60).pack(side="left", fill="x", expand=True)
        ttk.Button(frm_icon, text="Parcourir …", command=self._browse_icon).pack(side="left", padx=(6, 0))

        # ── Section: Categories ─
        self._section("Catégories")
        cat_frame = ttk.Frame(self._inner)
        cat_frame.pack(fill="x", **epad)
        self.cat_vars = {}
        cols = 4
        for i, cat in enumerate(FREEDESKTOP_CATEGORIES):
            var = tk.BooleanVar(value=(cat == "Utility"))
            self.cat_vars[cat] = var
            ttk.Checkbutton(cat_frame, text=cat, variable=var).grid(
                row=i // cols, column=i % cols, sticky="w", padx=6, pady=2
            )

        # ── Section: Exclude libs ─
        self._section("Bibliothèques exclues (host-only)")
        self.txt_exclude = tk.Text(self._inner, height=5, bg=ENTRY_BG, fg=FG,
                                   insertbackground=FG, font=("Consolas", 9),
                                   relief="flat", wrap="word")
        self.txt_exclude.pack(fill="x", **epad)
        self.txt_exclude.insert("1.0", "\n".join(DEFAULT_EXCLUDE_LIBS))

        # ── Section: Extra files ─
        self._section("Fichiers supplémentaires (optionnel)")
        frm_extra = ttk.Frame(self._inner)
        frm_extra.pack(fill="x", **epad)
        self.lst_extra = tk.Listbox(frm_extra, height=3, bg=ENTRY_BG, fg=FG,
                                     selectbackground=ACCENT, font=("Consolas", 9),
                                     relief="flat")
        self.lst_extra.pack(side="left", fill="x", expand=True)
        btn_frame = ttk.Frame(frm_extra)
        btn_frame.pack(side="left", padx=(6, 0))
        ttk.Button(btn_frame, text="+", width=3, command=self._add_extra_file).pack(pady=2)
        ttk.Button(btn_frame, text="−", width=3, command=self._remove_extra_file).pack(pady=2)

        # ── Section: Output ─
        self._section("Sortie")
        frm_out = ttk.Frame(self._inner)
        frm_out.pack(fill="x", **epad)
        self.var_output = tk.StringVar(value=os.path.expanduser("~"))
        ttk.Entry(frm_out, textvariable=self.var_output, width=60).pack(side="left", fill="x", expand=True)
        ttk.Button(frm_out, text="Parcourir …", command=self._browse_output).pack(side="left", padx=(6, 0))

        # ── Progress ─
        self.progress = ttk.Progressbar(self._inner, orient="horizontal", mode="determinate",
                                         style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=14, pady=(16, 4))
        self.lbl_status = ttk.Label(self._inner, text="Prêt", style="Dim.TLabel")
        self.lbl_status.pack(padx=14, anchor="w")

        # ── Log ─
        self.txt_log = tk.Text(self._inner, height=8, bg=ENTRY_BG, fg=FG_DIM,
                               insertbackground=FG, font=("Consolas", 9),
                               relief="flat", state="disabled")
        self.txt_log.pack(fill="x", padx=14, pady=(8, 4))

        # ── Build button ─
        ttk.Button(self._inner, text="Construire l'AppImage", style="Accent.TButton",
                   command=self._on_build).pack(pady=(12, 20))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _section(self, title: str):
        ttk.Label(self._inner, text=title, style="Section.TLabel").pack(
            anchor="w", padx=14, pady=(14, 2))

    def _labeled_entry(self, label: str, pad: dict) -> tk.StringVar:
        ttk.Label(self._inner, text=label).pack(anchor="w", **pad)
        var = tk.StringVar()
        ttk.Entry(self._inner, textvariable=var, width=72).pack(fill="x",
                  padx=14, pady=(0, 6))
        return var

    def _browse_binary(self):
        path = filedialog.askopenfilename(title="Sélectionner le binaire Linux")
        if path:
            self.var_binary.set(path)

    def _browse_icon(self):
        path = filedialog.askopenfilename(
            title="Sélectionner l'icône",
            filetypes=[("Images", "*.png *.svg *.xpm *.ico"), ("Tous", "*.*")]
        )
        if path:
            self.var_icon.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Dossier de sortie")
        if path:
            self.var_output.set(path)

    def _add_extra_file(self):
        path = filedialog.askopenfilename(title="Ajouter un fichier")
        if path:
            self.lst_extra.insert("end", path)

    def _remove_extra_file(self):
        sel = self.lst_extra.curselection()
        if sel:
            self.lst_extra.delete(sel[0])

    def _auto_detect(self):
        binary = self.var_binary.get().strip()
        if not binary or not os.path.isfile(binary):
            messagebox.showwarning("Erreur", "Sélectionnez d'abord un binaire valide.")
            return
        # Name from filename
        name = os.path.basename(binary)
        if not self.var_name.get().strip():
            self.var_name.set(name)
        # Version
        ver = AppImageBuilder.detect_version(binary)
        if ver and not self.var_version.get().strip():
            self.var_version.set(ver)
            self._log_msg(f"Version auto-détectée : {ver}")
        else:
            self._log_msg("Version non détectée — veuillez la saisir manuellement.")
        # Arch
        arch = AppImageBuilder.detect_arch(binary)
        self._log_msg(f"Architecture détectée : {arch}")
        # Libs summary
        libs = AppImageBuilder.list_libraries(binary)
        self._log_msg(f"Bibliothèques partagées trouvées : {len(libs)}")

    def _log_msg(self, msg: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _gather_config(self) -> AppImageConfig:
        cats = [c for c, v in self.cat_vars.items() if v.get()]
        excludes = [l.strip() for l in self.txt_exclude.get("1.0", "end").strip().splitlines() if l.strip()]
        extras = list(self.lst_extra.get(0, "end"))
        return AppImageConfig(
            binary_path=self.var_binary.get().strip(),
            app_name=self.var_name.get().strip(),
            app_version=self.var_version.get().strip(),
            app_comment=self.var_comment.get().strip(),
            app_description=self.var_description.get().strip(),
            icon_path=self.var_icon.get().strip(),
            categories=cats,
            homepage_url=self.var_homepage.get().strip(),
            output_dir=self.var_output.get().strip(),
            use_terminal=self.var_terminal.get(),
            exclude_libs=excludes,
            extra_files=extras,
            reverse_domain=self.var_rdns.get().strip(),
        )

    # ── Build ────────────────────────────────────────────────────────────

    def _on_build(self):
        cfg = self._gather_config()
        builder = AppImageBuilder(cfg, log=lambda m: self.after(0, self._log_msg, m))
        errors = builder.validate()
        if errors:
            messagebox.showerror("Erreurs de validation", "\n• ".join([""] + errors))
            return

        # Disable button, run in thread
        for w in self._inner.winfo_children():
            if isinstance(w, ttk.Button):
                w.configure(state="disabled")

        def progress_cb(pct: int, msg: str):
            self.after(0, self._update_progress, pct, msg)

        def run():
            try:
                output = builder.build(progress=progress_cb)
                self.after(0, lambda: messagebox.showinfo(
                    "Succès",
                    f"AppImage créé avec succès !\n\n{output}"
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erreur", str(e)))
            finally:
                self.after(0, self._enable_buttons)

        threading.Thread(target=run, daemon=True).start()

    def _update_progress(self, pct: int, msg: str):
        self.progress["value"] = pct
        self.lbl_status.configure(text=msg)
        self._log_msg(msg)

    def _enable_buttons(self):
        for w in self._inner.winfo_children():
            if isinstance(w, ttk.Button):
                w.configure(state="normal")
