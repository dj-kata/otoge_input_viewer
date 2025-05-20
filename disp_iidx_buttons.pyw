# IIDXコントローラの入力状態を表示したりリリース速度を計算したりする
import pygame
import sys, time
import numpy as np
import PySimpleGUI as sg
from functools import partial
import os
import threading

FONT = ('Meiryo', 12)
FONTs = ('Meiryo', 8)

par_text = partial(sg.Text, font=FONT)
sg.theme('SystemDefault')

class DispButtons:
    def __init__(self):
        self.LONG_THRESHOLD = 225
        self.SIZE_RELEASE_HIST = 100 # リリース計算用
        self.SIZE_DENSITY_HIST = 100 # density計算用
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

    def gui(self):
        layout = [
            [par_text('release: ') ,par_text('', key='release'), par_text('[ms]')],
            [par_text('density: ') ,par_text('', key='density'), par_text('[notes/s]')],
            [par_text('')],
            [par_text('state_btn: '), par_text('', key='state_btn')],
            [par_text('state_scr: '), par_text('', key='state_scr')],
        ]
        self.window = sg.Window('display iidx controller tool for OBS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(0,0))

    def write_state(self,state, release, density):
        with open('buttons.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Items>\n")
            f.write(f"    <release>{release:.2f}</release>\n")
            f.write(f"    <density>{density:.2f}</density>\n\n")
            for i in range(14):
                f.write(f'    <btn{i+1}>{state[i]}</btn{i+1}>\n')
            f.write("</Items>\n")

    def detect(self):
        pygame.init()
        pygame.joystick.init()

        joystick_cnt = pygame.joystick.get_count()
        if joystick_cnt == 0:
            print('コントローラが接続されていません')
            return False

        # コントローラ一覧を表示
        for i in range(joystick_cnt):
            tmp = pygame.joystick.Joystick(i)
            print(i, tmp.get_name())

        # TBD とりあえず1番目を使う
        joystick = pygame.joystick.Joystick(0)
        joystick.init()

        state = [0]*14
        time_down = [-1]*14 # 押し始めた時刻を記録
        release_hist = []
        density_hist = []

        pre_scr_val = None
        release_avg = 0
        density = 0
        write_flag = False
        pre_scr_is_up = False

        while True:
            if self.stop_thread:
                break
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    #print('down', event.button)
                    state[event.button] = 1
                    time_down[event.button] = time.perf_counter()
                    write_flag = True
                elif event.type == pygame.JOYBUTTONUP:
                    write_flag = True
                    state[event.button] = 0
                    tmp_release = (time.perf_counter() - time_down[event.button])*1000
                    if tmp_release < self.LONG_THRESHOLD:
                        density_hist.append(time.perf_counter())
                        release_hist.append(tmp_release)
                        if len(release_hist) > self.SIZE_RELEASE_HIST:
                            release_hist.pop(0)
                        release_avg = sum(release_hist) / len(release_hist)
                        self.window['release'].update(f'{release_avg:.1f}')
                        #print('up', event.button, f'{tmp_release:.2f}')

                elif event.type == pygame.JOYAXISMOTION:
                    if pre_scr_val is not None:
                        if event.value > pre_scr_val:
                            self.window['state_scr'].update('up')
                            if not pre_scr_is_up:
                                write_flag = True
                                density_hist.append(time.perf_counter())
                            pre_scr_is_up = True
                        elif event.value < pre_scr_val:
                            self.window['state_scr'].update('down')
                            if pre_scr_is_up:
                                write_flag = True
                                density_hist.append(time.perf_counter())
                            pre_scr_is_up = False
                    pre_scr_val = event.value
                if write_flag: # 値が変更された場合のみxml更新
                    self.window['state_btn'].update(str(state))
                    self.write_state(state, release_avg, density)
                    write_flag = False

                    # densityを計算
                    density_hist = density_hist[-self.SIZE_DENSITY_HIST:]
                    if len(density_hist) == self.SIZE_DENSITY_HIST:
                        dur = density_hist[-1] - density_hist[0]
                        density = 100 / dur
                        self.window['density'].update(f"{density:.1f}")
            #time.sleep(0.001)

        joystick.quit()
        pygame.quit()

    def main(self):
        self.gui()
        self.th = threading.Thread(target=self.detect, daemon=True)
        self.th.start()
        while True:
            ev, val = self.window.read()
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'exit'):
                self.stop_thread = True
                self.th.join()
                break

app = DispButtons()
app.main()