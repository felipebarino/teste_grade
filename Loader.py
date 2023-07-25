import numpy as np
import telnetlib
from PyQt5.QtCore import QTimer, pyqtSignal, QObject
import os
import logging

logger = logging.getLogger(__name__)

class BraggMeter:
    def __init__(self, host='10.0.0.150', port=3500):
        self.commands = {'status': ":STAT?\r\n".encode('ascii'),
                         'start': ":ACQU:STAR\r\n".encode('ascii'),
                         'stop': ":ACQU:STOP\r\n".encode('ascii'),
                         'trace0': ":ACQU:OSAT:CHAN:0?\r\n".encode('ascii'),
                         'trace1': ":ACQU:OSAT:CHAN:1?\r\n".encode('ascii'),
                         'trace2': ":ACQU:OSAT:CHAN:2?\r\n".encode('ascii'),
                         'trace3': ":ACQU:OSAT:CHAN:3?\r\n".encode('ascii'),
                         'bragg0': ":ACQU:WAVE:CHAN:0?\r\n".encode('ascii'),
                         'bragg1': ":ACQU:WAVE:CHAN:1?\r\n".encode('ascii'),
                         'bragg2': ":ACQU:WAVE:CHAN:2?\r\n".encode('ascii'),
                         'bragg3': ":ACQU:WAVE:CHAN:3?\r\n".encode('ascii'),
                         }
        self.host = host
        self.port = port
        self.timeout = 10
        self.tn = telnetlib.Telnet(self.host, self.port, self.timeout)
        self.tn.close()

        status = self.get_status()
        logger.info(f"BraggMeter status: {status}")
        if status == 5:
            err_msg = 'BraggMETER em aquecimento'
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    def ask(self, key):
        string = self.commands[key]
        resp = self.send(string)
        return resp

    def send(self, string):
        self.tn.open(self.host, port=self.port)
        self.tn.write(string)
        resp = self.tn.read_until("\n".encode('ascii'), self.timeout)
        resp = resp.decode()
        logger.debug(f'{string} response: {resp}')
        self.tn.close()
        return resp

    def start(self):
        status = self.get_status()
        logger.info(f'BraggMETER status: {status}')
        if status == 1:
            self.ask('start')
        elif status == 3 or status == 4:
            self.ask('stop')
            self.ask('start')
        elif status == 5:
            err_msg = 'BraggMETER em aquecimento'
            logger.error(err_msg)
            raise RuntimeError(err_msg)

    def stop(self):
        resp = self.ask('stop')
        status = self.get_status()
        logger.info(f'BraggMETER status: {status}')
        return resp

    def get_status(self):
        resp = self.ask('status')
        logger.debug(f'Resposta do status: {resp}')
        resp = resp.split(':')
        loc = 0
        for i in range(0, len(resp)):
            if resp[i] == 'ACK':
                loc = i + 1
        return int(resp[loc])

    def get_osa_trace(self, channel):
        resp = self.ask(f'trace{channel}')
        init = resp.find('ACK') + 4
        resp = resp[init::]
        resp = resp[:-2]
        trace = resp.split(',')
        trace = np.array(trace, dtype=float)
        wl = np.linspace(1500, 1600, len(trace))

        return np.append(wl.reshape(-1, 1),
                         trace.reshape(-1, 1),
                         axis=1)

    def get_peaks(self, channel):
        try:
            lambdas = self.ask(f'bragg{channel}')
        except Exception as e:
            logger.error(f'Erro ao ler o Bragg: {e}')
            self.start()
            lambdas = self.ask(f'bragg{channel}')
        i = lambdas.find('ACK') + 4
        lambdas = lambdas[i:-2].split(',')
        return [float(lamb) for lamb in lambdas]


class SpectrumAcquirer(QObject):
    spectra_signal = pyqtSignal(object)
    bragg_signal = pyqtSignal(object)

    def __init__(self, osa, interval, channels, *args, return_bragg=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.osa = osa

        self.time_interval = interval
        self.channels = channels

        self.timer = QTimer()
        if return_bragg:
            self.timer.timeout.connect(self.getBragg)
        else:
            self.timer.timeout.connect(self.getSpectra)
        self.timer.setInterval(self.time_interval * 1000)
        self.timer.stop()

        try:
            self.osa.start()
        except Exception as e:
            logger.error(f'Não foi possível iniciar o OSA: {e}')

    def pause(self):
        logger.debug('Pause loader')
        if self.timer.isActive():
            self.timer.stop()
        else:
            logger.debug('Already stoped!')

    def resume(self):
        logger.debug('Resume loader')
        if ~self.timer.isActive():
            self.timer.start()
        else:
            logger.debug('Already active!')

    def getSpectra(self):
        spectra = []
        for channel in self.channels:
            spectra.append(self.osa.get_osa_trace(channel))
        self.spectra_signal.emit(spectra)

    def getBragg(self):
        bragg = []
        for channel in self.channels:
            bragg.append(self.osa.get_peaks(channel))
        self.bragg_signal.emit(bragg)

    def kill(self):
        logger.debug('Killing loader')
        self.osa.stop()
        self.timer.stop()

    def is_alive(self):
        return self.timer.isActive()
