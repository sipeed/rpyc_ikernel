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

from .adb import bind_rpycs

def config_maixpy3():
    from threading import Thread
    import time
    def tmp():
        while True:
          bind_rpycs()
          time.sleep(3)
    t = Thread(target=tmp,args=())
    t.setDaemon(True)
    t.start()

# from ipykernel.kernelbase import Kernel
from ipykernel.ipkernel import IPythonKernel

# Blend in with the notebook logging
class MjpgReader():
    """
    MJPEG format

    Content-Type: multipart/x-mixed-replace; boundary=--BoundaryString
    --BoundaryString
    Content-type: image/jpg
    Content-Length: 12390

    ... image-data here ...


    --BoundaryString
    Content-type: image/jpg
    Content-Length: 12390

    ... image-data here ...
    """

    def __init__(self, url: str):
        import io
        import requests
        self._url = url
        self.r = None
        self.r = requests.get(self._url, stream=True)

        # parse boundary
        content_type = self.r.headers['content-type']
        index = content_type.rfind("boundary=")
        # assert index != 1
        boundary = content_type[index+len("boundary="):] + "\r\n"
        self.boundary = boundary.encode('utf-8')

        self.rd = io.BufferedReader(self.r.raw)

    def __del__(self):
        if self.r:
            self.r.close()
            self.r = None

    def iter_content(self):
        """
        Raises:
            RuntimeError
        """
        self._skip_to_boundary(self.rd, self.boundary)
        length = self._parse_length(self.rd)
        yield self.rd.read(length)

    def _parse_length(self, rd) -> int:
        length = 0
        while True:
            line = rd.readline()
            if line == b'\r\n':
                return length
            if line.startswith(b"Content-Length"):
                length = int(line.decode('utf-8').split(": ")[1])
                assert length > 0

    def _skip_to_boundary(self, rd, boundary: bytes):
        for _ in range(10):
            if boundary in rd.readline():
                break
        else:
            raise RuntimeError("Boundary not detected:", boundary)

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
        config_maixpy3()
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
        try:
            if self._media_timer:
                self._media_timer.cancel()
                self._media_timer = None
            if self._media_client:
                self._media_client = None
        except Exception as e:
            self.log.debug(e)
          
    def _start_display(self):
        try:
            if self._media_timer == None:
                def _update(self):
                    self._update_display()
                self._media_timer = Scheduler('recur', 0.02, _update, args=(self,))
                self._media_timer.start()
                self._media_display = True
        except Exception as e:
            self.log.debug(e)

    def _update_display(self, host_port=18811):
        from requests import exceptions
        # self.log.debug('_update_display... (%s)' % self._media_client)
        if self._media_client == None:
            try:
                self._media_client = MjpgReader("http://%s:%d" % (self.address, host_port))
            except exceptions.ConnectionError as e:
                self.log.debug(e)
        else:
            try:
                content = next(self._media_client.iter_content())
                # print(len(content))
                from PIL import Image
                from io import BytesIO
                tmp = Image.open(BytesIO(content))
                buf = BytesIO()
                tmp.resize((tmp.size[0] * 2, tmp.size[1] * 2)).save(buf, format = "JPEG")
                buf.flush()
                content = buf.getvalue()
                
                if self.clear_output:  # used when updating lines printed
                    self.send_response(self.iopub_socket,
                                        'clear_output', {"wait": True})
                # self.log.debug(image.getvalue())
                image_type = imghdr.what(None, content)
                # self.log.debug(image_type)
                image_data = base64.b64encode(content).decode('ascii')
                # self.log.debug(image_data)
                self.send_response(self.iopub_socket, 'display_data', {
                    'data': {
                        'image/' + image_type: image_data
                    },
                    'metadata': {}
                })
            except ValueError as e:
              self.log.debug(e)

    def kill_task(self):
        master = rpyc.classic.connect(self.address)
        thread = master.modules.threading
        # print(thread.enumerate()) # kill remote's thread
        lists = [i for i in thread.enumerate() if i.__class__.__name__ not in [
            'MjpgServerThread', '_MainThread']]
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
