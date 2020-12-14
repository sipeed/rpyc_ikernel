#!/usr/bin/env python

"""
kernel.py

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import argparse
import logging
import os
import time
import rpyc
import pexpect

try:
    from pexpect import spawn as pexpect_spawn
except ImportError:
    from pexpect.popen_spawn import PopenSpawn

    class pexpect_spawn(PopenSpawn):
        def isalive(self):
            return self.proc.poll() is None


# from ipykernel.kernelbase import Kernel
from ipykernel.ipkernel import IPythonKernel

# Blend in with the notebook logging
def _setup_logging(verbose=logging.DEBUG):

    log = logging.getLogger("rpyc_ikernel")
    log.setLevel(verbose)
    # Logging on stderr
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') 
    console.setFormatter(formatter)

    log.handlers = []
    log.addHandler(console)

    # So that we can attach these to pexpect for debugging purposes
    # we need to make them look like files
    def _write(*args, **_):
        """
        Method to attach to a logger to allow it to act like a file object.

        """
        message = args[0]
        # convert bytes from pexpect to something that prints better
        if hasattr(message, "decode"):
            message = message.decode("utf-8")

        for line in message.splitlines():
            if line.strip():
                log.debug(line)

    def _pass():
        """pass"""
        pass

    log.write = _write
    log.flush = _pass

    return log
    
class RPycKernel(IPythonKernel):
    implementation = 'rpyc_kernel'
    implementation_version = "0.1.0"

    language_info = {'name': 'Python',
                     'codemirror_mode': 'python',
                     'mimetype': 'text/python',
                     'file_extension': '.py'}

    def __init__(self, **kwargs):
        IPythonKernel.__init__(self, **kwargs)
        self.log = _setup_logging()
        self.host = "localhost"
        self.do_connect()

    def do_connect(self):
        try:
            self.remote = rpyc.classic.connect(self.host)
            # self.remote_exec = rpyc.async_(self.remote.modules.builtins.exec)
        except Exception as e:
            self.log.info(e)
            raise e

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        self.log.info(code)
        try:
            with rpyc.classic.redirected_stdio(self.remote):
                try:
                    self.remote.modules.builtins.exec(code)
                except KeyboardInterrupt as e:
                    # self.remote.modules.sys.stdout.write("\x03")
                    self.remote.modules.builtins.exit(1) # not sys
                    # self.remote.modules.os._exit(0) # stop remote shell
                    self.log.info(e)
        except EOFError as e:
            self.log.error(e)
            self.do_connect()
        except Exception as e:
            self.log.error(e)
            
        return {
                'status': 'ok', 
                'execution_count': self.execution_count, 
                'payload': [], 
                'user_expressions': {}
            }
