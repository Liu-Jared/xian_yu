import sys
import os
import logging
import tempfile
import shutil
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
    QLabel, QHBoxLayout, QProgressBar, QSizePolicy, QLineEdit, QRadioButton, QButtonGroup, QGroupBox
)
from PIL import Image as PILImage
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, Alignment
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.utils.units import pixels_to_EMU
from openpyxl.drawing.xdr import XDRPositiveSize2D

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ExcelWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    skipped = pyqtSignal(str)

    def __init__(self, folder, output_path, use_height, size_cm, buffer_percentage_width, buffer_percentage_height):
        super().__init__()
        self.folder = folder
        self.output_path = output_path
        self.use_height = use_height
        self.size_cm = size_cm
        self.buffer_percentage_width = buffer_percentage_width
        self.buffer_percentage_height = buffer_percentage_height

    def convert_mpo_to_jpg(self, image_path):
        """将 MPO 格式的图像转换为 JPEG 格式，并返回新的图像路径。"""
        try:
            with PILImage.open(image_path) as im:
                if hasattr(im, 'n_frames') and im.n_frames > 1:
                    im.seek(0)  # 选择第一个帧
                rgb_im = im.convert('RGB')
                new_image_path = os.path.splitext(image_path)[0] + '_converted.jpg'
                rgb_im.save(new_image_path, format='JPEG')
                logging.info(f"已将 {image_path} 转换为 {new_image_path}")
                return new_image_path
        except Exception as e:
            logging.error(f"转换图像 {image_path} 时出错: {e}")
            return None

    def run(self):
        skipped_files = []
        processed_images = []
        new_sizes = []
        temp_dir = tempfile.mkdtemp()

        try:
            allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}
            image_files = [
                f for f in os.listdir(self.folder)
                if os.path.isfile(os.path.join(self.folder, f)) and
                os.path.splitext(f.lower())[1] in allowed_extensions
            ]

            logging.info(f"找到 {len(image_files)} 张支持的图片文件。")

            if not image_files:
                self.error.emit("文件夹中没有找到支持的图片文件！")
                return

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "图片列表"

            sheet["A1"] = "ID"
            sheet["B1"] = "Picture"
            sheet["A1"].font = Font(bold=True)
            sheet["B1"].font = Font(bold=True)
            sheet["A1"].alignment = Alignment(horizontal='center', vertical='center')
            sheet["B1"].alignment = Alignment(horizontal='center', vertical='center')
            sheet.column_dimensions['A'].width = 100 / 7

            total_files = len(image_files)
            self.progress.emit(0)
            progress_step = 100 / total_files if total_files > 0 else 100

            buffer_factor_width = 1 + (self.buffer_percentage_width / 100)
            buffer_factor_height = 1 + (self.buffer_percentage_height / 100)

            cm_to_pixels = 37.795275591
            desired_size_pixels = self.size_cm * cm_to_pixels
            desired_size_points = self.size_cm * 28.3465

            max_new_size = 0
            for image_name in image_files:
                image_path = os.path.join(self.folder, image_name)
                logging.info(f"正在处理图片: {image_name}")

                try:
                    with PILImage.open(image_path) as im:
                        original_width, original_height = im.size
                        image_format = im.format
                        if image_format not in ['JPEG', 'PNG']:
                            if image_format == 'MPO':
                                converted_path = self.convert_mpo_to_jpg(image_path)
                                if converted_path and os.path.isfile(converted_path):
                                    image_path = converted_path
                                    image_format = 'JPEG'
                                else:
                                    logging.warning(f"无法转换图像 {image_name}，跳过。格式: {image_format}")
                                    skipped_files.append(image_name)
                                    continue
                            else:
                                logging.warning(f"图像格式不支持 {image_name}，跳过。格式: {image_format}")
                                skipped_files.append(image_name)
                                continue
                except Exception as e:
                    logging.warning(f"无法打开图像文件 {image_name}，跳过。错误: {str(e)}")
                    skipped_files.append(image_name)
                    continue

                if self.use_height:
                    new_height = desired_size_pixels
                    new_width = (original_width * new_height) / original_height
                else:
                    new_width = desired_size_pixels
                    new_height = (original_height * new_width) / original_width

                new_sizes.append((new_width, new_height))
                processed_images.append(image_path)
                if self.use_height:
                    max_new_size = max(max_new_size, new_width)
                else:
                    max_new_size = max(max_new_size, new_height)

            if not new_sizes:
                self.error.emit("没有有效的图片被处理！")
                return

            if self.use_height:
                sheet.column_dimensions['B'].width = (max_new_size * buffer_factor_width) / 7.58
            else:
                sheet.column_dimensions['B'].width = (self.size_cm * buffer_factor_width * cm_to_pixels) / 7.58

            processed_files = 0
            for i, image_path in enumerate(processed_images):
                image_name = os.path.basename(image_path)
                image_id = os.path.splitext(image_name)[0]

                cell = sheet.cell(row=i + 2, column=1)
                cell.value = image_id
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center', vertical='center')

                try:
                    new_width, new_height = new_sizes[i]
                    if self.use_height:
                        sheet.row_dimensions[i + 2].height = desired_size_points * buffer_factor_height
                    else:
                        sheet.row_dimensions[i + 2].height = (new_height / cm_to_pixels) * 28.3465 * buffer_factor_height

                    img = OpenpyxlImage(image_path)
                    img.width = new_width
                    img.height = new_height

                    if self.use_height:
                        cell_width_pixels = max_new_size * buffer_factor_width
                        cell_height_pixels = self.size_cm * cm_to_pixels * buffer_factor_height
                    else:
                        cell_width_pixels = self.size_cm * cm_to_pixels * buffer_factor_width
                        cell_height_pixels = max_new_size * buffer_factor_height

                    offset_x = (cell_width_pixels - new_width) / 2
                    offset_y = (cell_height_pixels - new_height) / 2

                    emu_offset_x = pixels_to_EMU(offset_x)
                    emu_offset_y = pixels_to_EMU(offset_y)

                    marker = AnchorMarker(col=1, colOff=emu_offset_x, row=i + 1, rowOff=emu_offset_y)
                    img.anchor = OneCellAnchor(_from=marker, ext=XDRPositiveSize2D(pixels_to_EMU(new_width), pixels_to_EMU(new_height)))
                    sheet.add_image(img)

                    processed_files += 1
                    self.progress.emit(int((processed_files) * progress_step))

                except IndexError as index_error:
                    logging.error(f"插入图片 {image_name} 时发生错误: {index_error}")
                    skipped_files.append(image_name)
                    continue
                except Exception as insert_error:
                    logging.error(f"插入图片 {image_name} 时发生错误: {insert_error}")
                    skipped_files.append(image_name)
                    continue

            try:
                workbook.save(self.output_path)
                logging.info(f"Excel 已生成并保存到 {self.output_path}！")
                if skipped_files:
                    self.skipped.emit(", ".join(skipped_files))
                self.finished.emit(f"Excel 已生成并保存到 {self.output_path}！")
            except Exception as save_error:
                logging.error(f"保存 Excel 文件时出错: {save_error}")
                self.error.emit(f"保存 Excel 文件时出错: {save_error}")

        finally:
            shutil.rmtree(temp_dir)

class ConvertDocWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("转换文档")
        self.setGeometry(200, 200, 800, 600)

        # 创建布局
        main_layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        options_layout = QHBoxLayout()

        # 创建按钮和进度条
        self.select_folder_button = QPushButton("选择文件夹")
        self.select_folder_button.setFixedHeight(40)
        self.process_button = QPushButton("生成 Excel")
        self.process_button.setFixedHeight(40)
        self.process_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # 创建用于输入图片高度或宽度的文本框
        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("请输入图片高度（单位：cm）")
        self.height_input.setFixedHeight(40)
        self.height_input.setText("6.7")

        self.width_input = QLineEdit()
        self.width_input.setPlaceholderText("请输入图片宽度（单位：cm）")
        self.width_input.setFixedHeight(40)
        self.width_input.setText("10")
        self.width_input.setVisible(False)

        # 创建用于输入单元格宽度缓冲百分比的文本框，并设置默认值为10
        self.buffer_width_input = QLineEdit()
        self.buffer_width_input.setPlaceholderText("单元格宽度缓冲百分比（%）")
        self.buffer_width_input.setFixedHeight(40)
        self.buffer_width_input.setText("10")

        # 创建用于输入单元格高度缓冲百分比的文本框，并设置默认值为10
        self.buffer_height_input = QLineEdit()
        self.buffer_height_input.setPlaceholderText("单元格高度缓冲百分比（%）")
        self.buffer_height_input.setFixedHeight(40)
        self.buffer_height_input.setText("10")

        # 创建提示标签
        self.buffer_width_label = QLabel("输入单元格宽度相对于图片宽度的缓冲百分比，默认为10%。")
        self.buffer_width_label.setStyleSheet("font-size: 12px; color: #555;")
        self.buffer_height_label = QLabel("输入单元格高度相对于图片高度的缓冲百分比，默认为10%。")
        self.buffer_height_label.setStyleSheet("font-size: 12px; color: #555;")

        # 创建提示标签，用于通知用户跳过了不支持的文件
        self.unsupported_files_label = QLabel("注意: 文件夹中包含不支持的文件类型（如 .mpo），这些文件将被忽略。")
        self.unsupported_files_label.setStyleSheet("font-size: 12px; color: red;")
        self.unsupported_files_label.setVisible(False)

        # 创建用于显示已选择文件夹的标签
        self.selected_folder_label = QLabel("")
        self.selected_folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.selected_folder_label.setStyleSheet("font-size: 14px; padding: 10px;")

        # 创建单选按钮以选择使用高度或宽度
        self.radio_height = QRadioButton("按高度调整图片")
        self.radio_width = QRadioButton("按宽度调整图片")
        self.radio_height.setChecked(True)

        self.button_group = QButtonGroup()
        self.button_group.addButton(self.radio_height)
        self.button_group.addButton(self.radio_width)

        options_layout.addWidget(self.radio_height)
        options_layout.addWidget(self.radio_width)

        options_group = QGroupBox("调整方式")
        options_group.setLayout(options_layout)

        buffer_width_layout = QVBoxLayout()
        buffer_width_layout.addWidget(self.buffer_width_input)
        buffer_width_layout.addWidget(self.buffer_width_label)

        buffer_height_layout = QVBoxLayout()
        buffer_height_layout.addWidget(self.buffer_height_input)
        buffer_height_layout.addWidget(self.buffer_height_label)

        buffer_group = QGroupBox("缓冲百分比设置")
        buffer_group_layout = QVBoxLayout()
        buffer_group_layout.addLayout(buffer_width_layout)
        buffer_group_layout.addLayout(buffer_height_layout)
        buffer_group.setLayout(buffer_group_layout)

        button_layout.addWidget(self.select_folder_button)
        button_layout.addWidget(self.process_button)

        main_layout.addLayout(button_layout)
        main_layout.addWidget(options_group)
        main_layout.addWidget(self.height_input)
        main_layout.addWidget(self.width_input)
        main_layout.addWidget(buffer_group)
        main_layout.addWidget(self.unsupported_files_label)
        main_layout.addWidget(self.selected_folder_label)
        main_layout.addWidget(self.progress_bar)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                padding: 10px;
            }
            QPushButton:disabled {
                background-color: #a5d6a7;
            }
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QRadioButton {
                font-size: 14px;
            }
            QProgressBar {
                height: 25px;
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 20px;
            }
            QLabel {
                font-size: 14px;
            }
            QGroupBox {
                font-size: 14px;
                padding: 10px;
            }
        """)

        self.select_folder_button.clicked.connect(self.select_folder)
        self.process_button.clicked.connect(self.start_conversion)
        self.radio_height.toggled.connect(self.toggle_size_input)

        self.selected_folder = ""
        self.worker = None

    def toggle_size_input(self):
        if self.radio_height.isChecked():
            self.height_input.setVisible(True)
            self.width_input.setVisible(False)
        else:
            self.height_input.setVisible(False)
            self.width_input.setVisible(True)

    def select_folder(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", options=options)
        if folder:
            self.selected_folder = folder
            self.selected_folder_label.setText(f"已选择文件夹: {self.selected_folder}")
            self.process_button.setEnabled(True)

    def start_conversion(self):
        if not self.selected_folder:
            QMessageBox.warning(self, "警告", "请先选择一个文件夹！")
            return

        use_height = self.radio_height.isChecked()

        try:
            size_cm = float(self.height_input.text()) if use_height else float(self.width_input.text())
            if size_cm <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", f"请输入有效的图片{'高度' if use_height else '宽度'}（单位：cm）！")
            return

        try:
            buffer_percentage_width = float(self.buffer_width_input.text())
            if buffer_percentage_width < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的单元格宽度缓冲百分比（非负数）！")
            return

        try:
            buffer_percentage_height = float(self.buffer_height_input.text())
            if buffer_percentage_height < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的单元格高度缓冲百分比（非负数）！")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.process_button.setEnabled(False)
        self.select_folder_button.setEnabled(False)
        self.unsupported_files_label.setVisible(False)

        parent_directory = os.path.dirname(self.selected_folder)
        excel_path = os.path.join(parent_directory, "converted.xlsx")

        try:
            self.worker = ExcelWorker(
                self.selected_folder, 
                excel_path, 
                use_height, 
                size_cm, 
                buffer_percentage_width, 
                buffer_percentage_height
            )
            self.worker.progress.connect(self.update_progress)
            self.worker.finished.connect(self.show_finished)
            self.worker.finished.connect(lambda: self.progress_bar.setVisible(False))
            self.worker.finished.connect(lambda: self.process_button.setEnabled(True))
            self.worker.finished.connect(lambda: self.select_folder_button.setEnabled(True))
            self.worker.error.connect(self.show_error)
            self.worker.error.connect(lambda: self.progress_bar.setVisible(False))
            self.worker.error.connect(lambda: self.process_button.setEnabled(True))
            self.worker.error.connect(lambda: self.select_folder_button.setEnabled(True))
            self.worker.skipped.connect(self.show_skipped_files)
            self.worker.start()
        except Exception as thread_error:
            QMessageBox.critical(self, "错误", f"启动线程时出错: {thread_error}")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_finished(self, message):
        QMessageBox.information(self, "完成", message)

    def show_error(self, error_message):
        QMessageBox.critical(self, "错误", error_message)

    def show_skipped_files(self, skipped_str):
        if skipped_str:
            self.unsupported_files_label.setVisible(True)
            QMessageBox.warning(self, "跳过文件", f"以下文件无法处理并被跳过: {skipped_str}")

def main():
    app = QApplication(sys.argv)
    main_window = ConvertDocWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
