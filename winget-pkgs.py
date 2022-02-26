import os
from pathlib import Path

from mpkg.common import Soft, soft_data
from mpkg.utils import Download, Extract

os.system('pip install pyyaml -q')
try:
    import yaml
except ImportError:
    print('failed to import pyyaml')

os.system(r'mpkg set 7z "7z x {filepath} -o{root} -aoa > nul"')


def parser(path: Path):
    soft = soft_data()
    with open(path, 'rb') as f:
        f = f.read().decode('utf-8')
    data = yaml.safe_load(f)
    # path.absolute().as_posix().split('/')[-4:-2]
    soft.id = path.absolute().as_posix().split('/')[-3]
    soft.ver = data.get('PackageVersion')
    for item in data.get('Installers'):
        if item.get('Architecture') == 'x86':
            soft.arch['32bit'] = item['InstallerUrl']
            soft.sha256['32bit'] = item['InstallerSha256']
        elif item.get('Architecture') == 'x64':
            soft.arch['64bit'] = item['InstallerUrl']
            soft.sha256['64bit'] = item['InstallerSha256']
    return soft


class Package(Soft):
    ID = 'winget-pkgs'
    # ref: https://docs.microsoft.com/zh-cn/windows/package-manager/package/repository
    # ref: https://github.com/microsoft/winget-pkgs/blob/master/AUTHORING_MANIFESTS.md
    # ref: https://docs.microsoft.com/zh-cn/windows/package-manager/package/manifest
    letters = 'abcdefghijklmnopqrstuvwxyz1234567890'

    def _prepare(self):
        self.data.ver = 'nightly'

        def extract(repo):
            url = f'https://github.com/{repo}/archive/master.zip'
            file = Download(url, output=False, directory=Path(f'tmp/{repo}'))
            return Extract(file)

        for repo in ['microsoft/winget-pkgs']:
            manifests = extract(repo)/'manifests'
            for lettter in self.letters:
                if (manifests/lettter).exists():
                    for publisher in (manifests/lettter).iterdir():
                        for application in publisher.iterdir():
                            try:
                                versions = [v for v in os.listdir(
                                    application) if not v.startswith('.')]
                                version = sorted(versions, key=lambda x: tuple(
                                    map(int, x.split('.'))))[-1]
                                path = application/version
                                for mainfest in path.iterdir():
                                    if mainfest.name.endswith('.installer.yaml'):
                                        data = parser(mainfest)
                                        if data:
                                            data.id += '_winget'
                                            self.packages.append(
                                                data.asdict(simplify=True))
                            except Exception as err:
                                print(f'winget({application}): '+str(err))

        names = [data['id'] for data in self.packages]
        names_l = [data['id'].lower() for data in self.packages]
        conflicted = [(i, n)
                      for i, n in enumerate(names) if names_l.count(n.lower()) > 1]
        if conflicted:
            print(f'winget id conflict: {conflicted}')
        dict_ = dict([(n.lower(), []) for i, n in conflicted])
        for i, n in conflicted:
            dict_[n.lower()].append(i)
        for k, v in dict_.items():
            for i in v:
                self.packages[i]['id'] = f'{k}_{v.index(i)}'
