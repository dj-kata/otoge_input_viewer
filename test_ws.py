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

# 残件: changeボタン修正、アプデ機能、1P側の準備、ボルテもやる？、モード切替ボタン

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

        super().geometry(self.settings.geometry)
        super().protocol('WM_DELETE_WINDOW', self.save)

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="LongNotes判定しきい値(ms) (default=225):").grid(row=0, column=0, sticky=tk.W)
        self.ln_threshold = ttk.Entry(frame)
        self.ln_threshold.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="リリース速度計算用ノーツ数 (default=200):").grid(row=1, column=0, sticky=tk.W)
        self.size_release_hist_entry = ttk.Entry(frame)
        self.size_release_hist_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="単鍵リリース速度計算用ノーツ数 (default=30)").grid(row=2, column=0, sticky=tk.W)
        self.size_release_key_hist_entry = ttk.Entry(frame)
        self.size_release_key_hist_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(frame, text="譜面密度計算周期(s) (default=2)").grid(row=3, column=0, sticky=tk.W)
        self.density_interval_entry = ttk.Entry(frame)
        self.density_interval_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(frame, text="WebSocketポート: (default=8765)").grid(row=4, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(frame)
        self.port_entry.grid(row=4, column=1, padx=5, pady=5)

        self.debug_mode_var = tk.BooleanVar()
        self.debug_mode_check = ttk.Checkbutton(
            frame,
            text='debug_mode (default=off)',
            variable=self.debug_mode_var
        )
        self.debug_mode_check.grid(row=5, column=0, columnspan=2, pady=5, sticky=tk.W)

    def load_current_settings(self):
        self.ln_threshold.insert(0, str(self.settings.ln_threshold))
        self.size_release_hist_entry.insert(0, str(self.settings.size_release_hist))
        self.size_release_key_hist_entry.insert(0, str(self.settings.size_release_key_hist))
        self.density_interval_entry.insert(0, str(self.settings.density_interval))
        self.port_entry.insert(0, str(self.settings.port))
        self.debug_mode_var.set(self.settings.debug_mode)

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
        self.scratch_queue = Queue() # スクラッチだけoff用処理も入れるため分ける
        self.calc_queue = Queue()  # 計算用のキュー、全イベントをここに流す
        self.event_queue = Queue() # HTMLへの出力をすべてここに通す
        self.running = False
        self.clients = set()
        self.button_count = 0
        self.current_joystick_id = 0
        # スクラッチ判定用
        self.pre_scr_val = [None, None]
        self.pre_scr_direction = [-1, -1]
        self.settings = Settings()

        self.root.geometry(self.settings.geometry)

        self.setup_gui()
        self.init_pygame()
        self.start_monitor()
        self.start_threads()
        logger.debug('started!')

    def setup_gui(self):
        """GUIの設定を行う
        """
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        settings_menu = tk.Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="config", command=self.open_settings_dialog)
        self.menubar.add_cascade(label="file", menu=settings_menu)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ジョイパッド情報
        self.joystick_info = ttk.Label(
            main_frame,
            text="接続ジョイパッド: なし",
            font=("Meiryo UI", 10)
        )
        self.joystick_info.pack(pady=5)

        # コントローラ変更ボタン
        self.change_joystick_btn = ttk.Button(
            main_frame,
            text="change",
            command=self.change_joystick,
        )
        self.change_joystick_btn.pack(pady=5)

        # ボタンカウンター
        self.counter_label = ttk.Label(
            main_frame,
            text="notes: 0",
            font=("Meiryo UI", 10)
        )
        self.counter_label.pack(pady=5)

        # サーバー状態表示
        self.server_status = ttk.Label(
            main_frame,
            text=f"WebSocket port: {self.settings.port}",
            font=("Meiryo UI", 10)
        )
        self.server_status.pack(pady=5)

        # 制御ボタン
        self.control_button = ttk.Button(
            main_frame,
            text="reset threads",
            command=self.toggle_server
        )
        self.control_button.pack(pady=10)

        # その他情報表示
        self.other_info = ttk.Label(
            main_frame,
            text=f"",
            font=("Meiryo UI", 10)
        )
        self.other_info.pack(pady=5)

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
        self.scratch_thread = threading.Thread(
            target=self.thread_scratch,
            daemon=True
        )
        self.scratch_thread.start()

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
        #self.init_pygame()
        count = pygame.joystick.get_count()
        print('count=', count)
        if count < 1:
            return
        elif count == 1:
            self.reconnect_joystick()
        else:
            devices = [f"ジョイパッド {i}" for i in range(count)]
            choice = simpledialog.askinteger(
                "ジョイパッド選択",
                "接続するジョイパッドの番号を入力:",
                minvalue=0,
                maxvalue=count-1,
                parent=self.root
            )
            if choice is not None:
                self.reconnect_joystick()

    def reconnect_joystick(self):
        """ジョイパッドへの再接続処理。
        """
        try:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.current_joystick_id = 0
            name = self.joystick.get_name()
            self.joystick_info.config(text=f"connected: {name} (ID: 0)", foreground='blue')
        except pygame.error as e:
            print(f"ジョイパッド接続エラー: {e}")

    def init_pygame(self):
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() == 0:
                raise pygame.error("No joystick detected")
            
            self.reconnect_joystick()
            self.change_joystick_btn.config(state=tk.NORMAL)
        except pygame.error as e:
            print(e)
            self.joystick_info.config(text=str(e), foreground="red")

    def thread_scratch(self):
        """scratch処理用スレッド。リリース/密度の送信及び皿オフの扱いを入れる。scratch_queueのデータを受信してevent_queueに送る。
        """
        state_last = [0]*4
        time_last_active = [0]*4 # 最後に命令を受信した時刻
        print('scratch thread start')
        while self.running:
            if not self.scratch_queue.empty(): # スクラッチ用キューがある場合
                tmp = self.scratch_queue.get()
                self.event_queue.put(tmp)
                state_last[tmp['pos']] = 1
                time_last_active[tmp['pos']] = time.perf_counter()
                # 反対側をオフにする
                tmp_off = {'value':0, 'direction':1-tmp['direction'], 'type':'axis', 'pos': tmp['axis']*2 + (1-tmp['direction'])}
                self.event_queue.put(tmp_off)
                state_last[tmp_off['pos']] = 0
            else:
                cur = time.perf_counter()
                for i in range(4):
                    if (cur - time_last_active[i] > 0.1) and state_last[i]:
                        event_data = {
                            'type': 'axis',
                            'pos': i,
                            'value': 0
                        }
                        self.event_queue.put(event_data)
                        state_last[i] = 0
            time.sleep(0.01)

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
            cur_time = time.perf_counter()
            if not self.calc_queue.empty(): # non-blocking 
                tmp = self.calc_queue.get()
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
            elif cur_time - time_last_sent > self.settings.density_interval: # 各種出力
                if len(list_density) > 0: # 密度の出力
                    if cur_time - list_density[-1] > self.settings.time_window_density:
                        list_density = []
                    for i in range(len(list_density)):
                        if cur_time - list_density[i] <= self.settings.time_window_density:
                            break
                    list_density = list_density[i:] # 直近5秒以内の範囲だけに整形
                    density = len(list_density) / self.settings.time_window_density
                    event_data = {
                        'type': 'density',
                        'value': f"{density:.1f}"
                    }
                    self.event_queue.put(event_data)
                time_last_sent = time.perf_counter()
            time.sleep(0.01)

    def monitor_thread(self):
        """ジョイパッドの入力イベントを受け取るループ
        """
        print('monitor_thread start')
        while True:
            try:
                for event in pygame.event.get():
                    if self.settings.debug_mode:
                        logger.debug(event)
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

        # TODO 接続されたIDの保存、切断時の対策(現IDの接続ならNoneにする)、再接続時の対策
        
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
                self.button_count += 1
                self.root.after(0, self.update_counter_display)
                self.event_queue.put({'type':'notes', 'value':self.button_count})
            self.pre_scr_direction[event.axis] = out_direction
        elif event.type == pygame.JOYBUTTONDOWN:
            self.button_count += 1
            self.root.after(0, self.update_counter_display)
            self.event_queue.put({'type':'notes', 'value':self.button_count})
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
        
        if event_data:
            self.calc_queue.put(event_data)
            if event_data['type'] == 'axis':
                self.scratch_queue.put(event_data)
            else:
                self.event_queue.put(event_data)

    def update_counter_display(self):
        self.counter_label.config(text=f"notes: {self.button_count}")

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
            self.scratch_thread.join()
            self.calc_thread.join()
            self.update_server_status_display()
            self.loop.stop()
            self.loop.close()
        
        logger.debug('')
        self.running = True
        self.server_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )
        self.server_thread.start()
        logger.debug('')

        self.update_server_status_display()
        logger.debug('')

        self.joystick_thread = threading.Thread(
            target=self.monitor_thread,
            daemon=True
        )
        self.joystick_thread.start()
        logger.debug('')

        self.scratch_thread = threading.Thread(
            target=self.thread_scratch,
            daemon=True
        )
        self.scratch_thread.start()
        logger.debug('')

        self.calc_thread = threading.Thread(
            target=self.thread_calc,
            daemon=True
        )
        self.calc_thread.start()
        logger.debug('')

    def on_close(self):
        """メインウィンドウ終了時に実行される関数
        """
        logger.debug('exit')
        self.running = False
        self.settings.geometry = self.root.geometry()
        self.settings.save()
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JoystickWebSocketServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
