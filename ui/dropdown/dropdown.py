"""Dropdown — วิดเจ็ต dropdown แบบลอย (popup) ใต้ trigger (PyQt6).

เมนูจะลอยทับ content อื่น ไม่ขยับ layout.
- เปิดได้ 1 อันเท่านั้น (เปิดอันใหม่ = ปิดอันเก่า)
- Popup ตามหน้าต่างเมื่อเลื่อน/ขยาย

ใช้งาน:
    dd = Dropdown(parent, items=[
        ('gold', 'Farm Gold'),
        ('exp', 'Farm EXP'),
        '---',
        ('box', 'Farm Box', None, 'No jump mode'),
    ])
    dd.set_current('gold')
    dd.current_key()   # -> 'gold'
    dd.current_text()  # -> 'Farm Gold'
"""
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

# track ONE active popup
_active_popup = None
_active_dropdown = None


class _MenuItem(QFrame):
    """แถวรายการในเมนู dropdown."""

    clicked = pyqtSignal(str)

    HEIGHT = 30

    def __init__(self, parent, key, label, icon=None, selected=False):
        super().__init__(parent)
        self.key = key
        self._selected = selected
        self._hovered = False

        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 0, 10, 0)
        root.setSpacing(6)

        if icon:
            self._icon = QLabel(icon, self)
            self._icon.setFixedWidth(16)
            self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(self._icon)
        else:
            self._icon = None

        self._label = QLabel(label, self)
        root.addWidget(self._label, 1)

        self._check = QLabel('\u2713' if selected else '', self)
        self._check.setFixedWidth(16)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._check)

        self._apply_style()

    def _apply_style(self):
        from ui import theme
        if self.key is None:
            bg, fg, fg_icon, fg_chk = (
                theme.BG_INPUT, theme.FG_MUTED, theme.FG_MUTED, theme.FG_MUTED)
        elif self._hovered:
            bg, fg, fg_icon, fg_chk = (
                theme.BG_INPUT_FOCUS, theme.FG, theme.ACCENT_GLOW, theme.ACCENT_GLOW)
        elif self._selected:
            bg, fg, fg_icon, fg_chk = (
                theme.ACCENT_SOFT, theme.ACCENT_GLOW, theme.ACCENT_GLOW, theme.ACCENT_GLOW)
        else:
            bg, fg, fg_icon, fg_chk = (
                'transparent', theme.FG, theme.FG_DIM, theme.FG_DIM)

        self.setStyleSheet(
            'QFrame { background: %s; border: none; }' % bg)
        self._label.setStyleSheet(
            'color: %s; background: transparent;' % fg)
        self._label.setFont(theme.qfont(*theme.SMALL_FONT))
        self._check.setStyleSheet(
            'color: %s; background: transparent;' % fg_chk)
        self._check.setFont(theme.qfont(*theme.SMALL_FONT))
        if self._icon:
            self._icon.setStyleSheet(
                'color: %s; background: transparent;' % fg_icon)
            self._icon.setFont(theme.qfont(*theme.SMALL_FONT))

    def set_selected(self, val):
        self._selected = val
        self._check.setText('\u2713' if val else '')
        self._apply_style()

    def enterEvent(self, event):
        if self.key is not None:
            self._hovered = True
            self._apply_style()

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.key is not None:
            self.clicked.emit(self.key)


class _DropdownPopup(QFrame):
    """เมนู popup ลอยใต้ trigger."""

    item_selected = pyqtSignal(str)

    def __init__(self, trigger, items, current_key, searchable, max_visible):
        super().__init__(None)
        self._trigger = trigger
        self._items = items
        self._current_key = current_key
        self._searchable = searchable
        self._max_visible = max_visible
        self._menu_widgets = []
        self._pressed_inside = False

        # ทำให้ popup เป็น child widget ของ central widget (ไม่ลอยนอกหน้าต่าง)
        main_win = trigger.window()
        if main_win:
            central = main_win.centralWidget()
            if central:
                self.setParent(central)
            else:
                self.setParent(main_win)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName('dropdownPopup')
        self.setStyleSheet(
            'QFrame#dropdownPopup {'
            ' background: %s;'
            ' border: 1px solid %s;'
            ' border-radius: 0 0 8px 8px;'
            ' border-top: 1px solid %s;'
            ' }' % ('#262935', '#2E3140', '#2E3140'))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if searchable:
            self._build_search(root)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName('dropdownScroll')
        self._scroll.setStyleSheet(
            'QScrollArea { background: transparent; border: none; }')
        root.addWidget(self._scroll, 1)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet('background: transparent;')
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_widget)

        self._render_items()
        self._position()

        # ติดตั้ง event filter บน parent เพื่อปิด popup เมื่อคลิกนอก popup
        parent = self.parentWidget()
        if parent is not None:
            parent.installEventFilter(self)

        # Timer สำหรับ update ตำแหน่งตามหน้าต่าง
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(16)  # ~60fps
        self._follow_timer.timeout.connect(self._position)
        self._follow_timer.start()

    def _build_search(self, parent_layout):
        from ui import theme
        box = QFrame(self)
        box.setStyleSheet('background: transparent; border: none;')
        sh = QHBoxLayout(box)
        sh.setContentsMargins(8, 4, 8, 4)
        sh.setSpacing(4)
        icon = QLabel('\u2315', box)
        icon.setStyleSheet('color: %s; background: transparent;' % theme.FG_MUTED)
        icon.setFont(theme.qfont(*theme.SMALL_FONT))
        sh.addWidget(icon)
        self._search = QLineEdit(box)
        self._search.setPlaceholderText('Search...')
        self._search.setFont(theme.qfont(*theme.SMALL_FONT))
        self._search.textChanged.connect(self._on_filter)
        self._search.setStyleSheet(
            'QLineEdit { background: %s; color: %s; border: 1px solid %s;'
            ' border-radius: 4px; padding: 3px 6px; }'
            % (theme.BG_INPUT, theme.FG, theme.BORDER))
        sh.addWidget(self._search, 1)
        parent_layout.addWidget(box)

    def _render_items(self):
        for w in self._menu_widgets:
            w.deleteLater()
        self._menu_widgets.clear()

        filter_text = ''
        if self._searchable and hasattr(self, '_search'):
            filter_text = self._search.text().lower()

        for item_data in self._items:
            key = self._extract_key(item_data)
            label = self._extract_label(item_data)

            if key is None and label == '':
                sep = QFrame(self._list_widget)
                sep.setFixedHeight(4)
                sep.setStyleSheet('background: transparent; border: none;')
                self._list_layout.insertWidget(
                    self._list_layout.count() - 1, sep)
                self._menu_widgets.append(sep)
                continue

            if filter_text and filter_text not in label.lower():
                continue

            icon = None
            if isinstance(item_data, (list, tuple)) and len(item_data) > 2:
                icon = item_data[2]

            item = _MenuItem(
                self._list_widget, key, label, icon=icon,
                selected=(key == self._current_key))
            item.clicked.connect(self._on_item_clicked)
            self._list_layout.insertWidget(
                self._list_layout.count() - 1, item)
            self._menu_widgets.append(item)

        self._update_height()

    def _update_height(self):
        visible = [w for w in self._menu_widgets
                   if isinstance(w, _MenuItem)]
        n = min(len(visible), self._max_visible)
        h = n * _MenuItem.HEIGHT + 2
        if self._searchable:
            h += 34
        self.setFixedHeight(h)

    def _on_item_clicked(self, key):
        self.item_selected.emit(key)
        QTimer.singleShot(0, self._close_from_filter)

    def _on_filter(self, text):
        self._render_items()

    def _position(self):
        dropdown = self._trigger
        frame = dropdown._trigger
        self.setFixedWidth(frame.width())

        # แปลงเป็นพิกัด relative กับ parent (central widget)
        parent = self.parentWidget()
        if parent is None:
            return

        # แปลง global pos ของ trigger ไปเป็น local pos ของ parent
        global_pos = frame.mapToGlobal(QPoint(0, frame.height()))
        local_pos = parent.mapFromGlobal(global_pos)

        x = local_pos.x()
        y = local_pos.y()
        pw = self.width()
        ph = self.height()
        parent_w = parent.width()
        parent_h = parent.height()

        # ซ้าย
        if x < 0:
            x = 0
        # ขวา
        if x + pw > parent_w:
            x = parent_w - pw
        # ล่าง (ถ้าเกิน ให้เปิดขึ้นด้านบนแทน)
        if y + ph > parent_h:
            global_top = frame.mapToGlobal(QPoint(0, 0))
            local_top = parent.mapFromGlobal(global_top)
            y = local_top.y() - ph
        # บน
        if y < 0:
            y = 0

        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        if self._searchable and hasattr(self, '_search'):
            self._search.setFocus()

    def closeEvent(self, event):
        global _active_popup, _active_dropdown
        if hasattr(self, '_follow_timer'):
            self._follow_timer.stop()
        if _active_popup is self:
            _active_popup = None
            _active_dropdown = None
        super().closeEvent(event)

    def mousePressEvent(self, event):
        self._pressed_inside = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._pressed_inside:
            QTimer.singleShot(0, self._close_from_filter)
        self._pressed_inside = False
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        # ปิด popup เมื่อคลิกบน parent (นอก popup)
        if obj is self.parentWidget() and event.type() == event.Type.MouseButtonPress:
            pos = event.position().toPoint()
            global_pos = obj.mapToGlobal(pos)
            popup_global = self.mapToGlobal(QPoint(0, 0))
            popup_rect = self.rect()
            px, py = popup_global.x(), popup_global.y()
            pw, ph = popup_rect.width(), popup_rect.height()
            gx, gy = global_pos.x(), global_pos.y()
            if not (px <= gx <= px + pw and py <= gy <= py + ph):
                # ปิด popup หลังจบ event เพื่อป้องกัน crash
                QTimer.singleShot(0, self._close_from_filter)
        return super().eventFilter(obj, event)

    def _close_from_filter(self):
        try:
            if not self.isVisible():
                return
        except RuntimeError:
            return
        if _active_dropdown is not None:
            _active_dropdown._close_popup()
        else:
            self.close()
            self.deleteLater()

    def _extract_key(self, item_data):
        if isinstance(item_data, str):
            return item_data if item_data != '---' else None
        if isinstance(item_data, (list, tuple)):
            return item_data[0] if item_data else None
        return str(item_data)

    def _extract_label(self, item_data):
        if isinstance(item_data, str):
            return item_data if item_data != '---' else ''
        if isinstance(item_data, (list, tuple)):
            return item_data[1] if len(item_data) > 1 else str(item_data[0])
        return str(item_data)


class Dropdown(QWidget):
    """วิดเจ็ต dropdown — trigger ด้านบน + เมนูลอยใต้ trigger.

    - เปิดได้ 1 อันเท่านั้น (เปิดอันใหม่ = ปิดอันเก่า)
    - Popup ตามหน้าต่างเมื่อเลื่อน/ขยาย

    Signals:
        current_changed(str)  —  emits key เมื่อเลือกใหม่
    """

    current_changed = pyqtSignal(str)

    def __init__(self, parent, items=None, placeholder='Select...',
                 searchable=False, max_visible=6):
        super().__init__(parent)
        self._items = items or []
        self._placeholder = placeholder
        self._searchable = searchable
        self._max_visible = max_visible
        self._current_key = None
        self._current_label = ''
        self._popup = None

        self.setObjectName('dropdownWrap')
        self.setFixedHeight(30)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._trigger = QFrame(self)
        self._trigger.setObjectName('dropdownTrigger')
        self._trigger.setCursor(Qt.CursorShape.PointingHandCursor)

        th = QHBoxLayout(self._trigger)
        th.setContentsMargins(10, 0, 10, 0)
        th.setSpacing(6)

        self._label = QLabel(placeholder, self._trigger)
        th.addWidget(self._label, 1)

        self._arrow = QLabel('\u203A', self._trigger)
        self._arrow.setFixedWidth(14)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        th.addWidget(self._arrow)

        root.addWidget(self._trigger)

        self._apply_style()

    # ── Public API ────────────────────────────────────────

    def items(self):
        return list(self._items)

    def set_items(self, items):
        self._items = items
        self._current_key = None
        self._current_label = ''
        self._label.setText(self._placeholder)
        self._close_popup()

    def add_item(self, item):
        self._items.append(item)

    def add_items(self, items):
        self._items.extend(items)

    def clear(self):
        self._items.clear()
        self._current_key = None
        self._current_label = ''
        self._label.setText(self._placeholder)
        self._close_popup()

    def current_key(self):
        return self._current_key

    def current_text(self):
        return self._current_label

    def set_current(self, key):
        for item_data in self._items:
            k = self._extract_key(item_data)
            if k == key:
                self._current_key = key
                self._current_label = self._extract_label(item_data)
                self._label.setText(self._current_label)
                self._apply_style()
                return

    def set_current_by_text(self, text):
        for item_data in self._items:
            label = self._extract_label(item_data)
            if label == text:
                self._current_key = self._extract_key(item_data)
                self._current_label = text
                self._label.setText(text)
                self._apply_style()
                return

    def find_text(self, text):
        for item_data in self._items:
            if self._extract_label(item_data) == text:
                return self._extract_key(item_data)
        return None

    def count(self):
        return len(self._items)

    def item_data(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def is_open(self):
        return self._popup is not None and self._popup.isVisible()

    # ── Internal ──────────────────────────────────────────

    def _extract_key(self, item_data):
        if isinstance(item_data, str):
            return item_data if item_data != '---' else None
        if isinstance(item_data, (list, tuple)):
            return item_data[0] if item_data else None
        return str(item_data)

    def _extract_label(self, item_data):
        if isinstance(item_data, str):
            return item_data if item_data != '---' else ''
        if isinstance(item_data, (list, tuple)):
            return item_data[1] if len(item_data) > 1 else str(item_data[0])
        return str(item_data)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                local = self._trigger.mapFromParent(event.position().toPoint())
                if self._trigger.rect().contains(local):
                    self._toggle_popup()
                    event.accept()
                    return
            except RuntimeError:
                pass
        super().mousePressEvent(event)

    def _toggle_popup(self):
        global _active_popup, _active_dropdown
        if self._popup and self._popup.isVisible():
            self._close_popup()
        else:
            # close other dropdown first
            if _active_dropdown is not None and _active_dropdown is not self:
                _active_dropdown._close_popup()
            self._open_popup()

    def _open_popup(self):
        global _active_popup, _active_dropdown
        from ui import theme
        self._popup = _DropdownPopup(
            self, self._items, self._current_key,
            self._searchable, self._max_visible)
        self._popup.item_selected.connect(self._on_item_selected)
        self._popup.show()
        _active_popup = self._popup
        _active_dropdown = self
        self._trigger.setStyleSheet(
            'QFrame#dropdownTrigger {'
            ' background: %s; border: 1px solid %s;'
            ' border-radius: 8px 8px 0 0; }'
            % (theme.BG_INPUT, theme.ACCENT))
        self._arrow.setStyleSheet(
            'color: %s; background: transparent;' % theme.ACCENT_GLOW)

    def _close_popup(self):
        if self._popup:
            popup = self._popup
            self._popup = None
            popup.close()
            popup.deleteLater()
        self._apply_style()

    def _on_item_selected(self, key):
        self.set_current(key)
        self._close_popup()
        self.current_changed.emit(key)

    def _apply_style(self):
        from ui import theme
        has = self._current_key is not None
        self.setStyleSheet(
            'QFrame#dropdownTrigger {'
            ' background: %s; border: 1px solid %s;'
            ' border-radius: 8px; }'
            % (theme.BG_INPUT, theme.BORDER))
        self._label.setStyleSheet(
            'color: %s; background: transparent;'
            % (theme.FG if has else theme.FG_MUTED))
        self._label.setFont(theme.qfont(*theme.SMALL_FONT))
        self._arrow.setStyleSheet(
            'color: %s; background: transparent;' % theme.FG_DIM)
        self._arrow.setText('\u203A')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._popup and self._popup.isVisible():
            self._popup.setFixedWidth(self.width())
