



import weakref, types, collections, struct, time, socket,threading,random,os,logging,traceback

from .common import nonce_from_number,pavillion_logger,DEFAULT_PORT,DEFAULT_MCAST_ADDR,ciphers,MAX_RETRIES



def is_multicast(addr):
    if not ":" in addr:
        a = addr.split(".")
        if 224>= int(a[0]) >= 239:
            return True
        return False
    else:
        if addr.startswith('ff') or addr.startswith("FF"):
            return True
    return False

import queue


class ReturnChannel():
    def __init__(self,queue=None):
        self.queue = queue or queue.Queue(64)
    
    def onResponse(self,data):
        self.queue.put(data,True,3)

class ExpectedAckCounter():
    #TODO track specific servers
    def __init__(self,e,counter):
        self.e = e
        self.counter = counter
        self.target = None

    def onResponse(self, data):
        self.counter-=1
        if not self.counter:
            self.e.set()


class _Client():
    def __init__(self, address=('255.255.255.255',DEFAULT_PORT),clientID=None,psk=None,cipher=1,server=None,keypair=None, serverkey=None, handle=None):
        "Represents a Pavillion client that can both initiate and respond to requests"
        #The address of our associated server
        self.server_address = address

        #Our message counter
        self.counter = random.randint(1024,1000000000)

        self.server_counter = 0

        self.cipher= ciphers[cipher]

        self.keypair = keypair
        self.server_pubkey = serverkey

        #Clients can be associated with a server
        self.server = server

        self.psk = psk
        self.clientID = clientID


        self.skey = None
        self.nonce = os.urandom(32)
        self.challenge = os.urandom(16)

        if self.psk:
            self.key = self.cipher.keyedhash(self.nonce,psk)
        
        elif  self.keypair:
            self.key = os.urandom(32)
        else:
            self.key= None

        

        self_address = ('', 0)

        self.lock=threading.Lock()

        # Create the socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) 
        # Bind to the server address
        self.sock.bind(self_address)
        self.sock.settimeout(1)


        if is_multicast(address[0]):
            # Create the socket
            self.msock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
            self.msock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) 
            # Bind to the server address
            self.msock.bind(self_address)
            self.msock.settimeout(1)
            group = socket.inet_aton(address[0])
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            self.msock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)


        
        self.running = True

        def cl(*args):
            self.close()
        self.clfun = cl
        #If we have a handle, make it so that if the handle gets collected the server thread stops
        if handle:
            self.handle = weakref.ref(handle,cl)

        #lastseen time  dicts indexed by the name of what you are subscribing to, then indexed by subscriber IP
        #This is a list of *other* machines that are subscribing. All a "subscription" is, is a response to a multicast packet.
        #If we get less responses than usual, we know we should retry.
        self.known_subscribers = {}

        self.subslock = threading.Lock()
        self.waitingForAck = weakref.WeakValueDictionary()
        self.backoff_until = time.time()


        t = threading.Thread(target=self.loop)
        t.start()

        if is_multicast(address[0]):
            t = threading.Thread(target=self.mcast_loop)
            t.start()


        if self.psk and self.clientID:
            self.sendSetup(0, 1, struct.pack("<B",self.cipher.id)+self.clientID+self.challenge)
        elif self.keypair:
            self.sendSetup(0, 1, struct.pack("<B",self.cipher.id)+self.clientID+self.challenge)

        else:
            self.synced = False
            counter = 8
            while not self.synced and counter:
                self.sendSetup(0, 1, struct.pack("<B",self.cipher.id)+self.clientID+self.challenge)
                time.sleep(0.05)
                counter-=1




    def close(self):
        self.running = False

    def send(self, counter, opcode, data):
        if self.psk or self.keypair:
            self.sendSecure(counter,opcode,data)
        else:
            self.sendPlaintext(counter,opcode,data)


    def sendPlaintext(self, counter, opcode, data):
        "Send an unsecured packet"
        m = struct.pack("<Q",counter)+struct.pack("<B",opcode)+data
        self.sock.sendto(b"Pavillion0"+m,self.server_address)

    def sendSetup(self, counter, opcode, data):
        "Send an unsecured packet"
        m = struct.pack("<Q",counter)+struct.pack("<B",opcode)+data
        self.sock.sendto(b"PavillionS0"+m,self.server_address)

    def sendSecure(self, counter, opcode, data):
        "Send a secured packet"
        q = struct.pack("<Q",counter)
        n = b'\x00'*(24-8)+struct.pack("<Q",counter)
        m = struct.pack("<B",opcode)+data
        m = self.cipher.encrypt(m,self.key,n)
        self.sock.sendto(b"PavillionS0"+q+m,self.server_address)


    #Get rid of old subscribers, only call from seenSubscriber
    def cleanSubscribers(self):
            try:
                for i in self.known_subscribers:
                    for j in self.known_subscribers[i]:
                        if self.known_subscribers[i](j)[1]<time.time()-120:
                            self.known_subscribers[i].pop(j)
            except:
                pass


    def countBroadcastSubscribers(self,target):
        with self.subslock:
            if not target in self.known_subscribers:
                return 0
            else:
                return len(self.known_subscribers[target])


    def onRawMessage(self, msg,addr):
        s = b"PavillionS0"
        if msg.startswith(s):
            msg=msg[len(s):]
            counter = struct.unpack("<Q",msg[:8])[0]
        

            #Normal Pavillion, pass through to application layer
            if counter:
                if self.skey:
                    msg2 = self.cipher.decrypt(msg[8:], self.skey,nonce_from_number(counter))
                    #Duplicate protection
                    if self.server_counter>=counter:
                        pavillion_logger.debug("Duplicate Pavillion")
                        return
                    self.server_counter = counter

                                
                    opcode =msg2[0]
                    data=msg2[1:]
                    self.onMessage(addr,counter,opcode,data)

                #We don't know how to process this message. So we send
                #a nonce request to the server
                else:
                    self.sendSetup(0, 1, struct.pack("<B",self.cipher.id)+self.clientID+self.challenge)

            #Counter 0 indicates protocol setup messages
            else:
                opcode = msg[8]
                data = msg[9:]
                #Message 5 is an "Unrecognized Client" message telling us to redo the whole auth process.
                #Send a nonce request.
                if opcode==5:
                    self.sendSetup(0, 1, struct.pack("<B",self.cipher.id)+self.clientID+self.challenge)

        
                if opcode==6:
                    if data==self.challenge:
                        self.backoff_until = time.time()+15
                        logging.error("Client attempted to connect with invalid client ID")
                        self.challenge = os.urandom(16)


                if opcode==2:
     
                    if self.psk:
                        servernonce,challenge,h = struct.unpack("<32s16s32s",data)
                        if not challenge==self.challenge:
                            logging.debug("Client recieved bad challenge response")

                        #Ensure the nonce we get is real, or else someone could DoS us with bad nonces.
                        if self.cipher.keyedhash(servernonce+challenge,self.psk)==h:
                        
                                #overwrite old string to Ensure challenge only used once
                                self.challenge = os.urandom(16)
                                
                                #send client info
                                m = struct.pack("<B16s32s32sQ",self.cipher.id,self.clientID,self.nonce,servernonce,self.counter)
                                self.counter +=3
                                v = self.cipher.keyedhash(m,self.psk)
                                self.skey = self.cipher.keyedhash(servernonce+self.nonce,self.psk)
                                self.sendSetup(0, 3, m+v)

                        else:
                            logging.debug("Client recieved bad challenge response")
                            
                if opcode == 11:
                    if  self.keypair:

                        data = self.cipher.pubkey_decrypt(data[24:],data[:24],self.server_pubkey,self.keypair[1])
                       
                        servernonce,challenge = struct.unpack("<32s16s",data)

                        m = struct.pack("<B",self.cipher.id)
                        self.key = os.urandom(32)
                        self.serverkey=os.urandom(32)

                        n=os.urandom(24)

                        #Send an ECC Client Info
                        p = struct.pack("<32s32s32sQ",servernonce, self.key, self.serverkey,self.counter)
                        p = self.cipher.pubkey_encrypt(p, n,self.server_pubkey,self.keypair[1])
                        self.sendSetup(0, 12, self.clientID+m+n+p)



                # print(msg,addr)
                # x = parsePavillion(msg)
                # print(x)
                # if x:
                #     self.onMessage(m,addr)
        else:
            unsecure = b'Pavillion0'

            #Only if PSK is None do we accept these unsecured messages
            if self.psk is None and s.startswith(unsecure):
                msg=msg[len(unsecure):]
                counter = struct.unpack("<Q",msg[:8])[0]
                opcode=msg[8]
                msg = msg[9:]
                if opcode==11:
                    self.synced = True
                else:
                    self.onMessage(addr, counter,opcode,msg)
                return

            logging.warning("Bad header "+str(msg))


    def loop(self):
        "Main loop that should always be running in a thread"
        while(self.running):
            try:
                msg,addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue

            try:
                self.onRawMessage(msg,addr)
            except:
                logging.exception("Exception in client loop")
     
        #Close socket at loop end
        self.sock.close()

    def mcast_loop(self):
        "If we are connecting to a server on a multicast server, we need this other loop to listen to traffic there"
        while(self.running):
            try:
                msg,addr = self.msock.recvfrom(4096)
            except socket.timeout:
                continue

            try:
                self.onRawMessage(msg,addr)
            except:
                logging.exception("Exception in client loop")
     
        #Close socket at loop end
        self.sock.close()

    def onMessage(self,addr,counter,opcode,data):
        #If we've recieved an ack or a call response
        if opcode==2 or opcode==5:
            #Get the message number it's an ack for
            d = struct.unpack("<Q",data)[0]


            if d in self.waitingForAck:
                #We've seen a subscriber for that target
                if self.waitingForAck[d].target:
                    self.seenSubscriber(addr,self.waitingForAck[d].target)

                try:
                    #Decrement the counter that started at 0
                    self.waitingForAck[d].onResponse(data)
                except Exception:
                    print(traceback.format_exc(6))
                    pass

    #Call this with target, IP when you get an ACK from a packet you sent
    #It uses a lock so it's probably really slow, but that's fine because
    #This protocol isn't meant for high data rate stuff.
    def seenSubscriber(self,t,s):
        with self.subslock:
            if t in self.known_subscribers:
                x = self.known_subscribers[t]
                if not s in t:
                    self.cleanSubscribers()
                x[s] = time.time()
            else:
                self.cleanSubscribers()
                self.known_subscribers[t]={s:time.time()}

    def sendMessage(self, target, name, data, reliable=True, timeout = 10):
        "Attempt to send the message to all subscribers. Does not raise an error on failure, but will attempt retries"
        with self.lock:
            self.counter+=1
            counter = self.counter

        if reliable:
            try:
                expected = len([i for i in known_subscribers[t] if i>120])
            except:
                expected = 1

            e = threading.Event()
            w = ExpectedAckCounter(e,expected)
            w.target = target
            self.waitingForAck[counter] =w
        
        self.send(counter, 1 if reliable else 3, target.encode('utf-8')+b"\n"+name.encode('utf-8')+b"\n"+data)


        #Resend loop
        if reliable:
            x = 0.010
            ctr = MAX_RETRIES
            if e.wait(x):
                return
            while ctr and (not e.wait(x)):
                x=min(1, x*1.1)
                ctr-=1
                time.sleep(x)
                if e.wait(x):
                    return
                self.send(counter, 1 if reliable else 3, target.encode('utf-8')+b"\n"+name.encode('utf-8')+b"\n"+data)

        #Return how many subscribers definitely recieved the message.
        return expected-w.counter
                

    def call(self,name,data, timeout=10):
        "Call a function by it's register ID"
        return self._call(name,data,timeout)

    def _call(self, name, data, timeout = 10):
        with self.lock:
            self.counter+=1
            counter = self.counter


        w = ReturnChannel()
        self.waitingForAck[counter] =w
        
        self.send(counter, 4, struct.pack("<H",name)+data)

        x = 0.003
        ctr = 24
        time.sleep(x)

        q = w.queue
        
        while ctr and q.empty():
            x=min(1, x*1.1)
            ctr-=1
            time.sleep(x)
            self.send(counter, 4, struct.pack("<H",name)+data)

        if q.Empty():
            raise RuntimeError("Server did not respond")
        
        d = q.get()
        if struct.unpack("<H",d[:2])[0] >0:
            raise RuntimeError(d[2:].decode("utf-8","backslashreplace"))
        return d[1][2:]




class Client():
    def __init__(self, address=('255.255.255.255',1783),clientID=None,psk=None,cipher=1,keypair=None, serverkey=None, server=None):
        "Represents a public handle for  Pavillion client that can initiate requests"
        self.client= _Client(address,clientID,psk,cipher=cipher, server=server,keypair=keypair,serverkey=serverkey,handle=self)
        self.clientID = clientID

    def sendMessage(self,target,name,value):
        return self.client.sendMessage(target,name,value)

    def close(self):
        self.client.close()