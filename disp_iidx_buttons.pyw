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

class DispButtons:
    def __init__(self):
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
            [par_text('release: ') ,par_text('', key='release')],
            [par_text('density: ') ,par_text('', key='density')],
            [par_text('')],
            [par_text('state_btn: '), par_text('', key='state_btn')],
            [par_text('state_scr: '), par_text('', key='state_scr')],
        ]
        self.window = sg.Window('iidx_disp', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(0,0))

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

        pre_val = 0
        release_avg = 0
        density = 0

        while True:
            if self.stop_thread:
                break
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    #print('down', event.button)
                    state[event.button] = 1
                    time_down[event.button] = time.perf_counter()
                elif event.type == pygame.JOYBUTTONUP:
                    state[event.button] = 0
                    tmp_release = (time.perf_counter() - time_down[event.button])*1000
                    if tmp_release < 225:
                        release_hist.append(tmp_release)
                        if len(release_hist) > 2000:
                            release_hist.pop(0)
                        release_avg = sum(release_hist) / len(release_hist)
                        #print('up', event.button, f'{tmp_release:.2f}')

                elif event.type == pygame.JOYAXISMOTION:
                    if event.value > pre_val:
                        print('scratch up')
                    else:
                        print('scratch down')
                    pre_val = event.value
                self.write_state(state, release_avg, density)
            time.sleep(0.001)

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