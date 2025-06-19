# 設定用クラス及び設定ダイアログをここに書く
import pickle, os
from enum import Enum
import tkinter as tk
from tooltip import ToolTip
from tkinter import ttk, simpledialog, messagebox
import ipaddress
savefile = 'oiv_conf.pkl'

class playmode(Enum):
    iidx_sp=0
    iidx_dp=1
    sdvx=2

    @classmethod
    def get_names(cls) -> list:
        return [i.name for i in cls]

class Settings:
    def __init__(self):
        self.lx = 50
        self.ly = 50
        self.ln_threshold = 225
        self.size_release_hist = 200
        self.size_release_key_hist = 30
        self.density_interval = 0.5
        self.host = 'localhost'
        self.port = 8765
        self.connected_idx = [None,None]
        self.debug_mode = False # コントローラ入力の全dumpなど
        self.auto_update = True # 自動アップデート
        self.playmode = playmode.iidx_sp
        #self.log_offset = '0'
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']

        self.load()
        self.save()
        self.write_websocket_settings()

    def disp(self):
        print(f"lx, ly = {self.lx}, {self.ly}")
        print(f"ln_threshold={self.ln_threshold}")
        print(f"host:port = {self.host}:{self.port}")
        print(f"size_release_hist={self.size_release_hist}")
        print(f"size_release_key_hist={self.size_release_key_hist}")
        print(f"density_interval={self.density_interval}")
        print(f"connected_idx={self.connected_idx}")
        print(f"playmode={self.playmode.name}")
        print(f"debug_mode={self.debug_mode}")
        print(f"auto_update={self.auto_update}")

    def load(self):
        try:
            with open(savefile, 'rb') as f:
                tmp = pickle.load(f)
                for k in tmp.__dict__.keys():
                    if k == 'connected_idx' and type(getattr(tmp, k)) is not list:
                        print(f'connected_idxをListに変更します')
                        setattr(self, k, [None, None])
                    else:
                        setattr(self, k, getattr(tmp, k))
        except Exception: # 読み込みエラー時はデフォルトで使う
            pass
        self.disp()

    def save(self):
        with open(savefile, 'wb') as f:
            pickle.dump(self, f)

    def write_websocket_settings(self):
        """websocketサーバのパラメータをcssファイルに出力
        """
        # 呼び出される時点で正しいパラメータが設定されている想定
        with open('html/websocket.css', 'w', encoding='utf-8') as f:
            f.write(':root {\n')
            f.write('    --host:'+self.host+';\n')
            f.write('    --port:'+str(self.port)+';\n')
            f.write('}')

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings:Settings):
        super().__init__(parent)
        self.title("設定")
        self.settings = settings
        self.result = None
        self.grab_set() # メインウィンドウの操作禁止
        
        self.create_widgets()
        self.load_current_settings()

        lx = parent.winfo_x()
        ly = parent.winfo_y()
        super().geometry(f'+{lx}+{ly}')
        super().protocol('WM_DELETE_WINDOW', self.save)

    def create_widgets(self):
        frame_mode = ttk.Frame(self)
        frame_mode.pack(padx=0, pady=0)

        self.playmode_radios = []
        self.playmode_var = tk.IntVar()
        ttk.Label(frame_mode, text="playmode:").pack(side=tk.LEFT, padx=5, pady=0)
        for i in range(len(playmode.get_names())):
            self.playmode_radios.append(tk.Radiobutton(frame_mode, value=i, variable=self.playmode_var, text=playmode.get_names()[i]))
            self.playmode_radios[i].pack(side=tk.LEFT, padx=5, pady=5)

        frame = ttk.Frame(self, padding=0)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5)

        ttk.Label(frame, text="LongNotes判定しきい値(ms) (default=225):").grid(row=0, column=0, sticky=tk.W)
        self.ln_threshold = ttk.Entry(frame)
        self.ln_threshold.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(frame, text="リリース速度計算用ノーツ数 (default=200):").grid(row=2, column=0, sticky=tk.W)
        self.size_release_hist_entry = ttk.Entry(frame)
        self.size_release_hist_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame, text="単鍵リリース速度計算用ノーツ数 (default=30)").grid(row=3, column=0, sticky=tk.W)
        self.size_release_key_hist_entry = ttk.Entry(frame)
        self.size_release_key_hist_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frame, text="譜面密度計算周期(s) (default=0.5)").grid(row=4, column=0, sticky=tk.W)
        self.density_interval_entry = ttk.Entry(frame)
        self.density_interval_entry.grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(frame, text="WebSocketホスト: (default=localhost)").grid(row=5, column=0, sticky=tk.W)
        self.host_entry = ttk.Entry(frame)
        self.host_entry.grid(row=5, column=1, padx=5, pady=5)
        ToolTip(self.host_entry, '変更する場合、本設定ダイアログを閉じた後に\nOBS側でブラウザソースのプロパティから\n"現在のページのキャッシュを更新"をクリックしてください。')

        ttk.Label(frame, text="WebSocketポート: (default=8765)").grid(row=6, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(frame)
        self.port_entry.grid(row=6, column=1, padx=5, pady=5)
        ToolTip(self.port_entry, '変更する場合、本設定ダイアログを閉じた後に\nOBS側でブラウザソースのプロパティから\n"現在のページのキャッシュを更新"をクリックしてください。')

        self.debug_mode_var = tk.BooleanVar()
        self.debug_mode_check = ttk.Checkbutton(
            frame,
            text='debug_mode (default=off)',
            variable=self.debug_mode_var
        )
        self.debug_mode_check.grid(row=7, column=0, columnspan=2, pady=5, sticky=tk.W)

        self.auto_update_var = tk.BooleanVar()
        self.auto_update_check = ttk.Checkbutton(
            frame,
            text='起動時にアプリを自動更新する (default=on)',
            variable=self.auto_update_var
        )
        self.auto_update_check.grid(row=8, column=0, columnspan=2, pady=5, sticky=tk.W)

    def load_current_settings(self):
        self.ln_threshold.insert(0, str(self.settings.ln_threshold))
        self.size_release_hist_entry.insert(0, str(self.settings.size_release_hist))
        self.size_release_key_hist_entry.insert(0, str(self.settings.size_release_key_hist))
        self.density_interval_entry.insert(0, str(self.settings.density_interval))
        self.host_entry.insert(0, str(self.settings.host))
        self.port_entry.insert(0, str(self.settings.port))
        self.debug_mode_var.set(self.settings.debug_mode)
        self.auto_update_var.set(self.settings.auto_update)
        self.playmode_var.set(self.settings.playmode.value)

    def is_valid_ip(self, address):
        try:
            ipaddress.ip_address(address)
            return True
        except ValueError:
            return False

    def save(self):
        """設定値をファイルに保存
        """
        try:
            host = self.host_entry.get()
            port = int(self.port_entry.get())
            ln_threshold = int(self.ln_threshold.get())
            size_release_hist = int(self.size_release_hist_entry.get())
            size_release_key_hist = int(self.size_release_key_hist_entry.get())
            density_interval = float(self.density_interval_entry.get())
            if (host != 'localhost') and (not self.is_valid_ip(host)):
                raise ValueError("hostが無効です")
            if not (1 <= port <= 65535):
                raise ValueError("ポート番号が無効です")
            if not (ln_threshold > 0):
                raise ValueError("LongNotes判定しきい値が無効です")
            if not (density_interval > 0):
                raise ValueError("譜面密度計算周期が無効です")
            if not (size_release_hist > 0):
                raise ValueError("リリース速度計算用ノーツ数が無効です")
            if not (size_release_key_hist > 0):
                raise ValueError("単鍵リリース速度計算用ノーツ数が無効です")
            self.settings.host = host
            self.settings.port = port
            self.settings.ln_threshold = ln_threshold
            self.settings.size_release_hist = size_release_hist
            self.settings.size_release_key_hist = size_release_key_hist
            self.settings.density_interval = density_interval
            self.settings.debug_mode = self.debug_mode_var.get()
            self.settings.auto_update = self.auto_update_var.get()
            self.settings.playmode = playmode(self.playmode_var.get())
            self.settings.save()
            self.settings.write_websocket_settings()
            self.destroy()
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))

if __name__ == '__main__':
    a = Settings()
    a.save()
    print(a.is_valid())