# 新処理方式のテスト用
import tkinter as tk
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

        # GUI部品の初期化
        self.setup_gui()
        
        # pygame初期化
        self.init_pygame()
        
        # スレッド起動
        self.start_threads()

    def setup_gui(self):
        """GUIコンポーネントの設定"""
        self.status_frame = tk.Frame(self.root, padx=20, pady=10)
        self.status_frame.pack()

        self.joystick_status = tk.Label(
            self.status_frame, 
            text="ジョイパッド: 未接続",
            font=("Meiryo UI", 12)
        )
        self.joystick_status.pack(side=tk.LEFT, padx=10)

        self.server_status = tk.Label(
            self.status_frame,
            text="WebSocket: 停止中",
            font=("Meiryo UI", 12)
        )
        self.server_status.pack(side=tk.LEFT, padx=10)

        self.control_button = tk.Button(
            self.root,
            text="サーバー起動",
            command=self.toggle_server,
            font=("Meiryo UI", 12),
            width=15
        )
        self.control_button.pack(pady=10)

    def init_pygame(self):
        """pygameの初期化処理"""
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() == 0:
                raise pygame.error("No joystick detected")
            
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.update_joystick_status(f"接続中: {self.joystick.get_name()}", "green")
            
        except pygame.error as e:
            self.update_joystick_status(str(e), "red")
            self.running = False

    def start_threads(self):
        """スレッドの起動"""
        # ジョイパッド監視スレッド
        self.joystick_thread = threading.Thread(
            target=self.joystick_monitor,
            daemon=True
        )
        self.joystick_thread.start()

        # WebSocketサーバースレッド
        self.server_thread = threading.Thread(
            target=self.run_websocket_server,
            daemon=True
        )

    def joystick_monitor(self):
        """ジョイパッドイベントの監視"""
        self.running = True
        while self.running:
            if pygame.joystick.get_count() > 0:
                for event in pygame.event.get():
                    self.process_joystick_event(event)
                pygame.time.wait(20)
            else:
                self.update_joystick_status("ジョイパッド切断", "red")
                pygame.time.wait(1000)

    def process_joystick_event(self, event):
        """ジョイパッドイベントの処理"""
        event_data = None
        
        if event.type == pygame.JOYAXISMOTION:
            event_data = {
                'type': 'axis',
                'axis': event.axis,
                'value': round(event.value, 2)
            }
        elif event.type == pygame.JOYBUTTONDOWN:
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

    async def websocket_handler(self, websocket):
        """WebSocket接続ハンドラー"""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                # クライアントからのメッセージ受信（必要に応じて実装）
                pass
        finally:
            self.clients.remove(websocket)

    async def send_joystick_events(self):
        """ジョイパッドイベントの送信"""
        while self.running:
            if not self.event_queue.empty():
                event = self.event_queue.get()
                message = json.dumps(event)
                for client in self.clients.copy():
                    try:
                        await client.send(message)
                    except:
                        self.clients.remove(client)
            await asyncio.sleep(0.02)

    async def main_server(self):
        """WebSocketサーバー本体"""
        async with websockets.serve(self.websocket_handler, "0.0.0.0", 8765):
            await self.send_joystick_events()

    def run_websocket_server(self):
        """WebSocketサーバー実行スレッド"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.main_server())

    def toggle_server(self):
        """サーバー起動/停止切り替え"""
        if self.server_thread.is_alive():
            self.running = False
            self.control_button.config(text="サーバー起動")
            self.server_status.config(text="WebSocket: 停止中", fg="red")
        else:
            self.running = True
            self.server_thread = threading.Thread(
                target=self.run_websocket_server,
                daemon=True
            )
            self.server_thread.start()
            self.control_button.config(text="サーバー停止")
            self.server_status.config(text="WebSocket: 稼働中 (port 8765)", fg="green")

    def update_joystick_status(self, text, color):
        """ジョイパッド状態表示更新"""
        self.joystick_status.config(text=text, fg=color)

    def on_close(self):
        """終了処理"""
        self.running = False
        pygame.quit()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = JoystickWebSocketServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
