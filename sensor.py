import logging

logger = logging.getLogger(__name__)

class Sensor:
    def __init__(self, name, position, calibration_params):
        self.type = None
        self.name = name
        self.pos = position
        self.temperature = None
        self.lambdaBragg_0 = calibration_params['Lambda Bragg (nm)']
        self.lambdaBragg = calibration_params['Lambda Bragg (nm)']
        self.param_dict = calibration_params

        self.curve_item = None

class TemperatureSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'Temperatura'
        self.s0 = self.param_dict['s0 (°C)']
        self.s1 = self.param_dict['s1 (°C/nm)']
        self.s2 = self.param_dict['s2 (°C/nm²)']

    def getTemperature(self):
        x = self.lambdaBragg - self.lambdaBragg_0
        self.temperature = x ** 2 * self.s2 + x * self.s1 + self.s0
        return self.temperature

class StrainSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'Deformação'
        self.k = self.param_dict['k']
        self.tcs = self.param_dict['tcs (um/m/°C)']
        self.cte = self.param_dict['cte (um/m/°C)']
        self.t0 = self.param_dict['T0 (°C)']
        self.strain = None

    def getStrain(self, temperature=None):
        self.setTemperature(temperature)
        x = self.lambdaBragg - self.lambdaBragg_0
        self.strain = x / (self.k * self.lambdaBragg_0) * 1e6 - (self.cte + self.tcs) * (self.temperature - self.t0)
        return self.strain

    def setTemperature(self, temperature):
        if temperature is None:
            temperature = self.t0
        self.temperature = temperature
