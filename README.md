# 18349-f16-tbrunner
Script to manage the 18-349 testbench

## Usage
    usage: run_tb.py [-h] [-l LOGFILE] [-p {}]

    Run the testbench for 18-349's RPi/JTAG setup.

    optional arguments:
      -h, --help            show this help message and exit
      -l, --logfile LOGFILE Unimplemented: Write ftditerm output to file.
      -p, --project {kernel,kernel_blink,kernel_optimization}
                            specify PROJECT variable to make

Other usage notes:

    Running the script will create new xterm windows for FTDITerm and
        gdb. OpenOCD's output is visible from the same window from
        which you invoked the script.

    In order to close all the windows, you simply need to exit the
        script. This can be safely done with ^C while the original
        window which ran the script is in focus. This is the same
        window that shows OpenOCD's output. Alternatively, you may
        close windows individually.
        NOTE: This has not been tested in the VM, but because of how
            OpenOCD is run, you may be able to effectively use ^C to
            close OpenOCD.

Expert mode:

    In order to run FTDITerm and GDB in your favorite terminal
        emulator, you should edit TBRunner.FS_XTERM_BASE
