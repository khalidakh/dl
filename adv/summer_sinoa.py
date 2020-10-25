from core.advbase import *

class Summer_Sinoa(Adv):
    def prerun(self):
        self.overload = 0

    @staticmethod
    def prerun_skillshare(adv, dst):
        self.overload = -1

    def charge(self, name, sp, target=None):
        sp_s1 = self.sp_convert(self.sp_mod(name) - 0.3*self.overload, sp)
        sp = self.sp_convert(self.sp_mod(name), sp)
        targets = self.get_targets(target)
        if not targets:
            return
        for s in targets:
            if s == self.s1:
                s.charge(sp_s1)
            else:
                s.charge(sp)
        self.think_pin('sp')
        log('sp', name if not target else f'{name}_{target}', sp, ', '.join([f'{s.charged}/{s.sp}' for s in self.skills]))

    def s1_before(self, e):
        if self.overload == -1:
            return
        if self.overload < 3:
            self.overload += 1
        self.determination = Modifier('determination', 's', 'passive', 0.15+0.05*self.overload).on()

    def s1_proc(self, e):
        if self.overload == -1:
            return
        self.determination.off()

    def s2_proc(self, e):
        if self.overload == 3:
            self.inspiration.add(2, team=True)
            Teambuff('s2_crit_rate', 0.20, 30, 'crit', 'chance').on()
            Teambuff('s2_crit_dmg', 0.15, 30, 'crit', 'damage').on()
        else:
            buffs = [
                lambda: self.inspiration.add(2),
                lambda: Selfbuff('s2_crit_rate', 0.20, 30, 'crit', 'chance').on(),
                lambda: Selfbuff('s2_crit_dmg', 0.15, 30, 'crit', 'damage').on(),
            ]
            log('debug', 'overload', self.overload)
            for _ in range(max(1, self.overload)):
                buff = random.choice(buffs)
                buff()
                buffs.remove(buff)
        self.overload = 0

variants = {None: Summer_Sinoa}
