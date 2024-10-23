import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QMessageBox,
                             QLabel, QHBoxLayout, QScrollArea, QListWidget, QListWidgetItem, QColorDialog, QSpinBox,
                             QLineEdit, QInputDialog)
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QPen, QColor, QFont
from PyQt5.QtCore import Qt, QPoint, QRect
import os


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


def main():
    app = QApplication(sys.argv)
    main_window = ImageAnnotator()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
