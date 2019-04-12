#Upload the pavillionexample.ino sketch if you want to try this out.

from pavillion import *
import time



psk = b'PSK1'*8
cid2 = b'cid2'*4

c = Client(psk=b"ZbCG43nkb6kuUwynqSsIgLZmn0SGd1Sp", clientID=cid2, address=("255.255.255.255",12345))
time.sleep(1)
#print(c.call(0,b"foo"))
print(time.time())
print(c.analogRead(3))
print("in",time.time())
#print(c.listDir("/spiffs/"),"rslt")
#print(c.readFile("/spiffs/raven.txt").decode("utf8"))

#The ID of the client will be None if the message is sent unsecured.
def z(name,data,client):
    print(time.strftime("%b %e %l:%M%p:%S:%L"))

m = c.messageTarget('testTarget',z)
c.sendMessage("test","test",b'')
time.sleep(2)
print(c.getServer().rssi())
print(c.getServer().netType())
print(c.getServer().battery())
print(c.getServer().batteryState())

time.sleep(10000)

#print(c.listDir("/"))
c.close()
exit()
