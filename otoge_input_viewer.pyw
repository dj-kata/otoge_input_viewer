# 新処理方式のテスト用
import pygame
import websockets
import asyncio
import json
import threading
from queue import Queue
import os
import sys
import json
import time
from collections import defaultdict
import logging, logging.handlers
from src.settings import Settings, playmode, SettingsDialog
from src.key_config import KeyConfigDialog, event_to_spec, spec_key, spec_matches, target_definitions, target_to_event_data
from src.update import GitHubUpdater
import traceback
import urllib
import webbrowser
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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


class JoystickWebSocketServer(QMainWindow):
    label_update_requested = Signal(object, str, str)
    button_enabled_requested = Signal(object, bool)
    counter_update_requested = Signal()
    key_config_event_received = Signal(dict)

    def __init__(self):
        super().__init__()
        self.time_start = time.perf_counter()
        self.setWindowTitle("Otoge Input Viewer")
        self.setWindowIcon(QIcon("src/icon.ico"))
        self.label_update_requested.connect(self.set_label_text)
        self.button_enabled_requested.connect(self.set_button_enabled)
        self.counter_update_requested.connect(self.update_counter_display)
        self.scratch_queue = Queue() # スクラッチだけoff用処理も入れるため分ける
        self.calc_queue = Queue()  # 計算用のキュー、全イベントをここに流す
        self.event_queue = Queue() # HTMLへの出力をすべてここに通す
        self.running = False
        self.clients = set()
        self.today_notes  = 0 # 合計
        self.today_keys   = 0 # 鍵盤部分
        self.today_others = 0 # スクラッチとかツマミとかピックとか
        # スクラッチ判定用
        self.pre_scr_val = [None, None]
        self.pre_scr_direction = [-1, -1]
        self.pre_mapped_axis_val = {}
        self.pre_mapped_axis_direction = {}
        self.pre_event_axis_val = {}
        self.pre_event_axis_cache = {}
        self.mapped_button_axis_state = {}
        self.mapped_button_axis_direction = {}
        self.held_axis_button_events = {}
        self.held_axis_button_lock = threading.Lock()
        self.list_density = []
        self.settings = Settings()
        logger.debug(f'settings = {self.settings.__dict__}')

        self.joystick = [None, None]
        self.key_config_dialog = None

        self.move(self.settings.lx, self.settings.ly)

        self.setup_gui()
        self.init_pygame()
        self.start_monitor()
        self.start_threads()
        logger.debug('started!')
        if self.settings.auto_update:
            self.check_updates()

    def check_updates(self, always_disp_dialog=False):
        updater = GitHubUpdater(
            github_author="dj-kata",
            github_repo="otoge_input_viewer",
            zipfile_basename="otoge_input_viewer",
            current_version=SWVER,
            main_exe_name="otoge_input_viewer.exe",
            updator_exe_name="otoge_input_viewer.exe",
        )
        updater.check_and_update(show_no_update=always_disp_dialog)

    def get_uptime(self):
        """アプリの起起動時を文字列として返す

        Returns:
            str: HH:MM:SS形式の文字列
        """
        uptime = time.perf_counter() - self.time_start
        uptime_h = int(uptime//3600)
        uptime_m = int((uptime - uptime_h*3600)//60)
        uptime_s = int((uptime-uptime_h*3600-uptime_m*60))
        uptime_str = f"{uptime_h:02d}:{uptime_m:02d}:{uptime_s:02d}"
        return uptime_str

    def tweet(self):
        """本日の打鍵数をTwitterに投稿する
        """
        msg = f"notes: {self.today_notes}"
        if self.settings.playmode == playmode.sdvx:
            msg += f" (key: {self.today_keys}, vol: {self.today_others})\n"
        elif self.settings.playmode in (playmode.iidx_sp, playmode.iidx_dp):
            msg += f" (key: {self.today_keys}, scratch: {self.today_others})\n"
        msg += f"mode: {self.settings.playmode.name}\n"
        msg += f"uptime: {self.get_uptime()}\n#otoge_input_viewer\n"
        encoded_msg = urllib.parse.quote(f"{msg}")
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")

    def setup_gui(self):
        """GUIの設定を行う
        """
        settings_menu = self.menuBar().addMenu("file")
        settings_menu.addAction(QAction("config", self, triggered=self.open_settings_dialog))
        settings_menu.addAction(QAction("キーイベント登録", self, triggered=self.open_key_config_dialog))
        settings_menu.addAction(QAction("update", self, triggered=lambda:self.check_updates(True)))
        settings_menu.addAction(QAction("reset counter", self, triggered=self.reset_counter))
        settings_menu.addAction(QAction("tweet", self, triggered=self.tweet))

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(2)
        self.setCentralWidget(central)

        ctr_layout = QGridLayout()
        ctr_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(ctr_layout)

        # ジョイパッド情報
        self.joystick_info = []
        self.joystick_info.append(QLabel("接続ジョイパッド: なし"))
        ctr_layout.addWidget(self.joystick_info[0], 0, 0, alignment=Qt.AlignLeft)

        # コントローラ変更ボタン1
        self.change_joystick_btn = QPushButton("change")
        self.change_joystick_btn.clicked.connect(lambda:self.change_joystick(0))
        ctr_layout.addWidget(self.change_joystick_btn, 0, 1, alignment=Qt.AlignLeft)

        # ジョイパッド情報
        self.joystick_info.append(QLabel("接続ジョイパッド: なし"))
        ctr_layout.addWidget(self.joystick_info[1], 1, 0, alignment=Qt.AlignLeft)

        # コントローラ変更ボタン2
        self.change_joystick_btn2 = QPushButton("change")
        self.change_joystick_btn2.clicked.connect(lambda:self.change_joystick(1))
        ctr_layout.addWidget(self.change_joystick_btn2, 1, 1, alignment=Qt.AlignLeft)
        if self.settings.playmode != playmode.iidx_dp:
            self.change_joystick_btn2.setEnabled(False)

        # モード表示
        self.mode_label = QLabel(f'mode: {self.settings.playmode.name}')
        layout.addWidget(self.mode_label, alignment=Qt.AlignLeft)

        # ボタンカウンター
        self.counter_label = QLabel("notes: 0")
        layout.addWidget(self.counter_label, alignment=Qt.AlignLeft)

        # サーバー状態表示
        self.server_status = QLabel(f"WebSocket port: {self.settings.port}")
        layout.addWidget(self.server_status, alignment=Qt.AlignLeft)

        # uptime表示
        self.uptime_label = QLabel(f"uptime: 00:00:00")
        layout.addWidget(self.uptime_label, alignment=Qt.AlignLeft)

        # その他情報表示
        self.other_info = QLabel("")
        layout.addWidget(self.other_info, alignment=Qt.AlignLeft)

    def set_label_text(self, label, text, color=""):
        label.setText(text)
        label.setStyleSheet(f"color: {color};" if color else "")

    def set_button_enabled(self, button, enabled):
        button.setEnabled(enabled)

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

        # ボタン割当スクラッチの押しっぱなしを疑似的な連続回転として扱う
        self.axis_button_repeat_thread = threading.Thread(
            target=self.thread_axis_button_repeat,
            daemon=True
        )
        self.axis_button_repeat_thread.start()

        # 時計更新用スレッド
        self.uptime_thread = threading.Thread(
            target=self.thread_uptime,
            daemon=True
        )
        self.uptime_thread.start()

    def open_settings_dialog(self):
        """設定ウィンドウを開く
        """
        dialog = SettingsDialog(self, self.settings)
        dialog.exec()
        self.settings.load()
        self.settings.disp()
        self.update_server_status_display()
        if self.settings.playmode == playmode.iidx_dp:
            self.change_joystick_btn2.setEnabled(True)
        else:
            if self.settings.connected_idx[1] is not None:
                self.change_joystick_btn2.setEnabled(False)
                self.joystick[1].quit()
                self.joystick[1] = None
                self.set_label_text(self.joystick_info[1], f"joypad disconnected", 'red')
                self.settings.connected_idx[1] = None
        self.toggle_server()

    def open_key_config_dialog(self):
        """キーイベント登録ウィンドウを開く
        """
        dialog = KeyConfigDialog(self, self.settings)
        self.key_config_dialog = dialog
        dialog.exec()
        self.key_config_dialog = None
        self.settings.load()

    def change_joystick(self, controller_pos:int):
        """検出するジョイパッドを変更する

        Args:
            controller_pos (int): DP時に使うコントローラ0,1のどちらを変更するか
        """
        count = pygame.joystick.get_count()
        logger.debug(f'pos={controller_pos}, count={count}')
        if count < 1:
            return
        else:
            if count == 1:
                if self.settings.playmode != playmode.iidx_dp:
                    if (self.settings.connected_idx[controller_pos] is None) or (self.joystick[controller_pos] is None):
                        self.reconnect_joystick(controller_pos, 0)
                else: # DPの場合、コントローラ1つなら他方に移動
                    if self.settings.connected_idx[1-controller_pos] is not None:
                        if self.joystick[1-controller_pos] is not None:
                            self.joystick[1-controller_pos].quit()
                        self.joystick[1-controller_pos] = None
                        self.label_update_requested.emit(self.joystick_info[1-controller_pos], f"joypad disconnected", 'red')
                        self.settings.connected_idx[1-controller_pos] = None
                    self.reconnect_joystick(controller_pos, 0)

            else: # コントローラ2つ以上
                if self.settings.playmode != playmode.iidx_dp:
                    idx = (self.joystick[controller_pos].get_id() + 1) % count
                    self.reconnect_joystick(controller_pos, idx)
                else: # DPかつコントローラ2つ以上検出済みの場合
                    if self.joystick[controller_pos] is None:
                        chk_used = [0]*count # 各コントローラが使われているかどうか
                        for i in range(2):
                            if self.settings.connected_idx[i] is not None:
                                chk_used[self.settings.connected_idx[i]] = 1
                        for i,flg in enumerate(chk_used):
                            if flg == 0:
                                idx = i # 必ず1回は通るはず
                                break
                    else:
                        idx = (self.joystick[controller_pos].get_id() + 1) % count
                    if self.settings.connected_idx[1-controller_pos] == idx: # 他方のコントローラの割当を奪う場合
                        idx_other = self.joystick[controller_pos].get_id()
                        self.reconnect_joystick(1-controller_pos, idx_other)
                    self.reconnect_joystick(controller_pos, idx)
        logger.debug(f'self.joystick = {self.joystick}')


    def reconnect_joystick(self, controller_pos:int=0, idx:int=0):
        """コントローラへの再接続処理。

        Args:
            controller_pos (int): 0,1のどちらのコントローラか
            idx (int): idx番のジョイパッドに接続
        """
        try:
            self.joystick[controller_pos] = pygame.joystick.Joystick(idx)
            self.joystick[controller_pos].init()
            name = self.joystick[controller_pos].get_name()
            self.label_update_requested.emit(self.joystick_info[controller_pos], f"connected: {name} (ID: {idx})", 'blue')
            self.settings.connected_idx[controller_pos] = idx
        except pygame.error as e:
            logger.error(f"ジョイパッド接続エラー: {e}")

    def init_pygame(self):
        """初回起動時のコントローラ初期化処理
        """
        pygame.init()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        logger.debug(f"count={count}, connected_idx={self.settings.connected_idx}")
        for controller_pos in range(2):
            try:
                if count == 0:
                    logger.debug('No joystick detected')
                else: # コントローラが接続されている
                    if self.settings.connected_idx[controller_pos] is not None:
                        self.reconnect_joystick(controller_pos, self.settings.connected_idx[controller_pos])
                        logger.debug(f'pos{controller_pos} connected (idx={self.settings.connected_idx[controller_pos]})')
                self.button_enabled_requested.emit(self.change_joystick_btn, True)
            except pygame.error as e:
                logger.error(e)
                self.label_update_requested.emit(self.joystick_info[controller_pos], str(e), "red")

    def thread_density(self):
        """scratch処理用スレッド。リリース/密度の送信及び皿オフの扱いを入れる。scratch_queueのデータを受信してevent_queueに送る。
        """
        print('scratch thread start')
        time_last_sent = 0 # 最後に送信した時間
        while True:
            cur_time = time.perf_counter()
            if cur_time - time_last_sent > self.settings.density_interval: # 各種出力
                if len(self.list_density) > 0: # 密度の出力
                    if cur_time - self.list_density[-1] > self.settings.density_interval:
                        self.list_density = []
                    for i in range(len(self.list_density)):
                        if cur_time - self.list_density[i] <= self.settings.density_interval:
                            break
                    self.list_density = self.list_density[i:] # 直近5秒以内の範囲だけに整形
                    if (len(self.list_density) == 0) or (cur_time == self.list_density[0]):
                        density = 0.0
                    else:
                        #density = len(self.list_density) / (cur_time - self.list_density[0])
                        density = len(self.list_density) / self.settings.density_interval
                        # logger.debug(f"len:{len(self.list_density)}, {self.list_density}, width:{cur_time - self.list_density[0]}s, density:{density:.2f}")
                    event_data = {
                        'type': 'density',
                        'value': f"{density:.1f}"
                    }
                    self.event_queue.put(event_data)
                time_last_sent = cur_time
            time.sleep(0.1)

    def thread_calc(self):
        """release及びdensityの計算用スレッド。
        """
        SEND_INTERVAL  = 0.5 # 送信周期
        time_last_active = defaultdict(int) # 各鍵盤で最後にpushされた時刻を記録。
        list_allkeys = [] # 全鍵盤用のログ保存リスト
        list_eachkey = defaultdict(list)
        list_last_scratch = defaultdict(str) # 最後にどの向きだったか, axisごとに用意
        print('calc thread start')
        while True:
            tmp = self.calc_queue.get()
            cur_time = time.perf_counter()
            if tmp['type'] == 'button': # 鍵盤
                key = tmp['button'] + tmp['controller_side']*7 # どの鍵盤か
                if tmp['state'] == 'down':
                    time_last_active[key] = cur_time
                    self.list_density.append(cur_time) # LNは関係なく密度計算には使う
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
                            list_eachkey[key].pop(0)
                        release = sum(list_eachkey[key]) / len(list_eachkey[key])
                        event_data = {
                            'type': 'release_eachkey',
                            'button': key,
                            'value': f"{release*1000:.1f}"
                        }
                        self.event_queue.put(event_data)

            elif tmp['type'] == 'axis': # スクラッチ
                if tmp['direction'] != list_last_scratch[tmp['axis']]:
                    self.list_density.append(cur_time)
                list_last_scratch[tmp['axis']] = tmp['direction']

    def thread_uptime(self):
        """uptimeの表示更新用スレッド
        """
        while True:
            uptime = self.get_uptime()
            self.label_update_requested.emit(self.uptime_label, f"uptime: {uptime}", "")
            time.sleep(1)

    def is_valid_event(self, event):
        if self.has_key_config():
            if self.is_mapped_event(event) or event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                return True
            if self.default_target_is_configured(event):
                return False
            return self.is_valid_default_event(event)
        return self.is_valid_default_event(event)

    def is_valid_default_event(self, event):
        ret = False
        if event.type == pygame.JOYBUTTONDOWN:
            if self.settings.playmode == playmode.iidx_sp:
                #if event.button <= 6 and event.instance_id == self.settings.connected_idx[0]:
                if event.button <= 6 :
                    ret = True
            elif self.settings.playmode == playmode.iidx_dp:
                #if event.button <= 6 and event.joy in self.settings.connected_idx:
                if event.button <= 6 :
                    ret = True
            elif self.settings.playmode==playmode.sdvx:
                if event.button >=1 and event.button<=6:
                    ret = True
        elif event.type == pygame.JOYAXISMOTION:
            if self.settings.playmode in (playmode.iidx_sp, playmode.iidx_dp):
                if event.axis==0:
                    ret = True
            elif self.settings.playmode==playmode.sdvx:
                if event.axis in (0,1):
                    ret = True
        elif event.type in (pygame.JOYBUTTONUP, pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            ret = True
        if self.settings.debug_mode:
            logger.debug(f'event = {event}')
            logger.debug(f'ret = {ret}')
        return ret

    def has_key_config(self):
        mode_config = getattr(self.settings, "key_config", {}).get(self.settings.playmode.name, {})
        return any(spec.get("event_type") for spec in mode_config.values() if spec)

    def joystick_name_from_event(self, event):
        try:
            if hasattr(event, 'joy'):
                return pygame.joystick.Joystick(event.joy).get_name()
        except pygame.error:
            pass
        return ""

    def event_axis_direction(self, event):
        axis_key = (getattr(event, 'joy', None), event.axis)
        cache_key = (getattr(event, 'joy', None), event.axis, event.value)
        cached = self.pre_event_axis_cache.get(axis_key)
        if cached and cached[0] == cache_key:
            return cached[1]
        if axis_key in self.pre_event_axis_val:
            if event.value > self.pre_event_axis_val[axis_key]:
                direction = 1
            elif event.value < self.pre_event_axis_val[axis_key]:
                direction = 0
            else:
                direction = -1
        else:
            direction = 1 if event.value >= 0 else 0
        self.pre_event_axis_val[axis_key] = event.value
        self.pre_event_axis_cache[axis_key] = (cache_key, direction)
        return direction

    def event_axis_value_sign(self, event):
        if event.value >= 0.5:
            return 1
        if event.value <= -0.5:
            return -1
        return 0

    def event_spec_from_pygame(self, event):
        if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            return event_to_spec(event, self.joystick_name_from_event(event), "button")
        if event.type == pygame.JOYAXISMOTION:
            return event_to_spec(
                event,
                self.joystick_name_from_event(event),
                "axis",
                self.event_axis_direction(event),
                self.event_axis_value_sign(event),
            )
        return None

    def is_key_config_capturing(self):
        return self.key_config_dialog is not None and self.key_config_dialog.capture_target_id is not None

    def is_registerable_event(self, event):
        if event.type == pygame.JOYBUTTONDOWN:
            return True
        if event.type == pygame.JOYAXISMOTION:
            return True
        return False

    def mapped_target_entries(self):
        mode_name = self.settings.playmode.name
        mode_config = getattr(self.settings, "key_config", {}).get(mode_name, {})
        targets = {target["id"]: target for target in target_definitions(mode_name)}
        ret = []
        for target_id, spec in mode_config.items():
            target = targets.get(target_id)
            if spec and target and spec.get("event_type"):
                ret.append((target_id, spec, target))
        return ret

    def is_same_physical_control(self, registered_spec, event_spec):
        if not registered_spec or not event_spec:
            return False
        keys = ("controller_name", "controller_id", "event_type", "control_id")
        return all(registered_spec.get(key) == event_spec.get(key) for key in keys)

    def has_axis_button_mapping_for_event(self, event):
        if event.type != pygame.JOYAXISMOTION:
            return False
        spec = self.event_spec_from_pygame(event)
        return any(
            target["kind"] == "button"
            and registered_spec.get("event_type") == "axis"
            and self.is_same_physical_control(registered_spec, spec)
            for _, registered_spec, target in self.mapped_target_entries()
        )

    def configured_target_ids(self):
        mode_config = getattr(self.settings, "key_config", {}).get(self.settings.playmode.name, {})
        return {target_id for target_id, spec in mode_config.items() if spec and spec.get("event_type")}

    def default_target_id_from_event(self, event):
        controller_side = 0
        if hasattr(event, 'joy') and self.settings.connected_idx[0] != event.joy:
            controller_side = 1
        if self.settings.playmode == playmode.iidx_sp:
            if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP) and 0 <= event.button <= 6:
                return f"k{event.button + 1}"
        elif self.settings.playmode == playmode.iidx_dp:
            prefix = f"p{controller_side + 1}"
            if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP) and 0 <= event.button <= 6:
                return f"{prefix}_k{event.button + 1}"
        elif self.settings.playmode == playmode.sdvx:
            button_targets = {
                1: "bt_a",
                2: "bt_b",
                3: "bt_c",
                4: "bt_d",
                5: "fx_l",
                6: "fx_r",
            }
            if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                return button_targets.get(event.button)
        return None

    def default_target_is_configured(self, event):
        target_id = self.default_target_id_from_event(event)
        if target_id is not None:
            return target_id in self.configured_target_ids()
        configured = self.configured_target_ids()
        controller_side = 0
        if hasattr(event, 'joy') and self.settings.connected_idx[0] != event.joy:
            controller_side = 1
        if self.settings.playmode == playmode.iidx_sp and event.type == pygame.JOYAXISMOTION and event.axis == 0:
            return bool({"scr_up", "scr_down"} & configured)
        if self.settings.playmode == playmode.iidx_dp and event.type == pygame.JOYAXISMOTION and event.axis == 0:
            prefix = f"p{controller_side + 1}_scr"
            return bool({f"{prefix}_up", f"{prefix}_down"} & configured)
        if self.settings.playmode == playmode.sdvx and event.type == pygame.JOYAXISMOTION:
            if event.axis == 0:
                return bool({"vol_l_up", "vol_l_down"} & configured)
            if event.axis == 1:
                return bool({"vol_r_up", "vol_r_down"} & configured)
        return False

    def is_mapped_event(self, event):
        spec = self.event_spec_from_pygame(event)
        if spec is None:
            return False
        return self.has_axis_button_mapping_for_event(event) or any(
            spec_matches(registered_spec, spec)
            for _, registered_spec, _ in self.mapped_target_entries()
        )

    def monitor_thread(self):
        """ジョイパッドの入力イベントを受け取るループ
        """
        print('monitor_thread start')
        while True:
            try:
                for event in pygame.event.get():
                    if self.settings.debug_mode:
                        logger.debug(event)
                    if self.is_key_config_capturing() and self.is_registerable_event(event):
                        spec = self.event_spec_from_pygame(event)
                        if spec:
                            self.key_config_event_received.emit(spec)
                        continue
                    # モードごとに必要なノートのみ通すための判定処理
                    if not self.is_valid_event(event):
                        continue
                    if self.has_key_config() and self.is_mapped_event(event):
                        self.process_mapped_joystick_event(event)
                    else:
                        self.process_joystick_event(event)
                if pygame.joystick.get_count() == 0:
                    for i in range(2):
                        self.label_update_requested.emit(self.joystick_info[i], f"joypad disconnected", 'red')
            except Exception as e:
                logger.debug(traceback.format_exc())
            pygame.time.wait(20)

    def dispatch_event_data(self, event_data, count_notes=False, count_key=False, count_other=False):
        if count_notes:
            self.today_notes += 1
            if count_key:
                self.today_keys += 1
            if count_other:
                self.today_others += 1
            self.counter_update_requested.emit()
            self.event_queue.put({'type':'notes', 'value':self.today_notes})
        self.calc_queue.put(event_data)
        self.event_queue.put(event_data)

    def thread_axis_button_repeat(self):
        """スクラッチ/つまみに割り当てた通常ボタンの長押しを連続axis入力として流す。"""
        while True:
            with self.held_axis_button_lock:
                held_events = [dict(event_data) for event_data in self.held_axis_button_events.values()]
            for event_data in held_events:
                self.dispatch_event_data(event_data)
            time.sleep(0.12)

    def process_mapped_joystick_event(self, event):
        spec = self.event_spec_from_pygame(event)
        if spec is None:
            return
        matched_targets = [
            (target_id, registered_spec, target)
            for target_id, registered_spec, target in self.mapped_target_entries()
            if spec_matches(registered_spec, spec)
            or (
                target["kind"] == "button"
                and registered_spec.get("event_type") == "axis"
                and self.is_same_physical_control(registered_spec, spec)
            )
        ]
        if not matched_targets:
            return

        for target_id, registered_spec, target in matched_targets:
            if target["kind"] == "button":
                if event.type == pygame.JOYBUTTONDOWN:
                    event_data = target_to_event_data(target, state='down')
                    self.dispatch_event_data(event_data, count_notes=True, count_key=True)
                elif event.type == pygame.JOYBUTTONUP:
                    event_data = target_to_event_data(target, state='up')
                    self.dispatch_event_data(event_data)
                elif event.type == pygame.JOYAXISMOTION:
                    state_key = (target_id, spec_key(registered_spec))
                    sign = spec.get("value_sign", 0)
                    registered_sign = registered_spec.get("value_sign")
                    direction = spec.get("direction")
                    registered_direction = registered_spec.get("direction")
                    invert_axis = registered_spec.get("invert_axis", False)
                    if registered_sign is not None:
                        if invert_axis:
                            pressed = sign != 0 and sign != registered_sign
                        else:
                            pressed = sign != 0 and sign == registered_sign
                    elif registered_direction is None:
                        active_direction = self.mapped_button_axis_direction.get(state_key)
                        pressed = abs(event.value) >= 0.5 and (active_direction is None or direction == active_direction)
                        if invert_axis:
                            pressed = abs(event.value) >= 0.5 and not pressed
                        if pressed:
                            self.mapped_button_axis_direction[state_key] = direction
                    else:
                        if invert_axis:
                            pressed = abs(event.value) >= 0.5 and direction != registered_direction
                        else:
                            pressed = abs(event.value) >= 0.5 and direction == registered_direction
                    previous_pressed = self.mapped_button_axis_state.get(state_key)
                    if previous_pressed == pressed or (previous_pressed is None and not pressed):
                        continue
                    self.mapped_button_axis_state[state_key] = pressed
                    if not pressed:
                        self.mapped_button_axis_direction.pop(state_key, None)
                    event_data = target_to_event_data(target, state='down' if pressed else 'up')
                    self.dispatch_event_data(event_data, count_notes=pressed, count_key=pressed)
            elif target["kind"] == "axis_dir" and event.type == pygame.JOYAXISMOTION:
                if spec.get("direction") < 0:
                    continue
                event_data = target_to_event_data(target, value_org=event.value)
                count_other = target_id != self.pre_mapped_axis_direction.get((registered_spec.get("controller_id"), registered_spec.get("control_id")))
                self.pre_mapped_axis_direction[(registered_spec.get("controller_id"), registered_spec.get("control_id"))] = target_id
                self.dispatch_event_data(event_data, count_notes=count_other, count_other=count_other)
            elif target["kind"] == "axis_dir" and event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                is_down = event.type == pygame.JOYBUTTONDOWN
                hold_key = (target_id, spec_key(registered_spec))
                event_data = target_to_event_data(target, value=1 if is_down else 0)
                with self.held_axis_button_lock:
                    if is_down:
                        self.held_axis_button_events[hold_key] = target_to_event_data(target)
                    else:
                        self.held_axis_button_events.pop(hold_key, None)
                self.dispatch_event_data(event_data, count_notes=is_down, count_other=is_down)

    def process_joystick_event(self, event):
        """1つのジョイパッド入力イベントを読み込んでwebsocket出力に変換する。

        Args:
            event (pygame.event): 入力イベント
        """
        event_data = None

        # TODO 切断時の対策(現IDの接続ならNoneにする)、再接続時の対策
        controller_side = 0
        if hasattr(event, 'joy'):
            if self.settings.connected_idx[0]!=event.joy:
                controller_side = 1
        if event.type == pygame.JOYAXISMOTION:
            out_direction = -1
            if self.pre_scr_val[event.axis] is not None:
                if event.value > self.pre_scr_val[event.axis]:
                    out_direction = 1
                elif event.value < self.pre_scr_val[event.axis]:
                    out_direction = 0
            self.pre_scr_val[event.axis] = event.value
            event_data = {
                'type': 'axis',
                'axis': event.axis,
                'direction': out_direction,
                'pos': event.axis*2 + out_direction,
                'value': 1,
                'controller_side': controller_side,
                'value_org': event.value,
            }
            if out_direction != self.pre_scr_direction[event.axis]:
                self.today_notes += 1
                self.today_others += 1
                self.counter_update_requested.emit()
                self.event_queue.put({'type':'notes', 'value':self.today_notes})
            self.pre_scr_direction[event.axis] = out_direction
        elif event.type == pygame.JOYBUTTONDOWN:
            self.today_notes += 1
            self.today_keys += 1
            self.counter_update_requested.emit()
            self.event_queue.put({'type':'notes', 'value':self.today_notes})
            event_data = {
                'type': 'button',
                'button': event.button,
                'state': 'down',
                'controller_side': controller_side,
            }
        elif event.type == pygame.JOYBUTTONUP:
            event_data = {
                'type': 'button',
                'button': event.button,
                'state': 'up',
                'controller_side': controller_side,
            }
        elif event.type == pygame.JOYDEVICEADDED:
            if pygame.joystick.get_count() == 1:
                self.reconnect_joystick(0, 0)
            else:
                if self.settings.playmode != playmode.iidx_dp:
                    if pygame.joystick.get_count() == 2:
                        if self.joystick[0] is None:
                            self.reconnect_joystick(0, event.device_index)
        elif event.type == pygame.JOYDEVICEREMOVED:
            for i in range(2):
                if self.joystick[i] is not None and self.joystick[i].get_instance_id() == event.instance_id:
                    self.settings.connected_idx[i] = None
                    self.label_update_requested.emit(self.joystick_info[i], f"joypad disconnected", 'red')
                    logger.debug(f'joypad {i} disconnected. connected_idx={self.settings.connected_idx}')
            if self.settings.playmode != playmode.iidx_dp:
                if pygame.joystick.get_count() > 0:
                    self.reconnect_joystick(0)
        
        if event_data:
            self.calc_queue.put(event_data)
            self.event_queue.put(event_data)

    def reset_counter(self):
        self.today_notes = 0
        self.today_keys = 0
        self.today_others = 0
        self.time_start = time.perf_counter()
        self.counter_label.setText(f"notes: {self.today_notes}")

    def update_counter_display(self):
        if self.settings.playmode == playmode.sdvx:
            self.counter_label.setText(f"notes: {self.today_notes} (key: {self.today_keys} + vol: {self.today_others})")
        else: # 1p or 2p
            self.counter_label.setText(f"notes: {self.today_notes} (key: {self.today_keys} + scr: {self.today_others})")

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
        self.server_status.setText(f"WebSocket: {status_text} (ポート: {self.settings.port})")
        self.mode_label.setText(f"mode: {self.settings.playmode.name}")

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
            '0.0.0.0',
            self.settings.port
        ):
            await self.send_joystick_events()

    def toggle_server(self):
        logger.debug('')
        if self.server_thread.is_alive():
            self.running = False
            self.server_thread.join()
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

    def on_close(self):
        """メインウィンドウ終了時に実行される関数
        """
        logger.debug('exit')
        self.running = False
        self.settings.lx = self.x()
        self.settings.ly = self.y()
        self.settings.save()
        pygame.quit()
        QApplication.quit()

    def closeEvent(self, event):
        self.on_close()
        event.accept()

if __name__ == "__main__":
    try:
        qt_app = QApplication(sys.argv)
        qt_app.setWindowIcon(QIcon("src/icon.ico"))
        app = JoystickWebSocketServer()
        app.setMinimumSize(300, 200)
        app.show()
        sys.exit(qt_app.exec())
    except Exception as e:
        logger.error(traceback.format_exc())
