import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, 
    QFileDialog, QMessageBox, QLabel, QScrollArea, QListWidget, QListWidgetItem, 
    QColorDialog, QSpinBox, QLineEdit, QInputDialog, QGroupBox, QGridLayout,
    QStatusBar
)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, QPoint, QSize
import os

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.annotations = []  # 存储 (text, position, type) 三元组
        self.prefix = "BR"
        self.index = 1
        self.text_color = QColor(0, 0, 0)
        self.text_size = 20
        self.id_text = ""
        self.id_position = None  # 存储ID绘制的位置
        self.id_text_size = 20  # ID字体大小
        self.id_color = QColor(0, 0, 0)  # ID颜色

        # 固定水平绘制相关变量
        self.fixed_y_mode = False
        self.fixed_y_position = None
        self.fixed_y_mark_position = None
        self.is_fixed_y_confirmed = False  # 标志位：是否确定水平线

        # 增加标志位用于区分绘制模式
        self.is_id_mode = False  # 是否为ID绘制模式

    def load_image(self, image_path):
        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            QMessageBox.critical(self, "加载图片失败", f"无法加载图片: {image_path}")
        else:
            self.annotations.clear()
            self.index = 1
            self.id_position = None
            self.fixed_y_position = None
            self.fixed_y_mark_position = None
            self.is_fixed_y_confirmed = False
            self.is_id_mode = False  # 重置ID模式
            self.repaint()

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_text_color(self, color):
        self.text_color = color

    def set_text_size(self, size):
        self.text_size = size

    def set_id_text(self, id_text):
        self.id_text = id_text
        self.repaint()

    def set_id_text_size(self, size):
        """设置ID字体大小"""
        self.id_text_size = size

    def set_id_color(self, color):
        """设置ID颜色"""
        self.id_color = color

    def undo_last_annotation(self):
        if self.annotations:
            last_annotation = self.annotations.pop()
            if last_annotation[2] == 'normal':
                self.index -= 1
            self.repaint()

    def add_annotation(self, position, annotation_type='normal'):
        if annotation_type == 'normal':
            annotation_text = f"{self.prefix}{str(self.index).zfill(2)}"
            self.index += 1
        elif annotation_type == 'id':
            annotation_text = self.id_text
        else:
            annotation_text = "Unknown"

        # 根据模式确定是否使用固定Y轴坐标
        if self.fixed_y_mode and self.fixed_y_position is not None and annotation_type == 'normal':
            position.setY(self.fixed_y_position)

        self.annotations.append((annotation_text, position, annotation_type))
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap:
            painter = QPainter(self)
            label_rect = self.rect()

            # 缩放图像以适应标签大小
            scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            draw_rect = scaled_pixmap.rect()
            draw_rect.moveCenter(label_rect.center())
            painter.drawPixmap(draw_rect.topLeft(), scaled_pixmap)

            # 计算缩放因子
            scale_factor = draw_rect.width() / self.pixmap.width()

            # 绘制注释
            for annotation, pos, annotation_type in self.annotations:
                if annotation_type == 'normal':
                    pen_color = self.text_color
                    font_size = int(self.text_size * scale_factor)
                elif annotation_type == 'id':
                    pen_color = self.id_color
                    font_size = int(self.id_text_size * scale_factor)
                else:
                    pen_color = self.text_color
                    font_size = int(self.text_size * scale_factor)

                painter.setPen(QPen(pen_color, 3))
                font = QFont('Arial', font_size)
                painter.setFont(font)
                draw_x = int(pos.x() * scale_factor) + draw_rect.left()
                draw_y = int(pos.y() * scale_factor) + draw_rect.top()
                painter.drawText(draw_x, draw_y, annotation)

            # 绘制固定水平线
            if self.fixed_y_mark_position is not None:
                pen_color = Qt.red if not self.is_fixed_y_confirmed else Qt.green
                painter.setPen(QPen(pen_color, 2, Qt.DashLine))  # 红色虚线或绿色虚线
                y_pos_scaled = int(self.fixed_y_mark_position * scale_factor) + draw_rect.top()
                painter.drawLine(draw_rect.left(), y_pos_scaled, draw_rect.right(), y_pos_scaled)

    def mousePressEvent(self, event):
        if self.pixmap and event.button() == Qt.LeftButton:
            pos = event.pos()
            label_rect = self.rect()
            scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_width = scaled_pixmap.width()
            scaled_height = scaled_pixmap.height()
            offset_x = (label_rect.width() - scaled_width) / 2
            offset_y = (label_rect.height() - scaled_height) / 2

            if (offset_x <= pos.x() <= offset_x + scaled_width) and (offset_y <= pos.y() <= offset_y + scaled_height):
                adjusted_x = int((pos.x() - offset_x) * self.pixmap.width() / scaled_width)
                adjusted_y = int((pos.y() - offset_y) * self.pixmap.height() / scaled_height)

                if self.is_id_mode:
                    # 如果处于ID绘制模式，只绘制ID
                    self.id_position = QPoint(adjusted_x, adjusted_y)
                    self.add_annotation(self.id_position, annotation_type='id')
                else:
                    # 普通标注模式下绘制标注文字
                    if self.fixed_y_mode and not self.is_fixed_y_confirmed:
                        # 当水平线未确认时，设置新的Y坐标并显示水平线
                        self.set_fixed_y_position(adjusted_y)
                    else:
                        self.add_annotation(QPoint(adjusted_x, adjusted_y), annotation_type='normal')

    def save_image(self, save_path):
        if not self.pixmap:
            QMessageBox.critical(self, "保存失败", "没有可保存的图像。")
            return

        # 创建一个与原始图像大小相同的新 QPixmap
        pixmap_copy = QPixmap(self.pixmap.size())
        pixmap_copy.fill(Qt.white)
        painter = QPainter(pixmap_copy)
        painter.drawPixmap(0, 0, self.pixmap)

        # 绘制注释
        for annotation, pos, annotation_type in self.annotations:
            if annotation_type == 'normal':
                pen_color = self.text_color
                font_size = self.text_size
            elif annotation_type == 'id':
                pen_color = self.id_color
                font_size = self.id_text_size
            else:
                pen_color = self.text_color
                font_size = self.text_size

            painter.setPen(QPen(pen_color, 3))
            font = QFont('Arial', font_size)
            painter.setFont(font)
            painter.drawText(pos, annotation)

        painter.end()

        if pixmap_copy.save(save_path):
            QMessageBox.information(self, "保存成功", f"图片已成功保存至 {save_path}")
        else:
            QMessageBox.critical(self, "保存失败", f"无法保存图片至 {save_path}")

class ImageAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Annotator")
        self.setGeometry(100, 100, 1600, 1000)  # 增加窗口大小

        # 设置应用程序图标（可选）
        # self.setWindowIcon(QIcon('icons/icon.png'))  # 不使用图标，可以注释掉或移除

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

        # 设置颜色按钮和大小选择
        self.color_button = QPushButton("设置颜色")
        self.color_button.setToolTip("设置标注颜色")
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(10, 100)
        self.size_spinbox.setValue(20)
        self.size_spinbox.setToolTip("设置标注字体大小")
        grid.addWidget(self.color_button, 2, 0)
        grid.addWidget(QLabel("字体大小:"), 2, 1)
        grid.addWidget(self.size_spinbox, 2, 2)

        # 设置标注前缀按钮
        self.prefix_button = QPushButton("设置前缀")
        self.prefix_button.setToolTip("设置标注前缀")
        grid.addWidget(self.prefix_button, 3, 0, 1, 2)

        # ID设置组
        self.id_group = QGroupBox("ID设置")
        id_layout = QVBoxLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("输入ID")
        self.add_id_button = QPushButton("添加ID")
        self.add_id_button.setToolTip("添加ID标注 (Ctrl+I)")
        self.add_id_button.setShortcut("Ctrl+I")
        self.id_size_spinbox = QSpinBox()
        self.id_size_spinbox.setRange(10, 100)
        self.id_size_spinbox.setValue(20)
        self.id_size_spinbox.setToolTip("设置ID字体大小")
        self.id_color_button = QPushButton("设置ID颜色")
        self.id_color_button.setToolTip("设置ID标注颜色")
        self.end_id_button = QPushButton("结束ID绘制 (Ctrl+E)")
        self.end_id_button.setToolTip("结束ID绘制模式")
        self.end_id_button.setShortcut("Ctrl+E")
        
        id_layout.addWidget(self.id_input)
        id_layout.addWidget(self.add_id_button)
        id_layout.addWidget(QLabel("ID字体大小:"))
        id_layout.addWidget(self.id_size_spinbox)
        id_layout.addWidget(self.id_color_button)
        id_layout.addWidget(self.end_id_button)
        self.id_group.setLayout(id_layout)
        grid.addWidget(self.id_group, 4, 0, 1, 2)

        # 固定水平绘制相关按钮
        self.fixed_y_group = QGroupBox("固定水平绘制")
        fixed_y_layout = QVBoxLayout()

        # 添加“开始固定水平绘制”按钮
        self.start_fixed_y_button = QPushButton("开始固定水平绘制 (Ctrl+F)")
        self.start_fixed_y_button.setToolTip("开始固定水平绘制模式")
        self.start_fixed_y_button.setShortcut("Ctrl+F")

        self.confirm_fixed_y_button = QPushButton("确定水平线 (Ctrl+C)")
        self.confirm_fixed_y_button.setToolTip("确定当前水平线位置")
        self.confirm_fixed_y_button.setShortcut("Ctrl+C")
        self.modify_fixed_y_button = QPushButton("修改水平线 (Ctrl+M)")
        self.modify_fixed_y_button.setToolTip("修改固定水平线位置")
        self.modify_fixed_y_button.setShortcut("Ctrl+M")
        self.close_fixed_y_button = QPushButton("关闭固定绘制 (Ctrl+Q)")
        self.close_fixed_y_button.setToolTip("关闭固定水平绘制模式")
        self.close_fixed_y_button.setShortcut("Ctrl+Q")
        fixed_y_layout.addWidget(self.start_fixed_y_button)
        fixed_y_layout.addWidget(self.confirm_fixed_y_button)
        fixed_y_layout.addWidget(self.modify_fixed_y_button)
        fixed_y_layout.addWidget(self.close_fixed_y_button)
        self.fixed_y_group.setLayout(fixed_y_layout)
        grid.addWidget(self.fixed_y_group, 5, 0, 1, 2)

        # 当前模式标签
        self.mode_label = QLabel("当前模式：普通标注")
        self.mode_label.setFont(QFont('Arial', 12, QFont.Bold))
        self.mode_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.mode_label, 6, 0, 1, 2)

        # 保存图片按钮
        self.save_button = QPushButton("保存图片 (Ctrl+P)")
        self.save_button.setToolTip("保存当前标注的图片")
        self.save_button.setShortcut("Ctrl+P")
        grid.addWidget(self.save_button, 7, 0, 1, 2)

        # 添加网格布局到控制面板
        self.control_layout.addLayout(grid)
        self.control_layout.addStretch()

    def connect_signals(self):
        self.open_button.clicked.connect(self.open_file_or_folder)
        self.undo_button.clicked.connect(self.undo_annotation)
        self.save_button.clicked.connect(self.save_image)
        self.color_button.clicked.connect(self.choose_color)
        self.size_spinbox.valueChanged.connect(self.set_text_size)
        self.prefix_button.clicked.connect(self.set_prefix)
        self.thumbnail_list.itemClicked.connect(self.load_selected_image)
        self.add_id_button.clicked.connect(self.add_id)
        self.id_size_spinbox.valueChanged.connect(self.set_id_text_size)
        self.id_color_button.clicked.connect(self.choose_id_color)
        self.start_fixed_y_button.clicked.connect(self.start_fixed_y_mode)
        self.confirm_fixed_y_button.clicked.connect(self.confirm_fixed_y)
        self.modify_fixed_y_button.clicked.connect(self.modify_fixed_y_mode)
        self.close_fixed_y_button.clicked.connect(self.close_fixed_y_mode)
        self.end_id_button.clicked.connect(self.end_id_mode)

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
        try:
            # 允许用户选择多个文件或一个文件夹
            files, _ = QFileDialog.getOpenFileNames(
                self, "选择图片或文件夹", "",
                "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
                options=options
            )
            if files:
                # 检查是否选择的是一个文件夹
                if len(files) == 1 and os.path.isdir(files[0]):
                    folder = files[0]
                    self.load_images_from_folder(folder)
                else:
                    self.image_paths = files
                    self.populate_thumbnail_list(self.image_paths)
                    if self.image_paths:
                        self.load_image(self.image_paths[0])
            else:
                QMessageBox.information(self, "没有选择文件", "请选择一个文件或文件夹。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件或文件夹时出错：{str(e)}")

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
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存图片", self.current_image_path,
                "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;BMP Files (*.bmp);;All Files (*)"
            )
            if save_path:
                self.image_label.save_image(save_path)
                self.status_bar.showMessage(f"图片已保存至 {save_path}", 5000)
        else:
            QMessageBox.warning(self, "保存失败", "没有加载任何图片。")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_label.set_text_color(color)
            self.status_bar.showMessage(f"标注颜色已设置为: {color.name()}", 3000)

    def set_text_size(self):
        size = self.size_spinbox.value()
        self.image_label.set_text_size(size)
        self.status_bar.showMessage(f"标注字体大小已设置为: {size}", 3000)

    def set_prefix(self):
        prefix, ok = QInputDialog.getText(self, "设置前缀", "输入标注前缀:")
        if ok and prefix:
            self.image_label.set_prefix(prefix)
            self.status_bar.showMessage(f"标注前缀已设置为: {prefix}", 3000)
        elif ok:
            QMessageBox.warning(self, "无效输入", "前缀不能为空。")

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

    def confirm_fixed_y(self):
        if self.image_label.fixed_y_mark_position is not None:
            self.image_label.confirm_fixed_y_position()
            self.status_bar.showMessage("固定水平线已确认", 3000)
        else:
            QMessageBox.warning(self, "未设置水平线", "请先点击图像设置固定水平线的位置。")

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

def main():
    app = QApplication(sys.argv)
    main_window = ImageAnnotator()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()











