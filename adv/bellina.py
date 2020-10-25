from core.advbase import *

class Bellina(Adv):
    def prerun(self):
        self.dragondrive = self.dragonform.set_dragondrive(ModeManager(
            group='ddrive',
            buffs=[Selfbuff('dragondrive', 0.35, -1, 's', 'passive')],
            x=True, fs=True, s1=True, s2=True
        ))
        self.hp = 100

    def s2_before(self, e):
        if self.hp > 30 and e.group == 'default':
            self.dragonform.charge_gauge(3000*(self.hp-30)/100, utp=True, dhaste=False)

variants = {None: Bellina}
