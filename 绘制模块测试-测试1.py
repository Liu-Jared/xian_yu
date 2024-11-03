import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
    QFileDialog, QMessageBox, QLabel, QScrollArea, QListWidget, QListWidgetItem,
    QColorDialog, QSpinBox, QLineEdit, QInputDialog, QGroupBox, QGridLayout,
    QStatusBar
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIcon, QTransform
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, pyqtSignal, QPointF
import os
import math


class ImageLabel(QLabel):
    annotations_changed = pyqtSignal()  # 信号，用于通知主窗口更新标注列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.original_pixmap = None  # 保存原始图片，用于旋转和裁剪
        self.annotations = []  # 存储 (id, text, position, type, color) 五元组
        self.prefix = "BR"
        self.num_digits = 2  # 序号位数，默认为2
        self.index = 1
        self.current_annotation_color = QColor(0, 0, 0)  # 当前标注颜色
        self.text_size = 20
        self.id_text = ""
        self.id_position = None  # 存储ID绘制的位置
        self.id_text_size = 20  # ID字体大小
        self.id_color = QColor(0, 0, 0)  # ID颜色
        self.id_annotation = None  # 存储ID标注

        # 固定水平绘制相关变量
        self.fixed_y_mode = False
        self.fixed_y_position = None
        self.fixed_y_mark_position = None
        self.is_fixed_y_confirmed = False  # 标志位：是否确定水平线

        # 增加标志位用于区分绘制模式
        self.is_id_mode = False  # 是否为ID绘制模式
        self.is_cropping = False  # 是否处于裁剪模式
        self.is_rotating = False  # 是否处于旋转模式

        # 标注ID计数器
        self.annotation_id_counter = 0

        # 裁剪相关
        self.crop_rect = QRect()
        self.start_crop_pos = None

        # 旋转相关
        self.rotation_angle = 0  # 总旋转角度
        self.start_rotation_angle = 0  # 开始旋转时的角度
        self.rotation_center = QPointF()
        self.last_mouse_pos = QPointF()

        # 启用鼠标跟踪
        self.setMouseTracking(True)

    def load_image(self, image_path):
        self.pixmap = QPixmap(image_path)
        self.original_pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            QMessageBox.critical(self, "加载图片失败", f"无法加载图片: {image_path}")
        else:
            self.annotations.clear()
            self.index = 1
            self.id_position = None
            self.id_annotation = None
            self.fixed_y_position = None
            self.fixed_y_mark_position = None
            self.is_fixed_y_confirmed = False
            self.is_id_mode = False  # 重置ID模式
            self.is_cropping = False
            self.is_rotating = False
            self.crop_rect = QRect()
            self.rotation_angle = 0
            # self.setFixedSize(self.pixmap.size())  # 移除设置固定大小
            self.repaint()
            self.annotations_changed.emit()

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_num_digits(self, num_digits):
        self.num_digits = num_digits

    def set_current_annotation_color(self, color):
        self.current_annotation_color = color

    def set_text_size(self, size):
        self.text_size = size
        self.repaint()  # 即时更新字体大小

    def set_id_text(self, id_text):
        self.id_text = "ID:" + id_text
        self.repaint()

    def set_id_text_size(self, size):
        """设置ID字体大小"""
        self.id_text_size = size
        self.repaint()  # 即时更新ID字体大小

    def set_id_color(self, color):
        """设置ID颜色"""
        self.id_color = color

    def undo_last_annotation(self):
        if self.annotations:
            last_annotation = self.annotations.pop()
            if last_annotation[3] == 'normal':
                self.index -= 1
            self.repaint()
            self.annotations_changed.emit()

    def add_annotation(self, position, annotation_type='normal'):
        if annotation_type == 'normal':
            annotation_text = f"{self.prefix}{str(self.index).zfill(self.num_digits)}"
            self.index += 1
            # 使用固定Y坐标
            if self.fixed_y_mode and self.fixed_y_position is not None:
                position.setY(self.fixed_y_position)
            # 分配唯一ID
            annotation_id = self.annotation_id_counter
            self.annotation_id_counter += 1
            self.annotations.append((annotation_id, annotation_text, position, annotation_type, self.current_annotation_color))
        elif annotation_type == 'id':
            annotation_text = self.id_text
            self.id_position = position
            self.id_annotation = (annotation_text, position)
        else:
            annotation_text = "Unknown"
        self.annotations_changed.emit()
        self.repaint()

    def set_fixed_y_mode(self, mode: bool):
        self.fixed_y_mode = mode
        if not mode:
            self.fixed_y_mark_position = None
            self.is_fixed_y_confirmed = False
        self.repaint()

    def set_fixed_y_position(self, y_position: int):
        self.fixed_y_position = y_position
        self.fixed_y_mark_position = y_position  # 显示固定的Y轴标记
        self.repaint()

    def confirm_fixed_y_position(self):
        if self.fixed_y_mark_position is not None:
            self.is_fixed_y_confirmed = True  # 确认水平线
            self.repaint()

    def rotate_image(self, angle):
        if self.pixmap:
            # 创建旋转变换
            transform = QTransform()
            transform.rotate(angle)
            # 应用旋转到 pixmap
            rotated_pixmap = self.pixmap.transformed(transform, Qt.SmoothTransformation)
            self.pixmap = rotated_pixmap
            # 更新旋转角度
            self.rotation_angle = (self.rotation_angle + angle) % 360
            # 不再设置固定大小
            # self.setFixedSize(self.pixmap.size())
            self.repaint()

    def start_manual_rotation(self):
        if self.pixmap:
            self.is_rotating = True
            self.setCursor(Qt.OpenHandCursor)

    def stop_manual_rotation(self):
        self.is_rotating = False
        self.setCursor(Qt.ArrowCursor)
        self.repaint()

    def start_crop(self):
        if self.pixmap:
            self.is_cropping = True
            self.crop_rect = QRect()
            self.repaint()

    def crop_image(self):
        if self.pixmap and not self.crop_rect.isNull():
            # 计算实际裁剪区域
            crop_rect = self.crop_rect.normalized()
            # 逆向缩放裁剪区域到原始图片尺寸
            label_rect = self.rect()
            pixmap_width = self.pixmap.width()
            pixmap_height = self.pixmap.height()
            scale_x = pixmap_width / label_rect.width()
            scale_y = pixmap_height / label_rect.height()
            scaled_crop_rect = QRect(
                int(crop_rect.left() * scale_x),
                int(crop_rect.top() * scale_y),
                int(crop_rect.width() * scale_x),
                int(crop_rect.height() * scale_y)
            )

            # 更新图片
            self.pixmap = self.pixmap.copy(scaled_crop_rect)
            # 更新标注位置
            new_annotations = []
            for annotation in self.annotations:
                aid, text, pos, annotation_type, color = annotation
                new_pos = QPointF(pos.x() - scaled_crop_rect.left(), pos.y() - scaled_crop_rect.top())
                new_annotations.append((aid, text, new_pos, annotation_type, color))
            self.annotations = new_annotations
            if self.id_annotation:
                text, pos = self.id_annotation
                new_pos = QPointF(pos.x() - scaled_crop_rect.left(), pos.y() - scaled_crop_rect.top())
                self.id_annotation = (text, new_pos)
            self.is_cropping = False
            self.crop_rect = QRect()
            self.repaint()
            self.annotations_changed.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap:
            painter = QPainter(self)

            # 获取绘制区域的大小
            label_rect = self.rect()

            # 缩放图片以适应标签大小
            scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap_rect = scaled_pixmap.rect()
            pixmap_rect.moveCenter(label_rect.center())

            # 绘制图片
            painter.drawPixmap(pixmap_rect.topLeft(), scaled_pixmap)

            # 计算缩放比例
            scale_x = scaled_pixmap.width() / self.pixmap.width()
            scale_y = scaled_pixmap.height() / self.pixmap.height()

            # 绘制注释
            for annotation_id, annotation, pos, annotation_type, color in self.annotations:
                if annotation_type == 'normal':
                    pen_color = color
                    font_size = int(self.text_size * scale_x)
                else:
                    continue  # 忽略其他类型

                painter.setPen(QPen(pen_color, 3))
                font = QFont('Arial', font_size)
                painter.setFont(font)
                draw_x = pixmap_rect.left() + pos.x() * scale_x
                draw_y = pixmap_rect.top() + pos.y() * scale_y
                painter.drawText(QPointF(draw_x, draw_y), annotation)

            # 绘制ID标注
            if self.id_annotation is not None:
                annotation_text, pos = self.id_annotation
                pen_color = self.id_color
                font_size = int(self.id_text_size * scale_x)
                painter.setPen(QPen(pen_color, 3))
                font = QFont('Arial', font_size)
                painter.setFont(font)
                draw_x = pixmap_rect.left() + pos.x() * scale_x
                draw_y = pixmap_rect.top() + pos.y() * scale_y
                painter.drawText(QPointF(draw_x, draw_y), annotation_text)

            # 绘制固定水平线
            if self.fixed_y_mark_position is not None:
                pen_color = Qt.red if not self.is_fixed_y_confirmed else Qt.green
                painter.setPen(QPen(pen_color, 2, Qt.DashLine))  # 红色虚线或绿色虚线
                y_pos = pixmap_rect.top() + self.fixed_y_mark_position * scale_y
                painter.drawLine(pixmap_rect.left(), y_pos, pixmap_rect.right(), y_pos)

            # 绘制裁剪矩形
            if self.is_cropping and not self.crop_rect.isNull():
                painter.setPen(QPen(Qt.blue, 2, Qt.DashLine))
                painter.drawRect(self.crop_rect)

    def mousePressEvent(self, event):
        if self.pixmap and event.button() == Qt.LeftButton:
            if self.is_rotating:
                self.last_mouse_pos = event.pos()
            elif self.is_cropping:
                self.start_crop_pos = event.pos()
                self.crop_rect = QRect(self.start_crop_pos, QSize())
            else:
                label_rect = self.rect()
                pixmap_rect = self.pixmap.rect()
                scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixmap_rect = scaled_pixmap.rect()
                pixmap_rect.moveCenter(label_rect.center())

                if pixmap_rect.contains(event.pos()):
                    # 将鼠标位置转换为图片坐标
                    scale_x = self.pixmap.width() / scaled_pixmap.width()
                    scale_y = self.pixmap.height() / scaled_pixmap.height()
                    adjusted_x = (event.x() - pixmap_rect.left()) * scale_x
                    adjusted_y = (event.y() - pixmap_rect.top()) * scale_y
                    adjusted_point = QPointF(adjusted_x, adjusted_y)

                    if self.fixed_y_mode and not self.is_fixed_y_confirmed:
                        # 确认水平线位置
                        self.set_fixed_y_position(adjusted_y)
                        self.confirm_fixed_y_position()
                    elif self.is_id_mode:
                        # 如果处于ID绘制模式，移动ID位置
                        self.id_position = adjusted_point
                        self.id_annotation = (self.id_text, self.id_position)
                        self.annotations_changed.emit()
                        self.repaint()
                    else:
                        # 普通标注模式下绘制标注文字
                        self.add_annotation(adjusted_point, annotation_type='normal')

    def mouseMoveEvent(self, event):
        if self.pixmap:
            if self.is_rotating:
                # 计算旋转角度
                current_pos = event.pos()
                center = QPointF(self.width() / 2, self.height() / 2)
                angle1 = math.degrees(math.atan2(self.last_mouse_pos.y() - center.y(), self.last_mouse_pos.x() - center.x()))
                angle2 = math.degrees(math.atan2(current_pos.y() - center.y(), current_pos.x() - center.x()))
                delta_angle = angle2 - angle1
                self.rotate_image(delta_angle)
                self.last_mouse_pos = current_pos
            elif self.is_cropping and self.start_crop_pos:
                self.crop_rect = QRect(self.start_crop_pos, event.pos()).normalized()
                self.repaint()
            elif self.fixed_y_mode and not self.is_fixed_y_confirmed:
                # 更新固定水平线位置
                label_rect = self.rect()
                pixmap_rect = self.pixmap.rect()
                scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixmap_rect = scaled_pixmap.rect()
                pixmap_rect.moveCenter(label_rect.center())

                if pixmap_rect.contains(event.pos()):
                    scale_y = self.pixmap.height() / scaled_pixmap.height()
                    adjusted_y = (event.y() - pixmap_rect.top()) * scale_y
                    self.fixed_y_mark_position = adjusted_y
                    self.repaint()

    def mouseReleaseEvent(self, event):
        if self.is_rotating and event.button() == Qt.LeftButton:
            self.stop_manual_rotation()
        if self.is_cropping and event.button() == Qt.LeftButton:
            self.start_crop_pos = None

    def save_image(self, save_path):
        if not self.pixmap:
            QMessageBox.critical(self, "保存失败", "没有可保存的图像。")
            return

        # 创建一个与当前 pixmap 大小相同的新 QPixmap
        pixmap_copy = QPixmap(self.pixmap.size())
        pixmap_copy.fill(Qt.transparent)
        painter = QPainter(pixmap_copy)
        painter.drawPixmap(0, 0, self.pixmap)

        # 绘制注释
        for annotation_id, annotation, pos, annotation_type, color in self.annotations:
            if annotation_type == 'normal':
                pen_color = color
                font_size = self.text_size
            else:
                continue  # 忽略其他类型

            painter.setPen(QPen(pen_color, 3))
            font = QFont('Arial', font_size)
            painter.setFont(font)
            painter.drawText(pos, annotation)

        # 绘制ID标注
        if self.id_annotation is not None:
            annotation_text, pos = self.id_annotation
            pen_color = self.id_color
            font_size = self.id_text_size
            painter.setPen(QPen(pen_color, 3))
            font = QFont('Arial', font_size)
            painter.setFont(font)
            painter.drawText(pos, annotation_text)

        # 绘制固定水平线（如果需要）
        if self.fixed_y_mark_position is not None:
            pen_color = Qt.red if not self.is_fixed_y_confirmed else Qt.green
            painter.setPen(QPen(pen_color, 2, Qt.DashLine))
            y_pos = self.fixed_y_mark_position
            painter.drawLine(0, y_pos, self.pixmap.width(), y_pos)

        painter.end()

        if pixmap_copy.save(save_path):
            pass  # 不再弹出保存成功的信息
        else:
            QMessageBox.critical(self, "保存失败", f"无法保存图片至 {save_path}")


class ImageAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Annotator")
        self.setGeometry(100, 100, 1600, 1000)  # 增加窗口大小

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)  # 增加边距

        # 左侧控制面板
        self.control_panel = QGroupBox("控制面板")
        self.control_layout = QVBoxLayout()
        self.control_panel.setLayout(self.control_layout)
        self.main_layout.addWidget(self.control_panel, 0)

        # 图像显示区域
        self.image_label = ImageLabel(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area, 1)  # 让图像区域占据更多空间

        # 添加控件到控制面板
        self.add_controls_to_panel()

        # 缩略图列表
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setIconSize(QSize(100, 100))  # 使用 QSize
        self.thumbnail_list.setFixedWidth(200)
        self.main_layout.addWidget(self.thumbnail_list, 0)

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
        self.size_spinbox.setValue(20)
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
        self.prefix_input.setText(self.image_label.prefix)
        self.num_digits_label = QLabel("序号位数:")
        self.num_digits_spinbox = QSpinBox()
        self.num_digits_spinbox.setRange(1, 10)
        self.num_digits_spinbox.setValue(self.image_label.num_digits)
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
        self.id_size_spinbox.setValue(20)
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

        # 旋转和裁剪功能
        self.rotate_left_button = QPushButton("左旋转")
        self.rotate_left_button.setToolTip("向左旋转图片")
        self.rotate_right_button = QPushButton("右旋转")
        self.rotate_right_button.setToolTip("向右旋转图片")
        self.manual_rotate_button = QPushButton("手动旋转")
        self.manual_rotate_button.setToolTip("手动旋转图片")
        self.start_crop_button = QPushButton("开始裁剪")
        self.start_crop_button.setToolTip("开始裁剪模式")
        self.crop_button = QPushButton("裁剪")
        self.crop_button.setToolTip("执行裁剪")
        grid.addWidget(self.rotate_left_button, 7, 0)
        grid.addWidget(self.rotate_right_button, 7, 1)
        grid.addWidget(self.manual_rotate_button, 8, 0)
        grid.addWidget(self.start_crop_button, 9, 0)
        grid.addWidget(self.crop_button, 9, 1)

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
        self.start_crop_button.clicked.connect(self.start_crop)
        self.crop_button.clicked.connect(self.crop_image)
        self.image_label.annotations_changed.connect(self.update_annotations_list)
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
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        # 询问用户选择打开文件还是文件夹
        msg_box = QMessageBox()
        msg_box.setWindowTitle("选择文件或文件夹")
        msg_box.setText("请选择打开方式：")
        open_files_button = msg_box.addButton("打开文件", QMessageBox.AcceptRole)
        open_folder_button = msg_box.addButton("打开文件夹", QMessageBox.AcceptRole)
        cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)
        msg_box.exec_()

        if msg_box.clickedButton() == open_files_button:
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
                options=options
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
        for filename in os.listdir(folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                image_path = os.path.join(folder, filename)
                self.image_paths.append(image_path)
        self.populate_thumbnail_list(self.image_paths)
        if self.image_paths:
            self.load_image(self.image_paths[0])

    def populate_thumbnail_list(self, image_paths):
        self.thumbnail_list.clear()
        for image_path in image_paths:
            pixmap = QPixmap(image_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item = QListWidgetItem(QIcon(pixmap), os.path.basename(image_path))
            self.thumbnail_list.addItem(item)

    def load_image(self, image_path):
        try:
            self.current_image_path = image_path
            self.image_label.load_image(image_path)
            self.status_bar.showMessage(f"已加载图片: {os.path.basename(image_path)}", 5000)
            self.mode_label.setText("当前模式：普通标注")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时出错：{str(e)}")

    def load_selected_image(self, item):
        image_name = item.text()
        for image_path in self.image_paths:
            if image_name == os.path.basename(image_path):
                self.load_image(image_path)
                break

    def undo_annotation(self):
        self.image_label.undo_last_annotation()
        self.status_bar.showMessage("撤销最后一个标注", 3000)

    def save_image(self):
        if self.current_image_path:
            save_path = self.current_image_path
            self.image_label.save_image(save_path)
            self.status_bar.showMessage(f"图片已保存至 {save_path}", 5000)
        else:
            QMessageBox.warning(self, "保存失败", "没有加载任何图片。")

    def choose_current_annotation_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_label.set_current_annotation_color(color)
            self.status_bar.showMessage(f"当前标注颜色已设置为: {color.name()}", 3000)

    def set_text_size(self):
        size = self.size_spinbox.value()
        self.image_label.set_text_size(size)
        self.status_bar.showMessage(f"标注字体大小已设置为: {size}", 3000)

    def set_prefix(self, prefix):
        self.image_label.set_prefix(prefix)
        self.status_bar.showMessage(f"标注前缀已设置为: {prefix}", 3000)

    def set_num_digits(self, value):
        self.image_label.set_num_digits(value)
        self.status_bar.showMessage(f"序号位数已设置为: {value}", 3000)

    def add_id(self):
        id_text = self.id_input.text().strip()
        if id_text:
            # 切换到ID绘制模式，同时关闭固定水平绘制模式
            self.image_label.set_id_text(id_text)
            self.image_label.is_id_mode = True
            self.image_label.set_fixed_y_mode(False)
            self.status_bar.showMessage("进入ID绘制模式", 3000)
            self.mode_label.setText("当前模式：ID标注")
        else:
            QMessageBox.warning(self, "无效输入", "ID 不能为空。")

    def set_id_text_size(self):
        size = self.id_size_spinbox.value()
        self.image_label.set_id_text_size(size)
        self.status_bar.showMessage(f"ID字体大小已设置为: {size}", 3000)

    def choose_id_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_label.set_id_color(color)
            self.status_bar.showMessage(f"ID标注颜色已设置为: {color.name()}", 3000)

    def start_fixed_y_mode(self):
        if not self.image_label.fixed_y_mode:
            # 进入固定水平绘制模式时，确保退出ID绘制模式
            if self.image_label.is_id_mode:
                self.image_label.is_id_mode = False
                self.status_bar.showMessage("退出ID绘制模式", 3000)
                self.mode_label.setText("当前模式：固定水平绘制")
            self.image_label.set_fixed_y_mode(True)
            self.status_bar.showMessage("进入固定水平绘制模式", 3000)
            self.mode_label.setText("当前模式：固定水平绘制")
        else:
            QMessageBox.information(self, "已在固定模式", "当前已处于固定水平绘制模式。")

    def modify_fixed_y_mode(self):
        if self.image_label.fixed_y_mode:
            # 允许修改水平线
            self.image_label.is_fixed_y_confirmed = False
            self.status_bar.showMessage("固定水平线已置为可修改", 3000)
            self.mode_label.setText("当前模式：固定水平绘制 (可修改)")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")

    def close_fixed_y_mode(self):
        if self.image_label.fixed_y_mode:
            self.image_label.set_fixed_y_mode(False)
            self.status_bar.showMessage("固定水平绘制模式已关闭", 3000)
            self.mode_label.setText("当前模式：普通标注")
        else:
            QMessageBox.warning(self, "未开启固定模式", "请先开启固定水平绘制模式。")

    def end_id_mode(self):
        if self.image_label.is_id_mode:
            self.image_label.is_id_mode = False
            self.status_bar.showMessage("退出ID绘制模式", 3000)
            self.mode_label.setText("当前模式：普通标注")
        else:
            QMessageBox.warning(self, "未开启ID模式", "当前未处于ID绘制模式。")

    def delete_id(self):
        if self.image_label.id_annotation is not None:
            self.image_label.id_annotation = None
            self.image_label.id_position = None
            self.image_label.repaint()
            self.update_annotations_list()
            self.status_bar.showMessage("ID标注已删除", 3000)
        else:
            QMessageBox.warning(self, "没有ID标注", "当前没有ID标注可以删除。")

    def update_annotations_list(self):
        self.annotations_list.clear()
        # 添加普通标注
        for annotation_id, text, pos, annotation_type, color in self.image_label.annotations:
            if annotation_type == 'normal':
                item_text = f"{text} at ({pos.x():.1f}, {pos.y():.1f})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, annotation_id)
                self.annotations_list.addItem(item)
        # 添加ID标注
        if self.image_label.id_annotation is not None:
            text, pos = self.image_label.id_annotation
            item_text = f"ID: {text} at ({pos.x():.1f}, {pos.y():.1f})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, 'id')
            self.annotations_list.addItem(item)

    def delete_selected_annotation(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先在标注列表中选择要删除的标注。")
            return
        for item in selected_items:
            annotation_id = item.data(Qt.UserRole)
            if annotation_id == 'id':
                # 删除ID标注
                self.image_label.id_annotation = None
                self.image_label.id_position = None
            else:
                # 删除普通标注
                for i, (aid, text, pos, annotation_type, color) in enumerate(self.image_label.annotations):
                    if aid == annotation_id:
                        del self.image_label.annotations[i]
                        break
        self.image_label.repaint()
        self.update_annotations_list()
        self.status_bar.showMessage("选中的标注已删除", 3000)

    def change_selected_annotation_color(self):
        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "未选择标注", "请先在标注列表中选择要更改颜色的标注。")
            return
        color = QColorDialog.getColor()
        if color.isValid():
            for item in selected_items:
                annotation_id = item.data(Qt.UserRole)
                for i, (aid, text, pos, annotation_type, _) in enumerate(self.image_label.annotations):
                    if aid == annotation_id:
                        self.image_label.annotations[i] = (aid, text, pos, annotation_type, color)
                        break
            self.image_label.repaint()
            self.status_bar.showMessage("选中标注的颜色已更改", 3000)

    def rotate_image(self, angle):
        self.image_label.rotate_image(angle)
        self.status_bar.showMessage(f"图片已旋转{angle}度", 3000)

    def start_manual_rotate(self):
        self.image_label.start_manual_rotation()
        self.status_bar.showMessage("进入手动旋转模式，拖动鼠标旋转图片", 3000)
        self.mode_label.setText("当前模式：手动旋转")

    def start_crop(self):
        self.image_label.start_crop()
        self.status_bar.showMessage("进入裁剪模式，请拖动鼠标选择裁剪区域", 3000)

    def crop_image(self):
        if self.image_label.is_cropping:
            self.image_label.crop_image()
            self.status_bar.showMessage("图片已裁剪", 3000)
        else:
            QMessageBox.warning(self, "未进入裁剪模式", "请先点击“开始裁剪”按钮进入裁剪模式。")


def main():
    app = QApplication(sys.argv)
    main_window = ImageAnnotator()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
