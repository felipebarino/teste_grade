import pandas as pd

from ui.ui_MainWindow import Ui_MainWindow
from PyQt5.QtWidgets import QMainWindow
import logging
import pandas as pd
import numpy as np
from Loader import BraggMeter, SpectrumAcquirer
from sensor import StrainSensor, TemperatureSensor
from pyqtgraph import mkColor, mkPen, BarGraphItem, PlotCurveItem, LegendItem
from PyQt5 import QtCore, QtGui

logger = logging.getLogger(__name__)

class MainWindow(Ui_MainWindow, QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setupUi(self)
        self.retranslateUi(self)
        self.connectActions()

        self.setupGraph()

        try:
            self.braggmeter = BraggMeter(host='10.0.0.150', port=3500)
        except Exception as e:
            logger.error(f"Erro ao abrir o BraggMeter: {e}")
            self.braggmeter = None

        self.sensor_data = pd.read_excel('Sensores_teste.xlsx')
        logger.debug(f'Sensores: \n{self.sensor_data}')
        self.strain_sensors = []
        self.temp_sensors = []
        colors = ['k', 'b', 'c', 'r', 'g', 'y']
        ci = 0
        for i in range(0, len(self.sensor_data)):
            sensor = self.sensor_data.iloc[i,:]
            logger.debug(sensor)
            if sensor['Tipo'] == 'Temperatura':
                self.temp_sensors.append(
                    TemperatureSensor(f'Temp{len(self.temp_sensors)}',
                                      (None, None),
                                      sensor.to_dict())
                )
            if sensor['Tipo'] == 'Deformação':
                self.strain_sensors.append(
                    StrainSensor(f'Def{len(self.strain_sensors)}',
                                      (None, None),
                                      sensor.to_dict())
                )
                self.strain_sensors[-1].curve_item = self.plotNewCurve([], [],
                                                                       name=f'Def{len(self.strain_sensors)}',
                                                                       pen=mkPen(color=colors[ci],
                                                                                 width=2)
                                                                       )
                ci += 1

        self.channels = self.sensor_data['Canal'].unique().tolist()

        if self.braggmeter is not None:
            time_interval = 1 # segundo
            self.timedAcquirer = SpectrumAcquirer(self.braggmeter, time_interval,
                                                  self.channels, return_bragg=True)
            self.timedAcquirer.bragg_signal.connect(self.processBragg)

        self.sensor_info = {'Temperatura': ['Lambda Bragg (nm)', 's0 (°C)', 's1 (°C/nm)', 's2 (°C/nm²)'],
                            'Deformação':  ['Lambda Bragg (nm)', 'k', 'tcs (um/m/°C)']}
        self.specimen_cte = 0
        self.ref_temp = 30


    def connectActions(self):
        self.pushButton.clicked.connect(self.sendString)
        self.pushButton_oneshot.clicked.connect(self.measure)
        self.pushButton_continuous.clicked.connect(self.continuousMeasure)

    def setupGraph(self):
        logger.debug('Setup plotWidget da série temporal')
        bg_color = self.palette().color(QtGui.QPalette.Window)
        self.graphWidget.setBackground(mkColor('white'))
        self.legend = LegendItem(offset=[0, 10])
        self.legend.setParentItem(self.graphWidget.plotItem)

        self.graphWidget.getAxis('left').setLabel('Deformação (ue)')
        self.graphWidget.getAxis('bottom').setLabel('Horário')
        self.graphWidget.plotItem.vb.setLimits()
        self.graphWidget.plotItem.vb.setLimits(xMin=0)

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
        resp = self.braggmeter.send(f':ACQU:STAR\r\n'.encode())
        logger.info(resp)
        sensors = []
        for channel in self.channels:
            logger.debug(f'Canal : {channel}')
            lambdas = self.braggmeter.ask(f'bragg{channel}')
            i = lambdas.find('ACK') + 4
            lambdas = lambdas[i:-2].split(',')
            lambdas = [float(lamb) for lamb in lambdas]
            sensors.extend(lambdas)
        sensors = np.array(sensors)
        sensors.sort()
        self.lambda2Measurement(sensors)

    def continuousMeasure(self):
        if self.braggmeter is None:
            logger.error('BraggMeter não conectado!')
            return -1
        if self.timedAcquirer.is_alive():
            self.pushButton_continuous.setText("Iniciar medição contínua")
            self.timedAcquirer.pause()
        else:
            self.pushButton_continuous.setText("Parar medição contínua")
            self.timedAcquirer.resume()

    def processBragg(self, bragg_per_ch):
        sensors = []
        for bragg_list in bragg_per_ch:
            sensors.extend(bragg_list)
        sensors = np.array(sensors)
        sensors.sort()
        self.lambda2Measurement(sensors)

    def lambda2Measurement(self, lambdas):
        measured_data = {}
        self.plainTextEdit_2.insertPlainText(f"Bragg \t\t {lambdas}")
        self.plainTextEdit_2.insertPlainText("\n")

        for bragg in lambdas:
            err = np.abs(bragg - self.sensor_data['Lambda Bragg (nm)'])
            i = err.argmin()
            tipo = self.sensor_data['Tipo'][i]
            if tipo == 'Temperatura':
                for j in range(len(self.temp_sensors)):
                    if self.temp_sensors[j].lambdaBragg_0 == self.sensor_data['Lambda Bragg (nm)'][i]:
                        self.temp_sensors[j].lambdaBragg = bragg
                        break
            if tipo == 'Deformação':
                for j in range(len(self.temp_sensors)):
                    if self.strain_sensors[j].lambdaBragg_0 == self.sensor_data['Lambda Bragg (nm)'][i]:
                        self.strain_sensors[j].lambdaBragg = bragg
                        break
        temp = 0
        for temp_sen in self.temp_sensors:
            temp_i = temp_sen.getTemperature()
            sensor_ref = temp_sen.param_dict['Sensor']
            measured_data[f'Temperatura (°C) @ {sensor_ref}'] = temp_i
            temp += temp_i
        temp = temp/(len(self.temp_sensors))
        self.plainTextEdit_2.insertPlainText(f"Temperatura \t\t {temp} °C")
        self.plainTextEdit_2.insertPlainText("\n")

        measured_data['Temperatura (°C)'] = temp

        for strain_sen in self.strain_sensors:
            sensor_ref = strain_sen.param_dict['Sensor']
            strain = strain_sen.getStrain(temperature=temp)
            measured_data[f'Strain (ue) @ {sensor_ref}'] = strain

            self.plot_strain(strain_sen)

            self.plainTextEdit_2.insertPlainText(f"Strain@{strain_sen.name} \t\t {strain} ue")
            self.plainTextEdit_2.insertPlainText("\n")

        self.plainTextEdit_2.insertPlainText("____________________________________________________\n")

        logger.debug(measured_data)

    def plot_strain(self, sensor):
        max_xaxis = 50
        xData, yData = sensor.curve_item.getData()
        if len(xData) > max_xaxis:
            xData = xData[-max_xaxis::]
            yData = yData[-max_xaxis::]
            xmin = xData[-max_xaxis]
            xmax = xData[-1] + 10

            self.graphWidget.setXRange(xmin, xmax, padding=0, update=False)
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
            logger.error(f'Erro ao fechar o Braggmeter: {e}')
        ev.accept()