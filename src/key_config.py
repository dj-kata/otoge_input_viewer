import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


MODE_LABELS = {
    "iidx_sp": "IIDX SP",
    "iidx_dp": "IIDX DP",
    "sdvx": "SDVX",
}


def target_definitions(mode_name):
    if mode_name == "iidx_sp":
        return [
            {"id": "scr", "label": "SCR", "kind": "axis", "axis": 0, "controller_side": 0, "row": 0, "col": 0},
            {"id": "k2", "label": "2", "kind": "button", "button": 1, "controller_side": 0, "row": 0, "col": 2},
            {"id": "k4", "label": "4", "kind": "button", "button": 3, "controller_side": 0, "row": 0, "col": 3},
            {"id": "k6", "label": "6", "kind": "button", "button": 5, "controller_side": 0, "row": 0, "col": 4},
            {"id": "k1", "label": "1", "kind": "button", "button": 0, "controller_side": 0, "row": 1, "col": 1},
            {"id": "k3", "label": "3", "kind": "button", "button": 2, "controller_side": 0, "row": 1, "col": 2},
            {"id": "k5", "label": "5", "kind": "button", "button": 4, "controller_side": 0, "row": 1, "col": 3},
            {"id": "k7", "label": "7", "kind": "button", "button": 6, "controller_side": 0, "row": 1, "col": 4},
        ]
    if mode_name == "iidx_dp":
        defs = []
        for side, offset, side_label in ((0, 0, "1P"), (1, 6, "2P")):
            defs.extend([
                {"id": f"p{side+1}_scr", "label": f"{side_label} SCR", "kind": "axis", "axis": 0, "controller_side": side, "row": 0, "col": offset},
                {"id": f"p{side+1}_k2", "label": f"{side_label} 2", "kind": "button", "button": 1, "controller_side": side, "row": 0, "col": offset + 2},
                {"id": f"p{side+1}_k4", "label": f"{side_label} 4", "kind": "button", "button": 3, "controller_side": side, "row": 0, "col": offset + 3},
                {"id": f"p{side+1}_k6", "label": f"{side_label} 6", "kind": "button", "button": 5, "controller_side": side, "row": 0, "col": offset + 4},
                {"id": f"p{side+1}_k1", "label": f"{side_label} 1", "kind": "button", "button": 0, "controller_side": side, "row": 1, "col": offset + 1},
                {"id": f"p{side+1}_k3", "label": f"{side_label} 3", "kind": "button", "button": 2, "controller_side": side, "row": 1, "col": offset + 2},
                {"id": f"p{side+1}_k5", "label": f"{side_label} 5", "kind": "button", "button": 4, "controller_side": side, "row": 1, "col": offset + 3},
                {"id": f"p{side+1}_k7", "label": f"{side_label} 7", "kind": "button", "button": 6, "controller_side": side, "row": 1, "col": offset + 4},
            ])
        return defs
    if mode_name == "sdvx":
        return [
            {"id": "vol_l", "label": "VOL-L", "kind": "axis", "axis": 0, "controller_side": 0, "row": 0, "col": 0},
            {"id": "vol_r", "label": "VOL-R", "kind": "axis", "axis": 1, "controller_side": 0, "row": 0, "col": 5},
            {"id": "bt_a", "label": "BT-A", "kind": "button", "button": 1, "controller_side": 0, "row": 1, "col": 1},
            {"id": "bt_b", "label": "BT-B", "kind": "button", "button": 2, "controller_side": 0, "row": 1, "col": 2},
            {"id": "bt_c", "label": "BT-C", "kind": "button", "button": 3, "controller_side": 0, "row": 1, "col": 3},
            {"id": "bt_d", "label": "BT-D", "kind": "button", "button": 4, "controller_side": 0, "row": 1, "col": 4},
            {"id": "fx_l", "label": "FX-L", "kind": "button", "button": 5, "controller_side": 0, "row": 2, "col": 2},
            {"id": "fx_r", "label": "FX-R", "kind": "button", "button": 6, "controller_side": 0, "row": 2, "col": 3},
        ]
    return []


def empty_key_config():
    return {mode_name: {} for mode_name in MODE_LABELS}


def event_to_spec(event, joystick_name="", event_type_name=None):
    if not hasattr(event, "joy"):
        return None
    if event_type_name == "button":
        return {
            "controller_name": joystick_name,
            "controller_id": event.joy,
            "event_type": "button",
            "control_id": event.button,
        }
    if event_type_name == "axis":
        return {
            "controller_name": joystick_name,
            "controller_id": event.joy,
            "event_type": "axis",
            "control_id": event.axis,
        }
    return None


def spec_key(spec):
    return (
        spec.get("controller_name", ""),
        spec.get("controller_id"),
        spec.get("event_type"),
        spec.get("control_id"),
    )


def format_spec(spec):
    if not spec:
        return ""
    event_label = "button" if spec.get("event_type") == "button" else "axis"
    return f"{spec.get('controller_name', '')} / ID:{spec.get('controller_id')} / {event_label}:{spec.get('control_id')}"


def target_to_event_data(target, state=None, direction=None, value_org=0.0):
    if target["kind"] == "button":
        return {
            "type": "button",
            "button": target["button"],
            "state": state,
            "controller_side": target["controller_side"],
        }
    return {
        "type": "axis",
        "axis": target["axis"],
        "direction": direction,
        "pos": target["axis"] * 2 + direction,
        "value": 1,
        "controller_side": target["controller_side"],
        "value_org": value_org,
    }


class CaptureLineEdit(QLineEdit):
    def __init__(self, target_id, parent):
        super().__init__(parent)
        self.target_id = target_id
        self.dialog = parent
        self.setReadOnly(True)
        self.setPlaceholderText("クリックして入力")

    def mousePressEvent(self, event):
        self.dialog.start_capture(self.target_id)
        super().mousePressEvent(event)


class KeyConfigDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("キーイベント登録")
        self.setModal(True)
        self.settings = settings
        self.key_config = copy.deepcopy(getattr(settings, "key_config", {}) or {})
        for mode_name in MODE_LABELS:
            self.key_config.setdefault(mode_name, {})
        self.capture_target_id = None
        self.inputs = {}
        self.mode_combo = None
        self.grid_container = None
        self.status_label = None
        self.parent().key_config_event_received.connect(self.receive_event)
        self.create_widgets()
        self.rebuild_grid()

    def create_widgets(self):
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("モード:"))
        self.mode_combo = QComboBox(self)
        for mode_name, label in MODE_LABELS.items():
            self.mode_combo.addItem(label, mode_name)
        cur_index = self.mode_combo.findData(self.settings.playmode.name)
        if cur_index >= 0:
            self.mode_combo.setCurrentIndex(cur_index)
        self.mode_combo.currentIndexChanged.connect(self.rebuild_grid)
        top.addWidget(self.mode_combo)
        top.addStretch()
        layout.addLayout(top)

        self.status_label = QLabel("入力欄をクリックして、割り当てたいコントローラ入力を押してください。Escでキャンセル。")
        layout.addWidget(self.status_label)

        self.grid_container = QWidget(self)
        layout.addWidget(self.grid_container)

        buttons_row = QHBoxLayout()
        clear_button = QPushButton("表示中モードをクリア", self)
        clear_button.clicked.connect(self.clear_current_mode)
        buttons_row.addWidget(clear_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def current_mode_name(self):
        return self.mode_combo.currentData()

    def rebuild_grid(self):
        old_layout = self.grid_container.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            old_layout.deleteLater()

        grid = QGridLayout(self.grid_container)
        grid.setSpacing(8)
        self.inputs = {}
        mode_name = self.current_mode_name()
        for target in target_definitions(mode_name):
            cell = QWidget(self.grid_container)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(target["label"])
            label.setAlignment(Qt.AlignCenter)
            entry = CaptureLineEdit(target["id"], self)
            entry.setMinimumWidth(150)
            entry.setText(format_spec(self.key_config[mode_name].get(target["id"])))
            cell_layout.addWidget(label)
            cell_layout.addWidget(entry)
            self.inputs[target["id"]] = entry
            grid.addWidget(cell, target["row"], target["col"])
        self.capture_target_id = None

    def start_capture(self, target_id):
        self.capture_target_id = target_id
        for item_id, entry in self.inputs.items():
            entry.setStyleSheet("background: #fff3bf;" if item_id == target_id else "")
        self.status_label.setText("入力待ちです。コントローラを操作してください。Escでキャンセル。")

    def receive_event(self, spec):
        if self.capture_target_id is None:
            return
        mode_name = self.current_mode_name()
        self.key_config[mode_name][self.capture_target_id] = spec
        self.inputs[self.capture_target_id].setText(format_spec(spec))
        self.cancel_capture("登録しました。")

    def cancel_capture(self, message="キャンセルしました。"):
        self.capture_target_id = None
        for entry in self.inputs.values():
            entry.setStyleSheet("")
        self.status_label.setText(message)

    def clear_current_mode(self):
        mode_name = self.current_mode_name()
        self.key_config[mode_name] = {}
        for entry in self.inputs.values():
            entry.clear()
        self.cancel_capture("表示中モードの割当をクリアしました。")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.capture_target_id is not None:
            self.cancel_capture()
            return
        super().keyPressEvent(event)

    def save(self):
        self.settings.key_config = self.key_config
        self.settings.save()
        QMessageBox.information(self, "キーイベント登録", "キーイベント設定を保存しました。")
        self.accept()

    def closeEvent(self, event):
        try:
            self.parent().key_config_event_received.disconnect(self.receive_event)
        except RuntimeError:
            pass
        super().closeEvent(event)
