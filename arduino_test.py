#Upload the pavillionexample.ino sketch if you want to try this out.

from pavillion import *
import time



psk = b'PSK1'*8
cid2 = b'cid2'*4

c = Client(psk=b"ZbCG43nkb6kuUwynqSsIgLZmn0SGd1Sp", clientID=cid2, address=("255.255.255.255",12345))
time.sleep(1)

print("Getting name of example function:")
#print(c.getFunctionName(5000))
print("Calling example function:")
print(c.call(5000,b"testing"))


exit()