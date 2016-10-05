18349-f16-tbrunner
==================
Script to manage the 18-349 testbench.

Prerequisites
-------------
An environment set up to run 18-349's testbench setup. See the **Lab 0
    handout, Appendix A** for detailed setup instructions.

Usage
-----
This script can be run from anywhere in the 349-f16 repository.

    usage: run_tb.py [-h] [-l LOGFILE] [-p {kernel,kernel_blink,kernel_optimization}]

    Run the testbench for 18-349's RPi/JTAG setup.

    optional arguments:
      -h, --help            show this help message and exit
      -l, --logfile LOGFILE Unimplemented: Write ftditerm output to file.
      -p, --project {kernel,kernel_blink,kernel_optimization}
                            specify PROJECT variable to make

Other usage notes
------------------
Running the script will create new terminal windows for FTDITerm and
    GDB. OpenOCD's output is visible in the same window from which the
    script was invoked.

In order to close all the windows, simply exit the script. This can be
    safely done with `^C` while the original window which ran the
    script is in focus. This is the same window that shows OpenOCD's
    output. Alternatively, each window may be closed individually.
NOTE: This has not been tested in the VM, but because of how
    OpenOCD is run, sending a `^C` to the original window can
    effectively close OpenOCD.

Finally, the script contains a global mapping called `USER_CONFIG`
    containing some parameters which may (rarely) need changing.
    Please do not delete any entries from this mapping; simply edit
    the values as necessary.

Expert mode
------------
See the block comment labeled `Internal config` in the source.

In order to run FTDITerm and GDB in an alternative terminal emulator,
    edit `TBRunner.FS_XTERM_BASE` accordingly.
