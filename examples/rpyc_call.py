import _thread
import rpyc
import time

# remote = rpyc.classic.connect("192.168.43.144")
# remote = rpyc.classic.connect("172.17.0.2")

remote = rpyc.classic.connect("localhost")

# proc = remote.modules.subprocess.Popen("ls", stdout = -1, stderr = -1)
# stdout, stderr = proc.communicate()
# print(stdout.split())

# remote_list = remote.builtin.range(7)

# remote.execute("print('foo')")

print(dir(remote))

# with rpyc.classic.redirected_stdio(remote):
#     remote.modules.sys.stdout.write("hello\n")   # will be printed locally

    # pt = rpyc.async_(remote.modules.builtins.print)
    # res = pt("124")
    # res.wait()
    # print(res.value)

# try:
    
# except Exception as e:
#     print(e)

# pt = rpyc.async_(remote.modules.builtins.print)
# res = pt("124")
# res.wait()
# print(res.value)
# print(dir(res))



# print(remote.modules.builtins.print('1234'))
# print(remote.modules.sys.stdin.readlines())

# def get_image(filename):
#     with open(filename, 'rb') as f:
#         image = f.read()
#     return image
    
# fn = remote.teleport(get_image)

# import imghdr
# while True:
#     image = fn("index4-3.png")
#     image_type = imghdr.what(None, image)
#     if image_type is None:
#         raise ValueError("Not a valid image: %s" % image)
#     print(time.time())

# image_data = base64.b64encode(image).decode('ascii')

# print(remote.execute('import platform\r\n'))
# while True:
#     # print(square())
#     # print(fn())
#     print(remote.eval('platform.uname()'))

# remote.teleport(lambda: print(sys.version_info))

# images = rpyc.classic.connect("192.168.0.172").modules

# def print_images(threadName, delay):
#     import time
#     while True:
#         print(images.os.getcwd())
        # time.sleep(delay)
# try:
#    _thread.start_new_thread(print_images, ("Thread-2", 0.002, ))
# except:
#    print("Error: not")

# while True:
#     print(repl.os.time())
