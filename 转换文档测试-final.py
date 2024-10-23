import sys  
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
    QLabel, QHBoxLayout, QProgressBar, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import QThread, pyqtSignal
from PIL import Image as PILImage  # 使用PIL来获取图片的宽高
import os
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, Alignment
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
from openpyxl.utils.units import pixels_to_EMU
from openpyxl.drawing.xdr import XDRPositiveSize2D

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

def main():
    app = QApplication(sys.argv)
    main_window = ConvertDocWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
