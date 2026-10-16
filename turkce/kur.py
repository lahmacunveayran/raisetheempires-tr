"""Türkçe yamayı kurar: turkce/mod/turkce klasörünü oyunun My Games klasöründeki mods altına kopyalar ve açar.

Kullanım (repo klasöründen):  python turkce/kur.py [My Games klasörü]
Klasör verilmezse RaiseTheEmpires.ini içindeki MyGamesPath kullanılır (sunucunun okuduğu dosya).
"""
import configparser
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(HERE, "mod", "turkce")


def my_games_from_ini():
    for folder in (os.getcwd(), ROOT):
        path = os.path.join(folder, "RaiseTheEmpires.ini")
        if not os.path.exists(path):
            continue
        for encoding in ("utf-8", "cp1254", "mbcs"):
            config = configparser.ConfigParser()
            try:
                config.read(path, encoding=encoding)
                return config["InstallFolders"]["MyGamesPath"]
            except (UnicodeDecodeError, KeyError, LookupError):
                continue
    return None


def enable(mods_folder):
    conf = os.path.join(mods_folder, "mods.conf")
    config = configparser.ConfigParser()
    if os.path.exists(conf):
        config.read(conf, encoding="utf-8")
    if "mods" not in config:
        config["mods"] = {}
    config["mods"]["turkce"] = "true"
    with open(conf, "w", encoding="utf-8") as f:
        config.write(f)


def main():
    my_games = sys.argv[1] if len(sys.argv) > 1 else my_games_from_ini()
    if not my_games or not os.path.isdir(my_games):
        sys.exit("My Games klasörü bulunamadı. Klasörü elle verin: python turkce/kur.py \"<My Games klasörü>\"")
    mods_folder = os.path.join(my_games, "mods")
    target = os.path.join(mods_folder, "turkce")
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(MOD, target)
    enable(mods_folder)
    print("Türkçe yama kuruldu:", target)
    print("Sunucuyu yeniden başlatın.")


if __name__ == "__main__":
    main()
