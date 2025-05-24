# IIDXコントローラの入力状態を表示したりリリース速度を計算したりする
import pygame
import sys, time
import numpy as np
import PySimpleGUI as sg
from functools import partial
import os
import threading
import traceback
from settings import Settings
from enum import Enum

FONT = ('Meiryo', 12)
FONTs = ('Meiryo', 8)

par_text = partial(sg.Text, font=FONT)
sg.theme('SystemDefault')

class gui_mode(Enum):
    init = 0
    main = 1
    settings = 2

class DispButtons:
    def __init__(self):
        """コンストラクタ
        """
        self.gui_mode = gui_mode.init
        self.settings = Settings()
        self.window = None
        self.stop_thread = False # 強制停止用

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

    def gui_main(self):
        """メイン画面の準備
        """
        if self.window:
            self.window.close()
        menuitems = [
            ['File', ['settings', 'exit']],
        ]
        layout = [
            [sg.Menubar(menuitems, key='menu')],
            [par_text('state: ') ,par_text('', key='state')],
            [par_text('release: ') ,par_text('', key='release'), par_text('[ms]')],
            [par_text('density: ') ,par_text('', key='density'), par_text('[notes/s]')],
            [par_text('')],
            [par_text('state_btn: '), par_text('', key='state_btn')],
            [par_text('state_scr: '), par_text('', key='state_scr')],
            [par_text('device1:'), par_text('', key='device1'), sg.Button('change', key='btn_change')]
        ]
        self.window = sg.Window('Otoge input viewer for OBS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(self.settings.lx,self.settings.ly))
        self.gui_mode = gui_mode.main

    def gui_settings(self):
        """設定画面の準備
        """
        if self.window:
            self.window.close()
        layout = [
            [par_text('threshold for LN(default=225):',
                      tooltip='Set the time for determining long notes.\n何ms以上をCNとみなすかを設定。\ndefault=225'),
                      sg.Input(self.settings.ln_threshold,key='ln_threshold', size=(6,1))],
            [par_text('History size for release(default=100)',
                      tooltip='Set the number of notes for calculating release avg.\nリリース速度計算のために何ノーツを用いるか。\ndefault=100'),
             sg.Input(self.settings.size_release_hist,key='size_release_hist', size=(6,1))],
            [par_text('History size for density(default=100)',
                      tooltip='Set the number of notes for calculating chart density.\nノーツ密度計算のために何ノーツを用いるか。\ndefault=100'),
             sg.Input(self.settings.size_density_hist, key='size_density_hist', size=(6,1))],
        ]
        self.window = sg.Window('Settings - Otoge input viewer for OBS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(self.settings.lx,self.settings.ly))
        self.gui_mode = gui_mode.settings

    def write_state(self, state, scratch, release, density):
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
            f.write(f"    <release>{release:.2f}</release>\n")
            f.write(f"    <density>{density:.2f}</density>\n\n")
            for i in range(14):
                f.write(f'    <btn{i+1}>{state[i]}</btn{i+1}>\n')
            for i in range(4):
                f.write(f'    <scr{i+1}>{scratch[i]}</btn{i+1}>\n')
            f.write("</Items>\n")

    def detect(self):
        """コントローラ入力を監視するスレッド。
        """
        pygame.init()
        pygame.joystick.init()

        if self.gui_mode == gui_mode.main:
            self.window['state'].update(f'OK')
            self.window['state'].update(text_color='#0000ff')

        state = [0]*14
        scratch = [0]*4
        time_down = [-1]*14 # 押し始めた時刻を記録
        release_hist = []
        density_hist = []

        pre_scr_val = None
        release_avg = 0
        density = 0
        write_flag = False
        pre_scr_is_up = False

        print('detect thread started')

        # 起動時のコントローラ接続
        cnt = pygame.joystick.get_count()
        if cnt > 0:
            if self.settings.connected_idx == None:
                self.settings.connected_idx = 0
            self.settings.connected_idx = min(self.settings.connected_idx, cnt-1)
            self.settings.connected_idx = self.settings.connected_idx
            joystick = pygame.joystick.Joystick(self.settings.connected_idx)
            joystick.init()
            if self.gui_mode == gui_mode.main:
                self.window['state'].update(f'OK')
                self.window['state'].update(text_color='#0000ff')
                self.window['device1'].update(f'{self.settings.connected_idx}.{joystick.get_name()}')

        while True:
            if self.stop_thread:
                print('stop detect thread')
                break
            try:
                for event in pygame.event.get():
                    #print(event)
                    if (event.type == pygame.JOYDEVICEADDED):
                        tmp = pygame.joystick.Joystick(event.device_index)
                        print(event.device_index, tmp.get_name())
                    elif (event.type == pygame.JOYDEVICEREMOVED):
                        print(f'コントローラ{event.instance_id} 接続解除')
                    elif event.type == pygame.JOYBUTTONDOWN:
                        if event.joy == self.settings.connected_idx:
                            if event.button >= 14:
                                continue
                            #print('down', event.button)
                            state[event.button] = 1
                            time_down[event.button] = time.perf_counter()
                            write_flag = True
                    elif event.type == pygame.JOYBUTTONUP:
                        if event.joy == self.settings.connected_idx:
                            if event.button >= 14:
                                continue
                            write_flag = True
                            state[event.button] = 0
                            tmp_release = (time.perf_counter() - time_down[event.button])*1000
                            if tmp_release < self.settings.ln_threshold:
                                density_hist.append(time.perf_counter())
                                release_hist.append(tmp_release)
                                if len(release_hist) > self.settings.size_release_hist:
                                    release_hist.pop(0)
                                release_avg = sum(release_hist) / len(release_hist)
                                if self.gui_mode == gui_mode.main:
                                    self.window['release'].update(f'{release_avg:.1f}')
                                #print('up', event.button, f'{tmp_release:.2f}')

                    elif event.type == pygame.JOYAXISMOTION:
                        if pre_scr_val is not None:
                            if event.value > pre_scr_val:
                                if self.gui_mode == gui_mode.main:
                                    self.window['state_scr'].update('up')
                                if not pre_scr_is_up:
                                    write_flag = True
                                    density_hist.append(time.perf_counter())
                                pre_scr_is_up = True
                            elif event.value < pre_scr_val:
                                if self.gui_mode == gui_mode.main:
                                    self.window['state_scr'].update('down')
                                if pre_scr_is_up:
                                    write_flag = True
                                    density_hist.append(time.perf_counter())
                                pre_scr_is_up = False
                        pre_scr_val = event.value
                    if write_flag: # 値が変更された場合のみxml更新
                        if self.gui_mode == gui_mode.main:
                            self.window['state_btn'].update(str(state))
                        self.write_state(state, scratch, release_avg, density)
                        write_flag = False

                        # densityを計算
                        density_hist = density_hist[-self.settings.size_density_hist:]
                        if len(density_hist) == self.settings.size_density_hist:
                            dur = density_hist[-1] - density_hist[0]
                            density = 100 / dur
                            if self.gui_mode == gui_mode.main:
                                self.window['density'].update(f"{density:.1f}")
            #time.sleep(0.001)
            except Exception:
                print(traceback.format_exc())
                if self.gui_mode == gui_mode.main:
                    self.window['state'].update(f'NG')
                    self.window['state'].update(text_color='#ff0000')
                break

        #joystick.quit()
        #pygame.quit()
        print('detect thread end')

    def change_device(self):
        """監視対象となるデバイスを変更する。外のコントローラがある場合はidxを1進める。
        """
        print('change device')
        cnt = pygame.joystick.get_count()
        self.settings.connected_idx = (self.settings.connected_idx + 1) % cnt
        joystick = pygame.joystick.Joystick(self.settings.connected_idx)
        joystick.init()
        if self.gui_mode == gui_mode.main:
            self.window['device1'].update(f'{self.settings.connected_idx}.{joystick.get_name()}')

    def update_settings(self, val):
        """設定画面の値を反映する。設定画面を閉じる時に実行する。

        Args:
            val (dict): sg.windowのevent
        """
        if str(self.settings.ln_threshold) != val['ln_threshold']:
            try:
                self.settings.ln_threshold = int(val['ln_threshold'])
            except Exception:
                pass
        if str(self.settings.size_release_hist) != val['size_release_hist']:
            try:
                self.settings.size_release_hist = int(val['size_release_hist'])
            except Exception:
                pass
        if str(self.settings.size_density_hist) != val['size_density_hist']:
            try:
                self.settings.size_density_hist = int(val['size_density_hist'])
            except Exception:
                pass

    def main(self):
        """メイン関数
        """
        #pygame.init()
        self.stop_thread = False
        self.gui_main()
        self.th = threading.Thread(target=self.detect, daemon=True)
        self.th.start()
        while True:
            self.settings.lx = self.window.current_location()[0]
            self.settings.ly = self.window.current_location()[1]
            self.settings.connected_idx = self.settings.connected_idx
            ev, val = self.window.read()
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'exit'):
                print(f"exit! (mode = {self.gui_mode.name})")
                if self.gui_mode == gui_mode.settings:
                    self.update_settings(val)
                if self.gui_mode == gui_mode.main: # 終了
                    self.stop_thread = True
                    self.th.join()
                    del self.th
                    self.settings.save()
                    self.settings.disp()
                    break
                else:
                    self.gui_main()
            elif ev == 'settings':
                self.gui_settings()
            elif ev == 'btn_change':
                self.change_device()
        print('main thread end')

app = DispButtons()
app.main()