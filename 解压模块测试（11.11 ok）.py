# -*- coding: utf-8 -*-
import sys
import traceback
import tempfile  # 确保导入
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
    QLabel, QProgressBar, QLineEdit, QHBoxLayout, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PIL import Image
import os
import zipfile
import py7zr  # For .7z files
import rarfile  # For .rar files
import tarfile  # For .tgz files
import shutil  # To remove temp folder
from pathlib import Path

# 设置 unrar 工具路径，使用原始字符串并确保路径正确
rarfile.UNRAR_TOOL = r"D:\WinRar\UnRAR.exe"  # 请根据您的实际路径修改


class Worker(QObject):
    # 定义信号
    progress_update = pyqtSignal(int)
    status_update = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    completion_signal = pyqtSignal(str)

    def __init__(self, mode, selected_path, prefix, digits):
        super().__init__()
        self.mode = mode  # 'decompress' or 'rename'
        self.selected_path = selected_path
        self.prefix = prefix
        self.digits = digits

    def run(self):
        try:
            if self.mode == 'decompress':
                self.decompress_and_rename()
            elif self.mode == 'rename':
                self.rename_in_folder()
            else:
                self.error_signal.emit("未知的操作模式。")
        except Exception as e:
            self.error_signal.emit(f"处理过程中出现意外错误：{str(e)}\n{traceback.format_exc()}")

    def decompress_and_rename(self):
        try:
            base_name = Path(self.selected_path).stem
            final_dir_base = Path(self.selected_path).parent / f"{base_name}-解压修改"
            final_dir = final_dir_base
            counter = 1
            while final_dir.exists():
                final_dir = Path(f"{final_dir_base}{counter}")
                counter += 1
            final_dir.mkdir(parents=True, exist_ok=True)

            self.status_update.emit("开始解压文件...")
            image_paths = []

            # 使用默认临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                if self.selected_path.lower().endswith('.zip'):
                    self.extract_zip(temp_path, image_paths)
                elif self.selected_path.lower().endswith('.7z'):
                    self.extract_7z(temp_path, image_paths)
                elif self.selected_path.lower().endswith('.rar'):
                    self.extract_rar(temp_path, image_paths)
                elif self.selected_path.lower().endswith('.tgz'):
                    self.extract_tgz(temp_path, image_paths)
                else:
                    self.error_signal.emit("不支持的文件格式！")
                    return

                if not image_paths:
                    self.error_signal.emit("解压后未找到任何图片文件。")
                    return

                total = len(image_paths)
                if total == 0:
                    self.error_signal.emit("没有需要处理的图片文件。")
                    return

                self.progress_update.emit(0)
                self.status_update.emit("开始重命名图片...")

                for index, image_path in enumerate(image_paths):
                    new_name = f"{self.prefix}{str(index + 1).zfill(self.digits)}.jpg"
                    new_path = final_dir / new_name

                    try:
                        # 打开图片
                        with Image.open(image_path) as image:
                            # 如果图片格式不是 JPEG，则转换为 JPEG
                            if image.format.lower() != 'jpeg':
                                image = image.convert('RGB')
                            # 保存为 JPEG，使用较高质量参数以尽量减少损失
                            image.save(new_path, format='JPEG', quality=95)

                        # 调整图片大小（只在必要时），确保不超过800KB
                        self.adjust_image_size(new_path)

                        self.status_update.emit(f"处理文件: {new_name}")
                        percentage = int((index + 1) / total * 100)
                        self.progress_update.emit(percentage)
                    except Exception as e:
                        self.error_signal.emit(f"处理文件 {image_path.name} 时出错：{str(e)}\n{traceback.format_exc()}")
                        continue  # 继续处理下一个文件

            # 确保进度条达到100%后再发出完成信号
            self.progress_update.emit(100)
            self.completion_signal.emit(f"文件已成功解压并改名至文件夹: {final_dir}")
        except Exception as e:
            self.error_signal.emit(f"解压和重命名过程中出现意外错误：{str(e)}\n{traceback.format_exc()}")

    def rename_in_folder(self):
        try:
            selected_folder = Path(self.selected_path)
            image_paths = [path for path in selected_folder.iterdir()
                           if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.gif')]

            if not image_paths:
                self.error_signal.emit("文件夹内没有任何图片文件。")
                return

            final_dir_base = selected_folder / "改名图片"
            final_dir = final_dir_base
            counter = 1
            while final_dir.exists():
                final_dir = Path(f"{final_dir_base}{counter}")
                counter += 1
            final_dir.mkdir(parents=True, exist_ok=True)

            total = len(image_paths)
            if total == 0:
                self.error_signal.emit("没有需要处理的图片文件。")
                return

            self.progress_update.emit(0)
            self.status_update.emit("开始重命名图片...")

            for index, image_path in enumerate(image_paths):
                sanitized_name = self.sanitize_filename(f"{self.prefix}{str(index + 1).zfill(self.digits)}.jpg")
                new_path = final_dir / sanitized_name

                try:
                    # 打开图片
                    with Image.open(image_path) as image:
                        # 如果图片格式不是 JPEG，则转换为 JPEG
                        if image.format.lower() != 'jpeg':
                            image = image.convert('RGB')
                        # 保存为 JPEG，使用较高质量参数以尽量减少损失
                        image.save(new_path, format='JPEG', quality=95)

                    # 调整图片大小（只在必要时），确保不超过800KB
                    self.adjust_image_size(new_path)

                    self.status_update.emit(f"处理文件: {sanitized_name}")
                    percentage = int((index + 1) / total * 100)
                    self.progress_update.emit(percentage)
                except Exception as e:
                    self.error_signal.emit(f"处理文件 {image_path.name} 时出错：{str(e)}\n{traceback.format_exc()}")
                    continue  # 继续处理下一个文件

            # 确保进度条达到100%后再发出完成信号
            self.progress_update.emit(100)
            self.completion_signal.emit(f"文件夹内图片已成功改名，并保存于: {final_dir}")
        except Exception as e:
            self.error_signal.emit(f"改名过程中出现意外错误：{str(e)}\n{traceback.format_exc()}")

    def adjust_image_size(self, image_path):
        """只在图片大小超过800KB时调整图片质量，以便减小文件大小。"""
        try:
            max_size_kb = 800
            image_size_kb = os.path.getsize(image_path) / 1024  # Get size in KB

            if image_size_kb > max_size_kb:
                quality = 90  # 开始的压缩质量参数，尽量保持高质量
                with Image.open(image_path) as img:
                    while image_size_kb > max_size_kb and quality > 10:
                        quality -= 5
                        img.save(image_path, format='JPEG', quality=quality)
                        image_size_kb = os.path.getsize(image_path) / 1024
        except Exception as e:
            self.error_signal.emit(f"调整图片大小时出现错误：{str(e)}\n{traceback.format_exc()}")

    def sanitize_filename(self, filename):
        """移除或替换文件名中的无效字符。"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def extract_zip(self, extract_dir, image_paths):
        try:
            with zipfile.ZipFile(self.selected_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                for name in zip_ref.namelist():
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_path = extract_dir / name
                        if image_path.is_file():
                            image_paths.append(image_path)
        except Exception as e:
            self.error_signal.emit(f"解压 .zip 文件时出现错误: {str(e)}\n{traceback.format_exc()}")

    def extract_7z(self, extract_dir, image_paths):
        try:
            with py7zr.SevenZipFile(self.selected_path, mode='r') as archive:
                archive.extractall(path=str(extract_dir))
                for name in archive.getnames():
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_path = extract_dir / name
                        if image_path.is_file():
                            image_paths.append(image_path)
        except Exception as e:
            self.error_signal.emit(f"解压 .7z 文件时出现错误: {str(e)}\n{traceback.format_exc()}")

    def extract_rar(self, extract_dir, image_paths):
        try:
            with rarfile.RarFile(self.selected_path, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
                for name in rar_ref.namelist():
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_path = extract_dir / name
                        if image_path.is_file():
                            image_paths.append(image_path)
        except Exception as e:
            self.error_signal.emit(f"解压 .rar 文件时出现错误: {str(e)}\n{traceback.format_exc()}")

    def extract_tgz(self, extract_dir, image_paths):
        try:
            with tarfile.open(self.selected_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
                for member in tar_ref.getmembers():
                    if member.name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_path = extract_dir / member.name
                        if image_path.is_file():
                            image_paths.append(image_path)
        except Exception as e:
            self.error_signal.emit(f"解压 .tgz 文件时出现错误: {str(e)}\n{traceback.format_exc()}")


class DecompressRenameWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("解压或改名工具")
        self.setGeometry(150, 150, 600, 400)

        layout = QVBoxLayout()

        # 操作模式选择
        self.select_mode_label = QLabel("选择操作模式:")
        self.decompress_mode_radio = QRadioButton("解压并改名压缩包")
        self.rename_folder_radio = QRadioButton("直接改名文件夹内的图片")
        self.decompress_mode_radio.setChecked(True)  # 默认选中解压模式
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.decompress_mode_radio)
        self.mode_group.addButton(self.rename_folder_radio)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.decompress_mode_radio)
        mode_layout.addWidget(self.rename_folder_radio)

        # 文件或文件夹选择按钮
        self.select_button = QPushButton("选择压缩文件或文件夹")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("输入文件前缀，默认：BRSF")
        self.digits_input = QLineEdit()
        self.digits_input.setPlaceholderText("输入序号位数，默认：3")
        self.process_button = QPushButton("开始处理")
        self.progress_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)  # 确保最大值为100

        layout.addWidget(self.select_mode_label)
        layout.addLayout(mode_layout)
        layout.addWidget(self.select_button)
        layout.addWidget(self.prefix_input)
        layout.addWidget(self.digits_input)
        layout.addWidget(self.process_button)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # 连接信号与槽
        self.select_button.clicked.connect(self.select_file_or_folder)
        self.process_button.clicked.connect(self.start_processing)

        self.selected_path = ""

    def select_file_or_folder(self):
        options = QFileDialog.Options()
        if self.decompress_mode_radio.isChecked():
            file, _ = QFileDialog.getOpenFileName(
                self,
                "选择压缩文件",
                "",
                "Compressed Files (*.zip *.7z *.rar *.tgz);;All Files (*)",
                options=options
            )
            if file:
                self.selected_path = os.path.normpath(file)
                self.progress_label.setText(f"已选择压缩文件: {Path(file).name}")
        else:
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                "",
                options=options
            )
            if folder:
                self.selected_path = os.path.normpath(folder)
                self.progress_label.setText(f"已选择文件夹: {Path(folder).name}")

    def start_processing(self):
        prefix = self.prefix_input.text().strip() or "BRSF"
        digits = int(self.digits_input.text().strip()) if self.digits_input.text().strip().isdigit() else 3

        if not self.selected_path:
            QMessageBox.warning(self, "错误", "请先选择一个有效的压缩文件或文件夹！")
            return

        mode = 'decompress' if self.decompress_mode_radio.isChecked() else 'rename'

        # 重置进度条
        self.progress_bar.setValue(0)
        self.progress_label.setText("开始处理...")

        # 禁用处理按钮，防止重复点击
        self.process_button.setEnabled(False)

        # 创建并启动工作线程
        self.thread = QThread()
        self.worker = Worker(mode, self.selected_path, prefix, digits)
        self.worker.moveToThread(self.thread)

        # 连接信号
        self.thread.started.connect(self.worker.run)
        self.worker.progress_update.connect(self.update_progress_bar)
        self.worker.status_update.connect(self.update_status_label)
        self.worker.error_signal.connect(self.show_error)
        self.worker.completion_signal.connect(self.show_completion)
        self.worker.completion_signal.connect(self.thread.quit)
        self.worker.completion_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self.process_button.setEnabled(True))  # 重新启用按钮

        self.thread.start()

    def update_progress_bar(self, value):
        # 确保值在0-100之间
        if value < 0:
            value = 0
        elif value > 100:
            value = 100
        self.progress_bar.setValue(value)

    def update_status_label(self, text):
        self.progress_label.setText(text)

    def show_error(self, message):
        QMessageBox.critical(self, "错误", message)
        # 可选择将进度条重置或保持当前状态
        # self.progress_bar.setValue(0)

    def show_completion(self, message):
        # 确保进度条达到100%
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "完成", message)


def main():
    app = QApplication(sys.argv)
    window = DecompressRenameWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
