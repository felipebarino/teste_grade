from PyQt5.QtWidgets import QApplication
from MainWindow import MainWindow
from sys import argv
import logging
logger = logging.getLogger(__name__)

FORMAT = '%(asctime)s @ %(name)s (%(levelname)s) >> %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt='%d-%m-%Y %H:%M:%S',
                    filename='info.log')

if __name__ == '__main__':
    logger.debug(f'Iniciando...')

    app = QApplication(argv)
    w = MainWindow()
    w.show()

    app.exec()