from os.path import exists, join
from zipfile import ZipFile

from glob import glob
from buffer import Buffer
from s3d import readS3D
from wld import Wld
from zon import readZon
from zonefile import *


def s3dFallback(*filedicts):
    ndicts = []
    for files in filedicts:
        nfiles = {}
        ndicts.append(nfiles)
        for xfiles in filedicts:
            if xfiles is not files:
                nfiles.update(xfiles)
        nfiles.update(files)
    return ndicts


def eqPath(fn):
    return join(eqdata, fn).replace("\\", "/")


def convertOld(name):
    with ZipFile("%s.zip" % name, "w") as zip:
        zone = Zone()
        objfiles = {}
        for fn in glob(eqPath("%s_obj*.s3d" % name)):
            objfiles[fn.split("/")[-1][:-4]] = readS3D(open(fn, "rb"))
        zfiles = readS3D(open(eqPath("%s.s3d" % name), "rb"))
        flists = list(objfiles.values()) + [zfiles]
        flists = s3dFallback(*flists)
        for i, fn in enumerate(objfiles.keys()):
            objfiles[fn] = flists[i]
        zfiles = flists[-1]

        wld_instances = []
        for fn, sf in objfiles.items():
            print(fn)
            wld_obj = Wld(sf["%s.wld" % fn], sf)
            wld_obj.convertObjects(zone)
            wld_instances.append(wld_obj)

        objects_wld = Wld(zfiles["objects.wld"], zfiles)
        objects_wld.convertObjects(zone)
        wld_instances.append(objects_wld)

        lights_wld = Wld(zfiles["lights.wld"], zfiles)
        lights_wld.convertLights(zone)
        wld_instances.append(lights_wld)

        zone_wld = Wld(zfiles["%s.wld" % name], zfiles)
        zone_wld.convertZone(zone)
        wld_instances.append(zone_wld)

        # Print texture warning summary
        for wld in wld_instances:
            wld.print_texture_warnings()

        zone.output(zip)


def convertChr(name):
    name = name[:-4]
    files = readS3D(open(eqPath("%s_chr.s3d" % name), "rb"))
    with ZipFile("%s_chr.zip" % name, "w") as zip:
        chr_wld = Wld(files["%s_chr.wld" % name], files)
        chr_wld.convertCharacters(zip)
        chr_wld.print_texture_warnings()


def convertNew(name):
    with ZipFile("%s.zip" % name, "w") as zip:
        zone = Zone()
        zfiles = readS3D(open(eqPath("%s.eqg" % name), "rb"))
        # for fn, data in zfiles.items():
        #    open('s3data/%s' % fn, 'wb').write(data)
        if "%s.zon" % name in zfiles:
            readZon(zfiles["%s.zon" % name], zone, zfiles)
        else:
            readZon(open(eqPath("%s.zon" % name), "rb").read(), zone, zfiles)
        zone.output(zip)


def main(name):
    global eqdata, config

    with open("openeq.cfg", "r") as fp:
        configdata = fp.read()

    config = dict(
        [x.strip() for x in line.split("=", 1)]
        for line in [x.split("#", 1)[0] for x in configdata.split("\n")]
        if "=" in line
    )

    eqdata = config["eqdata"]

    if "_chr" in name:
        convertChr(name)
    elif exists(eqPath("%s.s3d" % name)):
        convertOld(name)
    elif exists(eqPath("%s.eqg" % name)):
        convertNew(name)
    else:
        print("Cannot find zone")
        return
    print("All Done")


if __name__ == "__main__":
    import sys

    main(*sys.argv[1:])
