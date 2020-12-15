#!/usr/bin/env python

from rpyc.utils.server import ThreadedServer
from rpyc.core.service import SlaveService

class rpycs:
    server = None
    
    def start():
        rpycs.server = ThreadedServer(SlaveService, hostname="0.0.0.0", port=18812, reuse_addr=True)
        rpycs.server.start()
    
    def reload(*args):
        rpycs.server.close()
        rpycs.server.start()
    
    def stop(*args):
        rpycs.server.close()
        import sys
        sys.exit()

rpycs.start()
'''
while True:
    try:
        rpycs.start()
    except Exception as e:
        print(e)
'''
