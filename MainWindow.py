from ui.ui_MainWindow import Ui_MainWindow
from PyQt5.QtWidgets import QMainWindow
import logging
logger = logging.getLogger(__name__)

class MainWindow(Ui_MainWindow, QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setupUi(self)
        self.retranslateUi(self)