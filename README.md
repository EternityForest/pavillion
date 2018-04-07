# Pavillion UDP Protocol

## Intro

Pavillion is a UDP based protocol aiming to support most of the common messaging modes(Reliable and Unreliable pubsub, RPC, Read/Write/Unreliable write, discovery, etc). The protocol is conceptually connectionless and designed so that implementations can hide the existance of connections.

This reference implementation is written in Python, but the protocol is designed to be light enough to work on servers.

There is no requirement for message brokers, devices simply send directly to each other.

In addition, Pavillion aims to integrate encryption at the application layer, using the usual libsodium. The protocol is designed
to allow for future ciphers to be added

*As I am not a cryptography expert, you have no reason to trust this, but it should deter casual snooping.*

Not that it isn't *intended* to be fairly secure. It doesn't provide perfect forward secrecy or anything like that, but in theory nobody should be able
to read your messages, make fake ones, or do replay attacks.

Right now this doesn't even have a version number and everything is subject to change.

##Example
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

    #Define an RPC function, call it on the client
    s.registers[401] =lambda c,a: a

    x = c.call(401, b'A test string')
    self.assertEqual(x, b'A test string')
```
### Publish subscribe
Client and server objects are all-in-one, and support multiple communication modes.

In addition, the rest of the API is the same for PSK as it is for public key.
```
    #Causes f to be called, printing the message name, data, and the client ID.

    def f(name,data,client):
       print(name,data,client)

    m = s.messageTarget('TestTarget',f)
    c.sendMessage("TestTarget","MessageName",b'data')

```
## Client-Server model

Pavillion uses a traditional client-server model, except that clients and servers may share a port. With a few exceptions, only a client can initiate a request, and only a server may respond to or act on a request. This includes reliable and unreliable multicasting modes.

Every client has a 16-byte client ID which may be freely and arbitrarily chosen as a username might be. Clients using security
also have a 32 byte Preshared Key. This has to be a full-strength random key, because the protocol exposes it to offline attacks.

This should not be an issue in the intended use cases.


Messages from a client to a server may be multicast. As long as the servers listen on the same port, they will all recieve it, even with security enabled(If they all have the same keypair or PSK). Conceptually pavillion treats the servers as part of one distributed system.

Messages from a server back to a client are normally unicast.

## Ports

General multicast application traffic belongs on port 1783 on multicast group 239.255.28.12.


## What's working so far

At the moment, we have secure reliable multicasting with both ECC and preshared keys. Check out the unit tests for examples.