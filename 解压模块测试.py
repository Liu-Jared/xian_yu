import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                             QLabel, QProgressBar, QLineEdit)
from PIL import Image
import os
import zipfile
import py7zr  # For .7z files
import rarfile  # For .rar files
import tarfile  # For .tgz files
import tempfile
import shutil  # To remove temp folder

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


def main():
    app = QApplication(sys.argv)
    window = DecompressRenameWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
