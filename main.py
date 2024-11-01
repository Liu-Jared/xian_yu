import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                             QLabel, QHBoxLayout, QScrollArea, QListWidget, QListWidgetItem, QColorDialog, QSpinBox,
                             QLineEdit, QInputDialog, QProgressBar, QSizePolicy)
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QPen, QColor, QFont,QImage
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal
from PIL import Image, ImageDraw, ImageFont
import os
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, Alignment
import zipfile
import py7zr  # For .7z files
import rarfile  # For .rar files
import tarfile  # For .tgz files



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

    def load_image(self, image_path):
        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            QMessageBox.critical(self, "加载图片失败", f"无法加载图片: {image_path}")
        else:
            self.annotations.clear()
            self.index = 1
            self.repaint()

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_text_color(self, color):
        self.text_color = color

    def set_text_size(self, size):
        self.text_size = size

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
        self.annotations.append((annotation_text, position))
        self.repaint()

    def set_id_text(self, id_text):
        self.id_text = f"ID: {id_text}"
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

            # Draw ID text if exists
            if self.id_text:
                id_position = draw_rect.bottomLeft() + QPoint(10, -10)
                painter.drawText(int(id_position.x()), int(id_position.y()), self.id_text)

    def mousePressEvent(self, event):
        if self.drawing and self.pixmap:
            pos = event.pos()
            label_rect = self.rect()
            scaled_pixmap = self.pixmap.scaled(label_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_width = scaled_pixmap.width()
            scaled_height = scaled_pixmap.height()
            offset_x = (label_rect.width() - scaled_width) / 2
            offset_y = (label_rect.height() - scaled_height) / 2

            # Check if click is within the displayed image area
            if (offset_x <= pos.x() <= offset_x + scaled_width) and (offset_y <= pos.y() <= offset_y + scaled_height):
                adjusted_x = int((pos.x() - offset_x) * self.pixmap.width() / scaled_width)
                adjusted_y = int((pos.y() - offset_y) * self.pixmap.height() / scaled_height)
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
        if self.id_text:
            id_position = pixmap_copy.rect().bottomLeft() + QPoint(10, -10)
            painter.drawText(id_position, self.id_text)

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

        self.left_layout.addWidget(self.open_button)
        self.left_layout.addWidget(self.start_button)
        self.left_layout.addWidget(self.stop_button)
        self.left_layout.addWidget(self.undo_button)
        self.left_layout.addWidget(self.color_button)
        self.left_layout.addWidget(self.size_spinbox)
        self.left_layout.addWidget(self.prefix_button)
        self.left_layout.addWidget(self.id_input)
        self.left_layout.addWidget(self.add_id_button)
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

        self.image_paths = []
        self.current_image_path = ""

    def open_file_or_folder(self):
        options = QFileDialog.Options()
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
        self.current_image_path = image_path
        self.image_label.load_image(image_path)

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
        else:
            QMessageBox.warning(self, "无效输入", "ID 不能为空。")






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
            extract_dir_base = os.path.join(os.path.dirname(self.selected_file), f"{base_name}-解压修改")
            extract_dir = extract_dir_base

            counter = 1
            while os.path.exists(extract_dir):
                extract_dir = f"{extract_dir_base}{counter}"
                counter += 1

            os.makedirs(extract_dir, exist_ok=True)

            # Determine the file type and use appropriate extraction method
            if self.selected_file.lower().endswith('.zip'):
                self.extract_zip(extract_dir)
            elif self.selected_file.lower().endswith('.7z'):
                self.extract_7z(extract_dir)
            elif self.selected_file.lower().endswith('.rar'):
                self.extract_rar(extract_dir)
            elif self.selected_file.lower().endswith('.tgz'):
                self.extract_tgz(extract_dir)
            else:
                QMessageBox.warning(self, "错误", "不支持的文件格式！")
                return

            if not self.image_paths:
                QMessageBox.warning(self, "错误", "解压后未找到任何图片文件。")
                return

            self.progress_bar.setMaximum(len(self.image_paths))
            for index, image_path in enumerate(self.image_paths):
                new_name = f"{prefix}{str(index + 1).zfill(2)}.png"
                new_path = os.path.join(extract_dir, new_name)

                try:
                    image = Image.open(image_path)
                    draw = ImageDraw.Draw(image)
                    text = f"ID: {new_name.split('.')[0]}"

                    # Use a larger font size
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)  # Specify the desired font size
                    except IOError:
                        font = ImageFont.load_default()  # Fallback to default font if truetype font is not found

                    text_position = (10, image.height - 50)  # Adjusted position to fit larger text
                    draw.text(text_position, text, fill="black", font=font)

                    image.save(new_path, format='PNG')
                    if os.path.exists(new_path):
                        os.remove(image_path)

                    self.progress_label.setText(f"处理文件: {new_name}")
                    self.progress_bar.setValue(index + 1)

                except Exception as e:
                    QMessageBox.critical(self, "错误", f"处理文件 {os.path.basename(image_path)} 时出错：{str(e)}")

            QMessageBox.information(self, "完成", f"文件已成功解压并改名至文件夹: {extract_dir}")

        except Exception as e:
            QMessageBox.critical(self, "意外错误", f"解压和重命名过程中出现意外错误：{str(e)}")

    def extract_zip(self, extract_dir):
        """Extract .zip files using zipfile."""
        with zipfile.ZipFile(self.selected_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            self.image_paths = [os.path.join(extract_dir, name) for name in zip_ref.namelist()
                                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

    def extract_7z(self, extract_dir):
        """Extract .7z files using py7zr."""
        try:
            with py7zr.SevenZipFile(self.selected_file, mode='r') as archive:
                archive.extractall(path=extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in archive.getnames()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .7z 文件时出错: {str(e)}")
            print(f"Error extracting .7z file: {str(e)}")  # Debug output

    def extract_rar(self, extract_dir):
        """Extract .rar files using rarfile."""
        try:
            with rarfile.RarFile(self.selected_file, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in rar_ref.namelist()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .rar 文件时出错: {str(e)}")
            print(f"Error extracting .rar file: {str(e)}")  # Debug output

    def extract_tgz(self, extract_dir):
        """Extract .tgz files using tarfile."""
        try:
            with tarfile.open(self.selected_file, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, member.name) for member in tar_ref.getmembers()
                                    if member.name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .tgz 文件时出错: {str(e)}")
            print(f"Error extracting .tgz file: {str(e)}")  # Debug output




class ExcelWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, folder, output_path):
        super().__init__()
        self.folder = folder
        self.output_path = output_path

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

            # 设置进度条的最大值
            total_files = len(image_files)
            if total_files == 0:
                self.error.emit("没有找到图片文件！")
                return

            self.progress.emit(0)  # 初始进度为 0
            progress_step = 100 / total_files  # 每步的进度增量

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

                # 设置字体加粗和居中
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center', vertical='center')

                try:
                    # 插入图片到单元格并调整大小
                    img = OpenpyxlImage(image_path)  # 获取图片
                    img.width, img.height = (300, 250)  # 设置图片大小

                    # 设置列宽和行高
                    sheet.column_dimensions['B'].width = 50  # 设置列宽
                    sheet.row_dimensions[i + 2].height = 250  # 设置行高

                    # 插入图片到指定单元格
                    img.anchor = f"B{i + 2}"
                    sheet.add_image(img)

                    # 更新进度条
                    self.progress.emit(int((i + 1) * progress_step))  # 进度更新

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
        self.select_folder_button.setFixedHeight(30)  # 控制按钮高度
        self.process_button = QPushButton("生成Excel")
        self.process_button.setFixedHeight(30)  # 控制按钮高度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)  # 初始状态下隐藏进度条

        # 创建用于显示已选择文件夹的标签
        self.selected_folder_label = QLabel("")
        self.selected_folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)  # 控制标签的大小策略

        # 添加按钮到水平布局
        button_layout.addWidget(self.select_folder_button)
        button_layout.addWidget(self.process_button)

        # 添加控件到主布局
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.selected_folder_label)  # 显示选择的文件夹路径
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
            self.selected_folder_label.setText(f"已选择文件夹: {self.selected_folder}")  # 显示已选择的文件夹
            QMessageBox.information(self, "文件夹选择", f"您已选择文件夹: {self.selected_folder}")

    def start_conversion(self):
        if not self.selected_folder:
            QMessageBox.warning(self, "警告", "请先选择一个文件夹！")
            return

        self.progress_bar.setVisible(True)  # 开始任务时显示进度条
        self.progress_bar.setValue(0)  # 初始化进度条为 0

        parent_directory = os.path.dirname(self.selected_folder)
        excel_path = os.path.join(parent_directory, "converted.xlsx")

        # 确保在启动线程前正确设置路径和参数
        try:
            self.worker = ExcelWorker(self.selected_folder, excel_path)
            self.worker.progress.connect(self.update_progress)
            self.worker.finished.connect(self.show_finished)
            self.worker.finished.connect(lambda: self.progress_bar.setVisible(False))  # 完成后隐藏进度条
            self.worker.error.connect(self.show_error)
            self.worker.error.connect(lambda: self.progress_bar.setVisible(False))  # 出错后隐藏进度条
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