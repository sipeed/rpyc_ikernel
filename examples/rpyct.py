
import time
import sys
import rpyc

# _async_raise(ident, SystemExit)
def _async_raise(tid):
    import inspect, ctypes
    exctype = KeyboardInterrupt
    """raises the exception, performs cleanup if needed"""
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        return # maybe thread killed
        # raise ValueError("invalid thread id")
    if res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

class Machine():

    def __init__(self, *args, **kwargs):
        self.remote = None
        self.address = "localhost"
        self.timer = None
        self.do_reconnect()

    def do_reconnect(self):
        try:
            self.remote = rpyc.classic.connect(self.address)
            self.remote.modules.sys.stdin = sys.stdin
            self.remote.modules.sys.stdout = sys.stdout
            self.remote.modules.sys.stderr = sys.stderr
            # def _remote_exec(code):
            #     try:
            #         exec()
            #     except Exception as e:
            #         raise e
            #         # print(repr(e))
            #         # import traceback
            #         # traceback.print_exc()
            # self.remote_exec = rpyc.async_(self.remote.teleport(_remote_exec))
            # self.remote_exec = rpyc.async_(self.remote.modules.builtins.exec)
        except Exception as e: # ConnectionRefusedError: [Errno 111] Connection refused
            self.remote = None
            print(repr(e))

    def check_connect(self):
        if self.remote:
            try:
                if self.remote.closed:
                    raise Exception('remote %s closed' % self.address)
                print('checking...', self.remote.closed)
                self.remote.ping() # fail raise PingError
                return True
            except Exception as e: # PingError
                print(repr(e))
                if self.remote != None:
                    self.remote.close()
                    self.remote = None
        self.do_reconnect()
        return False

    # def display(self, var_name):
    #     self.timer = self._get_images.sched(self=self, var_name=var_name)
    #     self.timer.start()

    def display(self, var_name, interval=0.05): # 0.05 20 fps
        # self.log.info(var_name)
        from threading import Timer
        if self.remote:
            def show(self, var_name):
                try:
                    print(self.remote.namespace)
                    if var_name in self.remote.namespace:
                        print(self.remote.namespace[var_name])
                except (KeyboardInterrupt, SystemExit) as e:
                    raise e
                except Exception as e:
                    # self.log.debug(e)
                    if self.timer:
                        self.timer.cancel()
                    raise e
                self.timer = Timer(interval, show, args=(self, var_name))
                self.timer.start()
            if self.timer:
                self.timer.cancel()
            self.timer = Timer(interval, show, args=(self, var_name))
            self.timer.start()

    def kill_task(self):
        master = rpyc.classic.connect(self.address)
        thread = master.modules.threading
        # print(thread.enumerate()) # kill remote's thread
        kills = [i.ident for i in thread.enumerate() if i.ident not in [thread.main_thread().ident, thread.get_ident()]]
        # print(kills)
        for id in kills:
            try:
                master.teleport(_async_raise)(id)
            except Exception as e:
                print('teleport Exception', repr(e))
        # print(master.modules.threading.enumerate())
        master.close()

    def do_execute(self, code):
        if self.check_connect():
            try:
                try:
                    # with rpyc.classic.redirected_stdio(self.remote):
                    #     self.remote.execute(code)
                    self.remote.execute(code)
                    # self.remote.modules.builtins.exec(code)
                    # self.result = self.remote_exec(code)
                    # # self.result.wait()
                    # def get_result(result):
                    #     if result.error:
                    #         pass # is error
                    #     print('get_result', result, result.value)
                    # self.result.add_callback(get_result)
                    # while self.result.ready == False:
                    #     time.sleep(1)
                except KeyboardInterrupt as e:
                    # self.result.set_expiry(1)
                    # self.remote.execute("raise KeyboardInterrupt") # maybe raise main_thread Exception
                    self.kill_task()
                    print('\r\nTraceback (most recent call last):\r\n  File "<string>", line 1, in <module>\r\nKeyboardInterrupt\r\n')
                    # raise e
            except EOFError as e: # remote stream has been closed(cant return info)
                # self.remote.close() # not close self
                self.remote.modules.os._exit(233) # should close remote
            except Exception as e:
                print('do_execute Exception', repr(e))

code = '''
import time
while True:
    time.sleep(1)
    tmp = time.asctime()
    # print(tmp)
    # 1 / 0
    pass
'''

if __name__ == '__main__':
    tmp = Machine()
    print(code)
    while True:
        try:
            time.sleep(0.2)
            tmp.do_execute(code)
        except Exception as e:
            print(repr(e))
    # exec(code)
