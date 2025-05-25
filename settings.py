import pickle, os

savefile = 'oiv_conf.pkl'

class Settings:
    def __init__(self):
        self.lx = 0
        self.ly = 0
        self.ln_threshold = 225
        self.size_release_hist = 100
        self.time_window_density = 5
        self.connected_idx = None
        self.tweet_on_exit = False
        self.save_on_capture = True
        #self.log_offset = '0'
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']

        self.load()
        self.save()

    def disp(self):
        print(f"lx={self.lx}")
        print(f"ly={self.ly}")
        print(f"ln_threshold={self.ln_threshold}")
        print(f"size_release_hist={self.size_release_hist}")
        print(f"time_window_density={self.time_window_density}")
        print(f"connected_idx={self.connected_idx}")

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