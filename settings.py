import pickle, os
from enum import Enum
savefile = 'oiv_conf.pkl'

class playmode(Enum):
    iidx_sp=0
    iidx_dp=1
    sdvx=2

class Settings:
    def __init__(self):
        self.lx = 50
        self.ly = 50
        self.ln_threshold = 225
        self.size_release_hist = 20
        self.size_release_key_hist = 30
        self.density_interval = 0.5
        self.port = 8765
        self.connected_idx = None
        self.debug_mode = False # コントローラ入力の全dumpなど
        self.playmode = playmode.iidx_sp
        #self.log_offset = '0'
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']

        self.load()
        self.save()

    def disp(self):
        print(f"lx, ly = {self.lx}, {self.ly}")
        print(f"ln_threshold={self.ln_threshold}")
        print(f"size_release_hist={self.size_release_hist}")
        print(f"size_release_key_hist={self.size_release_key_hist}")
        print(f"density_interval={self.density_interval}")
        print(f"connected_idx={self.connected_idx}")
        print(f"playmode={self.playmode.name}")
        print(f"debug_mode={self.debug_mode}")

    def load(self):
        try:
            with open(savefile, 'rb') as f:
                tmp = pickle.load(f)
                for k in tmp.__dict__.keys():
                    setattr(self, k, getattr(tmp, k))
        except Exception: # 読み込みエラー時はデフォルトで使う
            pass

    def save(self):
        with open(savefile, 'wb') as f:
            pickle.dump(self, f)

if __name__ == '__main__':
    a = Settings()
    a.save()
    print(a.is_valid())