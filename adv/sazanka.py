from core.advbase import *
from module.bleed import Bleed, mBleed

def module():
    return Sazanka

class Sazanka(Adv):
    conf = {}
    conf['slots.a'] = ['Summer_Paladyns', 'The_Fires_of_Hate']
    conf['slots.poison.a'] = ['Summer_Paladyns', 'The_Fires_of_Hate']
    conf['acl'] = """
        `dragon(c3-s-end), s1.check()
        `s3, not buff(s3)
        `s4
        `s1
    """
    conf['coabs'] = ['Ieyasu', 'Wand', 'Bow']
    conf['afflict_res.sleep'] = 80
    conf['share.base'] = ['Kleimann']
    conf['share.poison'] = ['Curran']

    conf['mbleed'] = True


if __name__ == '__main__':
    from core.simulate import test_with_argv
    test_with_argv(None, *sys.argv)
