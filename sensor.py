import logging

logger = logging.getLogger(__name__)

class Sensor:
    def __init__(self, name, position, calibration_params):
        self.type = None
        self.name = name
        self.pos = position
        self.lambdaBragg_0 = calibration_params['Lambda Bragg (nm)']
        self.lambdaBragg = calibration_params['Lambda Bragg (nm)']
        self.param_dict = calibration_params

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
    def __init__(self, *args, cte=0, t0=30, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'Deformação'
        self.k = self.param_dict['k']
        self.tcs = self.param_dict['tcs (um/m/°C)']
        self.cte = cte
        self.t0 = t0
        self.strain = None

    def getStrain(self, temperature=None):
        if temperature is None:
            temperature = self.t0
        x = self.lambdaBragg - self.lambdaBragg_0
        self.strain = x / (self.k * self.lambdaBragg_0) * 1e6 - (self.cte + self.tcs) * (temperature - self.t0)
        return self.strain
