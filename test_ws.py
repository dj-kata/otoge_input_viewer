# 新処理方式のテスト用
import tkinter as tk
from tkinter import ttk, simpledialog
import pygame
import websockets
import asyncio
import json
import threading
from queue import Queue

class JoystickWebSocketServer:
    def __init__(self, root):
        self.root = root
        self.root.title("Joystick WebSocket Server")
        self.event_queue = Queue()
        self.running = False
        self.clients = set()
        self.aaa = 100
        self.button_count = 0
        self.current_joystick_id = 0

        # GUI初期化
        self.setup_gui()
        
        # pygame初期化
        self.init_pygame()
        
        # スレッド起動
        self.start_threads()

    def setup_gui(self):
        """GUIコンポーネントの設定"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        settings_menu = tk.Menu(self.menubar, tearoff=0)
        settings_menu.add_command(label="設定変更", command=self.open_settings_dialog)
        self.menubar.add_cascade(label="設定", menu=settings_menu)

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.joystick_info = ttk.Label(
            main_frame,
            text="接続ジョイパッド: なし",
            font=("Meiryo UI", 10)
        )
        self.joystick_info.pack(pady=5)

        self.change_joystick_btn = ttk.Button(
            main_frame,
            text="コントローラ変更",
            command=self.change_joystick,
            state=tk.DISABLED
        )
        self.change_joystick_btn.pack(pady=5)

        self.counter_label = ttk.Label(
            main_frame,
            text="ボタン押下回数: 0",
            font=("Meiryo UI", 10)
        )
        self.counter_label.pack(pady=5)

        self.server_status = ttk.Label(
            main_frame,
            text="WebSocket: 停止中",
            font=("Meiryo UI", 10)
        )
        self.server_status.pack(pady=5)

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
        new_value = simpledialog.askinteger(
            "設定",
            "変数AAAの値を入力:",
            parent=self.root,
            minvalue=0,
            maxvalue=1000,
            initialvalue=self.aaa
        )
        if new_value is not None:
            self.aaa = new_value
            print(f"AAAの値を {self.aaa} に更新しました")

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

    async def send_joystick_events(self):
        while self.running:
            if not self.event_queue.empty():
                event = self.event_queue.get()
                print(self.aaa, event)
                message = json.dumps(event)
                for client in self.clients.copy():
                    try:
                        await client.send(message)
                    except:
                        self.clients.remove(client)
            await asyncio.sleep(0.02)

    async def main_server(self):
        async with websockets.serve(self.websocket_handler, "0.0.0.0", 8765):
            await self.send_joystick_events()

    def run_websocket_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.main_server())

    def toggle_server(self):
        if self.server_thread.is_alive():
            self.running = False
            self.control_button.config(text="サーバー起動")
            self.server_status.config(text="WebSocket: 停止中", foreground="red")
        else:
            self.running = True
            self.server_thread = threading.Thread(
                target=self.run_websocket_server,
                daemon=True
            )
            self.server_thread.start()
            self.control_button.config(text="サーバー停止")
            self.server_status.config(text="WebSocket: 稼働中 (port 8765)", foreground="green")

    def on_close(self):
        self.running = False
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JoystickWebSocketServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
