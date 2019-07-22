# Pavillion UDP Protocol
![logo](logo.jpg)

## Intro

Pavillion is a UDP based protocol aiming to support most of the common messaging modes(Reliable and Unreliable pubsub, RPC, Read/Write/Unreliable write, discovery, etc). The protocol is conceptually connectionless and designed so that implementations can hide the existance of connections. If either side of a connection reboots, it will automatically
reconnect next time you try to send anything.


This reference implementation is written in Python, but the protocol is designed to be light enough to work on servers running on
the ESP8266(And in fact it does, and this repo includes Arduino libs).

There is no requirement for message brokers, devices simply send directly to each other, however it's possible to
use a server as a message broker for many clients.



In addition, Pavillion aims to integrate encryption at the application layer, using the usual libsodium. The protocol is designed to allow for future ciphers to be added

*As I am not a cryptography expert, you have no reason to trust this, but it should deter casual snooping.*

Not that it isn't *intended* to be fairly secure. It doesn't provide perfect forward secrecy or do much to prevent traffic analysis, or anything like that, but in theory(As long as you use full strength random keys) nobody should be able to read your messages, make fake ones, or do replay attacks. There's a challenge response authentication step that does not require a real time clock.

As far as those three goals are concerned, I've taken security fairly seriously. I don't know of any reason it's *wouldn't* be secure, but bugs happen, it's fairly complex, and hasn't been audited.



Right now this doesn't even have a version number and everything is subject to change, but most things probably won't, because
it all seems to work pretty well.

## Examples
### RPC With public keys
```
from pavillion import *
import time
import libnacl

c_pub, c_pk = libnacl.crypto_box_keypair()
s_pub, s_pk = libnacl.crypto_box_keypair()

#Client ID
cid2 = b'cid2'*4

#Servers identify clients by client id and key pairs.
#By default they communicate on a multicast address.

s = Server(pubkeys={cid2:c_pub}, ecc_keypair=(s_pub,s_pk))
c = Client(keypair=(c_pub,c_pk), serverkey=s_pub, clientID=cid2,cipher=2)

#This is a property returning a ip,port pair that the client is bound to
c.address

#This is an empty dict, but you can put ip,port pairs there to ignore them
s.ignore

#Define an RPC function, call it on the client
s.registers[401] =lambda c,a: a

x = c.call(401, b'A test string')
self.assertEqual(x, b'A test string')
```
### Publish subscribe
Client and server objects are all-in-one, and support multiple communication modes, and messages may be send client to server
or server to client.

In addition, the rest of the API is the same for PSK as it is for public key.
```
    #Causes f to be called, printing the message name, data, and the client ID.

    def f(name,data,client):
       print(name,data,client)

    m = s.messageTarget('TestTarget',f)
    c.sendMessage("TestTarget","MessageName",b'data')
 

    #Same as above, but sending from client to server.
    #In this mode, We can optionally send to only a subset of clients with the optional filter
    #that we can pass as a last param to sendMessage.

    #Filter must be an iterable. The client is included if either it's Id or (addr,port) are in the iterable.
    def ff(name,data,addr):
       print(name,data,addr)

    m = c.messageTarget('TestTarget',ff)
    s.sendMessage("TestTarget","MessageName",b'data')


```

## Client Objects
Incomplete docs

### c= Client(self, address=('255.255.255.255',1783),clientID=None,psk=None,cipher=1,keypair=None)

You have to either provide a PSK or a Keypair, as Pavillion does not support cleartext.



### c.messageTarget(target, f)
Returns a messageTarget obj you must keep a ref to, along with the function itself. As long as those exist, incoming messages will cause f(name, data, addr) to be called.

### x = c.call(number, arguments)
Calls RPC function number N with the given binary arg string. Normally returns the return data
As arg string, but may raise pavillion.Client.RemoteError or others if the server sends back an error code.

### x = c.getServer()
If there is only one connected server, returns a "server interface". If therew is more than one, it chooses randomly. If there is no connected server, returns None.


## Server Interface
These are used by code on the client to represent one individual server(Remember, we support multicast,
there could be more than one.)

### si.remoteMonotonic()

Gets the current value of the remote devices monotonic clock(Think millis()) on arduino. It does not
roll over as 64 bit microseconds are used internally. However it may appear to go backwards if the server reboots.

This function may fail if the time is not synced yet, or if the server is disconnected.

### si.toRemoteMonotonic(t)
Convert time as returned by time.monotonic() to the monotonic scale of the server.


### si.toRemoteMonotonic(t)
Convert time on remote server to the monotonic scale of the local time.monotonic().


### si.rssi()

Returns what the remote server reports as it's RSSI in dbm if on WiFi

### si.battery()

Returns what the remote server reports as it's battery level in percent, if it reports that.

### si.temperature()
Returns what the remote server reports as it's temperature in C, if it reports that.



## Server Objects
###  s=Server(self,port=DEFAULT_PORT, keys=None,pubkeys=None, address='',multicast=None,ecc_keypair=None,allow_guest=False,daemon=None,execute=None,*args,openWanPort=None)

port: Local machine port.
multicast: Multicast group, should this be a multicast server.
daemon: If true, the server's thread will run as a daemon and won't hold up program exit

openWanPort: If this is a port number, Pavillion will use UPnP to forward that port to the server on all
            discovered routers. This requires upnpclient be installed, but non-UPnP functions do not depend on this.



### s.sendMessage(target, name, data)
Sends a message to all clients. May be slow compared to client to server messages.

### s.setStatusReporting(s)
If s is True, this server will inform clients of system temp, WiFi connection strength, and battery status,
three important variables for embedded devices. This requires psutil.


## Client-Server model

Pavillion uses a traditional client-server model, except that clients and servers may share a port. With a few exceptions, only a client can initiate a request, and only a server may respond to or act on a request. This includes reliable and unreliable multicasting modes.

Every client has a 16-byte client ID which may be freely and arbitrarily chosen as a username might be. Clients using security
also have a 32 byte Preshared Key. This has to be a full-strength random key, because the protocol exposes it to offline attacks.

This should not be an issue in the intended use cases.


Messages from a client to a server may be multicast. As long as the servers listen on the same port, they will all recieve it, even with security enabled(If they all have the same keypair or PSK). Conceptually pavillion treats the servers as part of one distributed system.

Messages from a server back to a client are normally unicast.

## Ports

General multicast application traffic uses port 1783 on multicast group 239.255.28.12 by default, but performance could go down if you have many unrelated applications sharing a multicast address.

## Virtual Hairpin NAT

If two hosts are behind the same router, often they cannot communicate via their mapped WAN addresses. To solve
this, if upnpclient is installed, we automatically detect port mappings to the outside world, and "shortcut"
directly 

## What's working so far

At the moment, we have secure reliable multicasting and unicasting with both ECC and preshared keys. Servers can accept "Guest" connections when using ECC, RPC calls are working.

ESP32 and ESP8266 support is working, although the ESP8266 reliable messaging function is blocking, and there's no message recieve support.

We have fairly reliable and fast connections thanks to self otimizing retransmit times, and broadcast-based fast reconnection.

The Arduino libs integrate with Kaithem's Tag Points and Alarms.

Check out the unit tests for examples.