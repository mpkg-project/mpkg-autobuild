#!/usr/bin/env python3
# coding: utf-8

import json
import os
import re
from multiprocessing.dummy import Pool
from sys import argv

from mpkg.config import HOME, GetConfig, SetConfig
from mpkg.load import HasConflict, Load, Prepare, Sorted
from mpkg.utils import GetPage, PreInstall

jobs = 10

s = GetPage(
    'https://github.com/mpkg-project/mpkg-autobuild/releases/download/AutoBuild/warning.txt')
merged = re.findall('^merging (.*)', s, re.M)
failed = re.findall('^failed: (.*)', s, re.M)
failed = failed[0].split('|') if failed else []
for string in re.findall('^ dependency: (.*)', s, re.M):
    failed += string.split('|')
merged = [x for x in merged if not x in failed]


def readlist(file) -> list:
    if not os.path.exists(file):
        return []
    with open(file, 'r', encoding='utf8') as f:
        return [line.strip() for line in f.read().splitlines()]


def loadsources(sources):
    with Pool(jobs) as p:
        items = [x for x in p.map(Load, sources) if x]
    softs, pkgs = Sorted(items)
    return softs, pkgs


def write(value):
    print('warning: '+value)
    with open('release/warning.txt', 'a') as f:
        f.write(value+'\n')


def getsofts(file, lock=[]):
    sources = readlist(file)
    if not sources:
        return []

    softs, pkgs = [], []
    if lock:
        for source in sources:
            if source in lock:
                softs_, pkgs_ = loadsources(sources)
                softs += softs_
                pkgs += pkgs_
            else:
                softs_, pkgs_ = loadsources(sources)
                for soft in softs_:
                    if soft['id'] in lock:
                        softs.append(soft)
                    else:
                        print(f'pass {soft["id"]}')
                for pkg in pkgs_:
                    if pkg.ID in lock:
                        pkgs.append(pkg)
                    else:
                        print(f'pass {pkg.ID}')
    else:
        softs, pkgs = loadsources(sources)

    score = HasConflict(softs, pkgs)
    if score:
        write(f'id conflict: {set(score)}')

    pkgs = [pkg for pkg in pkgs if not pkg.needConfig]
    with Pool(jobs) as p:
        err = [result for result in p.map(Prepare, pkgs) if result]
    if err:
        write('failed: ' + '|'.join([pkg.ID for pkg in err]))

    for soft in [pkg.json_data['packages'] for pkg in pkgs if pkg not in err]:
        softs += soft

    return softs


def merge_softs(old, new, output=False):
    old = dict([(soft['id'], soft) for soft in old])
    new = dict([(soft['id'], soft) for soft in new])
    for k, v in old.items():
        if not k in new:
            if k in merged:
                write(f'deprecate {k}')
            else:
                if output:
                    write(f'merging {k}')
                    if 'depends' in v:
                        write(' dependency: {0}'.format(
                            '|'.join(v['depends'])))
                new[k] = v
    return list(new.values())


PreInstall()
repo = argv[1]

if not os.path.exists('release'):
    os.mkdir('release')

os.system('mpkg set unsafe yes')

for type in ['main', 'extras', 'scoop']:
    os.system(
        f'wget -q https://github.com/{repo}/releases/download/AutoBuild/{type}.json')
    if not os.path.exists(f'{type}.json'):
        write(f'no history file: {type}.json')
        history = []
    else:
        with open(f'{type}.json', 'r', encoding='utf8') as f:
            history = json.load(f)['packages']
    lock = readlist(type+'.lock.list')
    patch = getsofts(type+'.patch.list', lock)
    softs = getsofts(type+'.list', lock)
    softs = merge_softs(softs, patch)
    softs = merge_softs(history, softs, output=True)

    data = {}
    data['packages'] = softs
    filename = 'release/'+type+'.json' if not type == 'scoop' else 'scoop.json'
    with open(filename, 'w', encoding='utf8') as f:
        f.write(json.dumps(data))

if not os.path.exists('release/warning.txt'):
    os.system('echo pass > release/warning.txt')
