import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                             QLabel, QProgressBar, QLineEdit, QHBoxLayout, QRadioButton, QButtonGroup)
from PIL import Image
import os
import zipfile
import py7zr  # For .7z files
import rarfile  # For .rar files
import tarfile  # For .tgz files
import tempfile
import shutil  # To remove temp folder
from concurrent.futures import ThreadPoolExecutor
import threading

# 设置 unrar 工具路径
rarfile.UNRAR_TOOL = "D:/WinRar/UnRAR.exe"


class DecompressRenameWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("解压或改名")
        self.setGeometry(150, 150, 600, 400)

        layout = QVBoxLayout()

        # File selection options
        self.select_mode_label = QLabel("选择操作模式:")
        self.file_mode_radio = QRadioButton("解压并改名压缩包")
        self.folder_mode_radio = QRadioButton("直接改名文件夹内的图片")
        self.file_mode_radio.setChecked(True)
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.file_mode_radio)
        self.mode_group.addButton(self.folder_mode_radio)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.file_mode_radio)
        mode_layout.addWidget(self.folder_mode_radio)

        # File/folder selection button
        self.select_file_button = QPushButton("选择压缩文件或文件夹")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("输入文件前缀，默认：BRSF")
        self.digits_input = QLineEdit()
        self.digits_input.setPlaceholderText("输入序号位数，默认：3")
        self.process_button = QPushButton("开始处理")
        self.progress_label = QLabel("")
        self.progress_bar = QProgressBar()

        layout.addWidget(self.select_mode_label)
        layout.addLayout(mode_layout)
        layout.addWidget(self.select_file_button)
        layout.addWidget(self.prefix_input)
        layout.addWidget(self.digits_input)
        layout.addWidget(self.process_button)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.select_file_button.clicked.connect(self.select_file_or_folder)
        self.process_button.clicked.connect(self.process_files)

        self.selected_path = ""
        self.image_paths = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.lock = threading.Lock()

    def select_file_or_folder(self):
        options = QFileDialog.Options()
        if self.file_mode_radio.isChecked():
            file, _ = QFileDialog.getOpenFileName(
                self,
                "选择压缩文件",
                "",
                "Compressed Files (*.zip *.7z *.rar *.tgz);;All Files (*)",
                options=options
            )
            if file:
                self.selected_path = file
                self.progress_label.setText(f"已选择压缩文件: {os.path.basename(file)}")
        else:
            folder = QFileDialog.getExistingDirectory(
                self,
                "选择文件夹",
                "",
                options=options
            )
            if folder:
                self.selected_path = folder
                self.progress_label.setText(f"已选择文件夹: {os.path.basename(folder)}")

    def process_files(self):
        try:
            prefix = self.prefix_input.text().strip() or "BRSF"
            digits = int(self.digits_input.text().strip()) if self.digits_input.text().strip().isdigit() else 3

            if not self.selected_path:
                QMessageBox.warning(self, "错误", "请先选择一个有效的压缩文件或文件夹！")
                return

            if self.file_mode_radio.isChecked():
                self.decompress_and_rename(prefix, digits)
            else:
                self.rename_in_folder(prefix, digits)

        except Exception as e:
            QMessageBox.critical(self, "意外错误", f"处理过程中出现意外错误：{str(e)}")

    def decompress_and_rename(self, prefix, digits):
        try:
            base_name = os.path.splitext(os.path.basename(self.selected_path))[0]
            final_dir_base = os.path.join(os.path.dirname(self.selected_path), f"{base_name}-解压修改")
            final_dir = final_dir_base
            counter = 1
            while os.path.exists(final_dir):
                final_dir = f"{final_dir_base}{counter}"
                counter += 1
            os.makedirs(final_dir, exist_ok=True)

            # 使用临时文件夹作为缓存
            with tempfile.TemporaryDirectory() as temp_dir:
                # 根据文件类型进行解压
                if self.selected_path.lower().endswith('.zip'):
                    self.extract_zip(temp_dir)
                elif self.selected_path.lower().endswith('.7z'):
                    self.extract_7z(temp_dir)
                elif self.selected_path.lower().endswith('.rar'):
                    self.extract_rar(temp_dir)
                elif self.selected_path.lower().endswith('.tgz'):
                    self.extract_tgz(temp_dir)
                else:
                    QMessageBox.warning(self, "错误", "不支持的文件格式！")
                    return

                if not self.image_paths:
                    QMessageBox.warning(self, "错误", "解压后未找到任何图片文件。")
                    return

                self.rename_images(final_dir, prefix, digits)

            QMessageBox.information(self, "完成", f"文件已成功解压并改名至文件夹: {final_dir}")

        except Exception as e:
            QMessageBox.critical(self, "意外错误", f"解压和重命名过程中出现意外错误：{str(e)}")

    def rename_in_folder(self, prefix, digits):
        try:
            self.image_paths = [os.path.join(self.selected_path, name) for name in os.listdir(self.selected_path)
                                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

            if not self.image_paths:
                QMessageBox.warning(self, "错误", "文件夹内没有任何图片文件。")
                return

            # Create a new folder in the selected directory to store renamed images
            renamed_dir = os.path.join(self.selected_path, "改名图片")
            os.makedirs(renamed_dir, exist_ok=True)

            self.rename_images(renamed_dir, prefix, digits)

            QMessageBox.information(self, "完成", f"文件夹内图片已成功改名，并保存于: {renamed_dir}")

        except Exception as e:
            QMessageBox.critical(self, "意外错误", f"改名过程中出现意外错误：{str(e)}")

    def rename_images(self, target_dir, prefix, digits):
        self.progress_bar.setMaximum(len(self.image_paths))
        futures = []
        for index, image_path in enumerate(self.image_paths):
            new_name = f"{prefix}{str(index + 1).zfill(digits)}.jpg"
            new_path = os.path.join(target_dir, new_name)
            futures.append(self.executor.submit(self.process_image, image_path, new_path, index))

        for future in futures:
            future.result()

    def process_image(self, image_path, new_path, index):
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

            with self.lock:
                self.progress_label.setText(f"处理文件: {os.path.basename(new_path)}")
                self.progress_bar.setValue(index + 1)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理文件 {os.path.basename(image_path)} 时出现错误：{str(e)}")

    def adjust_image_size(self, image_path):
        """只在图片大小超过800KB时调整图片质量，以便减小文件大小。"""
        max_size_kb = 800
        image_size_kb = os.path.getsize(image_path) / 1024  # Get size in KB

        if image_size_kb > max_size_kb:
            quality = 90  # 开始的压缩质量参数，尽量保持高质量
            with Image.open(image_path) as img:
                while image_size_kb > max_size_kb and quality > 10:
                    quality -= 5
                    img.save(image_path, format='JPEG', quality=quality)
                    image_size_kb = os.path.getsize(image_path) / 1024

    def extract_zip(self, extract_dir):
        with zipfile.ZipFile(self.selected_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            self.image_paths = [os.path.join(extract_dir, name) for name in zip_ref.namelist()
                                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]

    def extract_7z(self, extract_dir):
        try:
            with py7zr.SevenZipFile(self.selected_path, mode='r') as archive:
                archive.extractall(path=extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in archive.getnames()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .7z 文件时出现错误: {str(e)}")

    def extract_rar(self, extract_dir):
        try:
            with rarfile.RarFile(self.selected_path, 'r') as rar_ref:
                rar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, name) for name in rar_ref.namelist()
                                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .rar 文件时出现错误: {str(e)}")

    def extract_tgz(self, extract_dir):
        try:
            with tarfile.open(self.selected_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
                self.image_paths = [os.path.join(extract_dir, member.name) for member in tar_ref.getmembers()
                                    if member.name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
        except Exception as e:
            QMessageBox.critical(self, "解压失败", f"解压 .tgz 文件时出现错误: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = DecompressRenameWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
