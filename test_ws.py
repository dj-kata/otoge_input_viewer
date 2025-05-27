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

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.title("設定")
        self.settings = settings
        self.result = None
        
        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # AAA設定
        ttk.Label(frame, text="変数AAA:").grid(row=0, column=0, sticky=tk.W)
        self.aaa_entry = ttk.Entry(frame)
        self.aaa_entry.grid(row=0, column=1, padx=5, pady=5)

        # ポート番号設定
        ttk.Label(frame, text="WebSocketポート:").grid(row=1, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(frame)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)

        # 自動起動チェックボックス
        self.auto_start_var = tk.BooleanVar()
        self.auto_start_check = ttk.Checkbutton(
            frame,
            text="起動時にWebSocketサーバーを自動開始",
            variable=self.auto_start_var
        )
        self.auto_start_check.grid(row=2, column=0, columnspan=2, pady=5, sticky=tk.W)

        # ボタン
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="保存", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=self.destroy).pack(side=tk.LEFT)

    def load_current_settings(self):
        self.aaa_entry.insert(0, str(self.settings['aaa']))
        self.port_entry.insert(0, str(self.settings['port']))
        self.auto_start_var.set(self.settings['auto_start'])

    def save(self):
        try:
            aaa = int(self.aaa_entry.get())
            port = int(self.port_entry.get())
            if not (1 <= port <= 65535):
                raise ValueError("ポート番号が無効です")
            
            self.settings.update({
                'aaa': aaa,
                'port': port,
                'auto_start': self.auto_start_var.get()
            })
            self.destroy()
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))

class JoystickWebSocketServer:
    CONFIG_FILE = "settings.json"
    DEFAULT_SETTINGS = {
        'aaa': 100,
        'port': 8765,
        'auto_start': False
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Joystick WebSocket Server")
        self.event_queue = Queue()
        self.running = False
        self.clients = set()
        self.button_count = 0
        self.current_joystick_id = 0
        self.settings = self.load_settings()

        self.setup_gui()
        self.init_pygame()
        self.start_threads()

        # 自動起動処理
        if self.settings['auto_start']:
            self.root.after(100, self.toggle_server)

    def setup_gui(self):
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        settings_menu = tk.Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="設定変更", command=self.open_settings_dialog)
        self.menubar.add_cascade(label="設定", menu=settings_menu)

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
            text="コントローラ変更",
            command=self.change_joystick,
            state=tk.DISABLED
        )
        self.change_joystick_btn.pack(pady=5)

        # ボタンカウンター
        self.counter_label = ttk.Label(
            main_frame,
            text="ボタン押下回数: 0",
            font=("Meiryo UI", 10)
        )
        self.counter_label.pack(pady=5)

        # サーバー状態表示
        self.server_status = ttk.Label(
            main_frame,
            text=f"WebSocket: 停止中 (ポート: {self.settings['port']})",
            font=("Meiryo UI", 10)
        )
        self.server_status.pack(pady=5)

        # 制御ボタン
        self.control_button = ttk.Button(
            main_frame,
            text="サーバー起動",
            command=self.toggle_server
        )
        self.control_button.pack(pady=10)

    def start_threads(self):
        """スレッドの起動処理（追加）"""
        # ジョイパッド監視スレッド
        self.joystick_thread = threading.Thread(
            target=self.joystick_monitor,
            daemon=True
        )
        self.joystick_thread.start()

        # WebSocketサーバースレッド（初期状態では非起動）
        self.server_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.root, self.settings)
        self.root.wait_window(dialog)
        self.save_settings()
        self.update_server_status_display()

    def change_joystick(self):
        count = pygame.joystick.get_count()
        if count < 1:
            return
        elif count == 1:
            self.reconnect_joystick(0)
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
                self.reconnect_joystick(choice)

    def reconnect_joystick(self, joystick_id):
        try:
            if pygame.joystick.get_count() > joystick_id:
                self.joystick = pygame.joystick.Joystick(joystick_id)
                self.joystick.init()
                self.current_joystick_id = joystick_id
                name = self.joystick.get_name()
                self.joystick_info.config(text=f"接続ジョイパッド: {name} (ID: {joystick_id})")
        except pygame.error as e:
            print(f"ジョイパッド接続エラー: {e}")

    def init_pygame(self):
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() == 0:
                raise pygame.error("No joystick detected")
            
            self.reconnect_joystick(0)
            self.change_joystick_btn.config(state=tk.NORMAL)
        except pygame.error as e:
            self.joystick_info.config(text=str(e), foreground="red")
            self.running = False

    def joystick_monitor(self):
        self.running = True
        while self.running:
            if pygame.joystick.get_count() > 0:
                for event in pygame.event.get():
                    self.process_joystick_event(event)
                pygame.time.wait(20)
            else:
                self.joystick_info.config(text="ジョイパッド切断", foreground="red")
                pygame.time.wait(1000)

    def process_joystick_event(self, event):
        event_data = None
        
        if event.type == pygame.JOYAXISMOTION:
            event_data = {
                'type': 'axis',
                'axis': event.axis,
                'value': round(event.value, 2)
            }
        elif event.type == pygame.JOYBUTTONDOWN:
            self.button_count += 1
            self.root.after(0, self.update_counter_display)
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
            self.event_queue.put(event_data)

    def update_counter_display(self):
        self.counter_label.config(text=f"ボタン押下回数: {self.button_count}")

    async def websocket_handler(self, websocket):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                pass
        finally:
            self.clients.remove(websocket)

    #async def send_joystick_events(self):
    #    while self.running:
    #        if not self.event_queue.empty():
    #            event = self.event_queue.get()
    #            print(self.settings['aaa'], event)
    #            message = json.dumps(event)
    #            for client in self.clients.copy():
    #                try:
    #                    await client.send(message)
    #                except:
    #                    self.clients.remove(client)
    #        await asyncio.sleep(0.02)
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
            await asyncio.sleep(0.05)  # 送信間隔調整

    async def main_server(self):
        async with websockets.serve(self.websocket_handler, "0.0.0.0", 8765):
            await self.send_joystick_events()

    def run_websocket_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.main_server())


    def update_server_status_display(self):
        status_text = "停止中" if not self.running else "稼働中"
        self.server_status.config(
            text=f"WebSocket: {status_text} (ポート: {self.settings['port']})"
        )

    def load_settings(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    return {**self.DEFAULT_SETTINGS, **json.load(f)}
            except:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()

    def save_settings(self):
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(self.settings, f)

    # 以下、前回の実装と同様のメソッド（変更部分のみ抜粋）

    async def main_server(self):
        async with websockets.serve(
            self.websocket_handler,
            "0.0.0.0",
            self.settings['port']
        ):
            await self.send_joystick_events()

    def toggle_server(self):
        if self.server_thread.is_alive():
            self.running = False
            self.control_button.config(text="サーバー起動")
            self.update_server_status_display()
        else:
            self.running = True
            self.server_thread = threading.Thread(
                target=self.run_websocket_server,
                daemon=True
            )
            self.server_thread.start()
            self.control_button.config(text="サーバー停止")
            self.update_server_status_display()

    # その他のメソッド（joystick_monitor、process_joystick_eventなど）は前回と同様
    def on_close(self):
        self.running = False
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JoystickWebSocketServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
