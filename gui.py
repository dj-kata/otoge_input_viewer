import PySimpleGUI as sg
from functools import partial
import os
import sys

FONT = ('Meiryo',12)
FONTs = ('Meiryo',8)
par_text = partial(sg.Text, font=FONT)

class GUI:
    def __init__(self):
        self.window = None
        self.obs = None
        self.ico=self.ico_path('icon.ico')

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

    def gui_main(self, settings):
        """メイン画面の準備
        """
        menuitems = [
            ['File', ['settings', 'check for updates', 'exit']],
        ]
        layout = [
            [sg.Menubar(menuitems, key='menu')],
            [par_text('release: ') ,par_text('', key='release'), par_text('[ms]')],
            [par_text('density: ') ,par_text('', key='density'), par_text('[notes/s]')],
            [par_text('')],
            [par_text('state_btn: '), par_text('', key='state_btn')],
            [par_text('state_scr: '), par_text('', key='state_scr')],
            [par_text('device1:'), par_text('', key='device1'), sg.Button('change', key='btn_change')]
        ]
        self.window = sg.Window('Otoge input viewer for OBS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(settings.lx,settings.ly))

    def gui_settings(self, settings):
        """設定画面の準備
        """
        # mainスレッド以外への遷移はすぐにやっておく
        layout = [
            [par_text('threshold for LN(default=225):',
                      tooltip='Set the time for determining long notes.\n何ms以上をCNとみなすかを設定。\ndefault=225'),
                      sg.Input(settings.ln_threshold,key='ln_threshold', size=(6,1))],
            [par_text('History size for release(default=100)',
                      tooltip='Set the number of notes for calculating release avg.\nリリース速度計算のために何ノーツを用いるか。\ndefault=100'),
             sg.Input(settings.size_release_hist,key='size_release_hist', size=(6,1))],
        ]
        # modal=Trueによって元のウィンドウを操作できなくする
        self.window_settings = sg.Window('Settings - Otoge input viewer for OBS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico_path('icon.ico'),location=(settings.lx,settings.ly), modal=True)
        while True:
            ev, val = self.window_settings.read()
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'exit'):
                self.window_settings.close()
                return val
