#Upload the pavillionexample.ino sketch if you want to try this out.

from pavillion import *
import time



psk = b'PSK1'*8
cid2 = b'cid2'*4

c = Client(psk="A"*64, clientID=cid2, address=("255.255.255.255",12345))
time.sleep(0.2)
#print(c.call(0,b"foo"))

print("Getting name of example function:")
print(c.digitalRead(14))
print("Calling example function:")
print(c.listDir("/spiffs/"),"rslt")
print(c.readFile("/spiffs/raven.txt").decode("utf8"))


#print(c.listDir("/"))

exit()
