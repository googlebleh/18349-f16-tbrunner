#!/usr/bin/python

##
## @file run_tb.py
## @brief      Run the testbench for 18-349's RPi/JTAG setup.
## @author     Colin Wee <cwee@andrew.cmu.edu>
##
## @todo Implement missing command-line args
## @todo convert xterm to start_new_session=True
##

from __future__ import print_function
from __future__ import unicode_literals  # target may have funky pathnames

import sys
import os
import atexit
import time
import re
import subprocess
from argparse import ArgumentParser
from getpass import getuser
from glob import glob
from tempfile import TemporaryFile

try:  # python version probably > 3.3
    from shlex import quote as cmd_quote
    from shutil import which
except ImportError:  # backwards compatibility
    from pipes import quote as cmd_quote

    def which(file):
        for path in os.environ["PATH"].split(os.pathsep):
            if os.path.exists(os.path.join(path, file)):
                    return os.path.join(path, file)

        return None


##
## @brief      Target-dependent configuration. It's not likely you'll
##             change these values often.
##
## @details    Yes, I am aware it's bad practice to put config params
##             in the source. I opted to keep it all in one file so
##             users could just drop it wherever, instead of worrying
##             about where the config files were stored.
##
USER_CONFIG = {
    "ftditerm baudrate" : 115200,
    "OpenOCD timeout": 40,  ##< Max number of seconds to wait for OpenOCD
}


def sudo_kill(pid):
    cmd = ["sudo", "kill", str(pid)]
    print(' '.join(cmd))
    subprocess.Popen(cmd).wait()


def sudo_kill_popen(p):
    if p.poll() is None:
        # TOCTTOU
        sudo_kill(p.pid)


class TBRunner:
    ##
    ## Internal config. Modify this if you know what you're doing.
    ##
    FTDITERM_FPATH = which("ftditerm.py")
    MAKER = "make"
    # use xterm to launch another shell
    FS_XTERM_BASE = ["xterm", "-e"]  # append args here
    FORK_SHELL = FS_XTERM_BASE
    # command to sync starting GDB with
    OPENOCD_CMD_349 = re.escape(r"openocd -f 349util/rpi2.cfg") + "$"
    OOCD_CMD_REGEX = re.compile(OPENOCD_CMD_349)
    # quit gdb asap
    GDB_INPUT_STR = "c\nq\ny\n"  # 'y' just in case proc still running

    ##
    ## @param      user_cfg  Some misc. user configuration. See top of
    ##                       file.
    ## @param      argv      An argument vector to parse. See
    ##                       self.parse_args()
    ##
    def __init__(self, user_cfg, argv):
        self.prepare_runtime()
        self.parse_args(argv)
        self.process_cfg(user_cfg)
        self.setup_commands()

    ##
    ## @brief      Modify a command (to be passed to subprocess.Popen)
    ##             such that it runs in a new shell window.
    ##
    def newshell(self, cmd):
        return (TBRunner.FORK_SHELL + cmd)

    ##
    ## @brief      Preprocessing: determine some info about the calling
    ##             environment
    ##
    def prepare_runtime(self):
        git_cmd = ["git", "rev-parse", "--show-toplevel"]
        git_repo_root = subprocess.Popen(git_cmd, stdout=subprocess.PIPE)
        git_repo_root.wait()

        proj_root = git_repo_root.stdout.read().decode().strip()
        make_root = os.path.join(proj_root, "code")
        self.make_cmd = [TBRunner.MAKER, "-C", make_root, "--debug=j"]

        kernel_dpaths = glob(os.path.join(make_root, "kernel*"))
        self.proj_names = list(map(os.path.basename, kernel_dpaths))

    ##
    ## @brief      Wait for OpenOCD to be ready to connect to GDB.
    ## @param      stdout  A file-like obj for OpenOCD's stdout
    ##
    ## @return     0 once OpenOCD is ready, a negative error code if
    ##             the timeout was reached.
    ##
    def openocd_wait(self, stdout):
        # stdout.seek(0)
        start_time = time.time()
        while ((time.time() - start_time) < self.openocd_timeout):
            stdout_data = stdout.readline()
            if TBRunner.OOCD_CMD_REGEX.match(stdout_data.strip()):
                return 0
        return -1

    ##
    ## @brief      Parse argument vector.
    ## @param      argv  The argv, without the currently running
    ##                   filename (generally argv[0])
    ##
    def parse_args(self, argv):
        long_desc = "Run the testbench for 18-349's RPi/JTAG setup."
        ap = ArgumentParser(description=long_desc)

        ap.add_argument("-i", "--interactive", action="store_true",
                        help="Enable debugging in GDB"                      \
                             " (instead of exiting as soon as execution"    \
                             " halts)")

        ap.add_argument("--log",
                        help="File to copy ftditerm output to")

        ap.add_argument("-p", "--project", default="kernel",
                        choices=self.proj_names,
                        help="specify PROJECT variable to make")

        self.args = ap.parse_args(argv)

    ##
    ## @brief      Process user-specific config.
    ## @param      user_cfg  A mapping representing the user's cfg.
    ## @todo Add error-checking.
    ##
    def process_cfg(self, user_cfg):
        self.ftditerm_baud = user_cfg["ftditerm baudrate"]
        self.openocd_timeout = user_cfg["OpenOCD timeout"]

    ##
    ## @brief      Prepare shell commands to start testbench processes.
    ##
    def setup_commands(self):
        # FTDITerm
        if TBRunner.FTDITERM_FPATH is None:
            print("ERROR: FTDITerm not installed.", file=sys.stderr)
            print("  Follow instructions in Appendix A of Lab 0 handout",
                  file=sys.stderr)
            sys.exit(-1)
        base_cmd = [TBRunner.FTDITERM_FPATH, "-b", str(self.ftditerm_baud)]
        self.ftditerm_cmd = ["sudo"] + self.newshell(base_cmd)
        # OpenOCD
        self.openocd_cmd = ["sudo"] + self.make_cmd + ["openocd"]
        # GDB
        gdb_base_cmd = self.make_cmd + ["PROJECT=" + self.args.project, "gdb"]
        self.gdb_cmd = self.newshell(gdb_base_cmd)

    def run(self):
        ftditerm_p = subprocess.Popen(self.ftditerm_cmd)
        openocd_p = subprocess.Popen(self.openocd_cmd, stdout=subprocess.PIPE)

        # cleanup on exit
        atexit.register(sudo_kill_popen, openocd_p)
        atexit.register(sudo_kill_popen, ftditerm_p)

        if self.openocd_wait(openocd_p.stdout) < 0:
            print("ERROR: OpenOCD not ready within", self.openocd_timeout,
                  "seconds", file=sys.stderr)
            return 1

        gdb_p = subprocess.Popen(self.gdb_cmd, stdin=subprocess.PIPE,
                                 universal_newlines=True)
        if not self.args.interactive:
            gdb_p.stdin.write(TBRunner.GDB_INPUT_STR)
            # gdb_p.communicate(TBRunner.GDB_INPUT_STR)  # sick hack bro
            # try:
            # except TimeoutExpired:
            #     gdb_p.kill()
            #     gdb_p.communicate()

        try:
            openocd_p.wait()
        except KeyboardInterrupt:
            prog_name = os.path.basename(__file__)
            print()  # clear any garbage on this line
            print("{}: Cleaning up...".format(prog_name))
            if gdb_p.poll() is None:
                print("  closing GDB...")
                gdb_p.terminate()

        return 0


if __name__ == '__main__':
    tb = TBRunner(USER_CONFIG, sys.argv[1:])
    sys.exit(tb.run())
