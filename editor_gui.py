"""Local desktop interface for the independent Resonant save editor."""
import hashlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from resonant_save import ROOT, Save, export_slot, export_slot_changes, material_changes, IDENTIFIED_ITEMS

SOURCE_CANDIDATE = 0x1E32CDB1862AA913

class Editor:
    def __init__(self, root):
        self.root = root
        self.path = None
        self.save = None
        root.title('CONTROL Resonant — Experimental Save Editor')
        root.geometry('900x720')
        root.minsize(720, 540)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='CONTROL Resonant', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Save inspector & experimental editor', font=('Segoe UI', 12)).pack(anchor='w', pady=(0, 14))
        ttk.Label(frame, text='Exports a new slot copy. Never installs edits or overwrites existing saves.').pack(anchor='w')
        ttk.Label(frame, text='Named currencies, cosmetic unlock exports, and ability / progression inspection.').pack(anchor='w', pady=(0, 12))
        buttons = ttk.Frame(frame); buttons.pack(fill='x')
        ttk.Button(buttons, text='Open persistent save…', command=self.choose).pack(side='left')
        ttk.Button(buttons, text='Compare another save…', command=self.compare).pack(side='left', padx=8)
        ttk.Button(buttons, text='Inspect abilities & progression', command=self.progression).pack(side='left')
        ttk.Button(buttons, text='Cosmetics…', command=self.cosmetics).pack(side='left', padx=8)
        self.file_text = tk.StringVar(value='No save loaded')
        ttk.Label(frame, textvariable=self.file_text, wraplength=820).pack(anchor='w', pady=10)
        search_row = ttk.Frame(frame); search_row.pack(fill='x', pady=(0, 8))
        ttk.Label(search_row, text='Filter by value or ID:').pack(side='left')
        self.filter = tk.StringVar()
        self.filter.trace_add('write', lambda *_: self.populate())
        ttk.Entry(search_row, textvariable=self.filter).pack(side='left', fill='x', expand=True, padx=8)
        tree_frame = ttk.Frame(frame); tree_frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=('id', 'value', 'label'), show='headings', selectmode='browse')
        for key, label, width in [('id', 'Numeric fact ID', 185), ('value', 'Current value', 160), ('label', 'Identity / evidence', 390)]:
            self.tree.heading(key, text=label); self.tree.column(key, width=width)
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True); scrollbar.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.select)
        edit = ttk.Frame(frame); edit.pack(fill='x', pady=14)
        ttk.Label(edit, text='New value:').pack(side='left')
        self.value = tk.StringVar()
        ttk.Entry(edit, textvariable=self.value, width=22).pack(side='left', padx=8)
        self.export_button = ttk.Button(edit, text='Export edited slot copy', command=self.export, state='disabled')
        self.export_button.pack(side='left', padx=8)
        ttk.Button(edit, text='Export 99 crafting items', command=self.export_materials).pack(side='left', padx=8)
        self.status = tk.StringVar(value='Select a numeric fact to edit.')
        ttk.Label(frame, textvariable=self.status, wraplength=820).pack(anchor='w')
        ttk.Label(frame, text='A checksum-valid export is not yet proven to load correctly in the game.', foreground='#9a5200').pack(anchor='w', pady=(12, 0))

    def choose(self):
        path = filedialog.askopenfilename(title='Choose a *-persi-global save', initialdir=str(ROOT / 'backups'))
        if path: self.load(Path(path))

    def load(self, path):
        try:
            save = Save.read(path)
            if not path.name.endswith('-persi-global'): raise ValueError('Choose a *-persi-global file')
        except (OSError, ValueError) as exc:
            messagebox.showerror('Could not load save', str(exc)); return
        self.save, self.path = save, path
        self.file_text.set(str(path))
        self.status.set(f'Checksum verified. {len(save.facts)} numeric facts; other save data is preserved.')
        self.export_button.configure(state='disabled'); self.value.set(''); self.populate()

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        self.export_button.configure(state='disabled')
        if not self.save: return
        query = self.filter.get().lower()
        for key in sorted(self.save.facts, key=lambda k: (k not in IDENTIFIED_ITEMS, k != SOURCE_CANDIDATE, k)):
            value = self.save.facts[key][0]
            label = IDENTIFIED_ITEMS.get(key, 'Other world fact')
            formatted = format(value, '.17g')
            if query and query not in f'{key:016x} {formatted} {label}'.lower(): continue
            self.tree.insert('', 'end', iid=f'{key:016x}', values=(f'{key:016x}', formatted, label))

    def select(self, _=None):
        selection = self.tree.selection()
        if not selection: return
        key = int(selection[0], 16)
        self.value.set(format(self.save.facts[key][0], '.17g'))
        self.export_button.configure(state='normal')

    def export(self):
        selection = self.tree.selection()
        if not selection or not self.path: return
        try:
            key = int(selection[0], 16)
            output = export_slot(self.path, key, self.save.facts[key][0], float(self.value.get()),
                                 hashlib.sha256(self.save.data).hexdigest())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Export refused', str(exc)); return
        self.status.set(f'Exported: {output}')
        messagebox.showinfo('Export complete', f'Created a new copy of all four slot files in:\n\n{output}\n\nThe original save is unchanged. This export has not been tested in-game.')

    def compare(self):
        if not self.save: return
        path = filedialog.askopenfilename(title='Compare another *-persi-global save', initialdir=str(self.path.parent))
        if not path: return
        try: other = Save.read(path)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Comparison failed', str(exc)); return
        lines = []
        for key in sorted(self.save.facts.keys() | other.facts.keys()):
            before = self.save.facts.get(key, (None,))[0]
            after = other.facts.get(key, (None,))[0]
            if before != after: lines.append(f'{key:016x}    {before}  ->  {after}')
        window = tk.Toplevel(self.root); window.title('Numeric fact changes'); window.geometry('740x450')
        text = tk.Text(window, wrap='none', font=('Consolas', 11))
        text.pack(fill='both', expand=True)
        text.insert('1.0', 'Loaded save -> comparison save\n\n' + ('\n'.join(lines) or 'No numeric changes.'))
        text.configure(state='disabled')

    def export_materials(self):
        if not self.path: return
        try:
            changes = material_changes(self.save)
            output = export_slot_changes(self.path, changes, hashlib.sha256(self.save.data).hexdigest())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Export refused', str(exc)); return
        self.status.set(f'Exported {len(changes)} materials / Reset Items: {output}')
        messagebox.showinfo('Export complete', f'Existing crafting materials and Reset Items set to 99 in a new slot copy:\n\n{output}\n\nSource, Living Shards, upgrade points, and unowned item fields are unchanged. The original save is unchanged.')

    def progression(self):
        if not self.save: return
        from progression import inspect_progression, markdown_report
        try: report=markdown_report(inspect_progression(self.save),self.path)
        except ValueError as exc:
            messagebox.showerror('Unsupported progression data',str(exc));return
        window=tk.Toplevel(self.root);window.title('Read-only ability and progression report');window.geometry('1100x700')
        text=tk.Text(window,wrap='word',font=('Consolas',10));text.pack(fill='both',expand=True)
        text.insert('1.0',report);text.configure(state='disabled')

    def cosmetics(self):
        if not self.save: return
        from cosmetics import inspect_cosmetics, export_cosmetics
        source, snapshot = self.path, self.save
        digest = hashlib.sha256(snapshot.data).hexdigest()
        rows = inspect_cosmetics(snapshot)
        window = tk.Toplevel(self.root); window.title('Cosmetic unlocks'); window.geometry('940x650')
        frame = ttk.Frame(window, padding=16); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Cosmetic unlocks', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        owned = sum(row['unlocked'] for row in rows)
        ttk.Label(frame, text=f'{owned} of {len(rows)} mapped unlocks owned. Select rows with Ctrl or Shift.').pack(anchor='w', pady=6)
        ttk.Label(frame, text='Exports a new save copy. Unlocks are experimental; your equipped appearance stays the same.').pack(anchor='w')
        ttk.Label(frame, text=str(source), wraplength=880).pack(anchor='w', pady=6)
        table = ttk.Frame(frame); table.pack(fill='both', expand=True)
        tree = ttk.Treeview(table, columns=('category', 'name', 'state'), show='headings', selectmode='extended')
        for col, label, width in [('category', 'Category', 110), ('name', 'Cosmetic', 480), ('state', 'Ownership', 170)]:
            tree.heading(col, text=label); tree.column(col, width=width)
        scroll = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
        for row in rows:
            state = ('Unlocked' if row['stored'] else 'Unlocked by default') if row['unlocked'] else 'Locked'
            tree.insert('', 'end', iid=row['id'], values=(row['category'], row['name'], state))
        def export(all_mapped=False):
            selected = [row['id'] for row in rows if not row['unlocked']] if all_mapped else tree.selection()
            if not selected:
                messagebox.showinfo('Cosmetics', 'Select a locked cosmetic to export.', parent=window); return
            try:
                output = export_cosmetics(source, [int(key, 16) for key in selected], digest)
            except (OSError, ValueError) as exc:
                messagebox.showerror('Export refused', str(exc), parent=window); return
            self.status.set(f'Cosmetic export: {output}')
            messagebox.showinfo('Export complete', f'Created a new four-file slot copy:\n\n{output}\n\nOpen the exported persistent save to inspect the result. The source save is unchanged; in-game verification is still needed.', parent=window)
        buttons = ttk.Frame(frame); buttons.pack(fill='x', pady=(12, 0))
        ttk.Button(buttons, text='Export selected unlocks', command=export).pack(side='left')
        ttk.Button(buttons, text='Export all mapped unlocks', command=lambda: export(True)).pack(side='left', padx=10)

if __name__ == '__main__':
    app = tk.Tk()
    Editor(app)
    app.mainloop()
