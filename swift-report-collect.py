#!/usr/bin/python
#
# Collect all known accounts, return one by line:
#  part/dir/hash
# For example:
#  5497/6ee/1579e4404e54e5edb53c00f1206696ee
#
# This is run at a storage node that serves accounts (over ssh, usually).

TAG="swift-report-collect"

import os
import sys
from iniparse import ConfigParser
from ConfigParser import NoSectionError, NoOptionError

# config()

class ConfigError(Exception):
    pass

def config(cfgname, inisect):
    cfg = { }
    cfgpr = ConfigParser()
    try:
        cfgfp = open(cfgname)
    except IOError, e:
        # This one contains the cfgname
        raise ConfigError(str(e))
    cfgpr.readfp(cfgfp)
    try:
        cfg["base"] = cfgpr.get(inisect, "devices")
    except NoSectionError, e:
        # Something is very wrong, should be at least an empty section
        raise ConfigError(cfgname+": "+str(e))
    except NoOptionError:
        cfg["base"] = "/srv/node"
    return cfg

def main():
    if len(sys.argv) != 2:
        print >>sys.stderr, "Usage: "+TAG+" devstr"
        sys.exit(1)
    devstr = sys.argv[1]

    cfgname = "/etc/swift/account-server.conf"
    try:
        cfg = config(cfgname, "DEFAULT")
    except ConfigError, e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

    topdir = os.path.join(cfg["base"], devstr, "accounts")

    accts = []
    plist = os.listdir(topdir)
    for p in plist:
        dlist = os.listdir(os.path.join(topdir, p))
        for d in dlist:
            hlist = os.listdir(os.path.join(topdir, p, d))
            for h in hlist:
                accts.append((p,d,h))

    for a in accts:
        print "%s/%s/%s" % (a[0],a[1],a[2])

if __name__ == "__main__":
    main()
