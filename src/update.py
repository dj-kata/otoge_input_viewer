#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import requests
import shutil
import subprocess
import threading
from pathlib import Path
from packaging import version

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

import logging, logging.handlers
import traceback
from bs4 import BeautifulSoup

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

class GitHubUpdater(QObject):
    status_update_requested = Signal(str, object)
    error_requested = Signal(str)
    cancel_requested = Signal()

    def __init__(
        self,
        github_author='',
        github_repo='',
        zipfile_basename=None,
        current_version='',
        main_exe_name=None,
        updator_exe_name=None,
    ):
        """
        GitHub自動アップデータの初期化
        
        Args:
            github_repo (str): GitHubリポジトリ名
            zipfile_basename (str): リリースzipのベース名
            current_version (str): 現在のバージョン（例: "1.0.0"）
            main_exe_name (str): メインプログラムのexe名（例: "main.exe"）
            updator_exe_name (str): 更新対象exe名。未指定時はメインexeと同じ。
        """
        super().__init__()
        self.github_author = github_author
        self.github_repo = github_repo
        self.zipfile_basename = zipfile_basename or github_repo
        self.current_version = current_version
        self.main_exe_name = main_exe_name or "main.exe"
        self.updator_exe_name = updator_exe_name or self.main_exe_name
        self.base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
        self.temp_dir = self.base_dir / "tmp"
        self.backup_dir = self.base_dir / "backup"
        logger.debug(f"base_dir:{self.base_dir}")
        
        # GUI関連
        self.root = None
        self.progress_var = None
        self.status_var = None
        self.progress_bar = None
        self.app = QApplication.instance()
        self.status_label = None
        self.status_update_requested.connect(self._apply_status)
        self.error_requested.connect(lambda message: QMessageBox.warning(self.root, "エラー", message))
        self.cancel_requested.connect(self.cancel_update)

    def get_latest_version(self):
        ret = None
        url = f'https://github.com/{self.github_author}/{self.github_repo}/tags'
        r = requests.get(url)
        soup = BeautifulSoup(r.text,features="html.parser")
        for tag in soup.find_all('a'):
            href = tag.get('href', '')
            if 'releases/tag/' in href:
                ret = href.split('/')[-1]
                break # 1番上が最新なので即break
        return ret

    def check_for_updates(self):
        """
        GitHubで最新版をチェック
        
        Returns:
            tuple: (is_update_available, latest_version, download_url)
        """
        logger.debug(f"github_repo:{self.github_author}/{self.github_repo}")
        try:
            latest_tag = self.get_latest_version()
            if latest_tag is None:
                return False, None, None

            latest_version = latest_tag.split("v.")[-1]
            current_version = str(self.current_version).split("v.")[-1]
            download_url = (
                f"https://github.com/{self.github_author}/{self.github_repo}"
                f"/releases/download/{latest_tag}/{self.zipfile_basename}.zip"
            )
            
            # バージョン比較
            if version.parse(latest_version) > version.parse(current_version):
                return True, latest_tag, download_url
            else:
                return False, latest_tag, None
                
        except Exception as e:
            print(f"アップデートチェックエラー: {e}")
            return False, None, None
    
    def create_gui(self):
        """アップデート用GUIの作成"""
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.root = QDialog()
        self.root.setWindowIcon(QIcon("src/icon.ico"))
        self.root.setWindowTitle("プログラム更新中...")
        self.root.setFixedSize(500, 200)

        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("プログラムを最新版に更新しています...")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)

        self.status_label = QLabel("更新確認中...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.cancel_update)
        layout.addWidget(cancel_button)

        self.root.show()
        
    def update_status(self, message, progress=None):
        """ステータス更新"""
        self.status_update_requested.emit(message, progress)

    def _apply_status(self, message, progress=None):
        if self.status_label:
            self.status_label.setText(message)
        if progress is not None and self.progress_bar:
            self.progress_bar.setValue(int(progress))
        if self.app:
            self.app.processEvents()
    
    def download_file(self, url, filepath):
        """
        ファイルをダウンロード（進行状況表示付き）
        
        Args:
            url (str): ダウンロードURL
            filepath (Path): 保存先パス
        """
        self.update_status("最新版をダウンロード中...", 0)
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded_size = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 50  # 50%まで
                        self.update_status(f"ダウンロード中... {downloaded_size // 1024}KB / {total_size // 1024}KB", 
                                         progress)
    
    def create_backup(self):
        """現在のファイルをバックアップ"""
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        self.backup_dir.mkdir()
        
        # 重要なファイルをバックアップ
        for item in self.base_dir.iterdir():
            if item.name not in ['temp_update', 'backup'] and item.is_file():
                shutil.copy2(item, self.backup_dir)
    
    def replace_files2(self):
        logger.debug(f'now moving..., repo:{self.github_repo}')
        p = self.temp_dir / self.zipfile_basename
        if not p.exists():
            dirs = [x for x in self.temp_dir.iterdir() if x.is_dir()]
            if len(dirs) == 1:
                p = dirs[0]
            else:
                p = self.temp_dir
        failed_list = []
        logger.debug('now moving...')
        for f in p.iterdir():
            logger.debug(f"f:{f}, is_dir:{f.is_dir()}")
            if f.is_dir():
                subdir = f.relative_to(p)
                logger.debug(f"mkdir {subdir}")
                (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)
        for f in p.glob('**/*.*'):
            try:
                base = f.relative_to(p)
                if base.name == self.updator_exe_name:
                    target = self.base_dir / f"new_{self.updator_exe_name}"
                    shutil.copy2(str(f), target)
                    logger.debug(f"from={str(f)}, to={target}")
                else:
                    target = self.base_dir / base
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), target)
                    logger.debug(f"from={str(f)}, to={target}")
            except Exception:
                if self.updator_exe_name not in str(f):
                    failed_list.append(f)
                logger.debug(f"error! ({f})")
                logger.debug(traceback.format_exc())
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        out = ''
        if len(failed_list) > 0:
            out = '更新に失敗したファイル(tmp/tmp.zipから手動展開してください): '
            out += '\n'.join(str(f) for f in failed_list)
            logger.warning(out)

    def create_restart_script(self, new_exe_path):
        logger.info('')
        """再起動用スクリプト作成"""
        if sys.platform.startswith('win'):
            script_path = self.base_dir / "restart_update.bat"
            script_content = f"""@echo off
timeout /t 2 /nobreak >nul
taskkill /f /im "{self.main_exe_name}" >nul 2>&1

:retry_move
timeout /t 1 /nobreak >nul
if exist "{new_exe_path}" (
    move /y "{new_exe_path}" "{self.base_dir / self.updator_exe_name}" >nul 2>&1
    if exist "{new_exe_path}" (
        echo 更新ファイルの差し替えを再試行中...
        goto retry_move
    )
)

start "" "{self.base_dir / self.main_exe_name}"
del "%~f0"
"""
            with open(script_path, 'w', encoding='shift_jis') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
        else:
            script_path = self.base_dir / "restart_update.sh"
            script_content = f"""#!/bin/sh
sleep 2
mv "{new_exe_path}" "{self.base_dir / self.updator_exe_name}"
"{self.base_dir / self.main_exe_name}" &
rm -- "$0"
"""
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
        
        logger.info(f"path:{script_path}")
        return script_path
    
    def cleanup(self):
        """一時ファイルの清掃"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"清掃エラー: {e}")
    
    def cancel_update(self):
        """アップデートキャンセル"""
        self.cleanup()
        if self.root:
            self.root.close()
        if self.app:
            self.app.quit()
        sys.exit(0)
    
    def extract_zip_file(self, zip_path):
        """zipファイルを解凍する。tmp直下にそのまま解凍する。

        Args:
            zip_path (str): path of zipfile
        """
        shutil.unpack_archive(zip_path, self.temp_dir)

    def check_and_update(self, show_no_update=False):
        """
        メインプログラムから呼び出す関数
        アップデートが必要な場合のみGUIを表示して更新実行
        
        Returns:
            bool: アップデートが実行された場合True
        """
        logger.info('check and update')
        try:
            # アップデート確認（GUIなし）
            is_update_available, latest_version, download_url = self.check_for_updates()
            logger.info(f"available:{is_update_available}, latest:{latest_version}, url:{download_url}")
            
            if is_update_available:
                # 確認ダイアログ
                result = QMessageBox.question(
                    self.root,
                    "アップデート確認",
                    f"新しいバージョン（{latest_version}）が利用可能です。\n"
                    f"現在のバージョン: {self.current_version}\n\n"
                    "今すぐ更新しますか？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                
                if result == QMessageBox.Yes:
                    self.create_gui()
                    self.cleanup()
                    
                    # 別スレッドで更新実行
                    def update_thread():
                        try:
                            # ダウンロード
                            zip_path = self.temp_dir / f"update_{latest_version}.zip"
                            logger.info(f'zip_path: {zip_path}')
                            self.temp_dir.mkdir(exist_ok=True)
                            
                            logger.info('download')
                            self.download_file(download_url, zip_path)
                            self.extract_zip_file(zip_path)
                            logger.info('replace')
                            self.replace_files2()
                            
                            new_exe_path = self.base_dir / f"new_{self.updator_exe_name}"
                            # 更新完了後にメインプログラムを再起動するためのバッチファイルを作成
                            self.create_restart_script(new_exe_path)

                            self.update_status("更新完了！プログラムを再起動します...", 100)
                            #self.root.after(2000, self.restart_program)
                            self.restart_program()
                            
                        except Exception as e:
                            logger.error(traceback.format_exc())
                            error_msg = f"更新エラー: {e}"
                            self.error_requested.emit(error_msg)
                            self.cancel_requested.emit()
                    
                    thread = threading.Thread(target=update_thread, daemon=True)
                    thread.start()
                    
                    if self.app and self._qt_event_loop_level() == 0:
                        self.app.exec()
                    return True
            else:
                logger.info('no update')
                if show_no_update:
                    QMessageBox.information(
                        self.root,
                        "Otoge Input Viewer",
                        f"お使いのバージョンは最新です({self.current_version})",
                    )
                if self.root:
                    self.root.close()
            return False
            
        except Exception as e:
            logger.debug(traceback.format_exc())
            print(f"アップデート確認エラー: {e}")
            return False

    def _qt_event_loop_level(self):
        if not self.app:
            return 0
        try:
            return self.app.thread().loopLevel()
        except AttributeError:
            return 0
    
    def restart_program(self):
        """プログラム再起動"""
        logger.info('retart program')
        script_path = self.base_dir / ("restart_update.bat" if sys.platform.startswith('win') 
                                     else "restart_update.sh")
        if script_path.exists():
            if sys.platform.startswith('win'):
                subprocess.Popen([str(script_path)], shell=True)
            else:
                subprocess.Popen(['/bin/bash', str(script_path)])
            
            if self.root:
                self.root.close()
            sys.exit(0)
