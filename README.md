# Pavillion UDP Protocol

## Intro

Pavillion is a UDP based protocol aiming to support most of the common messaging modes(Reliable and Unreliable pubsub, RPC, Read/Write/Unreliable write, discovery, etc). The protocol is conceptually connectionless and designed so that implementations can hide the existance of connections.

This reference implementation is written in Python, but the protocol is designed to be light enough to work on servers.

There is no requirement for message brokers, devices simly send directly to each other.

In addition, Pavillion aims to integrate encryption at the application layer, using the usual libsodium. The protocol is designed
to allow for future ciphers to be added

*As I am not a cryptography expert, you have no reason to trust this, but it should deter casual snooping.*

Not that it isn't *intended* to be fairly secure. It doesn't provide perfect forward secrecy or anything like that, but in theory nobody should be able
to read your messages, make fake ones, or do replay attacks.

## Client-Server model

Pavillion uses a traditional client-server model, except that clients and servers may share a port. Only a client can initiate a request, and
only a server may respond to or act on a request. This includes reliable and unreliable multicasting modes.

Every client has a 16-byte client ID which may be freely and arbitrarily chosen as a username might be. Clients using security
also have a 32 byte Preshared Key. This has to be a full-strength random key, because the protocol exposes it to offline attacks.

This should not be an issue in the intended use cases.

## Ports

General multicast application traffic belongs on port 1783 on multicast group 239.255.28.12.


## What's working so far

At the moment, we have secure reliable multicasting and that's about it