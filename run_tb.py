#!/usr/bin/python

##
## @file run_tb.py
## @brief      Run the testbench for 18-349's RPi/JTAG setup.
## @author     Colin Wee <cwee@andrew.cmu.edu>
##
## @todo Add capability to be run from anywhere (and specify repo path)
## @todo Implement commented command-line args.
## @todo Check for existing FTDITerm sessions before launching.
## @todo Run FTDITerm by imports rather than by invoking its script.
##
## @details    On the choice of xterm as the terminal emulator,
##             I simply chose it for its availability. It should be
##             included in most Linux distros, and I believe it's
##             included in the Mac setup too. This can be configured
##             by the TBRunner.FORK_SHELL attribute.
##

from __future__ import print_function
from __future__ import unicode_literals  # target may have funky pathnames

import atexit
import copy
import itertools  # different between Python 2 and 3
import os
import re
import subprocess
import sys
import time
from argparse import ArgumentParser
from glob import glob

try:  # python version probably > 3.3
    from shlex import quote as cmd_quote
    from shutil import which

    def partition(pred, iterable):
        'Use a predicate to partition entries into false and true entries'
        # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
        # https://docs.python.org/dev/library/itertools.html#itertools-recipes
        t1, t2 = itertools.tee(iterable)
        return itertools.filterfalse(pred, t1), filter(pred, t2)

except ImportError:  # backwards compatibility
    from pipes import quote as cmd_quote

    def which(file):
        for path in os.environ["PATH"].split(os.pathsep):
            if os.path.exists(os.path.join(path, file)):
                    return os.path.join(path, file)

        return None

    def partition(pred, iterable):
        'Use a predicate to partition entries into false and true entries'
        # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
        # https://docs.python.org/dev/library/itertools.html#itertools-recipes
        t1, t2 = itertools.tee(iterable)
        return itertools.ifilterfalse(pred, t1), itertools.ifilter(pred, t2)


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
    "FTDITerm Baudrate": 115200,
    "OpenOCD timeout": 40,  ##< Max number of seconds to wait for OpenOCD
}


##
## @brief      Kill a process as root.
## @param      pid   PID of the process to kill
## @return     Exit code of `kill`
##
def sudo_kill(pid):
    cmd = ["sudo", "kill", str(pid)]
    print(' '.join(cmd))
    kill_p = subprocess.Popen(cmd)
    kill_p.wait()
    return kill_p.returncode


##
## @brief      Kill a process as root.
## @param      p     subprocess.Popen object representing a process.
## @return     Exit code of `kill`, or None if the process is no longer
##             running.
##
def sudo_kill_popen(p):
    if p.poll() is None:
        # TOCTTOU
        return sudo_kill(p.pid)


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
    ## @brief      Wait for OpenOCD to be ready to connect to GDB.
    ## @param      stdout  A file-like obj for OpenOCD's stdout
    ##
    ## @return     0 once OpenOCD is ready, a negative error code if
    ##             the timeout was reached.
    ##
    def openocd_wait(self, stdout):
        start_time = time.time()
        while ((time.time() - start_time) < self.openocd_timeout):
            try:
                stdout_data = stdout.readline()

            except UnicodeDecodeError:
                pass  # this isn't the line we're looking for

            else:
                if TBRunner.OOCD_CMD_REGEX.match(stdout_data.strip()):
                    return 0
        return -1

    ##
    ## @brief      Preprocessing: determine some info about the calling
    ##             environment
    ##
    def prepare_runtime(self):
        # setup make command
        repo_root = subprocess.Popen(["git", "rev-parse", "--show-toplevel"],
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        repo_root_outp, _ = repo_root.communicate()
        if repo_root.returncode:
            prog_name = os.path.basename(__file__)
            print("ERROR:", prog_name, "must be run from within 349 git repo",
                  file=sys.stderr)
            sys.exit(128)

        proj_root = repo_root_outp.strip()
        make_root = os.path.join(proj_root, "code")
        self.make_cmd = [TBRunner.MAKER, "-C", make_root]

        # collect possible things to make
        makeable_fpaths = glob(os.path.join(make_root, "*/config.mk"))
        makeable_dpaths = map(os.path.dirname, makeable_fpaths)
        makeable_dnames = map(os.path.basename, makeable_dpaths)
        u_p = partition(lambda d: d.startswith("kernel"), makeable_dnames)
        self.uproj_names = list(u_p[0])
        self.proj_names = list(u_p[1])

    ##
    ## @brief      Parse argument vector.
    ## @param      argv  The argv, without the currently running
    ##                   filename (generally argv[0])
    ##
    def parse_args(self, argv):
        long_desc = "Run the testbench for 18-349's RPi/JTAG setup."
        ap = ArgumentParser(description=long_desc)
        # ap.add_argument("-f", "--no-ftdi", action="store_true",
        #                 help="Don't start a new FTDITerm session")
        #
        ap.add_argument("-l", "--logfile",
                        help="UNIMPLEMENTED: Write ftditerm output to file.")

        help_fmt = "specify PROJECT variable to make as one of: {{{}}}"
        ap.add_argument("-p", "--project", default="kernel",
                        choices=self.proj_names, metavar="",
                        help=help_fmt.format(", ".join(self.proj_names)))

        help_fmt = "specify USER_PROJ variable to make as one of: {{{}}}"
        ap.add_argument("-u", "--user-proj", choices=self.uproj_names,
                        metavar="",
                        help=help_fmt.format(", ".join(self.uproj_names)))
        self.args = ap.parse_args(argv)

    ##
    ## @brief      Process user-specific config.
    ## @param      user_cfg  A mapping representing the user's cfg.
    ## @todo Add error-checking.
    ##
    def process_cfg(self, user_cfg):
        self.ftditerm_baud = user_cfg["FTDITerm Baudrate"]
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
        base_cmd = copy.copy(self.make_cmd)
        base_cmd.append("PROJECT=" + self.args.project)
        if self.args.user_proj:
            base_cmd.append("USER_PROJ=" + self.args.user_proj)
        base_cmd.append("gdb")
        self.gdb_cmd = self.newshell(base_cmd)

    def run(self):
        ftditerm_p = subprocess.Popen(self.ftditerm_cmd)
        openocd_p = subprocess.Popen(self.openocd_cmd,
                                     stdout=subprocess.PIPE,
                                     universal_newlines=True)
        # cleanup on exit
        atexit.register(sudo_kill_popen, openocd_p)
        atexit.register(sudo_kill_popen, ftditerm_p)

        if self.openocd_wait(openocd_p.stdout) < 0:
            print("ERROR: OpenOCD not ready within", self.openocd_timeout,
                  "seconds", file=sys.stderr)
            return 1
        gdb_p = subprocess.Popen(self.gdb_cmd)

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
