# import faulthandler
# faulthandler.enable()
# python3 rpyc_test.py -X faulthander
try:
    from rpyc.utils.server import ThreadedServer
    from rpyc.core.service import SlaveService
    server = ThreadedServer(SlaveService, hostname="0.0.0.0", port=18812, reuse_addr=True)
    server.start()
except Exception as e:
    print(repr(e))
    import traceback
    traceback.print_exc()
