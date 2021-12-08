#!/usr/bin/env python

"""
kernel.py

Run standard IPython/Jupyter kernels on remote machines using
job schedulers.

"""

import imghdr
import base64
import os
import logging
import time
import traceback
import urllib.request
import io
import re
import _thread
import socket

from PIL import Image # , UnidentifiedImageError
import requests
import rpyc

try:
    from pexpect import spawn as pexpect_spawn
except ImportError:
    from pexpect.popen_spawn import PopenSpawn

    class pexpect_spawn(PopenSpawn):
        def isalive(self):
            return self.proc.poll() is None

# from .scheduler import Scheduler

from .adb import bind_rpycs, adb

def config_maixpy3():
    from threading import Thread
    import time
    def tmp():
        while True:
          bind_rpycs()
          time.sleep(1)
    t = Thread(target=tmp,args=())
    t.setDaemon(True)
    t.start()

# from ipykernel.kernelbase import Kernel
from ipykernel.ipkernel import IPythonKernel

########################################################################################################################################

class ProtoError(Exception):
    pass

class MjpgSocket():

    def read_header_line(self, stream):
        '''Read one header line within the stream.
        The headers come right after the boundary marker and usually contain
        headers like Content-Type and Content-Length which determine the type and
        length of the data portion.
        '''
        return stream.readline().decode('utf-8').strip()


    def read_headers(self, stream, boundary):
        '''Read and return stream headers.
        Each stream data packet starts with an empty line, followed by a boundary
        marker, followed by zero or more headers, followed by an empty line,
        followed by actual data. This function reads and parses the entire header
        section. It returns a dictionary with all the headers. Header names are
        converted to lower case. Each value in the dictionary is a list of header
        fields values.
        '''
        l = self.read_header_line(stream)
        if l == '':
            l = self.read_header_line(stream)
        # print("read_headers", l, boundary)
        if l != boundary:
            raise ProtoError('Boundary string expected, but not found')

        headers = {}
        while True:
            l = self.read_header_line(stream)
            # An empty line indicates the end of the header section
            if l == '':
                break

            # Parse the header into lower case header name and header body
            i = l.find(':')
            if i == -1:
                raise ProtoError('Invalid header line: ' + l)
            name = l[:i].lower()
            body = l[i+1:].strip()

            lst = headers.get(name, list())
            lst.append(body)
            headers[name] = lst

        return headers


    def skip_data(self, stream, left):
        while left:
            rv = stream.read(left)
            if len(rv) == 0 and left:
                raise ProtoError('Not enough data in chunk')
            left -= len(rv)


    def read_data(self, buf, stream, length):
        v = memoryview(buf)[:length]
        while len(v):
            n = stream.readinto(v)
            if n == 0 and len(v):
                raise ProtoError('Not enough data in chunk')
            v = v[n:]
        return buf


    def parse_content_length(self, headers):
        # Parse and check Content-Length. The header must be present in
        # each chunk, otherwise we wouldn't know how much data to read.
        clen = headers.get('content-length', None)
        try:
            return int(clen[0])
        except (ValueError, TypeError):
            raise ProtoError('Invalid or missing Content-Length')


    def check_content_type(self, headers, type_):
        ctype = headers.get('content-type', None)
        if ctype is None:
            raise ProtoError('Missing Content-Type header')
        ctype = ctype[0]

        i = ctype.find(';')
        if i != -1:
            ctype = ctype[:i]

        if ctype != type_:
            raise ProtoError('Wrong Content-Type: %s' % ctype)

        return True


    def open_mjpeg_stream(self, stream):
        if stream.status != 200:
            raise ProtoError('Invalid response from server: %d' % stream.status)
        h = stream.info()

        boundary = h.get_param('boundary', header='content-type', unquote=True)
        if boundary is None:
            raise ProtoError('Content-Type header does not provide boundary string')
        # boundary = '--' + boundary

        return boundary


    def read_mjpeg_frame(self, stream, boundary):
        hdr = self.read_headers(stream, boundary)
        clen = self.parse_content_length(hdr)
        if clen == 0:
            raise EOFError('End of stream reached')
        self.check_content_type(hdr, 'image/jpeg')
        buf = bytearray(clen)
        self.read_data(buf, stream, clen)
        return buf

    def unit_test(self):
        try:
            url = "http://127.0.0.1:18811"
            with urllib.request.urlopen(url, timeout = 1) as stream:
                boundary = self.open_mjpeg_stream(stream)
                while True:
                    tmp = self.read_mjpeg_frame(stream, boundary)
                    print(len(tmp), tmp)
        except EOFError:
            pass
        except Exception as e:
            traceback.print_exc()

    def __init__(self, url: str):
        self._url = url
        self.stream = urllib.request.urlopen(url, timeout = 1)
        self.boundary = self.open_mjpeg_stream(self.stream)

    def iter_content(self):
        while True:
            yield self.read_mjpeg_frame(self.stream, self.boundary)


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
        self._url = url
        self.session = requests.Session()

    def iter_content(self):
        """
        Raises:
            RuntimeError
        """

        r = self.session.get(self._url, stream=True, timeout=3)
        # r = requests.get(self._url, stream=True, timeout=3)

        # parse boundary
        content_type = r.headers['content-type']
        index = content_type.rfind("boundary=")
        assert index != 1
        boundary = content_type[index+len("boundary="):] + "\r\n"
        boundary = boundary.encode('utf-8')

        rd = io.BufferedReader(r.raw)
        while True:
            self._skip_to_boundary(rd, boundary)
            length = self._parse_length(rd)
            yield rd.read(length)

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

########################################################################################################################################

def _setup_logging(verbose=logging.INFO):

    log = logging.getLogger("rpyc_ikernel")
    log.setLevel(verbose)

    console = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
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
        self.clear_output = True
        self.last_result = ""
        # for do_handle
        self.pattern = re.compile("[$](.*?)[(](.*)[)]")
        self.commands = {
            'exec': '%s',
            'connect': 'self.connect_remote(%s)',
        }
        config_maixpy3()
        # self.do_reconnect()
        # bind_rpycs()


    def do_reconnect(self):
        for i in range(6):
            time.sleep(1)
            try:
                import sys
                self.remote = rpyc.classic.connect(self.address)
                self.remote.modules.sys.stdin = sys.stdin
                self.remote.modules.sys.stdout = sys.stdout
                self.remote.modules.sys.stderr = sys.stderr
                self.remote._config['sync_request_timeout'] = None
                self.remote_exec = rpyc.async_(self.remote.modules.builtins.exec) # Independent namespace
                # self.remote_exec = rpyc.async_(self.remote.execute) # Common namespace
                return True
            # ConnectionRefusedError: [Errno 111] Connection refused
            except Exception as e:
                self.remote = None
                # self.log.debug('%s on Remote IP: %s' % (repr(e), self.address))
                print("[ rpyc-kernel ]( Connect IP: %s ...)" % (self.address))
        print("[ rpyc-kernel ]( Connect IP: %s fail! )" % (self.address))
        try:
            if(adb.connect_check()):
                adb.kill_server() # maybe other usage
        except Exception as e:
            self.log.info("[ rpyc-kernel ]( adb %s )" % (str(e)))
        import sys
        sys.exit()

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

    def _ready_display(self, port=18811):
        self._media_client, self._media_port, self._media_work = None, port, True
        self._clear_display(self.remote)
        self._media_work = True
        _thread.start_new_thread(self._update_display, ())

    def _clear_display(self, remote):
        self.log.debug('[%s] _clear_display %s %s' % (self.remote, self._media_work, self._media_client))
        try:
            # if self._media_work == True or self._media_client != None:
            #     self.log.info('[%s] _media_work %s _media_client %s' % (self.remote, self._media_work, self._media_client))
            #     time.sleep(1) # many while True maybe ouput last result
            self._media_work = False
            remote.modules['maix.mjpg'].clear_mjpg()
        except Exception as e:
            self.log.debug(e)

    def _update_display(self):
        # return
        while self._media_work:
            try:
                self.log.debug('[%s] _update_display_ ' % (self._media_client))
                if self._media_client == None:
                    try:
                        self._media_client = MjpgSocket("http://%s:%d" % (self.address, self._media_port))
                        self.log.debug('[%s] connect... (%s)' % (self._media_client, os.getpid()))
                    except socket.timeout as e:
                        self.log.debug(e)
                        break
                if self._media_client != None:
                    # for content in self._media_client.iter_content():
                    #     self.log.info('iter_content... (%s)' % len(content))
                    content = next(self._media_client.iter_content())
                    tmp = Image.open(io.BytesIO(content))
                    buf = io.BytesIO()
                    tmp.resize((tmp.size[0] * 2, tmp.size[1] * 2)).save(buf, format = "JPEG")
                    buf.flush()
                    content = buf.getvalue()
                    if self.clear_output:  # used when updating lines printed
                        self.send_response(self.iopub_socket,
                                            'clear_output', {"wait": True})
                    # self.log.debug(content)
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
                    # except UnicodeDecodeError as e:
                    #     self.log.info('[%s] UnicodeDecodeError ' % (self._media_client))
                    #     # self._media_client.stream.close()
                    #     # self._media_client = None
                    # except UnidentifiedImageError as e:
                    #     self.log.info('[%s] UnidentifiedImageError ' % (self._media_client))
                    #     # self._media_client.stream.close()
                    #     # self._media_client = None
                    # time.sleep(0.02)
                time.sleep(0.01)
            # except OSError as e:
            #     pass
            # except ConnectionResetError as e:
            except Exception as e:
                self.log.debug(e)
                # import traceback
                # traceback.print_exc()
        if (self._media_client):
            try:
                self._media_client.stream.close()
            except Exception as e:
                self.log.debug('[%s] Exception ' % (e))
            self._media_client = None

    def kill_task(self):
        try:
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
            # master.modules['traceback'].print_exc()
            self._clear_display(master)
            master.close()
        except Exception as e:
            self.log.debug(e)

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
        self.last_result = ""
        if self.check_connect():
            try:
                try:
                    print("[ rpyc-kernel ]( running at %s )" % (time.asctime()))
                    self._ready_display()

                    # self.remote.modules.builtins.exec(code)

                    self.result = self.remote_exec(code)
                    # self.result.wait()
                    def get_result(result):
                        if result.error:
                            pass # is error
                            self.log.debug(result.value)
                        # print('get_result', result, result.value, result.error)
                    self.result.add_callback(get_result)
                    # self.log.info('self.result.ready (%s)' % repr(self.result.ready))
                    while self.result.ready == False:
                        # self.log.info('self.result.ready (%s)' % repr(self.result.ready))
                        time.sleep(0.001) # print(end='')
                    time.sleep(0.2)
                    # with rpyc.classic.redirected_stdio(self.remote):
                    #     self.remote_exec(code)

                    # self.remote.execute(code)
                    # self.log.info(self.result)
                except KeyboardInterrupt as e:
                    # self.remote.execute("raise KeyboardInterrupt") # maybe raise main_thread Exception
                    interrupted = True
                    # self.kill_task()
                    self.last_result = '\r\nTraceback (most recent call last):\r\n  File "<string>", line unknown, in <module>\r\nRemote.KeyboardInterrupt\r\n'
                    self.log.debug(self.last_result)
                    # raise e
            # remote stream has been closed(cant return info)
            except EOFError as e:
                self.log.debug(e)
                # self.remote.close() # not close self
                try:
                    self.remote.modules.os._exit(233)  # should close remote
                except Exception as e:
                    pass
            except Exception as e:
                import traceback, sys
                # traceback.print_exc()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                for s in traceback.format_exception(exc_type, exc_value, exc_traceback):
                    if "Remote Traceback" in s:
                        self.last_result = ""
                    self.last_result += s
                # self.log.error(e)
                # raise e
                pass
            finally:
                self.kill_task()

        if len(self.last_result) > 0:
            self.send_response(self.iopub_socket, 'execute_result', {
                'execution_count': self.execution_count,
                'status': 'ok',
                'payload': [],
                'user_expressions': {},
                'data': {
                    # 'text/' + image_type: image_data
                    "text/plain" : str(self.last_result)
                },
                'metadata': {},
            })

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        return {
            'status': 'ok',
            'execution_count': self.execution_count,
            'payload': [],
            'user_expressions': {}
        }
