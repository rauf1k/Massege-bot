import sys
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5 import QtGui
import os

app = QApplication(sys.argv)

# Получение пути к каталогу исполняемого файла
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(__file__)

background_image_path = os.path.join(application_path, "background.jpg")
label = QLabel()
pixmap = QtGui.QPixmap(background_image_path)
label.setPixmap(pixmap)
label.show()

sys.exit(app.exec_())
