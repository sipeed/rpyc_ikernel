#!/usr/bin/env python

"""
kernel.py

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import imghdr
import base64
import os
import io
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

from .scheduler import Scheduler

# from ipykernel.kernelbase import Kernel
from ipykernel.ipkernel import IPythonKernel

# Blend in with the notebook logging


def _setup_logging(verbose=logging.INFO):

    log = logging.getLogger("rpyc_ikernel")
    log.setLevel(verbose)
    # Logging on stderr
    console = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# _async_raise(ident, SystemExit)


def _async_raise(tid):
    import inspect
    import ctypes
    exctype = KeyboardInterrupt
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        tid, ctypes.py_object(exctype))
    if res == 0:
        return  # maybe thread killed
        # raise ValueError("invalid thread id")
    if res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


class RPycKernel(IPythonKernel):
    implementation = 'rpyc_kernel'

    language_info = {'name': 'Python',
                     'codemirror_mode': 'python',
                     'mimetype': 'text/python',
                     'file_extension': '.py'}

    def __init__(self, **kwargs):
        IPythonKernel.__init__(self, **kwargs)
        self.log = _setup_logging()
        self.remote = None
        self.address = "localhost"
        self._media_client = None
        self.clear_output = True
        self._media_timer = None
        # for do_handle
        self.pattern = re.compile("[$](.*?)[(](.*)[)]")
        self.commands = {
            'exec': '%s',
            'connect': 'self.connect_remote(%s)',
        }

        self.do_reconnect()

    def do_reconnect(self):
        try:
            self.remote = rpyc.classic.connect(self.address)
            self.remote.modules.sys.stdin = sys.stdin
            self.remote.modules.sys.stdout = sys.stdout
            self.remote.modules.sys.stderr = sys.stderr
            self.remote._config['sync_request_timeout'] = None
            # self.remote_exec = rpyc.async_(self.remote.modules.builtins.exec) # Independent namespace
            self.remote_exec = rpyc.async_(self.remote.execute) # Common namespace
            try:
                self.remote.modules["maix.display"].remote = self
            except Exception as e:
                pass
            return True
        # ConnectionRefusedError: [Errno 111] Connection refused
        except Exception as e:
            self.remote = None
            self.log.info('%s on Remote IP: %s' % (repr(e), self.address))
        return False

    def check_connect(self):
        if self.remote:
            try:
                if self.remote.closed:
                    raise Exception('remote %s closed' % self.address)
                self.log.debug('checking... (%s)' % self.remote.closed)
                self.remote.ping()  # fail raise PingError
                return True
            except Exception as e:  # PingError
                # self.log.error(repr(e))
                if self.remote != None:
                    self.remote.close()
                    self.remote = None
        return self.do_reconnect()

    def connect_remote(self, address="localhost"):
        self.address = address
        self.do_reconnect()

    def _stop_display(self):
        if self._media_timer:
            self._media_timer.cancel()
            self._media_timer = None
        if self._media_client:
            self._media_client.__del__()
            self._media_client = None

    def _start_display(self):
        if self._media_timer == None:
            def _update(self):
                self._update_display()
            self._media_timer = Scheduler('recur', 0.02, _update, args=(self,))
            self._media_timer.start()

    def _update_display(self, file_name='/dev/display', host_port=18811, rtp_port=18813):
        from .rtspc import Client
        if self._media_client == None:
            self._media_client = Client(
                file_name, self.address, host_port, rtp_port)
            self._media_client.establish_rtsp_connection()
            if self._media_client.is_rtsp_connected:
                self._media_client.send_setup_request()
                self._media_client.send_play_request()
        else:
            if self._media_client.is_rtsp_connected:
                if not self._media_client.is_receiving_rtp:
                    return
                frame = self._media_client.get_next_frame()
                if frame != None:
                    if self.clear_output:  # used when updating lines printed
                        self.send_response(self.iopub_socket,
                                           'clear_output', {"wait": True})
                    image_buffer = frame[0].getvalue()
                    # self.log.debug(image.getvalue())
                    image_type = imghdr.what(None, image_buffer)
                    # self.log.debug(image_type)
                    image_data = base64.b64encode(image_buffer).decode('ascii')
                    # self.log.debug(image_data)
                    self.send_response(self.iopub_socket, 'display_data', {
                        'data': {
                            'image/' + image_type: image_data
                        },
                        'metadata': {}
                    })

    def kill_task(self):
        master = rpyc.classic.connect(self.address)
        thread = master.modules.threading
        # print(thread.enumerate()) # kill remote's thread
        lists = [i for i in thread.enumerate() if i.__class__.__name__ not in [
            'RtspServerThread', '_MainThread']]
        kills = [i.ident for i in lists if i.ident not in [
            thread.main_thread().ident, thread.get_ident()]]
        # print(kills)
        for id in kills:
            try:
                master.teleport(_async_raise)(id)
            except Exception as e:
                self.log.debug('teleport Exception (%s)' % repr(e))
        # print(master.modules.threading.enumerate())
        master.close()

    def do_handle(self, code):
        # self.log.debug(code)
        # code = re.sub(r'([#](.*)[\n])', '', code) # clear '# etc...' but bug have "#"
        # self.log.info(code)

        cmds = self.pattern.findall(code)
        # self.log.info(cmds)
        for cmd in cmds:
            _format = self.commands.get(cmd[0], None)
            if _format:
                # print(_format % cmd[1])
                exec(_format % cmd[1])
        code = self.pattern.sub('', code)

        # self.log.debug(code)
        return code

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        self.log.debug(code)

        # Handle the host call code
        code = self.do_handle(code)

        interrupted = False

        if self.check_connect():
            try:
                try:
                    # self.remote.modules.builtins.exec(code)
                    self.result = self.remote_exec(code)
                    # self.result.wait()
                    def get_result(result):
                        if result.error:
                            pass # is error
                            print(result.value)
                        # print('get_result', result, result.value, result.error)
                    self.result.add_callback(get_result)
                    while self.result.ready == False:
                        time.sleep(0.1) # print(end='')
                    # with rpyc.classic.redirected_stdio(self.remote):
                    #     self.remote.execute(code)
                    # self.remote.execute(code)
                except KeyboardInterrupt as e:
                    # self.remote.execute("raise KeyboardInterrupt") # maybe raise main_thread Exception
                    interrupted = True
                    self.kill_task()
                    print('\r\nTraceback (most recent call last):\r\n  File "<string>", line unknown, in <module>\r\nRemote.KeyboardInterrupt\r\n')
                    # raise e
            # remote stream has been closed(cant return info)
            except EOFError as e:
                # self.remote.close() # not close self
                self.remote.modules.os._exit(233)  # should close remote
                self.log.debug(e)
            except Exception as e:
                self.log.error(e)
                # raise e
            finally:
                self._stop_display()

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        return {
            'status': 'ok',
            'execution_count': self.execution_count,
            'payload': [],
            'user_expressions': {}
        }
