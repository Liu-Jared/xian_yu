//水平线有问题，没有裁剪的办法
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QFileDialog, QMessageBox, QLabel, QListWidget, QListWidgetItem,
    QColorDialog, QSpinBox, QLineEdit, QGroupBox, QGridLayout, QStatusBar, QListView,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsTextItem, QGraphicsItem,
    QGraphicsItemGroup, QSplitter, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIcon, QTransform, QImage
from PyQt5.QtCore import Qt, QPoint, QSize, QRectF, pyqtSignal, QPointF, QThread, QObject, pyqtSlot


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
                self.icon_size, self.icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(pixmap)
            self.thumbnail_loaded.emit(file_path, icon)
            self.progress.emit(int((index + 1) / total_files * 100))
        self.finished.emit()


class ImageGraphicsView(QGraphicsView):
    annotations_changed = pyqtSignal()  # 信号，用于通知主窗口更新标注列表

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置对齐方式为居中
        self.setAlignment(Qt.AlignCenter)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 用于包含图片和标注的组
        self.image_group = QGraphicsItemGroup()
        self.scene.addItem(self.image_group)

        self.image_item = None  # 原始图片的图形项
        self.annotations = []  # 存储所有的标注项
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
        self.fixed_y_line = None  # 固定水平线的图形项

        # 标志位
        self.is_id_mode = False  # 是否为ID绘制模式
        self.is_rotating = False  # 是否处于旋转模式

        # 旋转相关
        self.rotation_angle = 0  # 总旋转角度
        self.last_mouse_pos = None  # 上一次鼠标位置

        # 缩放相关
        self.current_scale = 1.0  # 当前缩放比例

        # 启用鼠标跟踪
        self.setMouseTracking(True)

    def load_image(self, image_path):
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            QMessageBox.critical(self, "加载图片失败", f"无法加载图片: {image_path}")
        else:
            self.scene.clear()
            self.image_group = QGraphicsItemGroup()
            self.scene.addItem(self.image_group)

            self.image_item = QGraphicsPixmapItem(pixmap)
            self.image_item.setTransformationMode(Qt.SmoothTransformation)
            # 设置图片项的变换原点为图片中心
            self.image_item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
            # 将图片项的位置设置为 (-宽度/2, -高度/2)，使其中心位于组的中心
            self.image_item.setPos(-pixmap.width() / 2, -pixmap.height() / 2)
            self.image_group.addToGroup(self.image_item)

            self.annotations.clear()
            self.index = 1
            self.id_item = None
            self.fixed_y_line = None
            self.rotation_angle = 0
            self.image_group.setRotation(0)
            # 设置图形项组的变换原点为图片中心
            self.image_group.setTransformOriginPoint(0, 0)  # 组的原点与图片中心重合
            # 设置场景范围为图片组的边界
            self.setSceneRect(self.image_group.mapToScene(self.image_group.boundingRect()).boundingRect())
            # 初始适应视图
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
            self.annotations_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_num_digits(self, num_digits):
        self.num_digits = num_digits

    def set_current_annotation_color(self, color):
        self.current_annotation_color = color

    def set_text_size(self, size):
        self.text_size = size

    def set_id_text(self, id_text):
        self.id_text = "ID:" + id_text

    def set_id_text_size(self, size):
        """设置ID字体大小"""
        self.id_text_size = size

    def set_id_color(self, color):
        """设置ID颜色"""
        self.id_color = color

    def undo_last_annotation(self):
        if self.annotations:
            last_item = self.annotations.pop()
            # last_item.setParentItem(None)
            self.scene.removeItem(last_item)
            if last_item.data(0) == 'normal':
                self.index -= 1
            self.annotations_changed.emit()

    def finalize_annotation(self, position, annotation_type='normal'):
        if annotation_type == 'normal':
            annotation_text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
            self.index += 1
            font_size = self.text_size
            color = self.current_annotation_color
        elif annotation_type == 'id':
            annotation_text = self.id_text
            font_size = self.id_text_size
            color = self.id_color
            # 如果已有ID标注，先删除
            if self.id_item:
                self.id_item.setParentItem(None)
                self.scene.removeItem(self.id_item)
                self.id_item = None
        else:
            return

        text_item = QGraphicsTextItem(annotation_text)
        font = QFont('Arial', font_size)
        font.setKerning(True)
        text_item.setFont(font)
        text_item.setDefaultTextColor(color)

        # 将标注项的父项设置为 image_item
        text_item.setParentItem(self.image_item)
        text_item.setPos(position)
        text_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        text_item.setData(0, annotation_type)  # 用于标记类型

        # 设置文字项的旋转角度，使其在添加时正向显示
        # 但不改变其在图片上的位置和方向
        text_item.setRotation(-self.rotation_angle)

        if annotation_type == 'id':
            self.id_item = text_item
        else:
            self.annotations.append(text_item)
        self.annotations_changed.emit()

    def set_fixed_y_mode(self, mode: bool):
        self.fixed_y_mode = mode
        if not mode and self.fixed_y_line:
            self.scene.removeItem(self.fixed_y_line)
            self.fixed_y_line = None

    def set_fixed_y_position(self, y_position: float):
        if self.fixed_y_line:
            self.scene.removeItem(self.fixed_y_line)
            self.fixed_y_line = None
        line = self.image_item.addLine(
            self.image_item.boundingRect().left(), y_position,
            self.image_item.boundingRect().right(), y_position,
            QPen(Qt.red, 2, Qt.DashLine)
        )
        self.fixed_y_line = line

    def confirm_fixed_y_position(self):
        if self.fixed_y_line:
            self.fixed_y_line.setPen(QPen(Qt.green, 2, Qt.DashLine))

    def rotate_image(self, angle):
        if self.image_group:
            self.rotation_angle = (self.rotation_angle + angle) % 360
            self.image_group.setRotation(self.rotation_angle)

            # 不再调整文字项的旋转角度，文字将随图片一起旋转

            # 获取旋转后的图片和标注的外接矩形
            group_bounds = self.image_group.mapToScene(self.image_group.boundingRect()).boundingRect()
            # 设置场景范围
            self.scene.setSceneRect(group_bounds)

    def start_manual_rotation(self):
        if self.image_group:
            self.is_rotating = True
            self.setCursor(Qt.OpenHandCursor)
            self.last_mouse_pos = None

    def stop_manual_rotation(self):
        self.is_rotating = False
        self.setCursor(Qt.ArrowCursor)
        self.last_mouse_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            if self.is_rotating:
                self.last_mouse_pos = event.pos()
            else:
                # 将场景坐标转换为图片项的坐标系
                image_pos = self.image_item.mapFromScene(scene_pos)
                if self.fixed_y_mode and not self.fixed_y_line:
                    # 设置固定水平线
                    self.set_fixed_y_position(image_pos.y())
                else:
                    if self.is_id_mode:
                        annotation_type = 'id'
                    else:
                        annotation_type = 'normal'
                    position = image_pos
                    if self.fixed_y_mode and self.fixed_y_line:
                        position.setY(self.fixed_y_line.line().y1())
                    self.finalize_annotation(position, annotation_type)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_rotating and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            angle = delta.x()  # 根据鼠标水平移动量决定旋转角度
            self.rotate_image(angle)
            self.last_mouse_pos = event.pos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_rotating and event.button() == Qt.LeftButton:
            self.stop_manual_rotation()
        super().mouseReleaseEvent(event)

    def save_image(self, save_path):
        if not self.image_item:
            return False  # 没有可保存的图像，返回 False

        # 获取 image_group 在场景坐标系中的边界矩形
        rect = self.image_group.mapToScene(self.image_group.boundingRect()).boundingRect()
        image = QImage(rect.size().toSize(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()

        return image.save(save_path)  # 返回保存结果，True 或 False

    def delete_selected_annotation(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return False
        for item in selected_items:
            if item in self.annotations:
                self.annotations.remove(item)
            if item == self.id_item:
                self.id_item = None
            item.setParentItem(None)
            self.scene.removeItem(item)
        self.annotations_changed.emit()
        return True

    def change_selected_annotation_color(self, color):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return False
        for item in selected_items:
            item.setDefaultTextColor(color)
        return True

    def update_text_size(self, size):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return False
        for item in selected_items:
            font = item.font()
            font.setPointSize(size)
            item.setFont(font)
        return True


class ImageAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Annotator")
        self.setGeometry(100, 100, 1600, 1000)  # 增加窗口大小

        # 使用 QSplitter 作为中央控件
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # 左侧控制面板
        self.control_panel = QGroupBox("控制面板")
        self.control_layout = QVBoxLayout()
        self.control_panel.setLayout(self.control_layout)
        self.splitter.addWidget(self.control_panel)
        self.control_panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # 图像显示区域
        self.image_view = ImageGraphicsView(self)
        self.splitter.addWidget(self.image_view)
        self.image_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 缩略图列表
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setIconSize(QSize(100, 100))  # 使用 QSize
        self.thumbnail_list.setFixedWidth(200)
        self.thumbnail_list.setViewMode(QListView.IconMode)
        self.thumbnail_list.setResizeMode(QListWidget.Adjust)
        self.splitter.addWidget(self.thumbnail_list)
        self.thumbnail_list.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        # 设置 QSplitter 的伸缩因子
        self.splitter.setStretchFactor(0, 0)  # control_panel
        self.splitter.setStretchFactor(1, 1)  # image_view
        self.splitter.setStretchFactor(2, 0)  # thumbnail_list

        # 设置初始尺寸
        self.splitter.setSizes([200, 1200, 200])

        # 添加控件到控制面板
        self.add_controls_to_panel()

        # 连接信号和槽
        self.connect_signals()

        self.image_paths = []
        self.current_image_path = ""

        # 添加状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 应用样式表
        self.apply_styles()

    def add_controls_to_panel(self):
        # 使用网格布局组织控件
        grid = QGridLayout()

        # 打开文件/文件夹按钮
        self.open_button = QPushButton("打开文件/文件夹")
        self.open_button.setToolTip("打开图片文件或文件夹")
        grid.addWidget(self.open_button, 0, 0, 1, 2)

        # 撤销按钮
        self.undo_button = QPushButton("撤销 (Ctrl+Z)")
        self.undo_button.setToolTip("撤销最后一个标注")
        self.undo_button.setShortcut("Ctrl+Z")
        grid.addWidget(self.undo_button, 1, 0, 1, 2)

        # 设置当前标注颜色按钮
        self.color_button = QPushButton("设置当前标注颜色")
        self.color_button.setToolTip("设置当前标注颜色")
        grid.addWidget(self.color_button, 2, 0, 1, 2)

        # 标注字体大小
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(1, 10000)  # 设置一个非常大的上限
        self.size_spinbox.setValue(100)  # 初始值设置为100
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
        annotation_layout.addWidget(self.prefix_label, 0, 0)
        annotation_layout.addWidget(self.prefix_input, 0, 1)
        annotation_layout.addWidget(self.num_digits_label, 1, 0)
        annotation_layout.addWidget(self.num_digits_spinbox, 1, 1)
        self.annotation_settings_group.setLayout(annotation_layout)
        grid.addWidget(self.annotation_settings_group, 4, 0, 1, 2)

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
        self.id_size_spinbox.setValue(100)  # 初始值设置为100
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
        grid.addWidget(self.id_group, 5, 0, 1, 2)

        # 固定水平绘制相关按钮
        self.fixed_y_group = QGroupBox("固定水平绘制")
        fixed_y_layout = QVBoxLayout()

        # 添加“开始固定水平绘制”按钮
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
        grid.addWidget(self.fixed_y_group, 6, 0, 1, 2)

        # 旋转功能
        self.rotate_left_button = QPushButton("左旋转")
        self.rotate_left_button.setToolTip("向左旋转图片")
        self.rotate_right_button = QPushButton("右旋转")
        self.rotate_right_button.setToolTip("向右旋转图片")
        self.manual_rotate_button = QPushButton("手动旋转")
        self.manual_rotate_button.setToolTip("手动旋转图片")
        grid.addWidget(self.rotate_left_button, 7, 0)
        grid.addWidget(self.rotate_right_button, 7, 1)
        grid.addWidget(self.manual_rotate_button, 8, 0)

        # 当前模式标签
        self.mode_label = QLabel("当前模式：普通标注")
        self.mode_label.setFont(QFont('Arial', 12, QFont.Bold))
        self.mode_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.mode_label, 10, 0, 1, 2)

        # 保存图片按钮
        self.save_button = QPushButton("保存图片 (Ctrl+P)")
        self.save_button.setToolTip("保存当前标注的图片")
        self.save_button.setShortcut("Ctrl+P")
        grid.addWidget(self.save_button, 11, 0, 1, 2)

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
        grid.addWidget(self.annotations_group, 12, 0, 1, 2)

        # 添加网格布局到控制面板
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
        self.delete_annotation_button.clicked.connect(self.delete_selected_annotation)
        self.change_annotation_color_button.clicked.connect(self.change_selected_annotation_color)
        self.rotate_left_button.clicked.connect(lambda: self.rotate_image(-90))
        self.rotate_right_button.clicked.connect(lambda: self.rotate_image(90))
        self.manual_rotate_button.clicked.connect(self.start_manual_rotate)
        self.image_view.annotations_changed.connect(self.update_annotations_list)
        self.prefix_input.textChanged.connect(self.set_prefix)
        self.num_digits_spinbox.valueChanged.connect(self.set_num_digits)

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
        # 使用标准的 QFileDialog
        # 询问用户选择打开文件还是文件夹
        msg_box = QMessageBox()
        msg_box.setWindowTitle("选择文件或文件夹")
        msg_box.setText("请选择打开方式：")
        open_files_button = msg_box.addButton("打开文件", QMessageBox.AcceptRole)
        open_folder_button = msg_box.addButton("打开文件夹", QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)
        msg_box.exec_()

        if msg_box.clickedButton() == open_files_button:
            # 使用标准的 QFileDialog
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
                QMessageBox.information(self, "没有选择文件", "请选择一个或多个图片文件。")
        elif msg_box.clickedButton() == open_folder_button:
            folder = QFileDialog.getExistingDirectory(
                self, "选择包含图片的文件夹", "",
                options=QFileDialog.Options()
            )
            if folder:
                self.load_images_from_folder(folder)
            else:
                QMessageBox.information(self, "没有选择文件夹", "请选择一个包含图片的文件夹。")
        else:
            # 用户点击取消
            pass

    def load_images_from_folder(self, folder):
        self.image_paths = []
        self.thumbnail_list.clear()

        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
        file_paths = []
        for filename in os.listdir(folder):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                file_paths.append(os.path.join(folder, filename))

        # 启动后台线程加载缩略图
        self.loader = ThumbnailLoader(file_paths, 100)
        self.thread = QThread()
        self.loader.moveToThread(self.thread)
        self.thread.started.connect(self.loader.run)
        self.loader.finished.connect(self.thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.loader.thumbnail_loaded.connect(self.add_thumbnail_to_list)
        self.thread.start()

    @pyqtSlot(str, QIcon)
    def add_thumbnail_to_list(self, file_path, icon):
        item = QListWidgetItem(icon, os.path.basename(file_path))
        item.setData(Qt.UserRole, file_path)
        self.thumbnail_list.addItem(item)
        self.image_paths.append(file_path)

    def populate_thumbnail_list(self, image_paths):
        self.thumbnail_list.clear()
        self.image_paths = []
        # 启动后台线程加载缩略图
        self.loader = ThumbnailLoader(image_paths, 100)
        self.thread = QThread()
        self.loader.moveToThread(self.thread)
        self.thread.started.connect(self.loader.run)
        self.loader.finished.connect(self.thread.quit)
        self.loader.finished.connect(self.loader.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.loader.thumbnail_loaded.connect(self.add_thumbnail_to_list)
        self.thread.start()

    def load_image(self, image_path):
        try:
            self.current_image_path = image_path
            self.image_view.load_image(image_path)
            self.status_bar.showMessage(f"已加载图片: {os.path.basename(image_path)}", 5000)
            self.mode_label.setText("当前模式：普通标注")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时出错：{str(e)}")

    def load_selected_image(self, item):
        image_path = item.data(Qt.UserRole)
        if image_path:
            self.load_image(image_path)

    def undo_annotation(self):
        self.image_view.undo_last_annotation()
        self.status_bar.showMessage("撤销最后一个标注", 3000)

    def save_image(self):
        if self.current_image_path:
            success = self.image_view.save_image(self.current_image_path)
            if success:
                QMessageBox.information(self, "保存成功", f"图片已保存并覆盖原始图片: {self.current_image_path}")
            else:
                QMessageBox.warning(self, "保存失败", f"无法保存图片至 {self.current_image_path}")
        else:
            QMessageBox.warning(self, "保存失败", "没有加载任何图片。")



    def choose_current_annotation_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_view.set_current_annotation_color(color)
            self.status_bar.showMessage(f"当前标注颜色已设置为: {color.name()}", 3000)

    def set_text_size(self):
        size = self.size_spinbox.value()
        self.image_view.set_text_size(size)
        self.status_bar.showMessage(f"标注字体大小已设置为: {size}", 3000)

    def set_prefix(self, prefix):
        self.image_view.set_prefix(prefix)
        self.status_bar.showMessage(f"标注前缀已设置为: {prefix}", 3000)

    def set_num_digits(self, value):
        self.image_view.set_num_digits(value)
        self.status_bar.showMessage(f"序号位数已设置为: {value}", 3000)

    def add_id(self):
        id_text = self.id_input.text().strip()
        if id_text:
            # 切换到ID绘制模式，同时关闭固定水平绘制模式
            self.image_view.set_id_text(id_text)
            self.image_view.is_id_mode = True
            self.image_view.set_fixed_y_mode(False)
            self.status_bar.showMessage("进入ID绘制模式", 3000)
            self.mode_label.setText("当前模式：ID标注")
        else:
            QMessageBox.warning(self, "无效输入", "ID 不能为空。")

    def set_id_text_size(self):
        size = self.id_size_spinbox.value()
        self.image_view.set_id_text_size(size)
        self.status_bar.showMessage(f"ID字体大小已设置为: {size}", 3000)

    def choose_id_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_view.set_id_color(color)
            self.status_bar.showMessage(f"ID标注颜色已设置为: {color.name()}", 3000)

    def start_fixed_y_mode(self):
        if not self.image_view.fixed_y_mode:
            # 进入固定水平绘制模式时，确保退出ID绘制模式
            if self.image_view.is_id_mode:
                self.image_view.is_id_mode = False
                self.status_bar.showMessage("退出ID绘制模式", 3000)
                self.mode_label.setText("当前模式：固定水平绘制")
            self.image_view.set_fixed_y_mode(True)
            self.status_bar.showMessage("进入固定水平绘制模式", 3000)
            self.mode_label.setText("当前模式：固定水平绘制")
        else:
            QMessageBox.information(self, "已在固定模式", "当前已处于固定水平绘制模式。")

    def modify_fixed_y_mode(self):
        if self.image_view.fixed_y_mode:
            # 允许修改水平线
            if self.image_view.fixed_y_line:
                self.image_view.scene.removeItem(self.image_view.fixed_y_line)
                self.image_view.fixed_y_line = None
            self.status_bar.showMessage("固定水平线已置为可修改", 3000)
            self.mode_label.setText("当前模式：固定水平绘制 (可修改)")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")

    def close_fixed_y_mode(self):
        if self.image_view.fixed_y_mode:
            self.image_view.set_fixed_y_mode(False)
            self.status_bar.showMessage("固定水平绘制模式已关闭", 3000)
            self.mode_label.setText("当前模式：普通标注")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")

    def end_id_mode(self):
        if self.image_view.is_id_mode:
            self.image_view.is_id_mode = False
            self.status_bar.showMessage("退出ID绘制模式", 3000)
            self.mode_label.setText("当前模式：普通标注")
        else:
            QMessageBox.warning(self, "未开启ID模式", "当前未处于ID绘制模式。")

    def delete_id(self):
        if self.image_view.id_item:
            self.image_view.id_item.setParentItem(None)
            self.image_view.scene.removeItem(self.image_view.id_item)
            self.image_view.id_item = None
            self.image_view.annotations_changed.emit()
            self.status_bar.showMessage("ID标注已删除", 3000)
        else:
            QMessageBox.warning(self, "没有ID标注", "当前没有ID标注可以删除。")

    def update_annotations_list(self):
        self.annotations_list.clear()
        # 添加普通标注和ID标注
        for item in self.image_view.annotations + ([self.image_view.id_item] if self.image_view.id_item else []):
            if item:
                text = item.toPlainText()
                pos = item.pos()
                item_text = f"{text} at ({pos.x():.1f}, {pos.y():.1f})"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item)
                self.annotations_list.addItem(list_item)

    def delete_selected_annotation(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先在标注列表中选择要删除的标注。")
            return
        for list_item in selected_items:
            annotation_item = list_item.data(Qt.UserRole)
            if annotation_item:
                if annotation_item in self.image_view.annotations:
                    self.image_view.annotations.remove(annotation_item)
                if annotation_item == self.image_view.id_item:
                    self.image_view.id_item = None
                annotation_item.setParentItem(None)
                self.image_view.scene.removeItem(annotation_item)
                self.annotations_list.takeItem(self.annotations_list.row(list_item))
        self.image_view.annotations_changed.emit()
        self.status_bar.showMessage("选中的标注已删除", 3000)

    def change_selected_annotation_color(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先在标注列表中选择要更改颜色的标注。")
            return
        color = QColorDialog.getColor()
        if color.isValid():
            for list_item in selected_items:
                annotation_item = list_item.data(Qt.UserRole)
                if annotation_item:
                    annotation_item.setDefaultTextColor(color)
            self.status_bar.showMessage("选中标注的颜色已更改", 3000)

    def rotate_image(self, angle):
        self.image_view.rotate_image(angle)
        self.status_bar.showMessage(f"图片已旋转{angle}度", 3000)

    def start_manual_rotate(self):
        self.image_view.start_manual_rotation()
        self.status_bar.showMessage("进入手动旋转模式，按住鼠标左键拖动以旋转图片", 3000)
        self.mode_label.setText("当前模式：手动旋转")


def main():
    app = QApplication(sys.argv)
    main_window = ImageAnnotator()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
