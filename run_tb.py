#!/usr/bin/python

##
## @file run_tb.py
## @brief      Run the testbench for 18-349's RPi/JTAG setup.
## @author     Colin Wee <cwee@andrew.cmu.edu>
##
## @details    Yes, I am aware it's bad practice to put so much config
##             stuff in the source. I opted to keep it all in one file
##             so users could just drop it wherever, instead of
##             worrying about where the config files were stored.
##

# from __future__ import generators
from __future__ import print_function
# from __future__ import unicode_literals

import sys
import os
import time
import subprocess
from argparse import ArgumentParser
from glob import glob

##
## @brief      Target-dependent configuration.
##
ftditerm_path = "/home/cw/Downloads/software_setup/18349/ftditerm/ftditerm.py"
ftditerm_baud = 115200

##
## More config. Modify this if you know what you're doing.
##
maker = "make"  # some people may need to specify `gmake`
openocd_cmd = [maker, "openocd"]
FS_XTERM_BASE = ["xterm", "-e"]  # append args
FORK_SHELL = FS_XTERM_BASE
openocd_cmd_349 = "openocd -f 349util/rpi2.cfg"
oocd_cmd_regex_str = re.escape(openocd_cmd_349)
oocd_cmd_regex = re.compile(oocd_cmd_regex_str, re.MULTILINE)

##
## Preprocessing: determine some info about the current environment
##
git_repo_root = subprocess.Popen(["git", "rev-parse", "--show-toplevel"],
                                 stdout=subprocess.PIPE)
git_repo_root.wait()
proj_root = git_repo_root.stdout.read().decode().strip()
make_root = os.path.join(proj_root, "code")

kernel_dpaths = glob(os.path.join(make_root, "kernel*"))
proj_names = list(map(os.path.basename, kernel_dpaths))


def parse_args():
    long_desc = "Run the testbench for 18-349's RPi/JTAG setup."
    ap = ArgumentParser(description=long_desc)
    ap.add_argument("-p", "--project", default="kernel", choices=proj_names,
                    help="specify PROJECT variable to make")
    ap.add_argument("--log", help="specify file to copy ftditerm output to")
    return ap.parse_args()


def main():
    # check usage
    if os.getuid() != 0:
        err_str = "ERROR: root permissions required to run 18-349 testbench"
        print(err_str, file=sys.stderr)
        print("usage: sudo", __file__, file=sys.stderr)
        return 1

    args = parse_args()

    # setup commands
    ftditerm_cmd = [ftditerm_path, "-b", str(ftditerm_baud)]
    gdb_cmd = [maker, "PROJECT=" + args.project, "gdb"]
    gdb_cmd = ["python"]

    ftditerm_p = subprocess.Popen(FORK_SHELL + ftditerm_cmd)
    openocd_p = subprocess.Popen(FORK_SHELL + openocd_cmd)

    time.sleep(15)
    # for loop, oocd_cmd_regex.match(output)

    gdb_p = subprocess.Popen(FORK_SHELL + gdb_cmd)

    input("--> ")

    openocd_p.poll()
    if openocd_p.returncode is None:
        openocd_p.terminate()

    ftditerm_p.poll()
    if ftditerm_p.returncode is None:
        ftditerm_p.terminate()

    return 0


if __name__ == '__main__':
    sys.exit(main())
