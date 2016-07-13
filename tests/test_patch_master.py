#!/usr/bin/env python

import os
import nose
import struct
import subprocess
import logging
import patcherex.utils as utils

import patcherex
import shellphish_qemu
from patcherex.patch_master import PatchMaster

l = logging.getLogger("patcherex.test.test_patch_master")

bin_location = str(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../binaries-private'))
qemu_location = shellphish_qemu.qemu_path('cgc-tracer')


def test_run():
    def no_duplicate(tlist):
        return len(tlist) == len(set(tlist))

    fname = os.path.join(bin_location, "cgc_scored_event_2/cgc/0b32aa01_01")
    pm = PatchMaster(fname)
    patches = pm.run()
    nose.tools.assert_equal(len(patches) == pm.ngenerated_patches, True)

    nose.tools.assert_equal(len(patches)>1, True)
    nose.tools.assert_equal(no_duplicate(patches), True)

    with patcherex.utils.tempdir() as td:
        for i,(p,nrule) in enumerate(patches):
            tmp_fname = os.path.join(td,str(i))
            fp = open(tmp_fname,"wb")
            fp.write(p)
            fp.close()
            os.chmod(tmp_fname, 0755)
            pipe = subprocess.PIPE
            p = subprocess.Popen([qemu_location, tmp_fname], stdin=pipe, stdout=pipe, stderr=pipe)
            res = p.communicate("A"*10)
            expected = "\nWelcome to Palindrome Finder\n\n\tPlease enter a possible palindrome:" 
            nose.tools.assert_equal(expected in res[0], True)


def test_cfe_trials():
    def save_patch(fname,patch_content):
        fp = open(fname,"wb")
        fp.write(patch_content)
        fp.close()
        os.chmod(fname, 0755)

    tfolder = os.path.join(bin_location, "cfe_original")
    tests = utils.find_files(tfolder,"*",only_exec=True)
    inputs = ["","A","\x00"*10000,"A"*10000]

    bins = ["CROMU_00070","KPRCA_00016_1","KPRCA_00056","NRFIN_00073","CROMU_00071"]
    titerator = [t for t in tests if any([b in t for b in bins])]
    for tnumber,test in enumerate(titerator):
        with patcherex.utils.tempdir() as td:
            print "=====",str(tnumber+1)+"/"+str(len(titerator)),"building patches for",test
            pm = PatchMaster(test)
            patches = pm.run(return_dict=True)
            nose.tools.assert_equal(len(patches),pm.ngenerated_patches)

            for stdin in inputs:
                # TODO: test properly multi-cb, right now they are tested as separate binaries
                pipe = subprocess.PIPE
                p = subprocess.Popen([qemu_location, test], stdin=pipe, stdout=pipe, stderr=pipe)
                res = p.communicate(stdin)
                expected = (res[0],p.returncode)
                print expected

                for pname,(patch,nrule) in patches.iteritems():
                    print "testing:",os.path.basename(test),"input:",stdin[:10].encode("hex"),pname
                    tmp_fname = os.path.join(td,pname)
                    save_patch(tmp_fname,patch)
                    # save_patch("/tmp/aaa",patch)
                    nose.tools.assert_true(os.path.getsize(tmp_fname) > 1000)

                    p = subprocess.Popen([qemu_location, tmp_fname], stdin=pipe, stdout=pipe, stderr=pipe)
                    # very very partial support to network rules
                    # TODO if we add other "interesting rules", handle them here
                    if "bitflip" in nrule:
                        final_stdin = ''.join([chr((ord(c)^0xff) & 0xff) for c in stdin])
                    else:
                        final_stdin = stdin
                    res = p.communicate(final_stdin)
                    real = (res[0],p.returncode)
                    # there may be special cases in which the behavior changes
                    # because the patch prevent exploitation
                    # this is unlikely, given the naive inputs
                    nose.tools.assert_equal(real,expected)


def run_all():
    functions = globals()
    all_functions = dict(filter((lambda (k, v): k.startswith('test_')), functions.items()))
    for f in sorted(all_functions.keys()):
        if hasattr(all_functions[f], '__call__'):
            l.info("testing %s" % str(f))
            all_functions[f]()


if __name__ == "__main__":
    import sys
    logging.getLogger("patcherex.test.test_patch_master").setLevel("INFO")
    logging.getLogger("patcherex.backends.DetourBackend").setLevel("INFO")
    if len(sys.argv) > 1:
        globals()['test_' + sys.argv[1]]()
    else:
        run_all()

