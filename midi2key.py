import tkinter as tk
from tkinter import messagebox, filedialog
import mido
import threading
import json
import keyboard
import os
import sys

class MidiToKeyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("midi2key")

        # 初期のMIDIノート番号とキーボードキーのマッピング (「Sky 星を紡ぐ子どもたち」のKeyマッピング)
        self.mapping = {
            48: "y", 50: "u", 52: "i", 53: "o", 55: "p",
            57: "h", 59: "j", 60: "k", 62: "l", 64: ";",
            65: "n", 67: "m", 69: ",", 71: ".", 72: "/"
        }

        self.running = False
        self.threads = []
        self.inports = []

        self.note_entry_active = False
        self.note_entry_listener_thread = None

        self.create_widgets()

        settings_path = os.path.join(self.get_app_dir(), "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                data = json.load(f)
                self.mapping = {int(k): v for k, v in data.get("mapping", {}).items()}
                selected_ports = data.get("selected_ports", [])
                for port, var in self.port_vars.items():
                    var.set(port in selected_ports)

        self.refresh_listbox()

    def get_app_dir(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def create_widgets(self):
        tk.Label(self.root, text="🎛 MIDIポート選択（複数可）").grid(row=0, column=0, sticky='w', padx=10, pady=(10, 0))
        self.port_vars = {}
        self.port_frame = tk.LabelFrame(self.root, text="", padx=5, pady=5, relief=tk.GROOVE, borderwidth=2)
        self.port_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        for port in mido.get_input_names():
            var = tk.BooleanVar()
            cb = tk.Checkbutton(self.port_frame, text=port, variable=var)
            cb.pack(anchor="w")
            self.port_vars[port] = var

        tk.Label(self.root, text="※MIDIポートを追加・削除した場合はアプリを再起動してください。", fg="red").grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky='w')

        tk.Label(self.root, text="📄 マッピング一覧").grid(row=3, column=0, sticky='w', padx=10, pady=(10, 0))
        frame = tk.Frame(self.root)
        frame.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")
        self.mapping_listbox = tk.Listbox(frame, height=8, width=40)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=self.mapping_listbox.yview)
        self.mapping_listbox.config(yscrollcommand=scrollbar.set)
        self.mapping_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.mapping_listbox.bind("<<ListboxSelect>>", self.load_selected_mapping)

        tk.Label(self.root, text="🎹 ノート番号").grid(row=5, column=0, sticky='w', padx=10)
        tk.Label(self.root, text="⌨ キー").grid(row=5, column=0, sticky='w', padx=100)
        self.note_entry = tk.Entry(self.root, width=5)
        self.note_entry.grid(row=6, column=0, padx=10, pady=5, sticky='w')
        self.note_entry.bind("<FocusIn>", self.start_note_listener)
        self.note_entry.bind("<FocusOut>", self.stop_note_listener)
        self.key_entry = tk.Entry(self.root, width=5)
        self.key_entry.grid(row=6, column=0, padx=100, pady=5, sticky='w')
        self.key_entry.bind("<KeyRelease>", self.enforce_single_ascii)
        self.add_button = tk.Button(self.root, text="追加", command=self.add_mapping)
        self.add_button.grid(row=5, column=1, sticky='e', padx=10)
        self.del_button = tk.Button(self.root, text="削除", command=self.delete_selected)
        self.del_button.grid(row=6, column=1, sticky='e', padx=10)

        separator = tk.Frame(self.root, height=2, bd=1, relief=tk.SUNKEN)
        separator.grid(row=7, column=0, columnspan=2, sticky="we", padx=10, pady=10)

        self.save_button = tk.Button(self.root, text="設定保存", command=self.save_mapping)
        self.save_button.grid(row=8, column=0, padx=10, pady=5, sticky='w')
        self.load_button = tk.Button(self.root, text="設定読み込み", command=self.load_mapping)
        self.load_button.grid(row=8, column=1, padx=10, pady=5, sticky='e')
        self.start_button = tk.Button(self.root, text="変換開始", command=self.start_listening, bg="green", fg="white", font=("Arial", 10, "bold"))
        self.start_button.grid(row=9, column=0, padx=10, pady=10, sticky='w')
        self.stop_button = tk.Button(self.root, text="変換停止", command=self.stop_listening, bg="red", fg="white", font=("Arial", 10, "bold"))
        self.stop_button.grid(row=9, column=1, padx=10, pady=10, sticky='e')
        self.status_label = tk.Label(self.root, text="ステータス: 停止中", fg="red")
        self.status_label.grid(row=10, column=0, columnspan=2, pady=(5, 10))

    # キー入力欄にASCII 1文字のみを許可する
    def enforce_single_ascii(self, event=None):
        value = self.key_entry.get()
        ascii_chars = [c for c in value if ord(c) < 128]
        self.key_entry.delete(0, tk.END)
        if ascii_chars:
            self.key_entry.insert(0, ascii_chars[-1])

    def add_mapping(self):
        try:
            note = int(self.note_entry.get())
            key = self.key_entry.get()
            if not key:
                messagebox.showwarning("注意", "キーボードキーが未入力です")
                return
            self.mapping[note] = key
            self.refresh_listbox()
        except ValueError:
            messagebox.showerror("エラー", "ノート番号は整数で入力してください")

    def delete_selected(self):
        selected = self.mapping_listbox.curselection()
        if not selected:
            return
        line = self.mapping_listbox.get(selected[0])
        note = int(line.split("→")[0].strip().split()[1])
        self.mapping.pop(note, None)
        self.refresh_listbox()

    def refresh_listbox(self):
        self.mapping_listbox.delete(0, tk.END)
        for note, key in sorted(self.mapping.items()):
            self.mapping_listbox.insert(tk.END, f"Note {note} → {key}")

    # マッピングと選択されたMIDIポートをJSON形式で保存する
    def save_mapping(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialdir=self.get_app_dir(),
            initialfile="settings.json"
        )
        if not path:
            return

        data = {
            "selected_ports": [port for port, var in self.port_vars.items() if var.get()],
            "mapping": self.mapping
        }

        with open(path, 'w') as f:
            json.dump(data, f)
        messagebox.showinfo("保存完了", "マッピング設定を保存しました。")

    def load_mapping(self):
        path = filedialog.askopenfilename(
            initialdir=self.get_app_dir(),
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return

        with open(path, 'r') as f:
            data = json.load(f)

        self.mapping = {int(k): v for k, v in data.get("mapping", {}).items()}

        selected_ports = data.get("selected_ports", [])
        for port, var in self.port_vars.items():
            var.set(port in selected_ports).items()
        self.refresh_listbox()
        messagebox.showinfo("読込完了", "マッピング設定を読み込みました。")

    def start_listening(self):
        if self.running:
            return
        selected_ports = [port for port, var in self.port_vars.items() if var.get()]
        if not selected_ports:
            messagebox.showerror("エラー", "MIDIポートを1つ以上選択してください。")
            return
        self.running = True
        self.status_label.config(text="ステータス: 実行中", fg="green")
        self.threads = []
        self.inports = []
        for port_name in selected_ports:
            thread = threading.Thread(target=self.listen_loop, args=(port_name,), daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop_listening(self):
        self.running = False
        self.status_label.config(text="ステータス: 停止中", fg="red")
        for port in self.inports:
            try:
                port.close()
            except:
                pass
        self.inports = []

    # 指定されたMIDIポートを監視し、マッピングに従ってキー入力を送信する
    def listen_loop(self, port_name):
        try:
            inport = mido.open_input(port_name)
            self.inports.append(inport)
            for msg in inport:
                if not self.running:
                    break
                if msg.type == 'note_on' and msg.velocity > 0:
                    if msg.note in self.mapping:
                        keyboard.press(self.mapping[msg.note])
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in self.mapping:
                        keyboard.release(self.mapping[msg.note])
        except Exception as e:
            print(f"エラー: {e}")

    # ノート番号入力欄がアクティブな間、最初のMIDIポートからのノート入力を監視して自動入力
    def start_note_listener(self, event=None):
        self.note_entry_active = True

        def listen_note_input():
            # 選択されている最初のMIDIポートを取得
            selected_ports = [port for port, var in self.port_vars.items() if var.get()]
            if not selected_ports:
                print("ノート入力用ポートが選択されていません")
                return
            try:
                with mido.open_input(selected_ports[0]) as temp_inport:
                    while self.note_entry_active:
                        for msg in temp_inport.iter_pending():
                            if msg.type == 'note_on' and msg.velocity > 0:
                                self.note_entry.delete(0, tk.END)
                                self.note_entry.insert(0, str(msg.note))
                        self.root.update_idletasks()
            except Exception as e:
                print(f"ノート監視エラー: {e}")

        self.note_entry_listener_thread = threading.Thread(target=listen_note_input, daemon=True)
        self.note_entry_listener_thread.start()

    def stop_note_listener(self, event=None):
        self.note_entry_active = False

    
    def load_selected_mapping(self, event=None):
        selected = self.mapping_listbox.curselection()
        if not selected:
            return
        line = self.mapping_listbox.get(selected[0])
        try:
            parts = line.split("→")
            note = int(parts[0].strip().split()[1])
            key = parts[1].strip()
            self.note_entry.delete(0, tk.END)
            self.note_entry.insert(0, str(note))
            self.key_entry.delete(0, tk.END)
            self.key_entry.insert(0, key)
        except Exception as e:
            print(f"選択読み取りエラー: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MidiToKeyApp(root)
    root.mainloop()
