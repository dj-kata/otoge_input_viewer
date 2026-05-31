# 設定用クラス及び設定ダイアログをここに書く
import pickle, os
from enum import Enum
import ipaddress

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

savefile = 'oiv_conf.pkl'

class playmode(Enum):
    iidx_sp=0
    iidx_dp=1
    sdvx=2

    @classmethod
    def get_names(cls) -> list:
        return [i.name for i in cls]

class Settings:
    def __init__(self):
        self.lx = 50
        self.ly = 50
        self.ln_threshold = 225
        self.size_release_hist = 200
        self.size_release_key_hist = 30
        self.density_interval = 0.5
        self.port = 8765
        self.connected_idx = [None,None]
        self.debug_mode = False # コントローラ入力の全dumpなど
        self.auto_update = True # 自動アップデート
        self.playmode = playmode.iidx_sp
        #self.log_offset = '0'
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']

        self.load()
        self.save()
        self.write_websocket_settings()

    def disp(self):
        print(f"lx, ly = {self.lx}, {self.ly}")
        print(f"ln_threshold={self.ln_threshold}")
        print(f"port = {self.port}")
        print(f"size_release_hist={self.size_release_hist}")
        print(f"size_release_key_hist={self.size_release_key_hist}")
        print(f"density_interval={self.density_interval}")
        print(f"connected_idx={self.connected_idx}")
        print(f"playmode={self.playmode.name}")
        print(f"debug_mode={self.debug_mode}")
        print(f"auto_update={self.auto_update}")

    def load(self):
        try:
            with open(savefile, 'rb') as f:
                tmp = pickle.load(f)
                for k in tmp.__dict__.keys():
                    if k == 'connected_idx' and type(getattr(tmp, k)) is not list:
                        print(f'connected_idxをListに変更します')
                        setattr(self, k, [None, None])
                    else:
                        setattr(self, k, getattr(tmp, k))
        except Exception: # 読み込みエラー時はデフォルトで使う
            pass
        self.disp()

    def save(self):
        with open(savefile, 'wb') as f:
            pickle.dump(self, f)

    def write_websocket_settings(self):
        """websocketサーバのパラメータをcssファイルに出力
        """
        # 呼び出される時点で正しいパラメータが設定されている想定
        with open('html/websocket.css', 'w', encoding='utf-8') as f:
            f.write(':root {\n')
            f.write('    --port:'+str(self.port)+';\n')
            f.write('}')

class SettingsDialog(QDialog):
    def __init__(self, parent, settings:Settings):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.settings = settings
        self.result = None
        self.setModal(True)

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        layout = QVBoxLayout(self)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("playmode:"))
        self.playmode_group = QButtonGroup(self)
        for i in range(len(playmode.get_names())):
            radio = QRadioButton(playmode.get_names()[i])
            self.playmode_group.addButton(radio, i)
            mode_layout.addWidget(radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        form = QFormLayout()
        layout.addLayout(form)

        self.ln_threshold = QLineEdit()
        form.addRow("LongNotes判定しきい値(ms) (default=225):", self.ln_threshold)

        self.size_release_hist_entry = QLineEdit()
        form.addRow("リリース速度計算用ノーツ数 (default=200):", self.size_release_hist_entry)

        self.size_release_key_hist_entry = QLineEdit()
        form.addRow("単鍵リリース速度計算用ノーツ数 (default=30)", self.size_release_key_hist_entry)

        self.density_interval_entry = QLineEdit()
        form.addRow("譜面密度計算周期(s) (default=0.5)", self.density_interval_entry)

        self.port_entry = QLineEdit()
        self.port_entry.setToolTip('変更する場合、本設定ダイアログを閉じた後に\nOBS側でブラウザソースのプロパティから\n"現在のページのキャッシュを更新"をクリックしてください。')
        form.addRow("WebSocketポート: (default=8765)", self.port_entry)

        self.debug_mode_check = QCheckBox('debug_mode (default=off)')
        layout.addWidget(self.debug_mode_check)

        self.auto_update_check = QCheckBox('起動時にアプリを自動更新する (default=on)')
        layout.addWidget(self.auto_update_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_current_settings(self):
        self.ln_threshold.setText(str(self.settings.ln_threshold))
        self.size_release_hist_entry.setText(str(self.settings.size_release_hist))
        self.size_release_key_hist_entry.setText(str(self.settings.size_release_key_hist))
        self.density_interval_entry.setText(str(self.settings.density_interval))
        self.port_entry.setText(str(self.settings.port))
        self.debug_mode_check.setChecked(self.settings.debug_mode)
        self.auto_update_check.setChecked(self.settings.auto_update)
        button = self.playmode_group.button(self.settings.playmode.value)
        if button is not None:
            button.setChecked(True)

    def is_valid_ip(self, address):
        try:
            ipaddress.ip_address(address)
            return True
        except ValueError:
            return False

    def save(self):
        """設定値をファイルに保存
        """
        try:
            port = int(self.port_entry.text())
            ln_threshold = int(self.ln_threshold.text())
            size_release_hist = int(self.size_release_hist_entry.text())
            size_release_key_hist = int(self.size_release_key_hist_entry.text())
            density_interval = float(self.density_interval_entry.text())
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
            self.settings.debug_mode = self.debug_mode_check.isChecked()
            self.settings.auto_update = self.auto_update_check.isChecked()
            self.settings.playmode = playmode(self.playmode_group.checkedId())
            self.settings.save()
            self.settings.write_websocket_settings()
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "入力エラー", str(e))

if __name__ == '__main__':
    a = Settings()
    a.save()
    print(a.is_valid())
