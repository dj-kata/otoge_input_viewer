from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, QUrl, QUrlQuery
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class HtmlView:
    filename: str
    title: str
    description: str
    width: int
    height: int

    @property
    def thumbnail_filename(self) -> str:
        return f"{Path(self.filename).stem}.png"


HTML_VIEWS = (
    HtmlView(
        "iidx_1p_color.html",
        "IIDX 1P（色分け）",
        "リリースタイムを色分けして表示",
        580,
        370,
    ),
    HtmlView(
        "iidx_2p_color.html",
        "IIDX 2P（色分け）",
        "リリースタイムを色分けして表示",
        580,
        370,
    ),
    HtmlView(
        "iidx_dp_color.html",
        "IIDX DP（色分け）",
        "リリースタイムを色分けして表示",
        1200,
        370,
    ),
    HtmlView(
        "sdvx_color.html",
        "SDVX（色分け）",
        "リリースタイムを色分けして表示",
        870,
        430,
    ),
    HtmlView("iidx_1p.html", "IIDX 1P", "IIDX 1P側の入力表示", 700, 400),
    HtmlView("iidx_2p.html", "IIDX 2P", "IIDX 2P側の入力表示", 700, 400),
    HtmlView("iidx_dp.html", "IIDX DP", "IIDX DPの入力表示", 1400, 400),
    HtmlView("sdvx.html", "SDVX", "SDVXの入力表示", 870, 430),
    HtmlView(
        "stats_only.html",
        "統計情報のみ",
        "リリース・密度・ノーツ数のみ表示",
        800,
        100,
    ),
    HtmlView(
        "scratch_speed.html",
        "皿速度グラフ",
        "スクラッチの入力間隔をグラフ表示",
        610,
        300,
    ),
)


def build_obs_source_url(view: HtmlView, server_port: int) -> QUrl:
    source_url = QUrl(f"http://127.0.0.1:{server_port}/{view.filename}")
    query = QUrlQuery()
    query.addQueryItem("layer-name", view.title)
    query.addQueryItem("layer-width", str(view.width))
    query.addQueryItem("layer-height", str(view.height))
    source_url.setQuery(query)
    return source_url


class HtmlDragLabel(QLabel):
    """HTMLファイルを外部アプリへドラッグするためのラベル。"""

    def __init__(self, source_url: QUrl, drag_pixmap: QPixmap, parent=None):
        super().__init__("ここをOBSへD&D", parent)
        self.source_url = source_url
        self.drag_pixmap = drag_pixmap
        self.drag_start_position = QPoint()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("この部分をOBSのプレビュー画面へドラッグしてください")
        self.setMinimumHeight(42)
        self.setStyleSheet(
            "QLabel {"
            "  border: 2px dashed #6aa9ff;"
            "  border-radius: 6px;"
            "  background: #17304f;"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  padding: 6px;"
            "}"
            "QLabel:hover { background: #214a78; }"
        )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if (
            event.position().toPoint() - self.drag_start_position
        ).manhattanLength() < QApplication.startDragDistance():
            return
        mime_data = QMimeData()
        mime_data.setUrls([self.source_url])

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        if not self.drag_pixmap.isNull():
            preview = self.drag_pixmap.scaled(
                QSize(240, 140),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            drag.setPixmap(preview)
            drag.setHotSpot(QPoint(preview.width() // 2, preview.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class HtmlViewCard(QFrame):
    def __init__(self, view: HtmlView, html_dir: Path, server_port: int, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame {"
            "  border: 1px solid #555;"
            "  border-radius: 8px;"
            "  background: #252525;"
            "}"
            "QLabel { border: none; background: transparent; color: #eeeeee; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        thumbnail_path = html_dir / "thumbnails" / view.thumbnail_filename
        pixmap = QPixmap(str(thumbnail_path))
        thumbnail = QLabel()
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setFixedSize(400, 220)
        thumbnail.setStyleSheet("background: #111; border-radius: 5px;")
        if pixmap.isNull():
            thumbnail.setText("プレビューなし")
        else:
            thumbnail.setPixmap(
                pixmap.scaled(
                    thumbnail.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(thumbnail)

        title = QLabel(view.title)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        description = QLabel(view.description)
        description.setStyleSheet("color: #cccccc;")
        layout.addWidget(description)

        size = QLabel(f"推奨サイズ: {view.width} × {view.height}")
        size.setStyleSheet("color: #a9cfff;")
        layout.addWidget(size)

        layout.addWidget(
            HtmlDragLabel(build_obs_source_url(view, server_port), pixmap, self)
        )


class HtmlCatalogWindow(QWidget):
    def __init__(self, html_dir: Path, server_port: int, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.server_port = server_port
        self.setWindowTitle("OBSに表示 - HTMLカタログ")
        self.resize(920, 720)
        self.setMinimumSize(500, 420)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        guide = QLabel(
            "使いたいビューの「ここをOBSへD&D」を、OBSのプレビュー画面へドラッグしてください。"
            "確認画面が表示された場合は「はい」を選んでください。"
        )
        guide.setWordWrap(True)
        guide.setStyleSheet("font-size: 14px; padding: 2px 4px 8px 4px;")
        outer_layout.addWidget(guide)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll_area)

        contents = QWidget()
        grid = QGridLayout(contents)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        for index, view in enumerate(HTML_VIEWS):
            grid.addWidget(
                HtmlViewCard(view, html_dir, server_port), index // 2, index % 2
            )
        scroll_area.setWidget(contents)
