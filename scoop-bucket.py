import os
from pathlib import Path

from mpkg.common import Soft
from mpkg.load import Load
from mpkg.utils import Download, Extract

#os.system('sudo apt-get update')
#os.system('sudo apt-get install -y p7zip-full')
os.system(r'mpkg set 7z "7z x {filepath} -o{root} -aoa > nul"')


class Package(Soft):
    ID = 'scoop-bucket'

    def _prepare(self):
        self.data.ver = 'nightly'
        parser = Load(
            'https://github.com/zpcc/mpkg-pkgs/raw/master/parser/common.py->common-scoop_bucket.py')[0][0].scoop

        def load(file):
            with open(file, 'r', encoding='utf-8') as f:
                try:
                    data = parser(file, data=f.read(), getbin=True,
                                  getlnk=True, detail=False)
                except Exception as err:
                    print(f'scoop({file}): '+str(err))
                    return
                data.id += '_scoop'
                return data

        def extract(repo):
            url = f'https://github.com/{repo}/archive/master.zip'
            file = Download(url, output=False, directory=Path(f'tmp/{repo}'))
            return Extract(file)

        for repo in ['ScoopInstaller/Main', 'lukesampson/scoop-extras']:
            bucket = extract(repo)/'bucket'
            for file in os.listdir(bucket):
                if file.endswith('.json'):
                    data = load(str(bucket/file))
                    if data:
                        self.packages.append(data.asdict(simplify=True))
