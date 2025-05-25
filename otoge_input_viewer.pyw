# IIDXコントローラの入力状態を表示したりリリース速度を計算したりする
import pygame
import sys, time
import numpy as np
import PySimpleGUI as sg
from functools import partial
import os
import threading
import traceback
from settings import Settings, playmode
from enum import Enum
import copy
import subprocess
import logging, logging.handlers
from bs4 import BeautifulSoup
import requests
from gui import GUI

FONT = ('Meiryo', 12)
FONTs = ('Meiryo', 8)

par_text = partial(sg.Text, font=FONT)
sg.theme('SystemDefault')

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

class DispButtons:
    def __init__(self):
        """コンストラクタ
        """
        self.settings = Settings()
        self.gui = GUI()
        self.ico=self.ico_path('icon.ico')
        self.gui.window = None
        self.gui.window_settings = None
        self.joystick = None
        self.is_device_valid = False # コントローラを検出できている場合にTrue
        self.stop_thread = False # 強制停止用
        self.state = [0]*14
        self.scratch = [0]*4
        self.release = 0.0
        self.density = 0.0
        self.density_hist = []

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

    def update_string(self, target, value):
        """GUIの文字を変更する。main画面でのみ通したいので入口を共通化している。

        Args:
            target (str): パーツ名
            value (str): 書き込みたい文字列

        Returns:
            _type_: _description_
        """
        if self.gui.window is None:
            return False
        try:
            self.gui.window[target].update(value)
        except Exception:
            print(traceback.format_exc())
            pass

    def update_device_state(self):
        """コントローラの検出状態(OK/NG)を出力する
        """
        try:
            self.gui.window['state'].update(f'OK')
            self.gui.window['state'].update(text_color='#0000ff')
        except Exception:
            print(traceback.format_exc())
            pass


    def ico_path(self, relative_path:str):
        """アイコン表示用

        Args:
            relative_path (str): アイコンファイル名

        Returns:
            str: アイコンファイルの絶対パス
        """
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def thread_write(self):
        """メンバ変数をxml出力するためのスレッド。皿や密度などの計算を正確に行うために別スレッド化する。
        """
        pre_state = None
        pre_scratch = None
        pre_density = None
        last_density_ts = time.perf_counter() # 最後に密度を計算した時刻を覚えておく。1sおきに処理したい。
        while True:
            cur_ts = time.perf_counter()
            if self.stop_thread:
                logger.debug('stop write thread')
                break
            # densityを計算
            if cur_ts - last_density_ts >= 1.0:
                last_density_ts = cur_ts
                # 全データが5s前になってしまったら切り捨て
                # 直近5sの範囲を取得
                if len(self.density_hist) > 0:
                    if cur_ts - self.density_hist[-1] > self.settings.time_window_density:
                        self.density_hist = []
                    for i in range(len(self.density_hist)):
                        if cur_ts - self.density_hist[i] <= self.settings.time_window_density:
                            break
                    self.density_hist = self.density_hist[i:] # 直近5秒以内の範囲だけに整形
                    self.density = len(self.density_hist) / self.settings.time_window_density
                else:
                    self.density = 0.0
            if (pre_state != self.state) or (pre_scratch != self.scratch) or (pre_density != self.density):
                self.update_string('density', f"{self.density:.1f}")
                self.update_string('state_btn', str(self.state))
                self.update_string('state_scr', str(self.scratch))
                self.write_state()
                self.scratch = [0]*4
                pre_state = copy.copy(self.state)
                pre_scratch = copy.copy(self.scratch)
                pre_density = self.density
            #self.update_device_state()

            time.sleep(0.001)

    def write_state(self):
        """現在のキー入力状態をxmlファイルに出力

        Args:
            state (list(int)): キー入力状態(1-7鍵 *2)。0/1
            scratch (list(int)): 皿入力状態(up/down *2)
            release (float): 平均リリース時間
            density (float): 平均密度
        """
        with open('buttons.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Items>\n")
            f.write(f"    <release>{self.release:.2f}</release>\n")
            f.write(f"    <density>{self.density:.2f}</density>\n\n")
            for i in range(14):
                f.write(f'    <btn{i+1}>{self.state[i]}</btn{i+1}>\n')
            for i in range(4):
                f.write(f'    <scr{i+1}>{self.scratch[i]}</scr{i+1}>\n')
            f.write("</Items>\n")

    def thread_detect(self):
        """コントローラ入力を監視するスレッド。
        """
        pygame.init()
        pygame.joystick.init()

        time_down = [-1]*14 # 押し始めた時刻を記録
        release_hist = []
        self.density_hist = []

        pre_scr_val = None
        pre_scr_is_up = [False, False]

        logger.debug('detect thread started')

        # 起動時のコントローラ接続
        cnt = pygame.joystick.get_count()
        if cnt > 0:
            self.is_device_valid = True
            if self.settings.connected_idx == None:
                self.settings.connected_idx = 0
            self.settings.connected_idx = min(self.settings.connected_idx, cnt-1)
            self.settings.connected_idx = self.settings.connected_idx
            self.joystick = pygame.joystick.Joystick(self.settings.connected_idx)
            self.gui.window['device1'].update(f'{self.settings.connected_idx}.{self.joystick.get_name()}')
            self.joystick.init()

        while True:
            if self.stop_thread:
                logger.debug('stop detect thread')
                break
            try:
                for event in pygame.event.get():
                    if self.settings.debug_mode:
                        logger.debug(event)
                    if (event.type == pygame.JOYDEVICEADDED):
                        tmp = pygame.joystick.Joystick(event.device_index)
                        logger.debug(f'device_index={event.device_index}, name={tmp.get_name()} added')
                    elif (event.type == pygame.JOYDEVICEREMOVED):
                        logger.debug(f'instance_id={event.instance_id} removed')
                    elif event.type == pygame.JOYBUTTONDOWN:
                        if event.joy == self.settings.connected_idx:
                            if event.button >= 14:
                                continue
                            #print('down', event.button)
                            self.state[event.button] = 1
                            time_down[event.button] = time.perf_counter()
                    elif event.type == pygame.JOYBUTTONUP:
                        if event.joy == self.settings.connected_idx:
                            if event.button >= 14:
                                continue
                            self.state[event.button] = 0
                            tmp_release = (time.perf_counter() - time_down[event.button])*1000
                            if tmp_release < self.settings.ln_threshold:
                                self.density_hist.append(time.perf_counter())
                                release_hist.append(tmp_release)
                                if len(release_hist) > self.settings.size_release_hist:
                                    release_hist.pop(0)
                                self.release = sum(release_hist) / len(release_hist)
                                self.update_string('release', f"{self.release:.1f}")

                    elif event.type == pygame.JOYAXISMOTION:
                        if pre_scr_val is not None:
                            if event.value > pre_scr_val:
                                if not pre_scr_is_up[0]:
                                    self.density_hist.append(time.perf_counter())
                                self.scratch[0] = 1
                                pre_scr_is_up[0] = True
                            elif event.value < pre_scr_val:
                                if pre_scr_is_up[0]:
                                    self.density_hist.append(time.perf_counter())
                                self.scratch[1] = 1
                                pre_scr_is_up[0] = False
                        pre_scr_val = event.value
            #time.sleep(0.001)
            except Exception:
                logger.debug(traceback.format_exc())
                self.gui.window['state'].update(f'NG')
                self.gui.window['state'].update(text_color='#ff0000')
                break

        #joystick.quit()
        #pygame.quit()
        logger.debug('detect thread end')

    def change_device(self):
        """監視対象となるデバイスを変更する。外のコントローラがある場合はidxを1進める。
        """
        logger.debug('change device')
        cnt = pygame.joystick.get_count()
        if cnt > 0:
            self.settings.connected_idx = (self.settings.connected_idx + 1) % cnt
            self.joystick = pygame.joystick.Joystick(self.settings.connected_idx)
            self.gui.window['device1'].update(f'{self.settings.connected_idx}.{self.joystick.get_name()}')
            self.joystick.init()
            self.update_string('device1', f'{self.settings.connected_idx}.{self.joystick.get_name()}')
        else:
            logger.debug('error! device not found')

    def update_settings(self, settings):
        """設定画面の値を反映する。設定画面を閉じる時に実行する。

        Args:
            val (dict): sg.windowのevent
        """
        logger.debug(settings)
        if str(self.settings.ln_threshold) != settings['ln_threshold']:
            try:
                val = int(val['ln_threshold'])
                if val > 0:
                    self.settings.ln_threshold = val
            except Exception:
                pass
        if str(self.settings.size_release_hist) != settings['size_release_hist']:
            try:
                val = int(val['size_release_hist'])
                if val > 0:
                    self.settings.size_release_hist = val
            except Exception:
                pass
        self.settings.debug_mode = settings['debug_mode']
        if settings['playmode_iidx_sp']:
            self.settings.playmode = playmode.iidx_sp
        elif settings['playmode_sdvx']:
            self.settings.playmode = playmode.sdvx

    def main(self):
        """メイン関数兼GUI周りを扱うスレッド。
        """
        #pygame.init()
        self.stop_thread = False
        self.gui.gui_main(self.settings)
        self.th_detect = threading.Thread(target=self.thread_detect, daemon=True)
        self.th_detect.start()
        self.th_write = threading.Thread(target=self.thread_write, daemon=True)
        self.th_write.start()
        self.gui.window.write_event_value('check for updates on start', ' ')
        while True:
            self.settings.lx = self.gui.window.current_location()[0]
            self.settings.ly = self.gui.window.current_location()[1]
            self.settings.connected_idx = self.settings.connected_idx
            ev, val = self.gui.window.read()
            #print(ev)
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'exit'):
                self.stop_thread = True
                #self.th_detect.join()
                #self.th_write.join()
                self.settings.save()
                self.settings.disp()
                break
            elif ev == 'settings':
                settings = self.gui.gui_settings(self.settings)
                self.update_settings(settings)
            elif ev == 'btn_change':
                self.change_device()
            elif ev in ('check for updates', 'check for updates on start'):
                ver = self.get_latest_version()
                if (ver != SWVER) and (ver is not None):
                    logger.debug(f'現在のバージョン: {SWVER}, 最新版:{ver}')
                    ans = sg.popup_yes_no(f'アップデートが見つかりました。\n\n{SWVER} -> {ver}\n\nアプリを終了して更新します。', icon=self.ico)
                    if ans == "Yes":
                        #self.control_obs_sources('quit')
                        if os.path.exists('update.exe'):
                            logger.info('アップデート確認のため終了します')
                            res = subprocess.Popen('update.exe')
                            break
                        else:
                            sg.popup_error('update.exeがありません', icon=self.ico)
                else:
                    logger.debug(f'お使いのバージョンは最新です({SWVER})')
                    if ev == 'check for updates':
                        sg.popup_ok(f'Newest version is used({SWVER})', icon=self.ico)
        logger.debug('main thread end')

app = DispButtons()
app.main()