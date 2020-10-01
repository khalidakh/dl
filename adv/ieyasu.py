from core.advbase import *
from module.bleed import Bleed

def module():
    return Ieyasu

class Ieyasu(Adv):
    conf = {}
    conf['slots.a'] = [
        'Resounding_Rendition',
        'Flash_of_Genius',
        'Moonlight_Party',
        'The_Plaguebringer',
        'Dueling_Dancers'
    ]
    conf['acl'] = """
        ##Use Gala Cat Sith only when out of Skillful Trickery
        `dragon(c3-s-end), self.trickery <= 1
        `s3, not buff(s3)
        `s1, buff(s3)
        `s2, x=5
        `s4, fsc or not self.afflics.poison.get()
        `fs, x=5 and buff(s3)
    """
    conf['coabs'] = ['Wand','Delphi','Axe2']
    conf['share.base'] = ['Rodrigo']
    conf['share.poison'] = ['Curran']

    def s2ifbleed(self):
        if self.bleed_stack > 0:
            return self.s2buff.get()
        return 0

    def prerun(self):
        self.s2buff = Selfbuff('s2',0.20,15,'crit')
        self.s2buff.modifier.get = self.s2ifbleed

    # @staticmethod
    # def prerun_skillshare(adv, dst):
    #     adv.bleed = Bleed('g_bleed',0).reset()

    # def s2_proc(self, e):
    #     self.s2buff.on()


if __name__ == '__main__':
    from core.simulate import test_with_argv
    test_with_argv(None, *sys.argv)
