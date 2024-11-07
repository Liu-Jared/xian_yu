import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QFileDialog, QMessageBox, QLabel, QListWidget, QListWidgetItem,
    QColorDialog, QSpinBox, QLineEdit, QGroupBox, QGridLayout, QStatusBar,
    QListView, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsTextItem, QGraphicsItem, QGraphicsItemGroup, QSplitter,
    QSizePolicy, QGraphicsLineItem
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QColor, QFont, QIcon, QTransform, QImage,
    QFontMetrics
)
from PyQt5.QtCore import (
    Qt, QPoint, QSize, QRectF, pyqtSignal, QPointF, QThread, QObject,
    pyqtSlot
)


class ThumbnailLoader(QObject):
    """异步加载缩略图的工作线程"""
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    thumbnail_loaded = pyqtSignal(str, QIcon)

    def __init__(self, file_paths, icon_size):
        super().__init__()
        self.file_paths = file_paths
        self.icon_size = icon_size
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        total_files = len(self.file_paths)
        for index, file_path in enumerate(self.file_paths):
            if not self.is_running:
                break
            pixmap = QPixmap(file_path).scaled(
                self.icon_size, self.icon_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(pixmap)
            self.thumbnail_loaded.emit(file_path, icon)
            self.progress.emit(int((index + 1) / total_files * 100))
        self.finished.emit()


class ImageGraphicsView(QGraphicsView):
    annotations_changed = pyqtSignal()  # 通知主窗口更新标注列表
    mode_changed = pyqtSignal(str)        # 通知主窗口更新当前模式

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 创建独立的图层
        self.main_group = QGraphicsItemGroup()
        self.scene.addItem(self.main_group)

        self.image_group = QGraphicsItemGroup()
        self.main_group.addToGroup(self.image_group)

        self.annotation_group = QGraphicsItemGroup()
        self.main_group.addToGroup(self.annotation_group)

        self.id_annotation_group = QGraphicsItemGroup()
        self.scene.addItem(self.id_annotation_group)

        self.fixed_line_groups = []  # 用于管理多个固定水平线图层

        self.image_item = None  # 原始图片的图形项
        self.annotations = []  # 存储所有的普通标注项
        self.prefix = "BR"
        self.num_digits = 2  # 序号位数，默认为2
        self.index = 1
        self.current_annotation_color = QColor(0, 0, 0)  # 当前标注颜色
        self.text_size = 100  # 标注字体大小
        self.id_text = ""
        self.id_text_size = 100  # ID字体大小
        self.id_color = QColor(0, 0, 0)  # ID颜色
        self.id_item = None  # ID标注的图形项

        # 固定水平绘制相关变量
        self.fixed_y_mode = False
        self.current_fixed_line_group = None  # 当前固定水平线的图层
        self.fixed_y_line = None  # 当前固定水平线的图形项
        self.fixed_y_line_fixed = False  # 跟踪水平线是否已固定

        # 标志位
        self.is_id_mode = False  # 是否为ID绘制模式

        # 悬浮标注项
        self.floating_annotation_item = None  # 用于显示悬浮的标注项

        # 启用鼠标跟踪
        self.setMouseTracking(True)

    def load_image(self, image_path):
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            QMessageBox.critical(self, "加载图片失败", f"无法加载图片: {image_path}")
        else:
            self.scene.clear()

            # 重建图层
            self.main_group = QGraphicsItemGroup()
            self.scene.addItem(self.main_group)

            self.image_group = QGraphicsItemGroup()
            self.main_group.addToGroup(self.image_group)

            self.annotation_group = QGraphicsItemGroup()
            self.main_group.addToGroup(self.annotation_group)

            self.id_annotation_group = QGraphicsItemGroup()
            self.scene.addItem(self.id_annotation_group)

            self.fixed_line_groups = []

            # 添加图片到图层，放置在(0,0)位置
            self.image_item = QGraphicsPixmapItem(pixmap)
            self.image_item.setTransformationMode(Qt.SmoothTransformation)
            self.image_item.setTransformOriginPoint(0, 0)  # 旋转中心
            self.image_item.setPos(0, 0)
            self.image_group.addToGroup(self.image_item)

            # 初始化标注相关变量
            self.annotations.clear()
            self.index = 1
            self.id_item = None
            self.fixed_y_line = None
            self.fixed_y_line_fixed = False
            self.main_group.setRotation(0)
            self.main_group.setTransformOriginPoint(0, 0)

            # 设置 sceneRect 仅基于 image_group
            self.scene.setSceneRect(self.image_group.mapToScene(
                self.image_group.boundingRect()).boundingRect())
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
            self.floating_annotation_item = None  # 重置悬浮标注项
            self.annotations_changed.emit()

            print(f"Loaded image: {image_path}")
            print(f"Scene Rect set to: {self.scene.sceneRect()}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def set_prefix(self, prefix):
        self.prefix = prefix
        for i, item in enumerate(self.annotations, start=1):
            text = f"{self.prefix}{str(i).zfill(self.num_digits)}"
            item.setPlainText(text)
        # 更新悬浮标注的文本
        if self.floating_annotation_item and not self.is_id_mode:
            text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
            self.floating_annotation_item.setPlainText(text)
        self.annotations_changed.emit()
        print(f"Prefix set to: {prefix}")

    def set_num_digits(self, num_digits):
        self.num_digits = num_digits
        for i, item in enumerate(self.annotations, start=1):
            text = f"{self.prefix}{str(i).zfill(self.num_digits)}"
            item.setPlainText(text)
        # 更新悬浮标注的文本
        if self.floating_annotation_item and not self.is_id_mode:
            text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
            self.floating_annotation_item.setPlainText(text)
        self.annotations_changed.emit()
        print(f"Number of digits set to: {num_digits}")

    def set_current_annotation_color(self, color):
        self.current_annotation_color = color
        # 更新悬浮标注的颜色
        if self.floating_annotation_item and not self.is_id_mode:
            self.floating_annotation_item.setDefaultTextColor(color)
        print(f"Current annotation color set to: {color.name()}")

    def set_text_size(self, size):
        self.text_size = size
        for item in self.annotations:
            font = item.font()
            font.setPointSize(size)
            item.setFont(font)
        # 更新悬浮标注的字体大小
        if self.floating_annotation_item and not self.is_id_mode:
            font = self.floating_annotation_item.font()
            font.setPointSize(size)
            self.floating_annotation_item.setFont(font)
        self.annotations_changed.emit()
        print(f"Annotation text size set to: {size}")

    def set_id_text(self, id_text):
        self.id_text = "ID:" + id_text
        if self.id_item:
            self.id_item.setPlainText(self.id_text)
        # 更新悬浮ID标注的文本
        if self.floating_annotation_item and self.is_id_mode:
            self.floating_annotation_item.setPlainText(self.id_text)
        self.annotations_changed.emit()
        print(f"ID text set to: {self.id_text}")

    def set_id_text_size(self, size):
        self.id_text_size = size
        if self.id_item:
            font = self.id_item.font()
            font.setPointSize(size)
            self.id_item.setFont(font)
        # 更新悬浮ID标注的字体大小
        if self.floating_annotation_item and self.is_id_mode:
            font = self.floating_annotation_item.font()
            font.setPointSize(size)
            self.floating_annotation_item.setFont(font)
        self.annotations_changed.emit()
        print(f"ID text size set to: {size}")

    def set_id_color(self, color):
        self.id_color = color
        if self.id_item:
            self.id_item.setDefaultTextColor(color)
        # 更新悬浮ID标注的颜色
        if self.floating_annotation_item and self.is_id_mode:
            self.floating_annotation_item.setDefaultTextColor(color)
        self.annotations_changed.emit()
        print(f"ID color set to: {color.name()}")

    def undo_last_annotation(self):
        if self.annotations:
            last_item = self.annotations.pop()
            self.annotation_group.removeFromGroup(last_item)
            self.scene.removeItem(last_item)
            self.index -= 1
            self.annotations_changed.emit()
            print("Undid the last annotation.")
        else:
            print("No annotations to undo.")

    def finalize_annotation(self, position, annotation_type='normal'):
        print(f"Finalizing annotation at position: {position}, type: {annotation_type}")
        if annotation_type == 'normal':
            annotation_text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
            self.index += 1
            font_size = self.text_size
            color = self.current_annotation_color
            parent_group = self.annotation_group
        elif annotation_type == 'id':
            annotation_text = self.id_text
            font_size = self.id_text_size
            color = self.id_color
            parent_group = self.id_annotation_group
            if self.id_item:
                self.id_annotation_group.removeFromGroup(self.id_item)
                self.scene.removeItem(self.id_item)
                self.id_item = None
        else:
            return

        text_item = QGraphicsTextItem(annotation_text)
        font = QFont()  # 使用系统默认字体
        font.setPointSize(font_size)
        font.setKerning(True)
        text_item.setFont(font)
        text_item.setDefaultTextColor(color)
        text_item.setParentItem(parent_group)

        if self.fixed_y_mode and self.fixed_y_line:
            # 确保注释在固定水平线上方，并使文本的底部与水平线对齐
            image_pos = self.image_group.mapFromScene(position)
            print(f"Image position for annotation: {image_pos}")
            text_height = text_item.boundingRect().height()
            text_item.setPos(image_pos.x(), self.fixed_y_line.line().y1() - text_height)  # 调整为减去整个高度
        else:
            text_item.setPos(position)
        text_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        text_item.setData(0, annotation_type)
        if annotation_type == 'normal':
            text_item.setRotation(0)
            print(f"Setting rotation for normal annotation: 0")

        if annotation_type == 'id':
            self.id_item = text_item
        else:
            self.annotations.append(text_item)
        self.annotations_changed.emit()
        print(f"Annotation finalized. Current index: {self.index}")

    def set_fixed_y_mode(self, mode: bool):
        self.fixed_y_mode = mode
        self.fixed_y_line_fixed = False
        if not mode and self.current_fixed_line_group:
            # 如果关闭固定水平绘制模式，移除当前固定线图层
            self.scene.removeItem(self.current_fixed_line_group)
            self.fixed_line_groups.remove(self.current_fixed_line_group)
            self.current_fixed_line_group = None
            self.fixed_y_line = None
            self.fixed_y_line_fixed = False
            self.mode_changed.emit("普通标注")
            print("Fixed Y mode disabled and fixed line layer removed.")
        elif mode:
            # 开启固定水平绘制模式，创建新的固定线图层
            self.current_fixed_line_group = QGraphicsItemGroup()
            self.scene.addItem(self.current_fixed_line_group)
            self.fixed_line_groups.append(self.current_fixed_line_group)
            self.fixed_y_line = None
            self.fixed_y_line_fixed = False
            self.mode_changed.emit("固定水平绘制")
            print("Fixed Y mode enabled and new fixed line layer created.")

        # 移除悬浮标注项
        if self.floating_annotation_item:
            self.floating_annotation_item.setParentItem(None)
            self.scene.removeItem(self.floating_annotation_item)
            self.floating_annotation_item = None
            print("Floating annotation item removed.")

    def set_fixed_y_position(self, y_position: float):
        if not self.image_item or not self.fixed_y_mode or not self.current_fixed_line_group:
            return
        if not self.fixed_y_line:
            line = QGraphicsLineItem(
                self.image_item.boundingRect().left(), y_position,
                self.image_item.boundingRect().right(), y_position
            )
            line.setPen(QPen(Qt.red, 2, Qt.DashLine))
            self.current_fixed_line_group.addToGroup(line)
            self.fixed_y_line = line
            print(f"Fixed Y line created at y={y_position}")
        else:
            self.fixed_y_line.setLine(
                self.image_item.boundingRect().left(), y_position,
                self.image_item.boundingRect().right(), y_position
            )
            print(f"Fixed Y line updated to y={y_position}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.fixed_y_mode:
                if not self.fixed_y_line_fixed:
                    # 固定水平线
                    self.fixed_y_line_fixed = True
                    if self.fixed_y_line:
                        self.fixed_y_line.setPen(QPen(Qt.green, 2, Qt.DashLine))
                        print("Fixed Y line fixed (color changed to green).")
                    self.mode_changed.emit("固定水平绘制")
                else:
                    # 固定悬浮标注项
                    if self.floating_annotation_item:
                        position = self.mapToScene(event.pos())
                        if self.is_id_mode:
                            annotation_type = 'id'
                        else:
                            annotation_type = 'normal'
                        self.finalize_annotation(position, annotation_type)
                        # 移除悬浮标注项
                        self.floating_annotation_item.setParentItem(None)
                        self.scene.removeItem(self.floating_annotation_item)
                        self.floating_annotation_item = None
                        print("Annotation finalized in fixed Y mode.")
            else:
                # 固定悬浮标注项
                if self.floating_annotation_item:
                    position = self.mapToScene(event.pos())
                    if self.is_id_mode:
                        annotation_type = 'id'
                    else:
                        annotation_type = 'normal'
                    self.finalize_annotation(position, annotation_type)
                    # 移除悬浮标注项
                    self.floating_annotation_item.setParentItem(None)
                    self.scene.removeItem(self.floating_annotation_item)
                    self.floating_annotation_item = None
                    print("Annotation finalized in normal mode.")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.image_item:
            super().mouseMoveEvent(event)
            return

        scene_pos = self.mapToScene(event.pos())
        image_pos = scene_pos

        if self.fixed_y_mode and not self.fixed_y_line_fixed:
            # 更新固定水平线的位置
            self.set_fixed_y_position(image_pos.y())
            # 移除悬浮标注项
            if self.floating_annotation_item:
                self.floating_annotation_item.setParentItem(None)
                self.scene.removeItem(self.floating_annotation_item)
                self.floating_annotation_item = None
        else:
            # 创建或更新悬浮标注项
            if not self.floating_annotation_item:
                if self.is_id_mode:
                    text = self.id_text
                    font_size = self.id_text_size
                    color = self.id_color
                else:
                    text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
                    font_size = self.text_size
                    color = self.current_annotation_color

                self.floating_annotation_item = QGraphicsTextItem(text)
                font = QFont()  # 使用系统默认字体
                font.setPointSize(font_size)
                font.setKerning(True)
                self.floating_annotation_item.setFont(font)
                self.floating_annotation_item.setDefaultTextColor(color)
                if self.is_id_mode:
                    self.floating_annotation_item.setParentItem(self.id_annotation_group)
                    self.floating_annotation_item.setRotation(0)  # 保持水平
                else:
                    self.floating_annotation_item.setParentItem(self.main_group)
                    self.floating_annotation_item.setRotation(0)  # 保持水平
                self.floating_annotation_item.setFlag(
                    QGraphicsItem.ItemIsSelectable, True)
                print("Floating annotation item created.")

            # 更新悬浮标注项的位置
            position = scene_pos
            if self.fixed_y_mode and self.fixed_y_line_fixed and self.fixed_y_line:
                y_position = self.fixed_y_line.line().y1()
                font_metrics = QFontMetrics(
                    self.floating_annotation_item.font())
                text_height = font_metrics.height()
                position.setY(y_position - text_height)  # 调整为减去整个高度，使底部对齐
            self.floating_annotation_item.setPos(position)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """处理双击事件，结束固定水平绘制"""
        if self.fixed_y_mode and self.fixed_y_line and not self.fixed_y_line_fixed:
            # 双击结束固定水平绘制
            self.fixed_y_line_fixed = True
            if self.fixed_y_line:
                self.fixed_y_line.setPen(QPen(Qt.green, 2, Qt.DashLine))
                print("Fixed Y line fixed via double-click (color changed to green).")
            self.finalize_fixed_y_line()
            self.mode_changed.emit("普通标注")
        super().mouseDoubleClickEvent(event)

    def finalize_fixed_y_line(self):
        """将固定水平线及其标注转移到普通标注图层"""
        if not self.current_fixed_line_group:
            return
        # 将所有子项（线条和标注）从固定线图层转移到普通标注图层
        for item in self.current_fixed_line_group.childItems():
            if isinstance(item, QGraphicsLineItem):
                # 固定线条不需要转移
                continue
            elif isinstance(item, QGraphicsTextItem):
                # 将标注转移到普通标注图层
                self.annotation_group.addToGroup(item)
                self.annotations.append(item)
                item.setParentItem(self.annotation_group)
                item.setRotation(0)  # 保持水平
                print(f"Moved annotation to normal layer with rotation 0.")
        # 移除固定线图层
        self.scene.removeItem(self.current_fixed_line_group)
        self.fixed_line_groups.remove(self.current_fixed_line_group)
        self.current_fixed_line_group = None
        self.fixed_y_line = None
        self.fixed_y_line_fixed = False
        self.annotations_changed.emit()
        print("Fixed Y line finalized and fixed line layer removed.")

    def save_image(self, save_path):
        # 创建一个与图像大小相同的QImage
        rect = self.image_group.boundingRect()
        print(f"Image group bounding rect: {rect}")
        if rect.width() <= 0 or rect.height() <= 0:
            QMessageBox.warning(self, "保存失败", "图片尺寸无效。")
            print("Save failed: Invalid image dimensions.")
            return False
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.transparent)

        painter = QPainter(image)
        self.scene.render(painter, target=QRectF(image.rect()), source=rect)
        painter.end()

        success = image.save(save_path)
        if success:
            print(f"Image saved successfully: {save_path}")
        else:
            print(f"Failed to save image: {save_path}")
        return success


class ImageAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Annotator")
        self.setGeometry(100, 100, 1600, 1000)

        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        self.control_panel = QGroupBox("控制面板")
        self.control_layout = QVBoxLayout()
        self.control_panel.setLayout(self.control_layout)
        self.splitter.addWidget(self.control_panel)
        self.control_panel.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.image_view = ImageGraphicsView(self)
        self.splitter.addWidget(self.image_view)
        self.image_view.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setIconSize(QSize(100, 100))
        self.thumbnail_list.setFixedWidth(200)
        self.thumbnail_list.setViewMode(QListView.IconMode)
        self.thumbnail_list.setResizeMode(QListWidget.Adjust)
        self.splitter.addWidget(self.thumbnail_list)
        self.thumbnail_list.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)

        self.splitter.setSizes([200, 1200, 200])

        self.add_controls_to_panel()
        self.connect_signals()

        self.image_paths = []
        self.current_image_path = ""

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.apply_styles()

        # 连接 ImageGraphicsView 的 mode_changed 信号
        self.image_view.mode_changed.connect(self.update_mode_label)

    def add_controls_to_panel(self):
        grid = QGridLayout()

        # 打开文件/文件夹按钮
        self.open_button = QPushButton("打开文件/文件夹")
        self.open_button.setToolTip("打开图片文件或文件夹")
        grid.addWidget(self.open_button, 0, 0, 1, 3)

        # 撤销按钮
        self.undo_button = QPushButton("撤销 (Ctrl+Z)")
        self.undo_button.setToolTip("撤销最后一个标注")
        self.undo_button.setShortcut("Ctrl+Z")
        grid.addWidget(self.undo_button, 1, 0, 1, 3)

        # 设置当前标注颜色按钮
        self.color_button = QPushButton("设置当前标注颜色")
        self.color_button.setToolTip("设置当前标注颜色")
        grid.addWidget(self.color_button, 2, 0, 1, 3)

        # 设置标注字体大小
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(1, 10000)
        self.size_spinbox.setValue(100)
        self.size_spinbox.setToolTip("设置标注字体大小")
        self.size_confirm_button = QPushButton("确定")
        self.size_confirm_button.setToolTip("确定字体大小")
        grid.addWidget(QLabel("字体大小:"), 3, 0)
        grid.addWidget(self.size_spinbox, 3, 1)
        grid.addWidget(self.size_confirm_button, 3, 2)

        # 标注设置组
        self.annotation_settings_group = QGroupBox("标注设置")
        annotation_layout = QGridLayout()
        self.prefix_label = QLabel("标注前缀:")
        self.prefix_input = QLineEdit()
        self.prefix_input.setText(self.image_view.prefix)
        self.num_digits_label = QLabel("序号位数:")
        self.num_digits_spinbox = QSpinBox()
        self.num_digits_spinbox.setRange(1, 10)
        self.num_digits_spinbox.setValue(self.image_view.num_digits)
        self.prefix_confirm_button = QPushButton("确定")
        annotation_layout.addWidget(self.prefix_label, 0, 0)
        annotation_layout.addWidget(self.prefix_input, 0, 1)
        annotation_layout.addWidget(self.prefix_confirm_button, 0, 2)
        annotation_layout.addWidget(self.num_digits_label, 1, 0)
        annotation_layout.addWidget(self.num_digits_spinbox, 1, 1)
        self.num_digits_confirm_button = QPushButton("确定")
        annotation_layout.addWidget(self.num_digits_confirm_button, 1, 2)
        self.annotation_settings_group.setLayout(annotation_layout)
        grid.addWidget(self.annotation_settings_group, 4, 0, 1, 3)

        # ID设置组
        self.id_group = QGroupBox("ID设置")
        id_layout = QVBoxLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("输入ID")
        self.add_id_button = QPushButton("添加ID")
        self.add_id_button.setToolTip("添加ID标注 (Ctrl+I)")
        self.add_id_button.setShortcut("Ctrl+I")
        self.id_size_spinbox = QSpinBox()
        self.id_size_spinbox.setRange(1, 10000)
        self.id_size_spinbox.setValue(100)
        self.id_size_spinbox.setToolTip("设置ID字体大小")
        self.id_size_confirm_button = QPushButton("确定")
        self.id_size_confirm_button.setToolTip("确定ID字体大小")
        self.id_color_button = QPushButton("设置ID颜色")
        self.id_color_button.setToolTip("设置ID标注颜色")
        self.end_id_button = QPushButton("结束ID绘制 (Ctrl+E)")
        self.end_id_button.setToolTip("结束ID绘制模式")
        self.end_id_button.setShortcut("Ctrl+E")
        self.delete_id_button = QPushButton("删除ID")
        self.delete_id_button.setToolTip("删除ID标注")
        id_layout.addWidget(self.id_input)
        id_layout.addWidget(self.add_id_button)
        id_layout.addWidget(QLabel("ID字体大小:"))
        id_layout.addWidget(self.id_size_spinbox)
        id_layout.addWidget(self.id_size_confirm_button)
        id_layout.addWidget(self.id_color_button)
        id_layout.addWidget(self.delete_id_button)
        id_layout.addWidget(self.end_id_button)
        self.id_group.setLayout(id_layout)
        grid.addWidget(self.id_group, 5, 0, 1, 3)

        # 固定水平绘制组
        self.fixed_y_group = QGroupBox("固定水平绘制")
        fixed_y_layout = QVBoxLayout()
        self.start_fixed_y_button = QPushButton("开始固定水平绘制 (Ctrl+F)")
        self.start_fixed_y_button.setToolTip("开始固定水平绘制模式")
        self.start_fixed_y_button.setShortcut("Ctrl+F")
        self.modify_fixed_y_button = QPushButton("修改水平线 (Ctrl+M)")
        self.modify_fixed_y_button.setToolTip("修改固定水平线位置")
        self.modify_fixed_y_button.setShortcut("Ctrl+M")
        self.close_fixed_y_button = QPushButton("关闭固定绘制 (Ctrl+Q)")
        self.close_fixed_y_button.setToolTip("关闭固定水平绘制模式")
        self.close_fixed_y_button.setShortcut("Ctrl+Q")
        fixed_y_layout.addWidget(self.start_fixed_y_button)
        fixed_y_layout.addWidget(self.modify_fixed_y_button)
        fixed_y_layout.addWidget(self.close_fixed_y_button)
        self.fixed_y_group.setLayout(fixed_y_layout)
        grid.addWidget(self.fixed_y_group, 6, 0, 1, 3)

        # 当前模式标签
        self.mode_label = QLabel("当前模式：普通标注")
        self.mode_label.setFont(QFont('', 12, QFont.Bold))  # 使用系统默认字体
        self.mode_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.mode_label, 10, 0, 1, 3)

        # 保存图片按钮
        self.save_button = QPushButton("保存图片 (Ctrl+P)")
        self.save_button.setToolTip("保存当前标注的图片")
        self.save_button.setShortcut("Ctrl+P")
        grid.addWidget(self.save_button, 11, 0, 1, 3)

        # 标注列表组
        self.annotations_group = QGroupBox("标注列表")
        annotations_layout = QVBoxLayout()
        self.annotations_list = QListWidget()
        annotations_layout.addWidget(self.annotations_list)
        self.change_annotation_color_button = QPushButton("更改标注颜色")
        self.delete_annotation_button = QPushButton("删除选中标注")
        annotations_layout.addWidget(self.change_annotation_color_button)
        annotations_layout.addWidget(self.delete_annotation_button)
        self.annotations_group.setLayout(annotations_layout)
        grid.addWidget(self.annotations_group, 12, 0, 1, 3)

        self.control_layout.addLayout(grid)
        self.control_layout.addStretch()

    def connect_signals(self):
        self.open_button.clicked.connect(self.open_file_or_folder)
        self.undo_button.clicked.connect(self.undo_annotation)
        self.save_button.clicked.connect(self.save_image)
        self.color_button.clicked.connect(self.choose_current_annotation_color)
        self.size_confirm_button.clicked.connect(self.set_text_size)
        self.thumbnail_list.itemClicked.connect(self.load_selected_image)
        self.add_id_button.clicked.connect(self.add_id)
        self.id_size_confirm_button.clicked.connect(self.set_id_text_size)
        self.id_color_button.clicked.connect(self.choose_id_color)
        self.start_fixed_y_button.clicked.connect(self.start_fixed_y_mode)
        self.modify_fixed_y_button.clicked.connect(self.modify_fixed_y_mode)
        self.close_fixed_y_button.clicked.connect(self.close_fixed_y_mode)
        self.end_id_button.clicked.connect(self.end_id_mode)
        self.delete_id_button.clicked.connect(self.delete_id)
        self.delete_annotation_button.clicked.connect(
            self.delete_selected_annotation)
        self.change_annotation_color_button.clicked.connect(
            self.change_selected_annotation_color)
        self.image_view.annotations_changed.connect(
            self.update_annotations_list)
        self.prefix_confirm_button.clicked.connect(self.set_prefix)
        self.num_digits_confirm_button.clicked.connect(self.set_num_digits)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3e8e41;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                margin-top: 10px;
                padding: 10px;
            }
            QLabel {
                font-size: 14px;
            }
            QListWidget {
                background-color: white;
                border: 1px solid #ccc;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

    def open_file_or_folder(self):
        msg_box = QMessageBox()
        msg_box.setWindowTitle("选择文件或文件夹")
        msg_box.setText("请选择打开方式：")
        open_files_button = msg_box.addButton(
            "打开文件", QMessageBox.AcceptRole)
        open_folder_button = msg_box.addButton(
            "打开文件夹", QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)
        msg_box.exec_()

        if msg_box.clickedButton() == open_files_button:
            options = QFileDialog.Options()
            files, _ = QFileDialog.getOpenFileNames(
                self, "选择图片文件", "",
                "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
                options=options
            )
            if files:
                self.image_paths = files
                self.populate_thumbnail_list(self.image_paths)
                if self.image_paths:
                    self.load_image(self.image_paths[0])
            else:
                QMessageBox.information(
                    self, "没有选择文件", "请选择一个或多个图片文件。")
        elif msg_box.clickedButton() == open_folder_button:
            folder = QFileDialog.getExistingDirectory(
                self, "选择包含图片的文件夹", "",
                options=QFileDialog.Options()
            )
            if folder:
                self.load_images_from_folder(folder)
            else:
                QMessageBox.information(
                    self, "没有选择文件夹", "请选择一个包含图片的文件夹。")
        else:
            pass

    def load_images_from_folder(self, folder):
        self.image_paths = []
        self.thumbnail_list.clear()

        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
        file_paths = []
        for filename in os.listdir(folder):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                file_paths.append(os.path.join(folder, filename))

        self.loader = ThumbnailLoader(file_paths, 100)
        self.thread = QThread()
        self.loader.moveToThread(self.thread)
        self.thread.started.connect(self.loader.run)
        self.loader.finished.connect(self.thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.loader.thumbnail_loaded.connect(self.add_thumbnail_to_list)
        self.thread.start()
        print(f"Started loading thumbnails from folder: {folder}")

    @pyqtSlot(str, QIcon)
    def add_thumbnail_to_list(self, file_path, icon):
        item = QListWidgetItem(icon, os.path.basename(file_path))
        item.setData(Qt.UserRole, file_path)
        self.thumbnail_list.addItem(item)
        self.image_paths.append(file_path)
        print(f"Added thumbnail for: {file_path}")

    def populate_thumbnail_list(self, image_paths):
        self.thumbnail_list.clear()
        self.image_paths = []
        self.loader = ThumbnailLoader(image_paths, 100)
        self.thread = QThread()
        self.loader.moveToThread(self.thread)
        self.thread.started.connect(self.loader.run)
        self.loader.finished.connect(self.thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.loader.thumbnail_loaded.connect(self.add_thumbnail_to_list)
        self.thread.start()
        print("Started populating thumbnail list.")

    def load_image(self, image_path):
        try:
            self.current_image_path = image_path
            self.image_view.load_image(image_path)
            self.status_bar.showMessage(
                f"已加载图片: {os.path.basename(image_path)}", 5000)
            self.mode_label.setText("当前模式：普通标注")
            print(f"Loaded image: {image_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时出错：{str(e)}")
            print(f"Error loading image {image_path}: {e}")

    def load_selected_image(self, item):
        image_path = item.data(Qt.UserRole)
        if image_path:
            self.load_image(image_path)
            print(f"Selected image loaded: {image_path}")

    def undo_annotation(self):
        self.image_view.undo_last_annotation()
        self.status_bar.showMessage("撤销最后一个标注", 3000)
        print("Undo annotation triggered.")

    def save_image(self):
        if self.current_image_path:
            # 自动关闭固定水平绘制模式
            if self.image_view.fixed_y_mode:
                self.image_view.set_fixed_y_mode(False)
                self.status_bar.showMessage("固定水平绘制模式已关闭", 3000)
                self.mode_label.setText("当前模式：普通标注")
                print("Auto-closed fixed Y mode before saving.")
            success = self.image_view.save_image(self.current_image_path)
            if success:
                QMessageBox.information(
                    self, "保存成功",
                    f"图片已保存并覆盖原始图片: {self.current_image_path}")
                print(f"Image saved successfully: {self.current_image_path}")
            else:
                QMessageBox.warning(
                    self, "保存失败",
                    f"无法保存图片至 {self.current_image_path}")
                print(f"Failed to save image: {self.current_image_path}")
        else:
            QMessageBox.warning(self, "保存失败", "没有加载任何图片。")
            print("Save failed: No image loaded.")

    def choose_current_annotation_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_view.set_current_annotation_color(color)
            self.status_bar.showMessage(
                f"当前标注颜色已设置为: {color.name()}", 3000)
            print(f"Chosen annotation color: {color.name()}")

    def set_text_size(self):
        size = self.size_spinbox.value()
        self.image_view.set_text_size(size)
        self.status_bar.showMessage(f"标注字体大小已设置为: {size}", 3000)
        print(f"Annotation text size set to: {size}")

    def set_prefix(self):
        prefix = self.prefix_input.text()
        self.image_view.set_prefix(prefix)
        self.status_bar.showMessage(f"标注前缀已设置为: {prefix}", 3000)
        print(f"Annotation prefix set to: {prefix}")

    def set_num_digits(self):
        value = self.num_digits_spinbox.value()
        self.image_view.set_num_digits(value)
        self.status_bar.showMessage(f"序号位数已设置为: {value}", 3000)
        print(f"Number of digits for annotations set to: {value}")

    def add_id(self):
        id_text = self.id_input.text().strip()
        if id_text:
            self.image_view.set_id_text(id_text)
            self.image_view.is_id_mode = True
            self.image_view.set_fixed_y_mode(False)
            self.status_bar.showMessage("进入ID绘制模式", 3000)
            self.mode_label.setText("当前模式：ID标注")
            # 移除悬浮标注项
            if self.image_view.floating_annotation_item:
                self.image_view.floating_annotation_item.setParentItem(None)
                self.image_view.scene.removeItem(
                    self.image_view.floating_annotation_item)
                self.image_view.floating_annotation_item = None
                print("Entered ID annotation mode.")
        else:
            QMessageBox.warning(self, "无效输入", "ID 不能为空。")
            print("Add ID failed: Empty ID input.")

    def set_id_text_size(self):
        size = self.id_size_spinbox.value()
        self.image_view.set_id_text_size(size)
        self.status_bar.showMessage(f"ID字体大小已设置为: {size}", 3000)
        print(f"ID text size set to: {size}")

    def choose_id_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_view.set_id_color(color)
            self.status_bar.showMessage(f"ID标注颜色已设置为: {color.name()}", 3000)
            print(f"ID color set to: {color.name()}")

    def start_fixed_y_mode(self):
        if not self.image_view.fixed_y_mode:
            if self.image_view.is_id_mode:
                self.image_view.is_id_mode = False
                self.status_bar.showMessage("退出ID绘制模式", 3000)
                self.mode_label.setText("当前模式：固定水平绘制")
                print("Exited ID annotation mode to enter fixed Y mode.")
            self.image_view.set_fixed_y_mode(True)
            self.status_bar.showMessage("进入固定水平绘制模式", 3000)
            self.mode_label.setText("当前模式：固定水平绘制")
            # 移除悬浮标注项
            if self.image_view.floating_annotation_item:
                self.image_view.floating_annotation_item.setParentItem(None)
                self.image_view.scene.removeItem(
                    self.image_view.floating_annotation_item)
                self.image_view.floating_annotation_item = None
                print("Removed floating annotation item for fixed Y mode.")
        else:
            QMessageBox.information(self, "已在固定模式", "当前已处于固定水平绘制模式。")
            print("Fixed Y mode is already active.")

    def modify_fixed_y_mode(self):
        if self.image_view.fixed_y_mode:
            if self.image_view.fixed_y_line:
                self.image_view.fixed_y_line_fixed = False
                self.image_view.fixed_y_line.setPen(
                    QPen(Qt.red, 2, Qt.DashLine))
                self.mode_label.setText("当前模式：固定水平绘制 (可修改)")
                self.status_bar.showMessage("固定水平线已置为可修改", 3000)
                print("Fixed Y line set to modifiable (color changed to red).")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")
            print("Modify fixed Y mode failed: Fixed Y mode not active.")

    def close_fixed_y_mode(self):
        if self.image_view.fixed_y_mode:
            self.image_view.set_fixed_y_mode(False)
            self.status_bar.showMessage("固定水平绘制模式已关闭", 3000)
            self.mode_label.setText("当前模式：普通标注")
            print("Closed fixed Y mode.")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")
            print("Close fixed Y mode failed: Fixed Y mode not active.")

    def end_id_mode(self):
        if self.image_view.is_id_mode:
            self.image_view.is_id_mode = False
            self.status_bar.showMessage("退出ID绘制模式", 3000)
            self.mode_label.setText("当前模式：普通标注")
            # 移除悬浮标注项
            if self.image_view.floating_annotation_item:
                self.image_view.floating_annotation_item.setParentItem(None)
                self.image_view.scene.removeItem(
                    self.image_view.floating_annotation_item)
                self.image_view.floating_annotation_item = None
            print("Exited ID annotation mode.")
        else:
            QMessageBox.warning(self, "未开启ID模式", "当前未处于ID绘制模式。")
            print("End ID mode failed: ID mode not active.")

    def delete_id(self):
        if self.image_view.id_item:
            self.image_view.id_annotation_group.removeFromGroup(self.image_view.id_item)
            self.image_view.scene.removeItem(self.image_view.id_item)
            self.image_view.id_item = None
            self.image_view.annotations_changed.emit()
            self.status_bar.showMessage("ID标注已删除", 3000)
            print("ID annotation deleted.")
        else:
            QMessageBox.warning(self, "没有ID标注", "当前没有ID标注可以删除。")
            print("Delete ID failed: No ID annotation present.")

    def update_annotations_list(self):
        self.annotations_list.clear()
        # 普通标注
        for item in self.image_view.annotations:
            if item:
                text = item.toPlainText()
                pos = item.pos()
                item_text = f"{text} at ({pos.x():.1f}, {pos.y():.1f})"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item)
                self.annotations_list.addItem(list_item)
        # ID标注
        if self.image_view.id_item:
            text = self.image_view.id_item.toPlainText()
            pos = self.image_view.id_item.pos()
            item_text = f"{text} at ({pos.x():.1f}, {pos.y():.1f})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, self.image_view.id_item)
            self.annotations_list.addItem(list_item)
        print("Updated annotations list.")

    def delete_selected_annotation(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先选择要删除的标注。")
            print("Delete selected annotation failed: No annotation selected.")
            return
        for list_item in selected_items:
            annotation_item = list_item.data(Qt.UserRole)
            if annotation_item:
                if annotation_item in self.image_view.annotations:
                    self.image_view.annotations.remove(annotation_item)
                if annotation_item == self.image_view.id_item:
                    self.image_view.id_item = None
                if annotation_item.parentItem() == self.image_view.annotation_group:
                    self.image_view.annotation_group.removeFromGroup(annotation_item)
                elif annotation_item.parentItem() == self.image_view.id_annotation_group:
                    self.image_view.id_annotation_group.removeFromGroup(annotation_item)
                annotation_item.setParentItem(None)
                self.image_view.scene.removeItem(annotation_item)
                self.annotations_list.takeItem(
                    self.annotations_list.row(list_item))
                print(f"Deleted annotation: {annotation_item.toPlainText()}")
        self.image_view.annotations_changed.emit()
        self.status_bar.showMessage("选中的标注已删除", 3000)

    def change_selected_annotation_color(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先选择要更改颜色的标注。")
            print("Change annotation color failed: No annotation selected.")
            return
        color = QColorDialog.getColor()
        if color.isValid():
            for list_item in selected_items:
                annotation_item = list_item.data(Qt.UserRole)
                if annotation_item:
                    annotation_item.setDefaultTextColor(color)
                    print(f"Changed color of annotation '{annotation_item.toPlainText()}' to {color.name()}")
            self.status_bar.showMessage("选中标注的颜色已更改", 3000)

    def update_mode_label(self, mode_text):
        self.mode_label.setText(f"当前模式：{mode_text}")
        print(f"Mode label updated to: {mode_text}")


def main():
    app = QApplication(sys.argv)
    main_window = ImageAnnotator()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
