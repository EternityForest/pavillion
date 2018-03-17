
# The Pavillion Protocol

Pavillion is a UDP based protocol that provides reliable multicast messaging and RPC calls. 

By default, Port 1783 should be used general application traffic, and 2221 should be used for low data rate system status messages.

For multicasting, general application traffic by default should use 239.255.28.12 and low rate system messages should use 239.255.28.18

Chat messages between humans should use an application-specific port.

Remember every node must process every message on the chosen multicast group, so you may need to divide the space into multiples.

Port numbers remain the same if security is used.



## Nodes

A node may be a client, a server, and a client and server may share a port. If they do, the roles of client and server are still considered separatly.


## Message Format

Every Pavillion packet has the following general format:

|Offset|Value|
|------|-----|
|0|Fixed ASCII "Pavillion0"|
|12| 8 byte LE message counter|
|19|1 byte Opcode|
|20| N byte data area(Remainder of packet)|


The contents of the data area are opcode-dependant. The message counter must increase by at least one for
every message sent to a given address. Recievers should use this to ignore duplicates.

When a client first comes online, it should send a "sync" message to the server to tell it to reset it's counter.

To avoid issues when counters reset, nodes may use the current time in microseconds as a base for the
counter.


### Packet Types

#### 1: Reliable Message
Represents an MQTT or XMPP message with a name sent to a target(Akin to a topic).

Data area format:

<Newline terminated UTF8 target> <Newline terminated UTF8 name> <Binary payload>

#### 2: Message Acknowledge
Represents an acknowledgement of an `01 reliable message` packet. Data is the message counter for that packet.


#### 3: Unreliable Message
Same as reliable but should not trigger an acknowledgement message.

#### 4: RPC Call
The first 2 bytes represent a function number, where the first 4096 are reserved. The remaining represents an argument string to the called function. Currently RPC calls must be idempotent or
else it is not possible to automatically retry them.

#### 5: RPC Response
The first 8 bytes represent the packet number of the RPC call being responded to. The next 2 represent a response typecode, where anything other than 0 indicates an error. 

The remainder is the return data of the function call.



#### 6: Register Read
The first 2 bytes represent a register number. The next 2 bytes if present represent an offset, and the next 2 represent a data length.

#### 7: Register Declaration

The first 2 bytes represent a register. The next 2 represent an offset, and the remainder is the value of that register starting at that position.



#### 8: Observe
Represents a request to be notified about changes occurring at a register for a period of time.

The first 2 bytes are the register number. The second 2 bytes are the duration. The next 2 are a rate limit, both in milliseconds.

If the sender is already subscribed, the new time limit should simply replace the old one, renewing it.


#### 9: Register Info Request
Contains a 2 bytes register number

#### 10: Register Info
Contains a 2 byte register number followed by a string having the following format: Name, Datatype, interface, description.

Datatype is a either a UUID, a DNS bases identifier, or a function type expression joining the parameter type to the return type with ->

Interface must be a UUID or a DNS based name that identifies the datatypes and purpose of the register, much like a class inheritance.

#### 10: Sync
Sent by the client when it first connects to the network. Servers recievng this message should reset their local copy of the client's counter
to be able to accept messages from them. Not neccesary when using the secure protocol.

The data area must be the client's ID. This must not be trusted outside of private LANs

#### 11: Sync Response
Sent by the server in response to a sync message from the client to acknowledge it. Not used with the secure protocol.

Data area format:
<8 byte LE of packet counter of original message>


#### Opcode 15


### Reliable Messaging 

Only a client can send and only a server can recieve reliable and unreliable messages.

A reliable message is a single packet of data, sent to a "target" on a single server or a multicast group, having a utf8 name and a binary
data field.

A client wishing to send a multicast message must send an `01 reliable message` to the appropriate multicast group or unicast address. All servers recieving this message
should reply with an `02 acknowledge` message sent via unicast to the client. clients recieving this message should add the server to the list of active subscribers
for that target.

Clients should resend multicasts until all active subscribers have replied. Clients should send blank messages every minute as keepalives, and remove
servers that have not replied in five minutes.

### Unreliable Messaging

Unreliable messaging works the same, except clients send `03 Unreliable message` instead and no acknowledge is sent. Messages should be passed to the application
layer the same either way.


## State Machine Synchronization Protocol

### Background
In some cases it might be desired to have a set of state machines whos transitions can be controlled by timers remain in sync across a network.


### Outline

Each set of state machines has a target. Whenever a state machine transitions, it sends a message containing the conceptual timestamp of the transition,
unless the transition was caused by a network message.

Conceptual timestamps, for timer triggered transitions, are calculated by adding the entry time of the old state with the length of that state. They reflect
when a transition "should have" happened regardless or real world scheduling noise.

Upon recieving a message, you transition to that state unless you are both already in that state, and your transition timestamp exactly matches the one in the message.

You set your new transition timestamp to exactly the one recieved in the message regardless of the message's actual arrival time.

To increase efficiency, the actual transition times may be randomized slightly. They should always be computed after conceptual times and not affect them at all. This randomization means that one will act as the "master" by transitioning a few milliseconds ahead, as opposed to transitioning at the same time resulting in many transition messages.

No long term drift will result as real world timestamps aren't used to calculate the next transition.


The exception is manual or non-timer transitions. In these cases the actual and conceptual times should match the real event timestamp.


## Pavillion General Events Target

The General Events Target is a Pavillion target on port XX with the target name YYY. It is reserved for small and very infrequent events about certain defined events.


## Lighting Control
Pavillion was designed to coexist with ArtNet. Realtime lighting control data should be transmitted on 239.255.28.13 and port 6454.

Lighting control should be via standard ArtNet unless security is required, except multicast should be used instead of broadcast unless backwards
compatibility is needed.





## Notes

How should the alarm protocol work? Should that be a separate thing where we multicast alarms and also ask hey what alarms do you have?

Do we need signed messages? That have a Pubkey signature?

Or do we just need authenticated messages?

Or maybe we don't need any kind of authentication for these alarm messages.


An Alarm is multicast on the bus using secure or insecure messaging. It contains:

An Alarm ID
A state(A 16 bit number of seconds with 65536 special and meaning normal)
An alarm name
An 8 bit priority number
A description

Priority and description can be changed even after an alarm becomes active.

To cancel an alarm, resend it in state 65536

To send alarms in the "tripped but not yet active" state, send a number of seconds till it should activate
