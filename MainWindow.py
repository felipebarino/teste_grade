import os
import datetime
from ui.ui_MainWindow import Ui_MainWindow
from PyQt5.QtWidgets import QMainWindow
import logging
import pandas as pd
import numpy as np
from Loader import BraggMeter, SpectrumAcquirer, SimulateBraggMeter
from sensor import StrainSensor, TemperatureSensor
from pyqtgraph import mkColor, mkPen, PlotCurveItem, LegendItem
from PyQt5 import QtCore, QtGui

logger = logging.getLogger(__name__)

simulation = False
class MainWindow(Ui_MainWindow, QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setupUi(self)
        self.retranslateUi(self)
        self.connectActions()

        self.comboBox.model().item(2).setEnabled(True)

        self.setupGraph()

        self.file2save = 'medições.xlsx'

        self.comboBox.model().item(2).setEnabled(False)

        if simulation:
            self.braggmeter = SimulateBraggMeter(None)
        else:
            try:
                self.braggmeter = BraggMeter(host='10.0.0.150', port=3500)
            except Exception as e:
                logger.error(f"Erro ao abrir o BraggMeter: {e}")
                self.braggmeter = None

        self.sensor_data = None
        self.strain_sensors = None
        self.temp_sensors = None
        self.channels = None

        if self.braggmeter is not None:
            time_interval = 1  # segundo
            self.timedAcquirer = SpectrumAcquirer(self.braggmeter, time_interval,
                                                  self.channels, return_bragg=True)
            self.timedAcquirer.bragg_signal.connect(self.processBragg)

        self.data_buffer = None

    def setupSensors(self, config_path, sheet, plot=True):
        self.sensor_data = pd.read_excel(config_path, sheet_name=sheet)
        self.channels = self.sensor_data['Canal'].unique().tolist()
        logger.debug(f'Sensores: \n{self.sensor_data}')
        self.strain_sensors = []
        self.temp_sensors = []
        colors = ['k', 'b', 'c', 'r', 'g', 'y']
        ci = 0
        for i in range(0, len(self.sensor_data)):
            sensor = self.sensor_data.iloc[i, :]
            logger.debug(sensor)
            if sensor['Tipo'] == 'Temperatura':
                self.temp_sensors.append(
                    TemperatureSensor(sensor['Sensor'],
                                      (None, None),
                                      sensor.to_dict())
                )
            if sensor['Tipo'] == 'Deformação':
                self.strain_sensors.append(
                    StrainSensor(sensor['Sensor'],
                                 (None, None),
                                 sensor.to_dict())
                )
                if plot:
                    self.strain_sensors[-1].curve_item = self.plotNewCurve([], [],
                                                                           name=self.strain_sensors[-1].name,
                                                                           pen=mkPen(color=colors[ci],
                                                                                     width=2)
                                                                           )
                ci += 1
        if simulation:
            sensors = []
            for sensor in self.temp_sensors:
                sensors.append(sensor)
            for sensor in self.strain_sensors:
                sensors.append(sensor)
            self.braggmeter.set_simulation(sensors=sensors)

    def connectActions(self):
        self.pushButton.clicked.connect(self.sendString)
        self.pushButton_oneshot.clicked.connect(self.measure)
        self.pushButton_continuous.clicked.connect(self.continuousMeasure)

    def setupGraph(self):
        logger.debug('Setup plotWidget da série temporal')
        bg_color = self.palette().color(QtGui.QPalette.Window)
        self.graphWidget.setBackground(mkColor('white'))
        self.graphWidget.getAxis('left').setLabel('Deformação (ue)')
        self.graphWidget.getAxis('bottom').setLabel('Horário')
        self.graphWidget.plotItem.vb.setLimits()
        self.graphWidget.plotItem.vb.setLimits(xMin=0)
        self.graphWidget.plotItem.setClipToView(True)

        self.legend = LegendItem(offset=[0, 10])
        self.legend.setParentItem(self.graphWidget.plotItem)

    def plotNewCurve(self, x, y, name=None, **kwargs):
        logger.debug(('Plotar uma nova curva'))
        curve = PlotCurveItem(x=x, y=y, clickable=True, **kwargs)
        self.legend.addItem(curve, name)
        self.graphWidget.addItem(curve)
        return curve

    def sendString(self):
        text = self.lineEdit.text()
        text += '\r\n'
        if self.braggmeter is None:
            response = 'BraggMeter não conectado!'
        else:
            response = self.braggmeter.send(text.encode())
        self.plainTextEdit.insertPlainText(f"Enviado: {text}\t\tResposta: {response}")
        self.plainTextEdit.insertPlainText("\n")

    def measure(self):
        if self.braggmeter is None:
            logger.error('BraggMeter não conectado!')
            return -1
        self.setupSensors('sensor_data.xlsx', self.comboBox.currentText(), plot=False)
        resp = self.braggmeter.send(f':ACQU:STAR\r\n'.encode())
        logger.info(resp)
        sensors = []
        for channel in self.channels:
            logger.debug(f'Canal : {channel}')
            lambdas = self.braggmeter.get_peaks(channel)
            sensors.extend(lambdas)
        sensors = np.array(sensors)
        sensors.sort()
        self.lambda2Measurement(sensors, plot=False)

    def continuousMeasure(self):
        if self.braggmeter is None:
            logger.error('BraggMeter não conectado!')
            return -1

        if self.timedAcquirer.is_alive():
            self.pushButton_continuous.setText("Iniciar medição contínua")
            self.timedAcquirer.pause()
            if self.data_buffer is not None:
                self.appendData2Excel()
        else:
            self.pushButton_continuous.setText("Parar medição contínua")
            self.graphWidget.removeItem(self.legend)
            self.graphWidget.clear()
            self.legend.clear()

            self.setupSensors('sensor_data.xlsx', self.comboBox.currentText())
            self.timedAcquirer.setChannels(self.channels)
            self.timedAcquirer.resume()

    def processBragg(self, bragg_per_ch):
        sensors = []
        for bragg_list in bragg_per_ch:
            sensors.extend(bragg_list)
        sensors = np.array(sensors)
        sensors.sort()
        self.lambda2Measurement(sensors)

    def lambda2Measurement(self, lambdas, plot=True):
        cursor = QtGui.QTextCursor(self.plainTextEdit_2.document())
        cursor.setPosition(0)
        self.plainTextEdit_2.setTextCursor(cursor)

        measured_data = {'Horário': datetime.datetime.now()}
        self.plainTextEdit_2.insertPlainText(f"Timestamp \t\t {measured_data['Horário']}\n")

        if len(lambdas) == 0:
            logger.error("FALHA MÁXIMA NA AQUISIÇÃO!!!!!!")
            self.plainTextEdit_2.insertPlainText(f"FALHA MÁXIMA NA AQUISIÇÃO!!!!!!\n")

        self.plainTextEdit_2.insertPlainText(f"Bragg \t\t {lambdas}")
        self.plainTextEdit_2.insertPlainText("\n")

        for sensor in self.temp_sensors:
            dist = np.abs(lambdas - sensor.lambdaBragg_0)
            if len(dist) != 0:
                i = dist.argmin()
                if dist[i] < 2.5:        # Distância máxima: 2.5nm
                    sensor.lambdaBragg = lambdas[i]
                else:
                    sensor.lambdaBragg = 0
            else:
                sensor.lambdaBragg = 0
            
        for sensor in self.strain_sensors:
            dist = np.abs(lambdas - sensor.lambdaBragg_0)
            if len(dist) != 0:
                i = dist.argmin()
                if dist[i] < 2.5:        # Distância máxima: 2.5nm
                    sensor.lambdaBragg = lambdas[i]
                else:
                    sensor.lambdaBragg = 0
            else:
                sensor.lambdaBragg = 0
            
        temp = 0
        working_temp_sensors = 0

        for temp_sen in self.temp_sensors:
            temp_i = temp_sen.getTemperature()
            sensor_ref = temp_sen.param_dict['Sensor']
            measured_data[f'Bragg (nm) @ {sensor_ref}'] = temp_sen.lambdaBragg
            measured_data[f'Temperatura (°C) @ {sensor_ref}'] = temp_i

            if temp_sen.lambdaBragg != 0:
                temp += temp_i
                working_temp_sensors += 1

        if working_temp_sensors != 0:
            temp = temp / working_temp_sensors
        else:
            temp = None

        self.plainTextEdit_2.insertPlainText(f"Temperatura \t\t {temp} °C")
        self.plainTextEdit_2.insertPlainText("\n")
        measured_data['Temperatura (°C)'] = temp

        for strain_sen in self.strain_sensors:
            sensor_ref = strain_sen.param_dict['Sensor']
            strain = strain_sen.getStrain(temperature=temp)
            measured_data[f'Bragg (nm) @ {sensor_ref}'] = strain_sen.lambdaBragg
            measured_data[f'Strain (ue) @ {sensor_ref}'] = strain

            if plot:
                self.plot_strain(strain_sen)

            self.plainTextEdit_2.insertPlainText(f"Strain@{strain_sen.name} \t\t {strain} ue")
            self.plainTextEdit_2.insertPlainText("\n")
        self.plainTextEdit_2.insertPlainText("____________________________________________________\n")

        df = pd.DataFrame(measured_data, index=[0])
        if self.data_buffer is None:
            self.data_buffer = df
        else:
            self.data_buffer = pd.concat([self.data_buffer, df], ignore_index=True)

        if len(self.data_buffer) > 240:
            self.appendData2Excel()

    def appendData2Excel(self):
        self.thread = QtCore.QThread()
        self.worker = ExcelDumper()
        self.worker.setup(self.file2save, self.data_buffer, self.comboBox.currentText())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.file_changed.connect(self.update_file)
        self.thread.start()
        self.data_buffer = None

    def update_file(self, file_name):
        self.file2save = file_name

    def plot_strain(self, sensor):
        max_xaxis = 50
        xData, yData = sensor.curve_item.getData()
        if len(xData) > max_xaxis:
            xData = xData[-max_xaxis::]
            yData = yData[-max_xaxis::]
            xmin = xData[-max_xaxis]
            xmax = xData[-1] + 10

            self.graphWidget.setXRange(xmin, xmax, padding=0, update=False)
        # NOTE usar o timestamp (sec + 60*min + 3600*h) deve arrumar o delay introduzido por falha
        if len(xData) == 0:
            x = 0
        else:
            x = xData[-1] + 1
        sensor.curve_item.updateData(np.append(xData, x), np.append(yData, sensor.strain))

    def closeEvent(self, ev):
        try:
            if self.braggmeter is not None:
                self.timedAcquirer.kill()
                self.timedAcquirer = None
                self.braggmeter = None
        except Exception as e:
            logger.error(f'Erro ao fechar o aquisitor: {e}')
        ev.accept()

class ExcelDumper(QtCore.QObject):
    file_changed = QtCore.pyqtSignal(object)
    finished = QtCore.pyqtSignal()

    def setup(self, file_path, data, sheet_name):
        self.file_path = file_path
        self.data = data
        self.sheet_name = sheet_name

    def run(self):
        try:
            self.appendData2Excel()
        except Exception as e:
            logger.error(f'Erro ao salvar: {e}')
            k = 0
            fname = f'medições{k}.xlsx'
            while os.path.isfile(fname):
                k += 1
                fname = f'medições{k}.xlsx'
            self.file_path = fname
            self.appendData2Excel()
            self.file_changed.emit(fname)
        self.finished.emit()

    def appendData2Excel(self):
        file_exists = os.path.isfile(self.file_path)
        mode = 'a' if file_exists else 'w'
        if_sheet_exists = 'overlay' if file_exists else None

        with pd.ExcelWriter(self.file_path, mode=mode, if_sheet_exists=if_sheet_exists) as writer:
            startrow = writer.sheets[self.sheet_name].max_row if file_exists else 1
            if startrow == 1:
                startrow = 0
                header = True
            else:
                header = False
            self.data.to_excel(writer, sheet_name=self.sheet_name,
                        startrow=startrow, index=False, header=header)