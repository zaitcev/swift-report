#!/usr/bin/python
##
## Master for Swift consistency checking
##
TAG="swift-report"

# The master host where this is run must have an ssh access to
# storage nodes as defined in the ring. Sometimes it's the proxy,
# sometimes a master admin node and a bastion. Just make sure IPs
# are routable and ~/.ssh/authorized_keys is set.

# XXX This currently requires pre-positioning of swift-report-collect.py
# on the storage nodes in ${collect_path}. No attempt is made
# to upload swift-report-collect.py through ssh. It is all pretty
# badly hardcoded and incomplete.

#import os
import subprocess
import sys

from StringIO import StringIO
from iniparse import ConfigParser
from ConfigParser import NoSectionError, NoOptionError

from keystoneclient.v2_0 import client as keystone_client
from swift.common.ring import Ring
from swift.common.utils import hash_path

class LocalError(Exception):
    pass

class JointAccount(object):
    def __init__(self, accstr):
        self.accstr = accstr
        self.in_swift = False
        self.in_keystone = False
        self.name = None           # only valid when in_keystone

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
        # Using traditional keystonerc names
        cfg["tenant"] = cfgpr.get(inisect, "os_tenant_name")
        cfg["user"] = cfgpr.get(inisect, "os_username")
        cfg["pass"] = cfgpr.get(inisect, "os_password")
        cfg["authurl"] = cfgpr.get(inisect, "os_auth_url")
        #
        cfg["collpath"] = cfgpr.get(inisect, "collect_path")
    except NoSectionError, e:
        raise ConfigError(cfgname+": "+str(e))
    except NoOptionError, e:
        raise ConfigError(cfgname+": "+str(e))

    return cfg

# Param

class ParamError(Exception):
    pass

class Param:
    def __init__(self, argv):
        skip = 1;
        self.cfgname = None
        self.ringfn = None
        self.verbose = False
        for i in range(len(argv)):
            if skip:
                skip = 0
                continue
            arg = argv[i]
            if len(arg) != 0 and arg[0] == '-':
                if arg == "-c":
                    if i+1 == len(argv):
                        raise ParamError("Parameter -c needs an argument")
                    self.cfgname = argv[i+1];
                    skip = 1;
                elif arg == "-v":
                    self.verbose = True
                else:
                    raise ParamError("Unknown parameter " + arg)
            else:
                # raise ParamError("Parameters start with dashes")
                self.ringfn = arg
        if self.cfgname == None:
            raise ParamError("Mandatory parameter -c is missing")
        if self.ringfn == None:
            raise ParamError("Mandatory parameter account.ring.gz is missing")
        # convenience
        self.cfg = None

# XXX These are not "hosts" but "devices", so we may re-visit the same host.
# Returns a list of tuples [(ip,part)].
def get_stor_hosts(r):
    ret = []
    for dev in r.devs:
        # discard dev['port'] - not needed for ssh
        ret.append((dev['ip'],dev['device']))
    return ret

# Run ssh to every known device's host and collect accounts;
# Update accset in-place.
def fetch_swift_accounts(accset, par, stordevs):

    ssh_opts="-o ConnectTimeout=1 -o StrictHostKeyChecking=no"
    # XXX Silly to have just path and explicit python, make it 755 or something
    ssh_cmd="python %s" % par.cfg["collpath"]

    for dev in stordevs:
        ssh_remote = "%s %s" % (ssh_cmd, dev[1])
        pargs = "ssh %s %s %s" % (ssh_opts, dev[0], ssh_remote)
        # XXX go to shell=False later, needs tokenizing arguments
        p = subprocess.Popen(pargs, stdout=subprocess.PIPE, shell=True)
        # The errors actually go to terminal, so no need to capture them here.
        # We capture all of the out pipe because we do not know how to plug
        # into Popen.communicate(). Then, we make a file-like object from
        # the pipe contents string and use readline() on it. Yee-haaw.
        out = p.communicate()[0]
        sfp = StringIO(out)
        while 1:
            line = sfp.readline()
            if len(line)==0:
                break
            accstr = line.rstrip("\r\n")
            # Check basic syntax, just in case
            if len(accstr.split('/')) != 3:
                continue
            a = accset.get(accstr, JointAccount(accstr))
            a.in_swift = True
            accset[accstr] = a
        # XXX Check exit code
        excode = p.wait()

def find_storage_url(par, keystone):

    # Ultimately, we want for each user on ulist to find the corresponding
    # Storage URL. Swift client does it by supplying credentials for
    # authentication to Keystone server, which then substitutes into
    # the endpoint pattern and returns the result as a side effect.
    # We cannot do that, because we do not have a password, and Keystone
    # does not have a way to issue such 3-rd party lookup. Therefore,
    # we find the Swift endpoint outselves, and substitute, essentially
    # replicating what Keystone server does.

    slist = keystone.services.list()
    swift_svc = None
    for svc in slist:
        if svc.type == 'object-store':
            swift_svc = svc
            break
    if not swift_svc:
        raise LocalError("No 'object-store' service")

    if par.verbose:
        print "SwiftID", swift_svc.id

    elist = keystone.endpoints.list()
    swift_ep = None
    for ep in elist:
        if ep.service_id == swift_svc.id:
            swift_ep = ep
            break
        # print ep.service_id, ep.publicurl
    if not swift_ep:
        raise LocalError("No endpoint for service id %s" % swift_svc.id)
    if par.verbose:
        print "SwiftURL", swift_ep.publicurl
    return swift_ep.publicurl

def interpolate(swift_url, user_id):
    v = swift_url.replace('$(', '%(')
    d = {'tenant_id': user_id}
    return v % d

# Take the StorageURL and identify the account.
# Swift server does it as a part of generic URL parsing.
# Our function only works for URL without container (and/or object, of course).
def url_to_swift_account(storage_url):
    return storage_url.split('/')[-1]

# Update accset in-place with Keystone accounts.
def fetch_keystone_accounts(accset, par, r):
    cfg = par.cfg
    keystone = keystone_client.Client(username=cfg["user"],
        password=cfg["pass"], tenant_name=cfg["tenant"],
        auth_url=cfg["authurl"])
    # keystone.authenticate()

    # XXX relocate to main() because sys.exit()
    try:
        swift_url = find_storage_url(par, keystone)
    except LocalError, e:
        print >>sys.stderr, TAG+":", str(e)
        sys.exit(1)

    ulist = keystone.tenants.list()
    for user in ulist:
        # print user.id, "enabled" if user.enabled else "disabled", user.name
        account = url_to_swift_account(interpolate(swift_url, user.id))

        hash_str = hash_path(account)
        part, nodes = r.get_nodes(account)
        accstr = "%s/%s/%s" % (part, hash_str[-3:], hash_str)

        a = accset.get(accstr, JointAccount(accstr))
        a.in_keystone = True
        a.name = user.name
        accset[accstr] = a

# 1. find list of hosts from Ring
# 2. log to them, collect Swift accounts
# 3. compare with known accounts (from Keystone, e.g.)
def main():
    try:
        par = Param(sys.argv)
    except ParamError, e:
        print >>sys.stderr, TAG+": Error in arguments:", e
        print >>sys.stderr,\
              "Usage:", TAG+" [-v] -c "+TAG+".conf"+" account.ring.gz"
        sys.exit(1)
    try:
        par.cfg = config(par.cfgname, "main")
    except ConfigError, e:
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

    # This used to be a set, but we want attributes attached to its members.
    accset = dict()

    try:
        r = Ring(par.ringfn)
    except IOError, e:
        # ENOENT most likely
        print >>sys.stderr, TAG+":", e
        sys.exit(1)

    if par.verbose:
        print "Loading"
    stordevs = get_stor_hosts(r)
    if par.verbose:
        print "Scanning hosts"
    fetch_swift_accounts(accset, par, stordevs)
    if par.verbose:
        print "Poking Keystone"
    fetch_keystone_accounts(accset, par, r)

    lmax = 0
    for key in accset:
        l = len(key)
        if l > lmax: lmax = l

    for key in accset:
        a = accset[key]

        keystr = " "*(lmax-len(key)) + key

        bitstr = ""
        bitstr += ("S" if a.in_swift else "-")
        bitstr += ("K" if a.in_keystone else "-")

        if a.name:  # same as a.in_keystone in this case
            namestr = a.name
        else:
            namestr = "-"

        print keystr, bitstr, namestr

if __name__ == "__main__":
    main()
