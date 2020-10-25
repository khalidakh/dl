from core.advbase import Action, S
from core.timeline import Event, Timer, now
from core.log import log, g_logs
from core.acl import allow_acl
from math import ceil

class DragonForm(Action):
    def __init__(self, name, conf, adv):
        self.name = name
        self.conf = conf
        self.adv = adv
        self.disabled = False
        self.shift_event = Event('dragon')
        self.act_event = Event('dact')
        self.end_event = Event('dragon_end')
        self.delayed = set()

        self.ds_reset()
        self.act_list = []
        self.act_sum = []
        self.repeat_act = False

        self.dx_list = [dx for dx, _ in self.conf.find(r'^dx\d+$')]

        self.ds_event = Event('ds')
        self.ds_event.name = 'ds'
        self.dx_event = Event('dx')

        self.action_timer = None

        self.shift_start_time = 0
        self.shift_end_timer = Timer(self.d_shift_end)
        self.idle_event = Event('idle')

        self.c_act_name = None
        self.c_act_conf = None
        self.dracolith_mod = self.adv.Modifier('dracolith', 'att', 'dragon', 0)
        self.dracolith_mod.get = self.ddamage
        self.dracolith_mod.off()
        self.shift_mods = [self.dracolith_mod]
        self.shift_spd_mod = None

        self.off_ele_mod = None
        if self.adv.slots.c.ele != self.adv.slots.d.ele:
            self.off_ele_mod = self.adv.Modifier('off_ele', 'att', 'dragon', -1/3)
            self.off_ele_mod.off()

        self.dragon_gauge = 0
        self.dragon_gauge_val = self.conf.gauge_val
        self.conf.gauge_iv = min(int(self.adv.duration/12), 15)
        self.dragon_gauge_timer = Timer(self.auto_gauge, timeout=max(1, self.conf.gauge_iv), repeat=1).on()
        self.dragon_gauge_pause_timer = None
        self.dragon_gauge_timer_diff = 0
        self.max_gauge = 1000
        self.shift_cost = 500

        self.shift_count = 0
        self.shift_silence = False

        self.is_dragondrive = False
        self.can_end = True

        self.allow_end_cd = self.conf.allow_end + self.dstime()
        self.allow_force_end_timer = Timer(self.set_allow_end, timeout=self.allow_end_cd)
        self.allow_end = False

    def set_shift_end(self, value, percent=True):
        if self.can_end:
            max_d = self.dtime() - self.conf.dshift.startup
            cur_d = self.shift_end_timer.timing - now() - (self.conf.ds.uses - self.skill_use) * self.dstime()
            delta_t = value
            if percent:
                delta_t *= (max_d)
            delta_t = min(max_d, cur_d+delta_t) - cur_d
            if cur_d + delta_t > 0:
                self.shift_end_timer.add(delta_t)
                log('shift_time', f'{delta_t:+2.4}', f'{cur_d+delta_t:2.4}')
            else:
                self.d_shift_end(None)
                self.shift_end_timer.off()

    def can_interrupt(self, target):
        return None

    def can_cancel(self, target):
        return None

    def getstartup(self):
        return 0

    def getrecovery(self):
        return 0

    def reset_allow_end(self):
        if self.is_dragondrive:
            self.allow_end = True
        else:
            log('allow_end', self.allow_end_cd)
            self.allow_end = False
            self.allow_force_end_timer = Timer(self.set_allow_end, timeout=self.allow_end_cd)
            self.allow_force_end_timer.on()
            self.allow_end_cd += self.conf.allow_end_step

    def set_allow_end(self, _):
        self.allow_end = True

    def set_dragondrive(self, dd_buff, max_gauge=3000, shift_cost=1200, drain=150):
        self.disabled = False
        self.is_dragondrive = True
        self.shift_event = Event('dragondrive')
        self.dragondrive_end_event = Event('dragondrive_end')
        ratio = max_gauge / self.max_gauge
        self.dragon_gauge *= ratio
        self.dragon_gauge_val *= ratio
        self.max_gauge = max_gauge
        self.shift_cost = shift_cost # does not deduct, but need to have this much pt to shift
        self.drain = drain
        self.dragondrive_buff = dd_buff
        self.dragondrive_timer = Timer(self.d_dragondrive_end)
        return self.dragondrive_buff

    def set_dragonbattle(self, duration):
        self.disabled = False
        self.dragon_gauge = self.max_gauge
        self.conf.duration = duration
        self.can_end = False
        self.repeat_act = True
        if self.conf.ds['sp_db']:
            self.skill_sp = self.conf.ds['sp_db']
        else:
            self.skill_sp = self.conf.ds.sp+15
        self.skill_spc = self.skill_sp
        self.skill_use = -1

    def end_silence(self, t):
        self.shift_silence = False

    def dodge_cancel(self):
        if len(self.dx_list) <= 0:
            return False
        combo = self.conf[self.dx_list[-1]].recovery / self.speed()
        dodge = self.conf.dodge.startup + self.conf.dodge.recovery
        return combo > dodge

    def auto_gauge(self, t):
        self.charge_gauge(self.dragon_gauge_val)

    def pause_auto_gauge(self):
        if self.dragon_gauge_pause_timer is None:
            self.dragon_gauge_timer_diff = self.dragon_gauge_timer.timing - now()
        else:
            self.dragon_gauge_timer_diff = self.dragon_gauge_pause_timer.timing - now()
        self.dragon_gauge_timer.off()

    def resume_auto_gauge(self, t):
        self.dragon_gauge_pause_timer = None
        self.auto_gauge(t)
        self.dragon_gauge_timer.on()

    def add_drive_gauge_time(self, delta, skill_pause=False):
        max_duration = self.max_gauge/self.drain
        duration = self.dragondrive_timer.timing - now()
        max_add = max_duration - duration
        if skill_pause:
            add_time = min(delta, max_add)
        else:
            add_time = min(delta/self.drain, max_add)
        duration = self.dragondrive_timer.add(add_time)
        if duration <= 0:
            self.d_dragondrive_end('<gauge deplete>')
        else:
            self.dragon_gauge = (duration/max_duration)*self.max_gauge
            if add_time != 0:
                log('drive_time' if not skill_pause else 'skill_pause', f'{add_time:+2.4}', f'{duration:2.4}', f'{int(self.dragon_gauge)}/{int(self.max_gauge)}')

    def charge_gauge(self, value, utp=False, dhaste=True):
        # if dhaste is None:
        #     dhaste = not utp
        dh = self.adv.mod('dh') if dhaste else 1
        value = self.adv.sp_convert(dh, value)
        delta = min(self.dragon_gauge+value, self.max_gauge) - self.dragon_gauge
        if self.is_dragondrive and self.dragondrive_buff.get():
            self.add_drive_gauge_time(delta)
        elif delta != 0:
            self.dragon_gauge += delta
            if utp:
                log('dragon_gauge', '{:+} utp'.format(int(delta)), f'{int(self.dragon_gauge)}/{int(self.max_gauge)}', value)
            else:
                log('dragon_gauge', '{:+.2f}%'.format(delta/self.max_gauge*100), '{:.2f}%'.format(self.dragon_gauge/self.max_gauge*100))

    @allow_acl
    def dtime(self):
        return self.conf.dshift.startup + self.conf.duration * self.adv.mod('dt') + self.conf.exhilaration * (self.off_ele_mod is None)

    def dstime(self):
        return (self.conf.ds.startup + self.conf.ds.recovery) / self.speed()

    @allow_acl
    def ddamage(self):
        return self.conf.dracolith + self.adv.mod('da') - 1

    def ds_check(self):
        return self.skill_use != 0 and self.skill_spc >= self.skill_sp

    def ds_charge(self, value):
        if self.skill_use != 0 and self.skill_spc < self.skill_sp:
            self.skill_spc += self.adv.sp_convert(self.adv.sp_mod('x'), value)
            if self.skill_spc > self.skill_sp:
                self.skill_spc = self.skill_sp
            log(self.c_act_name, 'sp', f'{self.skill_spc}/{self.skill_sp}')

    def ds_reset(self):
        self.skill_use = self.conf.ds.uses
        self.skill_sp = self.conf.ds.sp
        self.skill_spc = self.skill_sp

    def d_shift_end(self, t):
        if self.action_timer is not None:
            self.action_timer.off()
            self.action_timer = None
        duration = now()-self.shift_start_time
        shift_dmg = g_logs.shift_dmg
        g_logs.log_shift_dmg(False)
        count = self.clear_delayed()
        if count > 0:
            log('cancel', self.c_act_name, f'by shift end', f'lost {count} hit{"s" if count > 1 else ""}')
        log(self.name, '{:.2f}dmg / {:.2f}s, {:.2f} dps'.format(shift_dmg, duration, shift_dmg/duration), ' '.join(self.act_sum))
        self.act_sum = []
        self.act_list = []
        if self.off_ele_mod is not None:
            self.off_ele_mod.off()
        if self.shift_spd_mod is not None:
            self.shift_spd_mod.off()
        self.ds_reset()
        if not self.is_dragondrive:
            self.shift_silence = True
            Timer(self.end_silence).on(10)
            self.dragon_gauge_pause_timer = Timer(self.resume_auto_gauge).on(self.dragon_gauge_timer_diff)
        self.status = Action.OFF
        self._setprev() # turn self from doing to prev
        self._static.doing = self.nop
        self.end_event()
        self.idle_event()

    def d_dragondrive_end(self, t):
        self.dragon_gauge = 0
        log('dragondrive', 'end', t if isinstance(t, str) else '<timeout>')
        self.dragondrive_buff.off()
        self.shift_silence = True
        Timer(self.end_silence).on(10)
        self.status = Action.OFF
        self._setprev() # turn self from doing to prev
        self._static.doing = self.nop
        self.dragondrive_end_event()
        self.idle_event()

    def act_timer(self, act, time, next_action=None):
        if self.c_act_name == 'dodge':
            self.action_timer = Timer(act, time)
        else:
            self.action_timer = Timer(act, time / self.speed())
        self.action_timer.next_action = next_action
        return self.action_timer.on()

    def d_act_start_t(self, t):
        self.action_timer = None
        self.d_act_start(t.next_action)

    def d_act_start(self, name):
        if name in self.conf and self._static.doing == self and self.action_timer is None:
            self.prev_act = self.c_act_name
            self.prev_conf = self.c_act_conf
            self.c_act_name = name
            self.c_act_conf = self.conf[name]
            self.act_timer(self.d_act_do, self.c_act_conf.startup)

    def d_act_do(self, t):
        if self.c_act_name == 'end':
            self.d_shift_end(None)
            self.shift_end_timer.off()
            return
        
        actconf = self.conf[self.c_act_name]
        e = self.act_event
        e.name = self.c_act_name 
        e.base = self.c_act_name
        e.group = 'dragon'
        self.adv.actmod_on(e)
        
        try:
            getattr(self.adv, f'{self.c_act_name}_before')(e)
        except AttributeError:
            pass

        final_mt = self.adv.schedule_hits(e, self.conf[self.c_act_name])
        if final_mt:
            final_mt.actmod = True
            final_mt.actmod = True
            try:
                final_mt.proc = getattr(self.adv, f'{self.c_act_name}_proc')
            except AttributeError:
                pass
        else:
            self.adv.actmod_off(e)
            try:
                getattr(self.adv, f'{self.c_act_name}_proc')(e)
            except AttributeError:
                pass
        if self.c_act_name == 'ds':
            self.skill_use -= 1
            self.skill_spc = 0
            self.act_sum.append('s')
            self.ds_event()
            self.shift_end_timer.add(self.dstime())
        elif self.c_act_name.startswith('dx'):
            if len(self.act_sum) > 0 and self.act_sum[-1][0] == 'c' and int(self.act_sum[-1][1]) < int(self.c_act_name[-1]):
                self.act_sum[-1] = 'c'+self.c_act_name[-1]
            else:
                self.act_sum.append('c'+self.c_act_name[-1])
            self.dx_event.index = int(self.c_act_name[-1])
            self.dx_event()

        self.d_act_next()

    def d_act_next(self):
        nact = None
        if self.repeat_act and not self.act_list:
            self.parse_act(self.conf.act)
        if self.act_list:
            if self.act_list[0] not in ('ds', 'dsf') or self.ds_check():
                if self.act_list[0] == 'end' and not self.allow_end:
                    nact = None
                else:
                    nact = self.act_list.pop(0)
            # print('CHOSE BY LIST', nact, self.c_act_name)
        if nact is None:
            if self.c_act_name[0:2] == 'dx':
                nact = 'dx{}'.format(int(self.c_act_name[2])+1)
                if not nact in self.dx_list:
                    if self.ds_check():
                        nact = 'ds'
                    elif self.dodge_cancel():
                        nact = 'dodge'
                    else:
                        nact = 'dx1'
            else:
                nact = 'dx1'
            # print('CHOSE BY DEFAULT', nact, self.c_act_name)
        if self.has_delayed and nact == 'dsf':
            nact = 'ds'
            count = self.clear_delayed()
            if count > 0:
                log('cancel', self.c_act_name, f'by {nact}', f'lost {count} hit{"s" if count > 1 else ""}')
            return self.act_timer(self.d_act_start_t, self.conf.latency, nact)
        if nact in ('ds', 'dsf', 'dodge') or (nact == 'end' and self.c_act_name != 'ds'): # cancel
            if nact == 'dsf':
                nact = 'ds'
            self.act_timer(self.d_act_start_t, self.max_delayed+self.conf.latency, nact)
        else: # regular recovery
            self.act_timer(self.d_act_start_t, self.c_act_conf.recovery, nact)

    def parse_act(self, act_str):
        if self.status != Action.OFF and not self.repeat_act:
            return
        act_str = act_str.strip()
        self.act_list = []
        skill_usage = 0

        for a in act_str.split('-'):
            if a[0] == 'c' or a[0] == 'x':
                for i in range(1, int(a[1])+1):
                    dxseq = 'dx{}'.format(i)
                    if dxseq in self.dx_list:
                        self.act_list.append(dxseq)
                try:
                    if self.dodge_cancel() or self.act_list[-1] != self.dx_list[-1]:
                        self.act_list.append('dodge')
                except IndexError:
                    pass
            else:
                try:
                    if len(self.act_list) > 0 and self.act_list[-1] == 'dodge':
                        self.act_list.pop()
                except IndexError:
                    pass
                if (a in ('s', 'ds', 'sf', 'dsf')) and (self.skill_use <= -1 or skill_usage < self.skill_use):
                    if a[-1] == 'f':
                        self.act_list.append('dsf')
                    else:
                        self.act_list.append('ds')
                    skill_usage += 1
                elif a == 'end' and self.can_end:
                    self.act_list.append('end')
                elif a == 'dodge':
                    self.act_list.append('dodge')

    def act(self, act_str):
        self.parse_act(act_str)
        return self()

    @allow_acl
    def check(self, dryrun=True):
        if self.disabled or self.shift_silence:
            return False
        if self.dragon_gauge < self.shift_cost and not (self.is_dragondrive and self.dragondrive_buff.get()):
            return False
        doing = self.getdoing()
        if not doing.idle:
            if isinstance(doing, S) or isinstance(doing, DragonForm):
                return False
            if dryrun == False:
                if doing.status == Action.STARTUP:
                    doing.startup_timer.off()
                    log('interrupt', doing.name , 'by '+self.name, 'after {:.2f}s'.format(now()-doing.startup_start))
                elif doing.status == Action.RECOVERY:
                    doing.recovery_timer.off()
                    log('cancel', doing.name , 'by '+self.name, 'after {:.2f}s'.format(now()-doing.recover_start))
        return True

    def __call__(self):
        if not self.check(dryrun=False):
            return False
        if self.is_dragondrive:
            self.act_list = ['end']
            if self.dragondrive_buff.get():
                self.d_dragondrive_end('<turn off>')
                return True
            else:
                log('cast', 'dragondrive', self.name, f'base duration {self.dragon_gauge/self.drain:.4}s')
                self.dragondrive_timer.on(self.dragon_gauge/self.drain)
                self.dragondrive_buff.on()
        else:
            log('cast', 'dshift', self.name)
            if len(self.act_list) == 0:
                self.parse_act(self.conf.act)
            self.dragon_gauge -= self.shift_cost
            if self.off_ele_mod is not None:
                self.off_ele_mod.on()
            if self.shift_spd_mod is not None:
                self.shift_spd_mod.on()
            self.pause_auto_gauge()
        self.shift_count += 1
        self.status = Action.STARTUP
        self._setdoing()
        g_logs.log_shift_dmg(True)
        self.shift_start_time = now()
        self.shift_end_timer.on(self.dtime())
        self.reset_allow_end()
        self.shift_event()
        self.d_act_start('dshift')
        return True
