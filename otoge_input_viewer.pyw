# 新処理方式のテスト用
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import pygame
import websockets
import asyncio
import json
import threading
from queue import Queue
import os
import json
import time
from collections import defaultdict
import logging, logging.handlers
from settings import Settings, playmode
from tooltip import ToolTip
import subprocess
from bs4 import BeautifulSoup
import requests
import traceback

# 残件: 1-7鍵だけ拾うように修正

os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

try:
    with open('version.txt', 'r') as f:
        SWVER = f.readline().strip()
except Exception:
    SWVER = "v?.?.?"

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
            if playmode(i) in (playmode.iidx_dp, playmode.sdvx):
            #if playmode(i) in (playmode.iidx_dp,):
                self.playmode_radios.append(tk.Radiobutton(frame_mode, value=i, variable=self.playmode_var, text=playmode.get_names()[i], state='disable'))
            else:
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

        ttk.Label(frame, text="WebSocketポート: (default=8765)").grid(row=5, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(frame)
        self.port_entry.grid(row=5, column=1, padx=5, pady=5)
        ToolTip(self.port_entry, '変更する場合、本設定ダイアログを閉じた後に\nOBS側でブラウザソースのプロパティから\n"現在のページのキャッシュを更新"をクリックしてください。')

        self.debug_mode_var = tk.BooleanVar()
        self.debug_mode_check = ttk.Checkbutton(
            frame,
            text='debug_mode (default=off)',
            variable=self.debug_mode_var
        )
        self.debug_mode_check.grid(row=6, column=0, columnspan=2, pady=5, sticky=tk.W)

        self.auto_update_var = tk.BooleanVar()
        self.auto_update_check = ttk.Checkbutton(
            frame,
            text='起動時にアプリを自動更新する (default=on)',
            variable=self.auto_update_var
        )
        self.auto_update_check.grid(row=7, column=0, columnspan=2, pady=5, sticky=tk.W)

    def load_current_settings(self):
        self.ln_threshold.insert(0, str(self.settings.ln_threshold))
        self.size_release_hist_entry.insert(0, str(self.settings.size_release_hist))
        self.size_release_key_hist_entry.insert(0, str(self.settings.size_release_key_hist))
        self.density_interval_entry.insert(0, str(self.settings.density_interval))
        self.port_entry.insert(0, str(self.settings.port))
        self.debug_mode_var.set(self.settings.debug_mode)
        self.auto_update_var.set(self.settings.auto_update)
        self.playmode_var.set(self.settings.playmode.value)

    def save(self):
        """設定値をファイルに保存
        """
        try:
            port = int(self.port_entry.get())
            ln_threshold = int(self.ln_threshold.get())
            size_release_hist = int(self.size_release_hist_entry.get())
            size_release_key_hist = int(self.size_release_key_hist_entry.get())
            density_interval = float(self.density_interval_entry.get())
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
            self.settings.port = port
            self.settings.ln_threshold = ln_threshold
            self.settings.size_release_hist = size_release_hist
            self.settings.size_release_key_hist = size_release_key_hist
            self.settings.density_interval = density_interval
            self.settings.debug_mode = self.debug_mode_var.get()
            self.settings.auto_update = self.auto_update_var.get()
            self.settings.playmode = playmode(self.playmode_var.get())
            self.settings.save()
            with open('html/websocket.css', 'w', encoding='utf-8') as f:
                f.write(':root {\n    --port:'+str(port)+';\n}')
            self.destroy()
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))

class JoystickWebSocketServer:
    def __init__(self, root):
        self.root = root
        self.root.title("Otoge Input Viewer")
        self.root.iconbitmap(default='icon.ico')
        self.scratch_queue = Queue() # スクラッチだけoff用処理も入れるため分ける
        self.calc_queue = Queue()  # 計算用のキュー、全イベントをここに流す
        self.event_queue = Queue() # HTMLへの出力をすべてここに通す
        self.running = False
        self.clients = set()
        self.today_notes = 0
        # スクラッチ判定用
        self.pre_scr_val = [None, None]
        self.pre_scr_direction = [-1, -1]
        self.settings = Settings()

        self.root.geometry(f'+{self.settings.lx}+{self.settings.ly}')

        self.setup_gui()
        self.init_pygame()
        self.start_monitor()
        self.start_threads()
        logger.debug('started!')
        if self.settings.auto_update:
            self.check_updates()

    def get_latest_version(self):
        """GitHubから最新版のバージョンを取得する。

        Returns:
            str: バージョン番号
        """
        ret = None
        url = 'https://github.com/dj-kata/otoge_input_viewer/tags'
        r = requests.get(url)
        soup = BeautifulSoup(r.text,features="html.parser")
        for tag in soup.find_all('a'):
            if 'releases/tag/v.' in tag['href']:
                ret = tag['href'].split('/')[-1]
                break # 1番上が最新なので即break
        return ret
    
    def check_updates(self, always_disp_dialog=False):
        ver = self.get_latest_version()
        if (ver != SWVER) and (ver is not None):
            logger.debug(f'現在のバージョン: {SWVER}, 最新版:{ver}')
            ans = tk.messagebox.askquestion('バージョン更新',f'アップデートが見つかりました。\n\n{SWVER} -> {ver}\n\nアプリを終了して更新します。', icon='warning')
            if ans == "yes":
                if os.path.exists('update.exe'):
                    logger.info('アップデート確認のため終了します')
                    res = subprocess.Popen('update.exe')
                    print('fug')
                    self.on_close()
                else:
                    raise ValueError("update.exeがありません")
        else:
            logger.debug(f'お使いのバージョンは最新です({SWVER})')
            if always_disp_dialog:
                messagebox.showinfo("Otoge Input Viewer", f'お使いのバージョンは最新です({SWVER})')

    def setup_gui(self):
        """GUIの設定を行う
        """
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        settings_menu = tk.Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="config", command=self.open_settings_dialog)
        settings_menu.add_command(label="update", command=lambda:self.check_updates(True))
        self.menubar.add_cascade(label="file", menu=settings_menu)

        main_frame = ttk.Frame(self.root, padding=6)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ジョイパッド情報
        self.joystick_info = ttk.Label(
            main_frame,
            text="接続ジョイパッド: なし",
            font=("Meiryo UI", 10)
        )
        self.joystick_info.grid(row=0, column=0,sticky=tk.W)

        # コントローラ変更ボタン
        self.change_joystick_btn = ttk.Button(
            main_frame,
            text="change",
            command=self.change_joystick,
        )
        self.change_joystick_btn.grid(row=0, column=1,sticky=tk.W)

        # モード表示
        self.mode_label = ttk.Label(main_frame, text=f'mode: {self.settings.playmode.name}', font=('Meiryo UI', 10))
        self.mode_label.grid(row=1, sticky=tk.W)

        # ボタンカウンター
        self.counter_label = ttk.Label(
            main_frame,
            text="notes: 0",
            font=("Meiryo UI", 10)
        )
        self.counter_label.grid(row=2, sticky=tk.W)

        # サーバー状態表示
        self.server_status = ttk.Label(
            main_frame,
            text=f"WebSocket port: {self.settings.port}",
            font=("Meiryo UI", 10)
        )
        self.server_status.grid(row=3, sticky=tk.W)

        # その他情報表示
        self.other_info = ttk.Label(
            main_frame,
            text=f"",
            font=("Meiryo UI", 10)
        )
        self.other_info.grid(row=4, sticky=tk.W)

    def start_monitor(self):
        # ジョイパッド監視スレッド
        self.joystick_thread = threading.Thread(
            target=self.monitor_thread,
            daemon=True
        )
        self.joystick_thread.start()

    def start_threads(self):
        """スレッドの起動処理
        """
        self.running = True
        # WebSocketサーバースレッド（初期状態では非起動）
        self.server_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )
        self.server_thread.start()

        # 皿処理スレッド
        self.density_thread = threading.Thread(
            target=self.thread_density,
            daemon=True
        )
        self.density_thread.start()

        # 計算用スレッド
        self.calc_thread = threading.Thread(
            target=self.thread_calc,
            daemon=True
        )
        self.calc_thread.start()

    def open_settings_dialog(self):
        """設定ウィンドウを開く
        """
        dialog = SettingsDialog(self.root, self.settings)
        self.root.wait_window(dialog)
        self.settings.load()
        self.settings.disp()
        self.update_server_status_display()
        self.toggle_server()

    def change_joystick(self):
        count = pygame.joystick.get_count()
        print('count=', count)
        if count < 1:
            return
        else:
            if (self.settings.connected_idx is None) or (not hasattr(self, 'joystick')):
                self.reconnect_joystick(0)
            else:
                idx = (self.joystick.get_id() + 1) % count
                self.reconnect_joystick(idx)

    def reconnect_joystick(self, idx:int):
        """ジョイパッドへの再接続処理。
        """
        try:
            self.joystick = pygame.joystick.Joystick(idx)
            self.joystick.init()
            name = self.joystick.get_name()
            self.joystick_info.config(text=f"connected: {name} (ID: {idx})", foreground='blue')
            self.settings.connected_idx = idx
        except pygame.error as e:
            logger.error(f"ジョイパッド接続エラー: {e}")

    def init_pygame(self):
        try:
            pygame.init()
            pygame.joystick.init()
            count = pygame.joystick.get_count()
            if count == 0:
                raise pygame.error("No joystick detected")
            
            elif self.settings.connected_idx is None:
                self.reconnect_joystick(0)
            else:
                self.reconnect_joystick(min(self.settings.connected_idx, count-1))
            self.change_joystick_btn.config(state=tk.NORMAL)
        except pygame.error as e:
            logger.error(e)
            self.joystick_info.config(text=str(e), foreground="red")

    def thread_density(self):
        """scratch処理用スレッド。リリース/密度の送信及び皿オフの扱いを入れる。scratch_queueのデータを受信してevent_queueに送る。
        """
        print('scratch thread start')
        while self.running:
            tmp = self.scratch_queue.get()
            if tmp['direction'] == -1:
                continue
            self.event_queue.put(tmp)

    def thread_calc(self):
        """release及びdensityの計算用スレッド。
        """
        SEND_INTERVAL  = 0.5 # 送信周期
        time_last_sent = 0 # 最後に送信した時間
        time_last_active = defaultdict(int) # 各鍵盤で最後にpushされた時刻を記録。
        list_allkeys = [] # 全鍵盤用のログ保存リスト
        list_eachkey = defaultdict(list)
        list_density = []
        list_last_scratch = defaultdict(str) # 最後にどの向きだったか, axisごとに用意
        print('calc thread start')
        while self.running:
            tmp = self.calc_queue.get()
            cur_time = time.perf_counter()
            if tmp['type'] == 'button': # 鍵盤
                key = tmp['button'] # どの鍵盤か。将来的にコントローラ番号も加味したい。 TODO
                if tmp['state'] == 'down':
                    time_last_active[key] = cur_time
                    list_density.append(cur_time) # LNは関係なく密度計算には使う
                else:
                    tmp_release = cur_time - time_last_active[key]
                    if tmp_release < self.settings.ln_threshold/1000:
                        list_allkeys.append(tmp_release)
                        list_eachkey[key].append(tmp_release)
                        # リリース出力
                        if len(list_allkeys) > self.settings.size_release_hist:
                            list_allkeys.pop(0)
                        release = sum(list_allkeys) / len(list_allkeys)
                        event_data = {
                            'type': 'release',
                            'value': f"{release*1000:.1f}"
                        }
                        self.event_queue.put(event_data)

                        if len(list_eachkey[key]) > self.settings.size_release_key_hist:
                            list_allkeys.pop(0)
                        release = sum(list_eachkey[key]) / len(list_eachkey[key])
                        event_data = {
                            'type': 'release_eachkey',
                            'button': key,
                            'value': f"{release*1000:.1f}"
                        }
                        self.event_queue.put(event_data)

            elif tmp['type'] == 'axis': # スクラッチ
                if tmp['direction'] != list_last_scratch[tmp['axis']]:
                    list_density.append(cur_time)
                list_last_scratch[tmp['axis']] = tmp['direction']
            if cur_time - time_last_sent > self.settings.density_interval: # 各種出力
                if len(list_density) > 0: # 密度の出力
                    if cur_time - list_density[-1] > self.settings.density_interval:
                        list_density = []
                    for i in range(len(list_density)):
                        if cur_time - list_density[i] <= self.settings.density_interval:
                            break
                    list_density = list_density[i:] # 直近5秒以内の範囲だけに整形
                    if (len(list_density) == 0) or (cur_time == list_density[0]):
                        density = 0.0
                    else:
                        density = len(list_density) / (cur_time - list_density[0])
                    event_data = {
                        'type': 'density',
                        'value': f"{density:.1f}"
                    }
                    self.event_queue.put(event_data)
                time_last_sent = time.perf_counter()

    def monitor_thread(self):
        """ジョイパッドの入力イベントを受け取るループ
        """
        print('monitor_thread start')
        while True:
            try:
                for event in pygame.event.get():
                    if self.settings.debug_mode:
                        logger.debug(event)
                    # モードごとに必要なノートのみ通すための判定処理
                    if event.type == pygame.JOYBUTTONDOWN:
                        if not ((self.settings.playmode==playmode.iidx_sp and event.button<=6) or (self.settings.playmode==playmode.sdvx and event.button >=1 and event.button<=6)):
                            continue
                    if event.type == pygame.JOYAXISMOTION:
                        if not ((self.settings.playmode==playmode.iidx_sp and event.axis==0) or (self.settings.playmode==playmode.sdvx and event.axis in (0,1))):
                            continue
                    self.process_joystick_event(event)
                if pygame.joystick.get_count() == 0:
                    self.joystick_info.config(text=f"joypad disconnected", foreground='red')
            except Exception as e:
                logger.debug(e)
            pygame.time.wait(20)

    def process_joystick_event(self, event):
        """1つのジョイパッド入力イベントを読み込んでwebsocket出力に変換する。

        Args:
            event (pygame.event): 入力イベント
        """
        event_data = None

        # TODO 切断時の対策(現IDの接続ならNoneにする)、再接続時の対策
        
        if event.type == pygame.JOYAXISMOTION:
            out_direction = -1
            if self.pre_scr_val[event.axis] is not None:
                if event.value > self.pre_scr_val[event.axis]:
                    out_direction = 0
                elif event.value < self.pre_scr_val[event.axis]:
                    out_direction = 1
            self.pre_scr_val[event.axis] = event.value
            event_data = {
                'type': 'axis',
                'axis': event.axis,
                'direction': out_direction,
                'pos': event.axis*2 + out_direction,
                'value': 1
            }
            if out_direction != self.pre_scr_direction[event.axis]:
                self.today_notes += 1
                self.root.after(0, self.update_counter_display)
                self.event_queue.put({'type':'notes', 'value':self.today_notes})
            self.pre_scr_direction[event.axis] = out_direction
        elif event.type == pygame.JOYBUTTONDOWN:
            self.today_notes += 1
            self.root.after(0, self.update_counter_display)
            self.event_queue.put({'type':'notes', 'value':self.today_notes})
            event_data = {
                'type': 'button',
                'button': event.button,
                'state': 'down'
            }
        elif event.type == pygame.JOYBUTTONUP:
            event_data = {
                'type': 'button',
                'button': event.button,
                'state': 'up'
            }
        elif event.type == pygame.JOYDEVICEADDED:
            if self.joystick.get_count() == 1:
                self.reconnect_joystick(0)
        elif event.type == pygame.JOYDEVICEREMOVED:
            if self.joystick.get_instance_id() == event.instance_id:
                self.settings.connected_idx = None
                self.joystick_info.config(text=f"joypad disconnected", foreground='red')
            if self.joystick.get_count() > 0:
                self.reconnect_joystick(0)
        
        if event_data:
            self.calc_queue.put(event_data)
            self.event_queue.put(event_data)

    def update_counter_display(self):
        self.counter_label.config(text=f"notes: {self.today_notes}")

    async def websocket_handler(self, websocket):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                pass
        finally:
            self.clients.remove(websocket)

    async def send_joystick_events(self):
        while self.running:
            events = []
            # キュー内の全イベントを取得
            while not self.event_queue.empty():
                events.append(self.event_queue.get())

            if events:
                message = json.dumps(events)  # 配列形式で送信
                for client in self.clients.copy():
                    try:
                        await client.send(message)
                    except:
                        self.clients.remove(client)
            await asyncio.sleep(0.001)  # 送信間隔調整

    async def main_server(self):
        async with websockets.serve(self.websocket_handler, "0.0.0.0", 8765):
            await self.send_joystick_events()

    def run_websocket_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.main_server())

    def update_server_status_display(self):
        status_text = "停止中" if not self.running else "稼働中"
        self.server_status.config(
            text=f"WebSocket: {status_text} (ポート: {self.settings.port})"
        )
        self.mode_label.config(text=f"mode: {self.settings.playmode.name}")

    def load_settings(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    return {**self.DEFAULT_SETTINGS, **json.load(f)}
            except:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()

    async def main_server(self):
        async with websockets.serve(
            self.websocket_handler,
            "0.0.0.0",
            self.settings.port
        ):
            await self.send_joystick_events()

    def toggle_server(self):
        logger.debug('')
        if self.server_thread.is_alive():
            self.running = False
            self.density_thread.join()
            self.calc_thread.join()
            self.update_server_status_display()
            self.loop.stop()
            while self.loop.is_running():
                time.sleep(0.3)
            self.loop.close()
        
        self.running = True
        self.server_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )
        self.server_thread.start()

        self.update_server_status_display()

        self.joystick_thread = threading.Thread(
            target=self.monitor_thread,
            daemon=True
        )
        self.joystick_thread.start()

        self.density_thread = threading.Thread(
            target=self.thread_density,
            daemon=True
        )
        self.density_thread.start()

        self.calc_thread = threading.Thread(
            target=self.thread_calc,
            daemon=True
        )
        self.calc_thread.start()

    def on_close(self):
        """メインウィンドウ終了時に実行される関数
        """
        logger.debug('exit')
        self.running = False
        self.settings.lx = self.root.winfo_x()
        self.settings.ly = self.root.winfo_y()
        self.settings.save()
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = JoystickWebSocketServer(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.minsize(300,200)
        root.mainloop()
    except Exception as e:
        logger.error(traceback.format_exc())
