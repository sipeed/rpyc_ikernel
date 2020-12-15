#!/usr/bin/env python

"""
kernel.py

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import argparse
import logging
import time
import traceback
import rpyc
import sys
import signal
import re

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
def _setup_logging(verbose=logging.INFO):

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
        self.remote_address = "localhost"
        self.remote = None
        self.pattern = re.compile(r"\s*#\s*exec[(](.*)[)]")
        self.do_reconnect()
    
    def do_reconnect(self, forced=False):
        try:
            if forced and self.remote:
                self.remote.close()
                self.remote = None
            if self.remote == None or self.remote.closed:
                self.remote = rpyc.classic.connect(self.remote_address)
                # self.remote_exec = rpyc.async_(self.remote.modules.builtins.exec)
        except Exception as e:
            self.log.info('%s on Remote IP: %s' % (e, self.remote_address))

    def connect_remote(self, address="localhost"):
        self.remote_address = address
        self.do_reconnect(True)

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        
        self.log.debug(code)

        result = self.pattern.findall(code)

        if len(result):
            try:
                # exec(self.remote_address = "localhost" and self.do_reconnect(True))
                for c in result:
                    exec(c) # self.log.info(c)
            except Exception as e:
                self.log.error(e)
                # return {'status': 'abort', 'execution_count': self.execution_count}

        interrupted = False
        try:
            self.do_reconnect()
            try:
                if self.remote is not None:
                    with rpyc.classic.redirected_stdio(self.remote):
                        self.remote.execute(code)
            except (KeyboardInterrupt, SystemExit) as e:
                interrupted = True
                self.log.error('\r\nTraceback (most recent call last):\r\n  File "<string>", line 1, in <module>\r\nKeyboardInterrupt\r\n')
                self.remote.execute("raise KeyboardInterrupt")
                # self.remote.teleport(RPycKernel.stop_all_task)()
                # self.log.info(self.remote.modules.threading.enumerate()[:])
                # self.remote.modules.sys.stdout.write("\x03")
                # self.remote.modules.builtins.sys.exit() # not sys
                # self.log.info(self.remote.modules.sys.exc_info())
                # self.remote.modules.os._exit(0) # stop remote shell
                # self.remote.modules.os.popen('kill -9 ' + str(self.remote.modules.os.getpid()))
                # self.remote.modules.os.kill(self.remote.modules.os.getpid(), signal.SIGKILL)
        except EOFError as e:
            self.log.debug(e)
            # self.log.info(sys.exc_info())
        except Exception as e:
            self.log.error(e)
            # # raise e
            # import traceback, sys
            # ex_type, ex, tb = sys.exc_info()
            # error_content = {
            #     'ename': str(ex_type),
            #     'evalue': str(e),
            #     'traceback': traceback.format_exception(ex_type, ex, tb)
            # }
            # self.send_response(self.iopub_socket, 'error', error_content)

            # error_content['execution_count'] = self.execution_count
            # error_content['status'] = 'error'
            # return error_content

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        return {
                'status': 'ok', 
                'execution_count': self.execution_count, 
                'payload': [], 
                'user_expressions': {}
            }

    def stop_all_task():
        import inspect
        import ctypes

        def _async_raise(tid, exctype):
            """raises the exception, performs cleanup if needed"""
            tid = ctypes.c_long(tid)
            if not inspect.isclass(exctype):
                exctype = type(exctype)
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
            if res == 0:
                raise ValueError("invalid thread id")
            elif res != 1:
                # """if it returns a number greater than one, you're in trouble,
                # and you should call it again with exc=NULL to revert the effect"""
                ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
                raise SystemError("PyThreadState_SetAsyncExc failed")

        import threading
        tasks = threading.enumerate()
        for task in tasks:
            if task.isDaemon():
                _async_raise(task.ident, SystemExit)

