
# Author: Chema Garcia (aka sch3m4)
# Contact: chema@safetybits.net | http://safetybits.net/contact
# Homepage: http://safetybits.net
# Project Site: http://github.com/sch3m4/pyadb

import sys
import os
import re
import subprocess


class ADB():
    __adb_path = None
    __output = None
    __error = None
    __return = 0
    __device = None
    # use device with given serial number (overrides $ANDROID_SERIAL)
    __target = None
    #  -s SERIAL
    #  use device with given serial number (overrides $ANDROID_SERIAL)
    devices = []
    try_times = 0

    # reboot modes
    REBOOT_RECOVERY = 1
    REBOOT_BOOTLOADER = 2

    # default TCP/IP port
    DEFAULT_TCP_PORT = 5555
    # default TCP/IP host
    DEFAULT_TCP_HOST = "localhost"

    def __init__(self, adb_path='adb', device=None):
        self.__adb_path = adb_path

        if device:
            self.set_target_device(device)
            self.connect_check()
            return

        if self.devices == None:
          self.init_devices()

        if self.devices:
            # default use the 1st device [adb -s serial_number]
            self.set_target_device(self.devices[0][0])
            self.connect_check()

    def connect_check(self):
        '''
        After we initialied an instance of Adb_Wrapper, we should check if it is
        working well. If not, we must initial it again. Considering with the
        case that we do not need to restart the adb while we re-initial it, so
        we set the global flag 'NEED_RESTART_ADB' to False.
        '''
        adb_shell_args_test = ['whoami']
        ret = self.run_shell_cmd(adb_shell_args_test)
        if ret is None or len(ret) == 0:
            self.try_times += 1
            if self.try_times > 3:
                # print("It has tried 3 times, please check your devices.")
                return False
            # print('[W] Init Android_native_debug falied, try again.')
            self.__init__()
            return False
        return True

    def is_emulator(self):
        target_dev = self.get_target_device()
        if target_dev.find('emulator') > -1:
            return True

        return False

    def __clean__(self):
        self.__output = None
        self.__error = None
        self.__return = 0

    def get_output(self):
        return self.__output

    def get_error(self):
        return self.__error

    def get_return_code(self):
        return self.__return

    def last_failed(self):
        '''
        Did the last command fail?
        '''
        if self.__output is None and self.__error is not None and self.__return:
            return True
        return False

    def __build_command__(self, cmd):
        ret = None

        if self.__device is not None and self.__target is None:
            self.__error = "Must set target device first"
            self.__return = 1
            return ret

        if sys.platform.startswith('win'):
            ret = self.__adb_path + " "
            if self.__target is not None:
                ret += "-s " + self.__target + " "
            if isinstance(cmd, list):
                ret += ' '.join(cmd)
            else:
                ret += cmd
        else:
            ret = [self.__adb_path]
            if self.__target is not None:
                ret += ["-s", self.__target]
            for i in cmd:
                ret.append(i)

        return ret

    def run_cmd(self, cmd):
        '''
        Runs a command by using adb tool ($ adb <cmd>)
        cmd have to be a list.
        '''
        self.__clean__()

        if self.__adb_path is None:
            self.__error = "ADB path not set"
            self.__return = 1
            return

        if not isinstance(cmd, list):
            cmd = cmd.split()

        # For compat of windows
        cmd_list = self.__build_command__(cmd)

        adb_proc = subprocess.Popen(cmd_list, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=False)
        (self.__output, self.__error) = adb_proc.communicate()
        self.__return = adb_proc.returncode

    def run_shell_cmd(self, cmd):
        '''
        Executes a shell command
        adb shell <cmd>
        '''
        self.__clean__()
        if not isinstance(cmd, list):
            cmd = cmd.split()
        sh_cmd = cmd.copy()
        sh_cmd.insert(0, 'shell')
        self.run_cmd(sh_cmd)
        return self.__output

    def get_version(self):
        '''
        Returns ADB tool version
        adb version
        '''
        self.run_cmd("version")
        ret = self.__output.split()[-1:][0]
        return ret

    def check_path(self):
        '''
        Intuitive way to verify the ADB path
        '''
        if self.get_version() is None:
            return False
        return True

    def set_adb_path(self, adb_path):
        '''
        Sets ADB tool absolute path
        '''
        if os.path.isfile(adb_path) is False:
            return False
        self.__adb_path = adb_path
        return True

    def get_adb_path(self):
        '''
        Returns ADB tool path
        '''
        return self.__adb_path

    def start_server(self):
        '''
        Starts ADB server
        adb start-server
        '''
        self.__clean__()
        self.run_cmd('start-server')
        return self.__output

    def kill_server(self):
        '''
        Kills ADB server
        adb kill-server
        '''
        self.__clean__()
        self.run_cmd('kill-server')

    def restart_server(self):
        '''
        Restarts ADB server
        '''
        self.kill_server()
        return self.start_server()

    def restore_file(self, file_name):
        '''
        Restore device contents from the <file> backup archive
        adb restore <file>
        '''
        self.__clean__()
        self.run_cmd(['restore', file_name])
        return self.__output

    def wait_for_device(self):
        '''
        Blocks until device is online
        adb wait-for-device
        '''
        self.__clean__()
        self.run_cmd('wait-for-device')
        return self.__output

    def get_help(self):
        '''
        Returns ADB help
        adb help
        '''
        self.__clean__()
        self.run_cmd('help')
        return self.__output

    def init_devices(self):
        '''
        Returns a list of connected devices
        adb devices
        '''
        self.run_cmd(['devices', '-l'])
        lines = re.split(r'\n', self.__output.decode(encoding='utf-8'))
        # print('init_devices', self.__output.decode(encoding='utf-8'))
        for line in lines[1:]: # [1:-1]:
            dev = line.split()
            if len(dev):
                self.devices.append(dev)

    def set_target_device(self, device):
        '''
        Select the device to work with
        '''
        self.__clean__()
        self.__target = device
        return True

    def get_target_device(self):
        '''
        Returns the selected device to work with
        '''
        return self.__target

    def get_state(self):
        '''
        Get ADB state
        adb get-state
        '''
        self.__clean__()
        self.run_cmd('get-state')
        return self.__output

    def get_serialno(self):
        '''
        Get serialno from target device
        adb get-serialno
        '''
        self.__clean__()
        self.run_cmd('get-serialno')
        return self.__output

    def reboot_device(self, mode):
        '''
        Reboot the target device
        adb reboot recovery/bootloader
        '''
        self.__clean__()
        if mode not in (self.REBOOT_RECOVERY, self.REBOOT_BOOTLOADER):
            self.__error = "mode must be REBOOT_RECOVERY/REBOOT_BOOTLOADER"
            self.__return = 1
            return self.__output
        self.run_cmd(["reboot", "%s" % "recovery"
                      if mode == self.REBOOT_RECOVERY else "bootloader"])
        return self.__output

    def check_root(self):
        self.run_shell_cmd(['whoami'])
        return 'root' in self.get_output().decode()

    def set_system_rw(self):
        '''
        Mounts /system as rw
        adb remount
        '''
        self.__clean__()
        self.run_cmd("remount")
        return self.__output

    def get_remote_file(self, remote, local):
        '''
        Pulls a remote file
        adb pull remote local
        '''
        self.__clean__()
        self.run_cmd(['pull', remote, local])

        if self.__error is not None and "bytes in" in self.__error:
            self.__output = self.__error
            self.__error = None

        return self.__output

    def push_local_file(self, local, remote):
        '''
        Push a local file
        adb push local remote
        '''
        self.__clean__()
        self.run_cmd(['push', local, remote])
        return self.__output

    def listen_usb(self):
        '''
        Restarts the adbd daemon listening on USB
        adb usb
        '''
        self.__clean__()
        self.run_cmd("usb")
        return self.__output

    def listen_tcp(self, port=DEFAULT_TCP_PORT):
        '''
        Restarts the adbd daemon listening on the specified port
        adb tcpip <port>
        '''
        self.__clean__()
        self.run_cmd(['tcpip', port])
        return self.__output

    def get_bugreport(self):
        '''
        Return all information from the device that should be included in a bug report
        adb bugreport
        '''
        self.__clean__()
        self.run_cmd("bugreport")
        return self.__output

    def get_jdwp(self):
        '''
        List PIDs of processes hosting a JDWP transport
        adb jdwp
        '''
        self.__clean__()
        self.run_cmd("jdwp")
        return self.__output

    def get_logcat(self, lcfilter=""):
        '''
        View device log
        adb logcat <filter>
        '''
        self.__clean__()
        self.run_cmd(['logcat', lcfilter])
        return self.__output

    def run_emulator(self, cmd=""):
        '''
        Run emulator console command
        '''
        self.__clean__()
        self.run_cmd(['emu', cmd])
        return self.__output

    def connect_remote(self, host=DEFAULT_TCP_HOST, port=DEFAULT_TCP_PORT):
        '''
        Connect to a device via TCP/IP
        adb connect host:port
        '''
        self.__clean__()
        self.run_cmd(['connect', "%s:%s" % (host, port)])
        return self.__output

    def disconnect_remote(self, host=DEFAULT_TCP_HOST, port=DEFAULT_TCP_PORT):
        '''
        Disconnect from a TCP/IP device
        adb disconnect host:port
        '''
        self.__clean__()
        self.run_cmd(['disconnect', "%s:%s" % (host, port)])
        return self.__output

    def ppp_over_usb(self, tty=None, params=""):
        '''
        Run PPP over USB
        adb ppp <tty> <params>
        '''
        self.__clean__()
        if tty is None:
            return self.__output

        cmd = ["ppp", tty]
        if params != "":
            cmd += params

        self.run_cmd(cmd)
        return self.__output

    def sync_directory(self, directory=""):
        '''
        Copy host->device only if changed (-l means list but don't copy)
        adb sync <dir>
        '''
        self.__clean__()
        self.run_cmd(['sync', directory])
        return self.__output

    def forward_socket(self, local=None, remote=None):
        '''
        Forward socket connections
        adb forward <local> <remote>
        '''
        self.__clean__()
        if local is None or remote is None:
            return self.__output
        self.run_cmd(['forward', local, remote])
        return self.__output

    def uninstall(self, package=None, keepdata=False):
        '''
        Remove this app package from the device
        adb uninstall [-k] package
        '''
        self.__clean__()
        if package is None:
            return self.__output

        cmd = 'uninstall '
        if keepdata:
            cmd += '-k '
        cmd += package
        self.run_cmd(cmd.split())
        return self.__output

    def install(self, fwdlock=False, reinstall=False, sdcard=False, pkgapp=None):
        '''
        Push this package file to the device and install it
        adb install [-l] [-r] [-s] <file>
        -l -> forward-lock the app
        -r -> reinstall the app, keeping its data
        -s -> install on sdcard instead of internal storage
        '''

        self.__clean__()
        if pkgapp is None:
            return self.__output

        cmd = "install "
        if fwdlock is True:
            cmd += "-l "
        if reinstall is True:
            cmd += "-r "
        if sdcard is True:
            cmd += "-s "

        cmd += pkgapp
        self.run_cmd(cmd.split())
        return self.__output

    def find_binary(self, name=None):
        '''
        Look for a binary file on the device
        '''
        self.run_shell_cmd(['which', name])

        if self.__output is None:  # not found
            self.__error = "'%s' was not found" % name
        elif self.__output.strip() == "which: not found":  # which binary not available
            self.__output = None
            self.__error = "which binary not found"
        else:
            self.__output = self.__output.strip()

        return self.__output

adb = ADB()

def bind_rpycs():
    # return
    global adb
    # for item in adb.devices:
    #     print(item)
    # if adb.check_root():
    #     print("I'm root.")
    if(adb.connect_check()):
        import time
        for i in range(3):
            adb.run_shell_cmd("ps | grep 'from maix import mjpg;mjpg.start();' | awk '{print $1}'")
            tmp = (adb.get_output().decode())
            tmp = tmp.replace('\r', '')
            res = tmp.split('\n')
            # filter(None, res)
            res = [x for x in res if x != '']
            # print(i, len(res), res) # exist server
            if (len(res) > 1):
                return True

        # ----
        adb.run_shell_cmd('/etc/init.d/S52ntpd stop')
        adb.run_shell_cmd("ps | grep python | awk '{print $1}' | xargs kill -9")
        # ----
        adb.forward_socket('tcp:18811', 'tcp:18811')
        adb.forward_socket('tcp:18811', 'tcp:18811')
        adb.forward_socket('tcp:18811', 'tcp:18811')
        adb.forward_socket('tcp:18812', 'tcp:18812')
        adb.forward_socket('tcp:18812', 'tcp:18812')
        adb.forward_socket('tcp:18812', 'tcp:18812')
        adb.run_shell_cmd("python -c 'from maix import mjpg;mjpg.start();'")
        # adb.run_shell_cmd('/etc/init.d/S40network stop')
        # print(adb.get_output().decode())
        # adb.run_shell_cmd('killall tcpsvd')
        # print(adb.get_output().decode())
        # adb.run_shell_cmd("ps | grep python | awk '{print $1}' | xargs kill -9")
        # # adb.run_shell_cmd('/etc/init.d/S51dropbear stop')
        # # print(adb.get_output().decode())
        # adb.run_shell_cmd('/etc/init.d/S52ntpd stop')
        # # print(adb.get_output().decode())
        # adb.forward_socket('tcp:18811', 'tcp:18811')
        # adb.forward_socket('tcp:18812', 'tcp:18812')
        # adb.run_shell_cmd('python -c "import maix.mjpg;maix.mjpg.start()"')
        # # print(adb.get_output().decode())
        # # import sys
        # sys.exit(666)
    return False

if __name__ == "__main__":
    # adb.run_shell_cmd('/etc/init.d/S52ntpd stop')
    # adb.run_shell_cmd("ps | grep python | awk '{print $1}' | xargs kill -9")
    # # ----
    adb.forward_socket('tcp:18811', 'tcp:18811')
    adb.forward_socket('tcp:18812', 'tcp:18812')
    # while True:
    #     print('bind_rpycs()', bind_rpycs())
