import socket
import os
import time
s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
e = os.getenv('NOTIFY_SOCKET')
if e.startswith('@'):
  # abstract namespace socket
  e = '\0%s' % e[1:]
print e
s.connect(e)
s.sendall("READY=1")
s.close()
time.sleep(5)
