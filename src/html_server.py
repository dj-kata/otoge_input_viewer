from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class HtmlCatalogRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        # OBSのブラウザソースによる通常アクセスはアプリログへ出力しない。
        pass


class HtmlCatalogServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def create_html_server(html_dir: Path, port: int) -> HtmlCatalogServer:
    """OBSカタログ用HTMLをlocalhostだけに配信するHTTPサーバーを作る。"""
    handler = partial(HtmlCatalogRequestHandler, directory=str(html_dir.resolve()))
    return HtmlCatalogServer(("127.0.0.1", port), handler)
