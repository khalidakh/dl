from core.advbase import *

class Forte(Adv):
    def prerun(self):
        Event('s').listener(self.s_dgauge)

    def s_dgauge(self, e):
        if e.name != 'ds':
            self.dragonform.charge_gauge(40, dhaste=False)

variants = {None: Forte}
