import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                             QLabel, QHBoxLayout, QScrollArea, QListWidget, QListWidgetItem, QColorDialog, QSpinBox,
                             QLineEdit, QInputDialog, QProgressBar, QSizePolicy)
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QPen, QColor, QFont, QImage
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal
from PIL import Image, ImageDraw, ImageFont
import os
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, Alignment
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.utils.units import pixels_to_EMU
from openpyxl.drawing.xdr import XDRPositiveSize2D
import zipfile
import py7zr  # For .7z files
import rarfile  # For .rar files
import tarfile  # For .tgz files
import tempfile
import shutil  # To remove temp folder
from PIL import Image as PILImage  # 使用PIL来获取图片的宽高


class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.drawing = False
        self.annotations = []
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

    def start_drawing(self):
        self.drawing = True
        self.setCursor(Qt.CrossCursor)

    def stop_drawing(self):
        self.drawing = False
        self.setCursor(Qt.ArrowCursor)

    def undo_last_annotation(self):
        if self.annotations:
            self.annotations.pop()
            self.index -= 1
            self.repaint()

    def add_annotation(self, position):
        annotation_text = f"{self.prefix}{str(self.index).zfill(2)}"
        self.index += 1
        # 根据模式确定是否使用固定Y轴坐标
        if self.fixed_y_mode and self.fixed_y_position is not None:
            position.setY(self.fixed_y_position)

        self.annotations.append((annotation_text, position))
        self.repaint()

    def set_fixed_y_mode(self, mode: bool):
        self.fixed_y_mode = mode
        self.fixed_y_mark_position = None
        self.is_fixed_y_confirmed = False  # 当开启或修改时，未确定新的水平线

    def set_fixed_y_position(self, y_position: int):
        self.fixed_y_position = y_position
        self.fixed_y_mark_position = y_position  # 显示固定的Y轴标记
        self.repaint()

    def confirm_fixed_y_position(self):
        self.is_fixed_y_confirmed = True  # 确认水平线
        self.repaint()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap:
            painter = QPainter(self)
            label_rect = self.rect()
            scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            draw_rect = scaled_pixmap.rect()
            draw_rect.moveCenter(label_rect.center())
            painter.drawPixmap(draw_rect.topLeft(), scaled_pixmap)

            # Draw annotations
            scale_factor = draw_rect.width() / self.pixmap.width()
            painter.setPen(QPen(self.text_color, 3))
            font = QFont('Arial', int(self.text_size * scale_factor))
            painter.setFont(font)
            for annotation, pos in self.annotations:
                draw_x = int(pos.x() * scale_factor) + draw_rect.left()
                draw_y = int(pos.y() * scale_factor) + draw_rect.top()
                painter.drawText(draw_x, draw_y, annotation)

            # 绘制固定水平线
            if self.fixed_y_mark_position is not None:
                pen_color = Qt.red if not self.is_fixed_y_confirmed else Qt.green
                painter.setPen(QPen(pen_color, 2, Qt.DashLine))  # 红色虚线或绿色虚线
                y_pos_scaled = int(self.fixed_y_mark_position * scale_factor) + draw_rect.top()
                painter.drawLine(draw_rect.left(), y_pos_scaled, draw_rect.right(), y_pos_scaled)

            # Draw ID text if exists
            if self.id_text and self.id_position:
                painter.setPen(QPen(self.id_color if hasattr(self, 'id_color') else self.text_color, 3))
                id_font = QFont('Arial', int(self.id_text_size * scale_factor))
                painter.setFont(id_font)
                draw_x = int(self.id_position.x() * scale_factor) + draw_rect.left()
                draw_y = int(self.id_position.y() * scale_factor) + draw_rect.top()
                painter.drawText(draw_x, draw_y, self.id_text)

    def mousePressEvent(self, event):
        if self.pixmap and self.drawing:
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
                    self.repaint()
                else:
                    # 普通标注模式下绘制标注文字
                    if self.fixed_y_mode and not self.is_fixed_y_confirmed:
                        # 当水平线未确认时，设置新的Y坐标并显示水平线
                        self.set_fixed_y_position(adjusted_y)
                    elif self.fixed_y_mode and self.is_fixed_y_confirmed:
                        # 当水平线已确认时，点击位置绘制文字
                        self.add_annotation(QPoint(adjusted_x, adjusted_y))
                    else:
                        self.add_annotation(QPoint(adjusted_x, adjusted_y))

    def save_image(self, save_path):
        if not self.pixmap:
            QMessageBox.critical(self, "保存失败", "没有可保存的图像。")
            return

        # Create a new pixmap the size of the original image
        pixmap_copy = QPixmap(self.pixmap.size())
        pixmap_copy.fill(Qt.white)
        painter = QPainter(pixmap_copy)
        painter.drawPixmap(0, 0, self.pixmap)

        # Draw annotations on the copy
        painter.setPen(QPen(self.text_color, 3))
        font = QFont('Arial', self.text_size)
        painter.setFont(font)
        for annotation, pos in self.annotations:
            painter.drawText(pos, annotation)

        # Draw ID text if exists
        if self.id_text and self.id_position:
            painter.setPen(QPen(self.id_color if hasattr(self, 'id_color') else self.text_color, 3))
            id_font = QFont('Arial', self.id_text_size)
            painter.setFont(id_font)
            painter.drawText(self.id_position, self.id_text)

        painter.end()

        if pixmap_copy.save(save_path):
            QMessageBox.information(self, "保存成功", f"图片已成功保存至 {save_path}")
        else:
            QMessageBox.critical(self, "保存失败", f"无法保存图片至 {save_path}")


class ImageAnnotator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Image Annotator")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        self.left_layout = QVBoxLayout()
        self.layout.addLayout(self.left_layout)

        self.image_label = ImageLabel(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        self.left_layout.addWidget(self.scroll_area)

        self.open_button = QPushButton("打开文件/文件夹")
        self.start_button = QPushButton("开始绘制")
        self.stop_button = QPushButton("停止绘制")
        self.undo_button = QPushButton("删除最后一个标注")
        self.save_button = QPushButton("保存图片")
        self.color_button = QPushButton("设置颜色")
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(10, 100)
        self.size_spinbox.setValue(20)
        self.prefix_button = QPushButton("设置标注前缀")

        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("输入ID")
        self.add_id_button = QPushButton("添加")

        # 新增的控件，用于设置ID文字大小和ID颜色
        self.id_size_spinbox = QSpinBox()
        self.id_size_spinbox.setRange(10, 100)
        self.id_size_spinbox.setValue(20)
        self.id_color_button = QPushButton("设置ID颜色")

        # 固定水平绘制相关按钮
        self.fixed_y_button = QPushButton("开启固定水平绘制")
        self.confirm_fixed_y_button = QPushButton("确定水平线")
        self.modify_fixed_y_button = QPushButton("修改水平线")
        self.close_fixed_y_button = QPushButton("关闭固定水平绘制")
        self.end_id_button = QPushButton("结束ID绘制")  # 新增的按钮，用于手动结束ID绘制
        self.mode_label = QLabel("当前模式：普通模式")  # 显示当前模式

        self.left_layout.addWidget(self.open_button)
        self.left_layout.addWidget(self.start_button)
        self.left_layout.addWidget(self.stop_button)
        self.left_layout.addWidget(self.undo_button)
        self.left_layout.addWidget(self.color_button)
        self.left_layout.addWidget(self.size_spinbox)
        self.left_layout.addWidget(self.prefix_button)
        self.left_layout.addWidget(QLabel("ID设置"))
        self.left_layout.addWidget(self.id_input)
        self.left_layout.addWidget(self.id_size_spinbox)  # 添加ID字体大小设置
        self.left_layout.addWidget(self.add_id_button)
        self.left_layout.addWidget(self.id_color_button)  # 添加ID颜色按钮
        self.left_layout.addWidget(self.end_id_button)  # 手动结束ID绘制的按钮
        self.left_layout.addWidget(self.fixed_y_button)
        self.left_layout.addWidget(self.confirm_fixed_y_button)
        self.left_layout.addWidget(self.modify_fixed_y_button)
        self.left_layout.addWidget(self.close_fixed_y_button)  # 添加关闭固定水平按钮
        self.left_layout.addWidget(self.mode_label)  # 显示当前绘制模式
        self.left_layout.addWidget(self.save_button)

        self.thumbnail_list = QListWidget()
        self.layout.addWidget(self.thumbnail_list)

        self.open_button.clicked.connect(self.open_file_or_folder)
        self.start_button.clicked.connect(self.start_drawing)
        self.stop_button.clicked.connect(self.stop_drawing)
        self.undo_button.clicked.connect(self.undo_annotation)
        self.save_button.clicked.connect(self.save_image)
        self.color_button.clicked.connect(self.choose_color)
        self.size_spinbox.valueChanged.connect(self.set_text_size)
        self.prefix_button.clicked.connect(self.set_prefix)
        self.thumbnail_list.itemClicked.connect(self.load_selected_image)
        self.add_id_button.clicked.connect(self.add_id)
        self.id_size_spinbox.valueChanged.connect(self.set_id_text_size)  # 设置ID字体大小
        self.id_color_button.clicked.connect(self.choose_id_color)  # 设置ID颜色按钮的事件
        self.fixed_y_button.clicked.connect(self.toggle_fixed_y_mode)
        self.confirm_fixed_y_button.clicked.connect(self.confirm_fixed_y)
        self.modify_fixed_y_button.clicked.connect(self.modify_fixed_y_mode)
        self.close_fixed_y_button.clicked.connect(self.close_fixed_y_mode)  # 关闭固定水平绘制模式
        self.end_id_button.clicked.connect(self.end_id_mode)  # 结束ID绘制模式

        self.image_paths = []
        self.current_image_path = ""

    def open_file_or_folder(self):
        options = QFileDialog.Options()
        try:
            files, _ = QFileDialog.getOpenFileNames(self, "选择图片或文件夹", "",
                                                    "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
                                                    options=options)
            if files:
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
            pixmap = QPixmap(image_path).scaled(100, 100, Qt.KeepAspectRatio)
            icon = QIcon(pixmap)
            item = QListWidgetItem()
            item.setIcon(icon)
            item.setText(os.path.basename(image_path))
            self.thumbnail_list.addItem(item)

    def load_image(self, image_path):
        try:
            self.current_image_path = image_path
            self.image_label.load_image(image_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载图片时出错：{str(e)}")

    def load_selected_image(self, item):
        image_name = item.text()
        for image_path in self.image_paths:
            if image_name in image_path:
                self.load_image(image_path)
                break

    def start_drawing(self):
        self.image_label.start_drawing()

    def stop_drawing(self):
        self.image_label.stop_drawing()

    def undo_annotation(self):
        self.image_label.undo_last_annotation()

    def save_image(self):
        if self.current_image_path:
            self.image_label.save_image(self.current_image_path)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_label.set_text_color(color)

    def set_text_size(self):
        size = self.size_spinbox.value()
        self.image_label.set_text_size(size)

    def set_prefix(self):
        prefix, ok = QInputDialog.getText(self, "设置前缀", "输入标注前缀:")
        if ok and prefix:
            self.image_label.set_prefix(prefix)
        elif ok:
            QMessageBox.warning(self, "无效输入", "前缀不能为空。")

    def add_id(self):
        id_text = self.id_input.text().strip()
        if id_text:
            self.image_label.set_id_text(id_text)
            self.image_label.is_id_mode = True  # 切换到ID绘制模式
            self.update_mode_label("ID模式")  # 更新提示为ID模式
        else:
            QMessageBox.warning(self, "无效输入", "ID 不能为空。")

    def set_id_text_size(self):
        size = self.id_size_spinbox.value()
        self.image_label.set_id_text_size(size)

    def choose_id_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.image_label.set_id_color(color)

    def toggle_fixed_y_mode(self):
        self.image_label.set_fixed_y_mode(True)
        self.update_mode_label("固定模式")

    def confirm_fixed_y(self):
        if self.image_label.fixed_y_mark_position is not None:
            self.image_label.confirm_fixed_y_position()

    def modify_fixed_y_mode(self):
        self.image_label.set_fixed_y_mode(True)
        self.image_label.is_fixed_y_confirmed = False  # 允许修改水平线
        self.update_mode_label("固定模式")

    def close_fixed_y_mode(self):
        self.image_label.set_fixed_y_mode(False)  # 关闭固定水平绘制
        self.update_mode_label("普通模式")  # 更新提示为普通模式

    def end_id_mode(self):
        self.image_label.is_id_mode = False  # 手动关闭ID绘制模式
        self.update_mode_label("普通模式")  # 更新提示为普通模式

    def update_mode_label(self, mode):
        """更新UI上显示的模式标签"""
        self.mode_label.setText(f"当前模式：{mode}")


class DecompressRenameWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("解压改名")
        self.setGeometry(150, 150, 600, 400)

        layout = QVBoxLayout()
        self.select_file_button = QPushButton("选择压缩文件")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("输入文件名前缀，默认：BRSF10")
        self.process_button = QPushButton("解压并改名")
        self.progress_label = QLabel("")
        self.progress_bar = QProgressBar()

        layout.addWidget(self.select_file_button)
        layout.addWidget(self.prefix_input)
        layout.addWidget(self.process_button)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.select_file_button.clicked.connect(self.select_file)
        self.process_button.clicked.connect(self.decompress_and_rename)

        self.selected_file = ""
        self.image_paths = []

    def select_file(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(
            self, 
            "选择压缩文件", 
            "", 
            "Compressed Files (*.zip *.7z *.rar *.tgz);;All Files (*)",  # Updated to include .zip, .7z, .rar, .tgz files
            options=options
        )
        if file:
            self.selected_file = file
            self.progress_label.setText(f"已选择文件: {os.path.basename(file)}")

    def decompress_and_rename(self):
        try:
            prefix = self.prefix_input.text().strip() or "BRSF10"

            if not self.selected_file:
                QMessageBox.warning(self, "错误", "请先选择一个有效的压缩文件！")
                return

            base_name = os.path.splitext(os.path.basename(self.selected_file))[0]
            final_dir_base = os.path.join(os.path.dirname(self.selected_file), f"{base_name}-解压修改")
            final_dir=final_dir_base
            counter = 1
            while os.path.exists(final_dir):
                final_dir = f"{final_dir_base}{counter}"
                counter += 1
            os.makedirs(final_dir, exist_ok=True)

            # 使用临时文件夹作为缓存
            with tempfile.TemporaryDirectory() as temp_dir:
                # 根据文件类型进行解压
                if self.selected_file.lower().endswith('.zip'):
                    self.extract_zip(temp_dir)
                elif self.selected_file.lower().endswith('.7z'):
                    self.extract_7z(temp_dir)
                elif self.selected_file.lower().endswith('.rar'):
                    self.extract_rar(temp_dir)
                elif self.selected_file.lower().endswith('.tgz'):
                    self.extract_tgz(temp_dir)
                else:
                    QMessageBox.warning(self, "错误", "不支持的文件格式！")
                    return

                if not self.image_paths:
                    QMessageBox.warning(self, "错误", "解压后未找到任何图片文件。")
                    return

                self.progress_bar.setMaximum(len(self.image_paths))
                for index, image_path in enumerate(self.image_paths):
                    new_name = f"{prefix}{str(index + 1).zfill(2)}.jpg"
                    new_path = os.path.join(final_dir, new_name)

                    try:
                        image = Image.open(image_path)
                        original_format = image.format.lower()

                        # 如果图片不是 .jpg 格式，转换为 .jpg
                        if original_format != 'jpeg':
                            image = image.convert('RGB')
                        image.save(new_path, format='JPEG', quality=95)
                        self.adjust_image_size(new_path)

                        # 处理完成后删除临时文件
                        os.remove(image_path)

                        self.progress_label.setText(f"处理文件: {new_name}")
                        self.progress_bar.setValue(index + 1)

                    except Exception as e:
                        QMessageBox.critical(self, "错误", f"处理文件 {os.path.basename(image_path)} 时出错：{str(e)}")

            QMessageBox.information(self, "完成", f"文件已成功解压并改名至文件夹: {final_dir}")

        except Exception as e:
            QMessageBox.critical(self, "意外错误", f"解压和重命名过程中出现意外错误：{str(e)}")

    def adjust_image_size(self, image_path):
        """Adjust the image size to be less than or equal to 800KB if needed."""
        max_size_kb = 800
        image_size_kb = os.path.getsize(image_path) / 1024  # Get size in KB

        if image_size_kb > max_size_kb:
            quality = 95
            while image_size_kb > max_size_kb and quality > 10:
                quality -= 5
                with Image.open(image_path) as img:
                    img.save(image_path, format='JPEG', quality=quality)
                image_size_kb = os.path.getsize(image_path) / 1024

    def extract_zip(self, extract_dir):
        with zipfile.ZipFile(self.selected_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            self.image_paths = [os.path.join(extract_dir, name) for name in zip_ref.namelist()
                                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

    def extract_7z(self, extract_dir):
        try:
            with py7zr.SevenZipFile(self.selected_file, mode='r') as archive:
                archive.extractall(path=extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in archive.getnames()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .7z 文件时出错: {str(e)}")

    def extract_rar(self, extract_dir):
        try:
            with rarfile.RarFile(self.selected_file, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in rar_ref.namelist()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .rar 文件时出错: {str(e)}")

    def extract_tgz(self, extract_dir):
        try:
            with tarfile.open(self.selected_file, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, member.name) for member in tar_ref.getmembers()
                                    if member.name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .tgz 文件时出错: {str(e)}")

class ExcelWorker(QThread): 
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, folder, output_path, image_height_cm, buffer_percentage_width, buffer_percentage_height):
        super().__init__()
        self.folder = folder
        self.output_path = output_path
        self.image_height_cm = image_height_cm
        self.buffer_percentage_width = buffer_percentage_width  # 单元格宽度缓冲百分比
        self.buffer_percentage_height = buffer_percentage_height  # 单元格高度缓冲百分比

    def run(self):
        try:
            # 获取文件夹中的所有图片文件
            image_files = [f for f in os.listdir(self.folder)
                           if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

            if not image_files:
                self.error.emit("文件夹中没有找到图片文件！")
                return

            # 使用 openpyxl 创建 Excel 工作簿
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "图片列表"

            # 设置表头
            sheet["A1"] = "ID"
            sheet["B1"] = "Picture"
            sheet["A1"].font = Font(bold=True)
            sheet["B1"].font = Font(bold=True)
            sheet["A1"].alignment = Alignment(horizontal='center', vertical='center')
            sheet["B1"].alignment = Alignment(horizontal='center', vertical='center')

            # 设置ID列的宽度为100/7字符单位（约等于100像素）
            sheet.column_dimensions['A'].width = 100 / 7

            # 设置进度条的最大值
            total_files = len(image_files)
            if total_files == 0:
                self.error.emit("没有找到图片文件！")
                return

            self.progress.emit(0)  # 初始进度为 0
            progress_step = 100 / total_files  # 每步的进度增量

            # 缓冲比例计算
            buffer_factor_width = 1 + (self.buffer_percentage_width / 100)
            buffer_factor_height = 1 + (self.buffer_percentage_height / 100)

            # 目标行高：用户输入的高度转换为点数
            desired_row_height_cm = self.image_height_cm
            desired_row_height_points = desired_row_height_cm * 28.3465  # 1cm约等于28.35点
            cm_to_pixels = 37.795275591  # 1厘米 ≈ 37.795275591像素

            # 第一遍遍历所有图片，计算调整后的宽度，并找到最大宽度
            max_new_width = 0
            new_widths = []  # 存储每张图片的调整后宽度
            for image_name in image_files:
                image_path = os.path.join(self.folder, image_name)
                if not os.path.isfile(image_path):
                    self.error.emit(f"文件未找到: {image_path}")
                    return

                try:
                    with PILImage.open(image_path) as im:
                        original_width, original_height = im.size

                    # 计算图片高度与单元格高度一致的缩放比例
                    new_height = desired_row_height_cm * cm_to_pixels
                    new_width = (original_width * new_height) / original_height
                    new_widths.append(new_width)

                    if new_width > max_new_width:
                        max_new_width = new_width
                except Exception as e:
                    self.error.emit(f"处理图片 {image_name} 时出错: {str(e)}")
                    return

            # 设置“图片”列的宽度基于最宽的图片和缓冲比例
            # 改进列宽转换公式：像素 = 宽度 * 7.58
            sheet.column_dimensions['B'].width = (max_new_width * buffer_factor_width) / 7.58

            # 插入图片和 ID
            for i, image_name in enumerate(image_files):
                image_id = os.path.splitext(image_name)[0]
                image_path = os.path.join(self.folder, image_name)

                if not os.path.isfile(image_path):
                    self.error.emit(f"文件未找到: {image_path}")
                    return

                # 插入 ID
                cell = sheet.cell(row=i + 2, column=1)
                cell.value = image_id
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center', vertical='center')

                try:
                    # 使用PIL获取图片的原始宽高
                    with PILImage.open(image_path) as im:
                        original_width, original_height = im.size

                    # 计算图片高度与单元格高度一致的缩放比例
                    new_height = desired_row_height_cm * cm_to_pixels
                    new_width = new_widths[i]  # 使用预先计算的宽度

                    # 调整单元格高度，应用缓冲比例
                    sheet.row_dimensions[i + 2].height = desired_row_height_points * buffer_factor_height

                    # 插入图片到单元格
                    img = OpenpyxlImage(image_path)
                    img.width = new_width
                    img.height = new_height

                    # 设置图片在单元格中居中
                    col_letter = 'B'
                    # 改进列宽转换公式：像素 = 宽度 * 7.58
                    cell_width_pixels = max_new_width * buffer_factor_width   # 转换为像素，增加缓冲
                    cell_height_pixels = desired_row_height_cm * cm_to_pixels * buffer_factor_height  # 考虑缓冲

                    # 计算偏移量以实现居中
                    offset_x = (cell_width_pixels - new_width) / 2
                    offset_y = (cell_height_pixels - new_height) / 2

                    # 将像素偏移量转换为 EMU
                    emu_offset_x = pixels_to_EMU(offset_x)
                    emu_offset_y = pixels_to_EMU(offset_y)

                    # 使用 AnchorMarker 进行图片插入和偏移
                    marker = AnchorMarker(col=1, colOff=emu_offset_x, row=i + 1, rowOff=emu_offset_y)
                    img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(pixels_to_EMU(new_width), pixels_to_EMU(new_height)))
                    sheet.add_image(img)

                    # 更新进度条
                    self.progress.emit(int((i + 1) * progress_step))

                except Exception as insert_error:
                    error_message = f"插入图片时发生错误: {insert_error}"
                    self.error.emit(error_message)
                    return

            # 保存并关闭工作簿
            try:
                workbook.save(self.output_path)
                self.finished.emit(f"Excel 已生成并保存到 {self.output_path}！")
            except Exception as save_error:
                self.error.emit(f"保存 Excel 文件时出错: {save_error}")

        except Exception as e:
            error_message = f"生成 Excel 时出错: {str(e)}"
            self.error.emit(error_message)

class ConvertDocWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("转换文档")
        self.setGeometry(200, 200, 600, 400)

        # 创建布局
        main_layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        # 创建按钮和进度条
        self.select_folder_button = QPushButton("选择文件夹")
        self.select_folder_button.setFixedHeight(30)
        self.process_button = QPushButton("生成Excel")
        self.process_button.setFixedHeight(30)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # 创建用于输入图片高度的文本框，并设置默认值为6.7
        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("请输入图片高度（单位：cm）")
        self.height_input.setFixedHeight(30)
        self.height_input.setText("6.7")  # 设置默认值

        # 创建用于输入单元格宽度缓冲百分比的文本框，并设置默认值为10
        self.buffer_width_input = QLineEdit()
        self.buffer_width_input.setPlaceholderText("请输入单元格宽度比图片大的百分比（例如 10 表示 10%）")
        self.buffer_width_input.setFixedHeight(30)
        self.buffer_width_input.setText("10")  # 设置默认值

        # 创建用于输入单元格高度缓冲百分比的文本框，并设置默认值为10
        self.buffer_height_input = QLineEdit()
        self.buffer_height_input.setPlaceholderText("请输入单元格高度比图片大的百分比（例如 10 表示 10%）")
        self.buffer_height_input.setFixedHeight(30)
        self.buffer_height_input.setText("10")  # 设置默认值

        # 创建用于显示已选择文件夹的标签
        self.selected_folder_label = QLabel("")
        self.selected_folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 添加按钮到水平布局
        button_layout.addWidget(self.select_folder_button)
        button_layout.addWidget(self.process_button)

        # 添加控件到主布局
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.height_input)
        main_layout.addWidget(self.buffer_width_input)   # 添加宽度缓冲输入框
        main_layout.addWidget(self.buffer_height_input)  # 添加高度缓冲输入框
        main_layout.addWidget(self.selected_folder_label)
        main_layout.addWidget(self.progress_bar)

        # 设置中央部件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # 连接信号和槽
        self.select_folder_button.clicked.connect(self.select_folder)
        self.process_button.clicked.connect(self.start_conversion)

        self.selected_folder = ""
        self.worker = None

    def select_folder(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", options=options)
        if folder:
            self.selected_folder = folder
            self.selected_folder_label.setText(f"已选择文件夹: {self.selected_folder}")
            QMessageBox.information(self, "文件夹选择", f"您已选择文件夹: {self.selected_folder}")

    def start_conversion(self):
        if not self.selected_folder:
            QMessageBox.warning(self, "警告", "请先选择一个文件夹！")
            return

        # 获取用户输入的图片高度
        try:
            image_height_cm = float(self.height_input.text())
            if image_height_cm <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的图片高度（单位：cm）！")
            return

        # 获取用户输入的单元格宽度缓冲百分比
        try:
            buffer_percentage_width = float(self.buffer_width_input.text())
            if buffer_percentage_width < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的单元格宽度缓冲百分比（非负数）！")
            return

        # 获取用户输入的单元格高度缓冲百分比
        try:
            buffer_percentage_height = float(self.buffer_height_input.text())
            if buffer_percentage_height < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的单元格高度缓冲百分比（非负数）！")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        parent_directory = os.path.dirname(self.selected_folder)
        excel_path = os.path.join(parent_directory, "converted.xlsx")

        try:
            self.worker = ExcelWorker(
                self.selected_folder, 
                excel_path, 
                image_height_cm, 
                buffer_percentage_width, 
                buffer_percentage_height
            )
            self.worker.progress.connect(self.update_progress)
            self.worker.finished.connect(self.show_finished)
            self.worker.finished.connect(lambda: self.progress_bar.setVisible(False))
            self.worker.error.connect(self.show_error)
            self.worker.error.connect(lambda: self.progress_bar.setVisible(False))
            self.worker.start()
        except Exception as thread_error:
            QMessageBox.critical(self, "错误", f"启动线程时出错: {thread_error}")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_finished(self, message):
        QMessageBox.information(self, "完成", message)

    def show_error(self, error_message):
        QMessageBox.critical(self, "错误", error_message)
        
        
        
        
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("主界面")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.decompress_button = QPushButton("解压改名")
        self.draw_text_button = QPushButton("绘制文字")
        self.convert_doc_button = QPushButton("转换文档")

        layout.addWidget(self.decompress_button)
        layout.addWidget(self.draw_text_button)
        layout.addWidget(self.convert_doc_button)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.decompress_button.clicked.connect(self.open_decompress_window)
        self.draw_text_button.clicked.connect(self.open_draw_text_window)
        self.convert_doc_button.clicked.connect(self.open_convert_doc_window)

    def open_decompress_window(self):
        self.decompress_window = DecompressRenameWindow()
        self.decompress_window.show()

    def open_draw_text_window(self):
        self.draw_text_window = ImageAnnotator()
        self.draw_text_window.show()

    def open_convert_doc_window(self):
        self.convert_doc_window = ConvertDocWindow()
        self.convert_doc_window.show()


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
