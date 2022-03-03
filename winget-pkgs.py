from pathlib import Path

import yaml
from mpkg.common import Soft, soft_data
from mpkg.config import SetConfig
from mpkg.parse import get_max_version
from mpkg.utils import Download, Extract

SetConfig('7z', '7z x {filepath} -o{root} -aoa > nul')


def parser(path: Path):
    soft = soft_data()
    with open(path, 'rb') as f:
        f = f.read().decode('utf-8')
    data = yaml.safe_load(f)
    soft.ver = str(data.get('PackageVersion'))
    # yaml.safe_load('ver:\n  2001-01-01')
    for item in data.get('Installers'):
        if item.get('Architecture') == 'x86':
            soft.arch['32bit'] = item['InstallerUrl']
            soft.sha256['32bit'] = item['InstallerSha256']
        elif item.get('Architecture') == 'x64':
            soft.arch['64bit'] = item['InstallerUrl']
            soft.sha256['64bit'] = item['InstallerSha256']
    return soft


def get_latest(manifests, depth=1):
    if not manifests:
        return
    versions = [manifest.as_posix().split('/')[-2] for manifest in manifests]
    version = get_max_version(versions, is_semver=False)
    manifest = manifests[versions.index(version)]
    data = parser(manifest)
    for i in range(depth):
        id_list = manifest.absolute().as_posix().split('/')[-3-i:-2]
    data.id = '.'.join(id_list)
    data.mpkg_src = f'{"/".join(id_list)}/{version}/{manifest.name}'
    data.id += '_winget'
    return data


class Package(Soft):
    ID = 'winget-pkgs'
    # ref: https://docs.microsoft.com/zh-cn/windows/package-manager/package/repository
    # ref: https://github.com/microsoft/winget-pkgs/blob/master/AUTHORING_MANIFESTS.md
    # ref: https://docs.microsoft.com/zh-cn/windows/package-manager/package/manifest

    def _prepare(self):
        self.data.ver = 'nightly'

        def extract(repo):
            url = f'https://github.com/{repo}/archive/master.zip'
            file = Download(url, output=False, directory=Path(f'tmp/{repo}'))
            return Extract(file)

        for repo in ['microsoft/winget-pkgs']:
            bucket = extract(repo)/'manifests'
            for letter in bucket.iterdir():
                for publisher in letter.iterdir():
                    for application in publisher.iterdir():
                        try:
                            manifests = {1: [], 2: [], 3: []}
                            for manifest in application.glob('**/*.installer.yaml'):
                                depth = manifest.relative_to(
                                    publisher).as_posix().count('/')-1
                                if depth > 3:
                                    print(manifest)
                                else:
                                    manifests[depth].append(manifest)
                            for depth in manifests:
                                soft = get_latest(manifests[depth], depth)
                                if soft:
                                    soft.mpkg_src = f'https://github.com/{repo}/blob/master/manifests/{letter.name}/{publisher.name}/'+soft.mpkg_src
                                    self.packages.append(
                                        soft.asdict(simplify=True))
                        except Exception as err:
                            print(
                                f'winget({publisher.name}/{application.name}): {err}')
                            # print(manifests)

        names = [data['id'] for data in self.packages]
        names_l = [data['id'].lower() for data in self.packages]
        conflicted = [(i, n)
                      for i, n in enumerate(names) if names_l.count(n.lower()) > 1]
        # mpkg show Server_winget*
        if conflicted:
            print(f'winget id conflict: {conflicted}')
        dict_ = dict([(n.lower(), []) for i, n in conflicted])
        for i, n in conflicted:
            dict_[n.lower()].append(i)
        for k, v in dict_.items():
            for i in v:
                self.packages[i]['id'] = f'{k}_{v.index(i)}'
