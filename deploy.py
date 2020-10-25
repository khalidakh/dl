import os
import sys
import hashlib
import json
from copy import deepcopy
from time import monotonic, time_ns
import core.simulate
from conf import ROOT_DIR, load_equip_json, load_adv_json, list_advs

ADV_DIR = 'adv'
CHART_DIR = 'www/dl-sim'
DURATIONS = (60, 120, 180)
SKIP_VARIANT = ('RNG', 'mass')

def sha256sum(filename):
    if not os.path.exists(filename):
        return None
    h = hashlib.sha256()
    b = bytearray(128*1024)
    mv = memoryview(b)
    with open(filename, 'rb', buffering=0) as f:
        for n in iter(lambda : f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


def sim_adv(name, variants, sanity_test=False):
    t_start = monotonic()
    is_mass = 'mass' in variants
    msg = []
    for v, adv_module in variants.items():
        if v in SKIP_VARIANT:
            continue
        verbose = -5
        outfile = None
        outpath = None
        mass = 1000 if is_mass and not sanity_test else None
        if sanity_test:
            durations = (30,)
            outpath = os.devnull
        else:
            if v is None:
                durations = DURATIONS
                outfile = f'{name}.csv'
            else:
                durations = (180,)
                outfile = f'{name}.{v}.csv'
            outpath = os.path.join(ROOT_DIR, CHART_DIR, 'chara', outfile)
        sha_before = sha256sum(outpath)
        output = open(outpath, 'w')
        try:
            for d in durations:
                run_results = core.simulate.test(
                    name, adv_module, {},
                    duration=d, verbose=verbose, mass=mass,
                    special=v is not None, output=output
                )
            if not sanity_test:
                print(f'{monotonic() - t_start:.4f}s - sim:{name}', flush=True)
                if sha_before != sha256sum(outpath):
                    msg.append(run_results[0][0].slots.c.icon)
        except Exception as e:
            print(f'\033[91m{monotonic()-t_start:.4f}s - sim:{name} {e}\033[0m', flush=True)
        finally:
            output.close()
    return msg


def run_and_save(name, module, ele, dkey, ekey, conf, repair=False):
    if ekey == 'affliction':
        aff_name = core.simulate.ELE_AFFLICT[ele]
        conf[f'sim_afflict.{aff_name}'] = 1
    with open(os.devnull, 'w') as output:
        run_res = core.simulate.test(name, module, conf, duration=int(dkey), verbose=0, output=output)
        core.simulate.save_equip(run_res[0][0], run_res[0][1], repair=repair, etype=ekey)


def repair_equips(name, variants):
    t_start = monotonic()
    try:
        module = variants[None]

        adv_ele = load_adv_json(name)['c']['ele']
        adv_equip = deepcopy(load_equip_json(name))
        for dkey, equip_d in adv_equip.items():
            pref = equip_d.get('pref', 'base')
            for ekey, conf in equip_d.items():
                if ekey == 'pref':
                    continue
                run_and_save(name, module, adv_ele, dkey, ekey, conf, repair=True)
                # if affliction, check if base equip actually better
                if ekey == 'affliction':
                    try:
                        run_and_save(name, module, adv_ele, dkey, ekey, equip_d['base'])
                    except KeyError:
                        pass
                # check if 180 equip is actually better for 120/60
                if dkey == '180':
                    continue
                try:
                    run_and_save(name, module, adv_ele, dkey, ekey, adv_equip['180'][ekey])
                except KeyError:
                    pass
    except Exception as e:
        print(f'\033[91m{monotonic()-t_start:.4f}s - repair:{name} {e}\033[0m', flush=True)
        return
    print('{:.4f}s - repair:{}'.format(monotonic() - t_start, name), flush=True)


def combine():
    t_start = monotonic()

    dst_dict = {}
    pages = [str(d) for d in DURATIONS] + ['sp']
    aff = ['_', 'affliction']
    for p in pages:
        dst_dict[p] = {}
        for a in aff:
            dst_dict[p][a] = open(os.path.join(
                ROOT_DIR, CHART_DIR, 'page/{}_{}.csv'.format(p, a)), 'w')

    for fn in os.listdir(os.path.join(ROOT_DIR, CHART_DIR, 'chara')):
        if not fn.endswith('.csv'):
            continue
        with open(os.path.join(ROOT_DIR, CHART_DIR, 'chara', fn), 'r', encoding='utf8') as chara:
            for line in chara:
                if line[0] == '-':
                    _, c_page, c_aff = line.strip().split(',')
                else:
                    dst_dict[c_page][c_aff].write(line.strip())
                    dst_dict[c_page][c_aff].write('\n')

    for p in pages:
        for a in aff:
            dst_dict[p][a].close()
            dst_dict[p][a].close()

    with open(os.path.join(ROOT_DIR, CHART_DIR, 'page/lastmodified.json'), 'r+') as f:
        try:
            lastmod = json.load(f)
        except:
            lastmod = {}
        f.truncate(0)
        f.seek(0)
        lastmod['timestamp'] = time_ns() // 1000000
        try:
            lastmod['message'] = lastmod['changed']
            del lastmod['changed']
        except KeyError:
            lastmod['message'] = []
        json.dump(lastmod, f)

    print(f'{monotonic() - t_start:.4f}s - combine', flush=True)


def get_sim_target_modules(targets):
    target_modules = {}
    if all([cmd not in targets for cmd in ('all', 'quick', 'slow')]):
        for adv in targets:
            try:
                core.simulate.load_adv_module(adv, in_place=target_modules)
            except Exception as e:
                print(f'\033[93m{0:.4f}s - load:{adv} {e}\033[0m', flush=True)
        return target_modules

    for adv in list_advs():
        try:
            core.simulate.load_adv_module(adv, in_place=target_modules)
        except Exception as e:
            print(f'\033[93m{0:.4f}s - load:{adv} {e}\033[0m', flush=True)
    if 'all' in targets:
        return target_modules
    if 'quick' in targets:
        for adv, variants in target_modules.copy().items():
            if 'mass' in variants:
                del target_modules[adv]
        return target_modules
    if 'slow' in targets:
        for adv, variants in target_modules.copy().items():
            if not 'mass' in variants:
                del target_modules[adv]
        return target_modules

def main(arguments):
    do_combine = False
    is_repair = False
    sanity_test = False
    if '-c' in arguments:
        do_combine = True
        arguments.remove('-c')
    if '-san' in arguments:
        sanity_test = True
    if '-rp' in arguments:
        arguments.remove('-rp')
        is_repair = True

    target_modules = get_sim_target_modules(arguments)

    message = []
    if is_repair:
        for name, variants in target_modules.items():
            repair_equips(name, variants)
        return
    else:
        for name, variants in target_modules.items():
            message.extend(sim_adv(name, variants, sanity_test=sanity_test))

    if sanity_test:
        return

    with open(os.path.join(ROOT_DIR, CHART_DIR, 'page/lastmodified.json'), 'r+') as f:
        try:
            lastmod = json.load(f)
        except:
            lastmod = {}
        f.truncate(0)
        f.seek(0)
        try:
            lastmod['changed'].extend(message)
        except KeyError:
            lastmod['changed'] = message
        json.dump(lastmod, f)

    if do_combine:
        combine()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('USAGE python {} sim_targets [-c] [-sp]'.format(sys.argv[0]))
        exit(1)
    t_start = monotonic()
    main(sys.argv.copy()[1:])
    print('total: {:.4f}s'.format(monotonic() - t_start))
