import socket
import threading

# Client class that holds general information about the client
class Client:
    
    # Constructor
    def __init__(self, nickname, username, realname, clientSock, address):
        self.nickname = nickname
        self.username = username
        self.realname = realname
        self.clientSocket = (clientSock, address)
        self.clientAddress = address
        self.channelList = []

    # Functions
    def getRealname(self):
        return self.realname

    def changeRealname(self, realname):
        self.realname = realname

    def changeNickname(self, nickname):
        self.nickname = nickname

    def getNickname(self):
        return self.nickname

    def getUsername(self):
        return self.username

    # Returns socket object and address, needed for inter-client communication
    def getClientSocket(self):
        return self.clientSocket
    
    #Returns specifically address and port
    def getClientAddress(self):
        return self.clientAddress
    
    def leaveChannel(self, channel):
        if channel in self.channelList:
            self.channelList.remove(channel)

    def addToChannel(self, channel):
        self.channelList.append(channel)

    #Used for error checking
    def getChannels(self):
        return self.channelList


# Server class that holds information about the server the user is connected to, including the available commands the server offers   
class Server:
    
    # Constructor
    def __init__(self, serverName):
        self.serverName = serverName
        self.clientList = [] # Client objects
        self.channelList = [] # Channel objects

        self.HOST = 'fc00:1337::17'
        self.PORT = 50000

        self.socket()

    # Validation for NICK message
    def checkNickMessage(self, message):
        nickMessage = message.split() # Allows to validate individual elements

        # More than 2 parameters or nickname > 10 characters
        if len(nickMessage) != 2 or len(nickMessage[1]) >= 10:
            replyCode = ReplyCode('432')
            return replyCode.getMessage() # error nickname
        
        # nick name in use.
        for client in self.clientList:
            if client.getNickname() == nickMessage[1]:
                replyCode = ReplyCode('433')
                return replyCode.getMessage() 

        return nickMessage[1]

    #Validates USER message
    def checkUserMessage(self, message, nick):
        userMessage = message.split(' ', 4) #Max 4 splits, so real name isn't split
        realnameCheck = userMessage[4]

        # Checks if user mode is an integer.
        try:
            int(userMessage[2])
        except ValueError as identifier:
            replyCode = ReplyCode('461')
            return replyCode.getMessage()

        # checks if user command is valid.
        if realnameCheck[0] != ':' or int(userMessage[2]) > 7 or userMessage[3] != '*' :
            replyCode = ReplyCode('461')
            return replyCode.getMessage()
        
        # Returns username and nickname
        realname = realnameCheck.replace(':', "") # real name without : is used for socket communication
        username = userMessage[1]
        return [username, realname]
    
    #Validate JOIN message
    def checkJoinMessage(self, message, sender):
        # JOIN (#,&,+,!)<channel name>
        joinMessage = message.split()
        channelName = joinMessage[1]
        commaCheck = channelName.split(',') # Checked later to see if there are commas in name.

        # If the user wants to leave all channels
        if channelName == '0':
            return 0
        
        # Max channel limit is 10.
        if (len(sender.getChannels()) > 9):
            replyCode = ReplyCode('405')
            return replyCode.getMessage()
        
        if (channelName[0] == '#' or channelName[0] == '&' or channelName[0] == '+' or channelName[0] == '!') and len(channelName) <= 50 and len(joinMessage) == 2 and len(commaCheck) == 1: # Correct input, client can join channel
            return channelName

        else: # Error
            replyCode = ReplyCode('403')
            return replyCode.getMessage()

    #Validate PART message
    def checkPartMessage(self, message, client):
        partMessage = message.split(' ', 2)
        removeList = partMessage[1].split(',') # Channels which user wants to leave, can be multiple at once

        if (partMessage[1][0] == '#' or partMessage[1][0] == '&' or partMessage[1][0] == '+' or partMessage[1][0] == '!') and (len(partMessage) == 3 or len(partMessage) == 2): # Correct input

            if len(removeList) == 1: # Leave from 1 channel

                for chan in self.channelList:

                    if removeList[0] == chan.getChannelName(): # Leave provided channel

                        client.leaveChannel(chan.getChannelName())
                        chan.removeClient(client)

                        if chan.isEmpty():
                            self.channelList.remove(chan) # Delete channels with no users

                        returnMessage = ':' + client.getNickname() + '!' + client.getNickname() + '@' + str(client.getClientAddress()[0]) + ' ' + message

                        self.broadcastToChannel(chan, returnMessage) # Tell 

                        return returnMessage

                else:
                    returnMessage = ':' + client.getNickname() + ' 442 ' + client.getNickname() + ' ' + removeList[0] + " :You're not in that channel"
                    return returnMessage

            elif len(removeList) > 1: # Client wants to leave multiple channels
                returnMessage = ''
                x = 0 # Iterator for all channels user wants to be removed from
                for leaveChan in removeList:

                    if (removeList[x][0] == '#' or removeList[x][0] == '&' or removeList[x][0] == '+' or removeList[x][0] == '!') and (len(partMessage) == 3 or len(partMessage) == 2): # Correct input

                        for chan in self.channelList:

                            if leaveChan == chan.getChannelName(): # Valid channel

                                client.leaveChannel(chan.getChannelName())
                                chan.removeClient(client)

                                if chan.isEmpty():
                                    self.channelList.remove(chan)

                                msg = ':' + client.getNickname() + '!' + client.getNickname() + '@' + str(client.getClientAddress()[0]) + ' ' + 'PART ' + leaveChan + ' ' + partMessage[2] + '\r\n'

                                returnMessage += msg # Appended as several messages must be sent

                                self.broadcastToChannel(chan, msg) # Broadcast to users in channel
                        x += 1 # Next channel in list
                
                return returnMessage

            else: # Error
                replyCode = ReplyCode('461')
                
                returnMessage = ':' + client.getNickname() + ' 461 ' + client.getNickname() + ' :' + replyCode.getMessage()
                return returnMessage

    # Validate QUIT message
    def checkQuitMessage(self, message):
    	quitMessage = message.split(' ', 1)
    	return quitMessage[1] #Returns quit message

    # Checks PRIVMSG command. Returns a list consisting of a message, a target (either client or channel object) and broadcast boolean (True if to broadcast to channel and false to send to either sender or target client).
    def checkPrivMessage(self, message, sender):
        # Splits main message into parts for validation
        sendMessage = message.split(' ', 2)

        # Checks if command has right number of elements
        if len(sendMessage) < 3:
            replyCode = ReplyCode('461')
            return [replyCode.getMessage(), sender, False] # False to only broadcast to sender.

        target = sendMessage[1] # Can be user or channel
        msg = sendMessage[2]
        returnMessage = ''

        # If a message is being sent to clients in the channel.
        if (target[0] == '#' or target[0] == '&' or target[0] == '+' or target[0] == '!' ): # Validate channel name prefix
            
            if len(msg) < 1: #if message is empty
                replyCode = ReplyCode('412')
                return [replyCode.getMessage(), sender, False]
            
            # Find channel in list of channels
            for targetChannel in self.channelList:
                
                # compare channel names
                if target == targetChannel.getChannelName():
                    
                    # Return message to broadcast and channel object.
                    returnMessage = ':' + sender.getNickname() + '!' + sender.getNickname() + '@' + str(sender.getClientAddress()[0]) + ' ' + message

                    return [returnMessage, targetChannel, True] #True for broadcasting to channel

            # if channel does not exist
            else:
                replyCode = ReplyCode('403')
                return [replyCode.getMessage(), sender, False] # False for only sending msg to sender.
        
        # If sending priv message to specific user.
        else:
            # Searching for specific client.
            for targetClient in self.clientList:
                
                # compares client names
                if target == targetClient.getNickname():
                    
                    # returns message to send to target client.
                    returnMessage = ':' + sender.getNickname() + '!' + sender.getNickname() + '@' + str(sender.getClientAddress()[0]) + ' ' + message

                    return [returnMessage, targetClient, False] # False for only sending msg to sender.
            
            # If specified client is not found.
            else:
                replyCode = ReplyCode('401')
                return [replyCode.getMessage(), sender, False] # False for only sending msg to sender.

    # Validate WHO message
    def checkWhoMessage(self, message, client):
        incomingData = message.split()
        returnMessage = ''

        for channel in self.channelList:
            
            if incomingData[1] == channel.getChannelName(): # Valid channel

                clients = channel.getClientList() # So we can send information about the clients
            
                if client in clients: # Client is in the channel

                    for c in clients:

                        msg = ':' + self.serverName + ' 352 ' + client.getNickname() + ' ' + incomingData[1] + ' ' + c.getUsername() + ' ' + str(c.getClientAddress()[0]) + ' ' + self.serverName + ' ' + c.getNickname() + ' H :0 ' + c.getRealname() + '\r\n'
                    
                        returnMessage += msg # Used to send information about clients
                    
                    msg = ':' + self.serverName + ' 315 ' + client.getNickname() + ' ' + incomingData[1] + ' :End of WHO list\r\n' # Signifies end of list of users
                    
                    returnMessage += msg
                    return returnMessage

                # client not in channel
                else:
                    replyCode = ReplyCode('441')
                    return replyCode.getMessage()

                break
        
        # if there are no channels in the server
        else:
            replyCode = ReplyCode('403')
            return replyCode.getMessage()

    # Reusable, required for WHO to work, sending just the information about the clients doesn't fit specification
    def sendNamesList(self, channel, senderName):
        
        msg = ':' + self.serverName + ' 353 ' + senderName + ' = ' + channel.getChannelName() + ' :'

        for client in channel.getClientList():
            msg += ' ' + client.getNickname()

        return msg

    # Reusable, retrieves client socket objects and sends them message.
    def broadcastToChannel(self, channel, message):

        if channel in self.channelList: # Channel exists

            for client in channel.getClientList():
                (conn, address) = client.getClientSocket()
                conn.sendall((message + '\r\n').encode())

    # Tells all clients that share channel with sender of nickname change.
    def broadcastNickChange(self, sender, oldNickname):

        clientChannels = sender.getChannels()

        for chan in clientChannels:

            for cl in chan.getClientList():
                
                if cl == sender: # Don't send to client that changed nick
                    continue

                (conn, address) = cl.getClientSocket()
                conn.sendall((':' + oldNickname + '!' + oldNickname + '@' + str(address[0]) + ' NICK ' + sender.getNickname() + '\r\n').encode())

    # Tells all clients which share channel with sender that sender is leaving.
    def broadcastQuitMessage(self, sender, message):
        
        for client in self.clientList:

            if client == sender:
                continue
            
            (conn, address) = client.getClientSocket()
            conn.sendall((message + '\r\n').encode())

    # Handles clients diconnecting with and without QUIT message. Removes clients from channels in which they are in.
    def clientDisconnected(self, line, client):

        address = client.getClientAddress()

        broadcastMessage = ':' + client.getNickname() + '!' + client.getNickname() + '@' + str(address[0]) + ' ' + line

        self.broadcastQuitMessage(client, broadcastMessage)
        
        clientChannels = client.getChannels() # Used so we can remove client from current channels

        for c in clientChannels:
            c.removeClient(client)

            if c.isEmpty():
                self.channelList.remove(c)

        self.clientList.remove(client)
        del client # Delete client object

    def handleClient(self, conn, addr): # Runs from connection to termination

        print('Connected by ', addr)
        nickname = ''
        realname = ''

        while True: # Until QUIT
            
            try:
                data = conn.recv(1024) # Waiting to receive data on socket
            except:
                
                if nickname != '' and realname != '':
                    
                    line = 'QUIT :[Errno 104] Connection reset by peer'                    
                    self.clientDisconnected(line, client)
                
                return False # Connection dropped

            if data: # Data received
                print("Incoming data: " + data.decode())
                incomingData = data.decode().splitlines()
                
                for line in incomingData:
                    
                    print("Line: " + line)
                    
                    lineCheck = line.split()
                    
                    if (lineCheck[0] == 'NICK'):

                        nickReply = self.checkNickMessage(line) # Validation

                        # If client is setting up nickname for the first time and they get an error.
                        if (nickReply == 'ERR_ERRONEUSNICKNAME' or nickReply == 'ERR_NICKNAMEINUSE') and nickname == '':
                            conn.sendall((nickReply + '\r\n').encode())
                            conn.shutdown(socket.SHUT_RDWR) # Terminate connection
                            conn.close()
                            return False

                        # Client trying to change nickname and they get an error.
                        elif (nickReply == 'ERR_ERRONEUSNICKNAME' or nickReply == 'ERR_NICKNAMEINUSE') and nickname != '':
                            conn.sendall((nickReply + '\r\n').encode())

                        # If client is changing nickname. 
                        elif nickReply != 'ERR_ERRONEUSNICKNAME' and nickReply != 'ERR_NICKNAMEINUSE' and nickname != '':

                            client.changeNickname(nickReply)

                            conn.sendall((':' + nickname + '!' + nickname + '@' + str(addr[0]) + ' NICK ' + nickReply + '\r\n').encode())

                            self.broadcastNickChange(client, nickname)

                            nickname = nickReply # Success, new nickname

                        else:
                            nickname = nickReply

                    elif (lineCheck[0] == 'USER' and nickname != ''): # Empty nickname as username can only be set on connection
                        
                        replyUser = self.checkUserMessage(line, nickname)
                        
                        if replyUser[0] == 'ERR_ERRONEOUSINPUT'and client.getNickname != '':
                            conn.sendall((replyUser + '\r\n').encode())
                            conn.shutdown(socket.SHUT_RDWR)
                            conn.close()
                            return False
                        
                        username = replyUser[0]
                        realname = replyUser[1]

                        client = Client(nickname, username, realname, conn, addr) 
                        self.clientList.append(client) # New client registered

                        RPL_WELCOME = ReplyCode('001') # Send welcome message to client
                        
                        conn.sendall(('001 ' + nickname + ' :' + RPL_WELCOME.getMessage() + '\r\n').encode())
                    
                    elif (lineCheck[0] == 'JOIN' and nickname != ''):
                        
                        replyJoin = self.checkJoinMessage(line, client)
                        targetChannel = None # Set it to empty until they have joined channel (for broadcasting).
                        
                        if replyJoin != 'ERR_UNKNOWNCOMMAND' and replyJoin != 'ERR_NOSUCHCHANNEL' and replyJoin != 'ERR_TOOMANYCHANNELS' and replyJoin != 0: # Correct input
                            
                            if len(self.channelList) != 0: # Channels exist on server
                                
                                for chan in self.channelList:

                                    # If channel exists, add to channel
                                    if chan.getChannelName() == replyJoin:
                                        targetChannel = chan
                                        chan.addClient(client) # Channel object list which stores clients
                                        client.addToChannel(chan) # Client object list which stores channels
                                        break

                                # Channel doesn't exists, create and add user
                                else:
                                    channel = Channel(replyJoin)
                                    targetChannel = channel
                                    self.channelList.append(channel)
                                    channel.addClient(client)
                                    client.addToChannel(channel)
                                    
                            else: # First channel, create and join it
                                channel = Channel(replyJoin)
                                targetChannel = channel
                                channel.addClient(client)
                                self.channelList.append(channel)
                                client.addToChannel(channel)

                            reply = ':' + nickname + '!' + client.getUsername() + '@' + str(addr[0]) + ' JOIN ' + str(replyJoin) + ' * :' + realname

                            # Tell clients (inc. you) in channel that user joined.
                            self.broadcastToChannel(targetChannel, reply)

                            #Send names list
                            conn.sendall((self.sendNamesList(targetChannel, client.getNickname()) + '\r\n').encode())

                        elif replyJoin == 0: # Leave all channels
                            
                            allClientsChannels = client.getChannels()

                            for chan in allClientsChannels:

                                msg = ':' + nickname + '!' + client.getUsername() + '@' + str(addr[0]) + ' PART ' + chan.getChannelName()
                                
                                self.broadcastToChannel(chan, msg) # Tells every user in channel that user is leaving
                                # Remove from appropriate lists
                                chan.removeClient(client)
                                client.leaveChannel(chan)

                            # If client is not in any channel
                            else:
                                replyCode = ReplyCode('441')
                                conn.sendall((replyCode.getMessage() + '\r\n').encode())

                        else:
                            conn.sendall((replyJoin + '\r\n').encode())

                    elif (lineCheck[0] == 'PRIVMSG' and nickname != ''):

                        replyMessage = self.checkPrivMessage(line, client)

                        if replyMessage[2]: # True, broadcast to channel
                            
                            cList = replyMessage[1].getClientList() # Get clients in user input channel

                            for c in cList:
                                
                                if c == client: # Don't send message to yourself
                                    continue
                                
                                (targetConn, targetAddress) = c.getClientSocket()

                                targetConn.send((replyMessage[0] + '\r\n').encode()) # For each client

                        else: # If there is error in message, send error to client only
                            (targetConn, targetAddress) = replyMessage[1].getClientSocket() # Get targets socket object

                            targetConn.send((replyMessage[0] + '\r\n').encode())

                    elif (lineCheck[0] == 'PART' and nickname != ''):

                        replyPart = self.checkPartMessage(line, client)
                        conn.sendall((replyPart + '\r\n').encode())
                    
                    elif (lineCheck[0] == 'QUIT'):
                        
                        msg = self.checkQuitMessage(line)
                        conn.sendall((msg + '\r\n').encode())
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close() # Close socket

                        self.clientDisconnected(line, client)

                        return False # Terminate

                    elif lineCheck[0] == 'WHO' and nickname != '':
                        
                        msg = self.checkWhoMessage(line, client)
                        conn.sendall(msg.encode())
                        
                    elif (lineCheck[0] == 'CAP' or lineCheck[0] == 'MODE'): # Server doesn't support these commands, next line
                        continue

                    else: # Unknown command
                        replycode = ReplyCode('421')
                        conn.sendall((replycode.getMessage() + '\r\n').encode())

    # Sets up socket and handles incoming clients.
    def socket(self):
        
        # Connects socket using ipv6.
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allows to reuse socket.
            
            s.bind((self.HOST, self.PORT))
            print ('Socket successfully created at port: ' + str(self.PORT))
            s.listen(5) # Buffer which stores max 5 clients waiting to connect.
            
            threads = list() # Stores a list of active thread (1 thread for each client).
            
            while True:
                
                conn, addr = s.accept() # Accepts new client

                # Handle client in new thread
                x = threading.Thread(target=self.handleClient, args=(conn, addr))
                threads.append(x)
                x.start()
                
                # If client has disconnected and thread is finished
                for t in threads:
                    if not t.is_alive():
                        t.join()

# ErrorCode class handles error codes that are sent to the client
class ReplyCode:
    
    # Constructor
    def __init__(self, id):
        
        replies = [
            ['001', 'Welcome to the internet relay network'],
            ['401', 'ERR_NOSUCHNICK'],
            ['403', 'ERR_NOSUCHCHANNEL'],
            ['404', 'ERR_CANNOTSENDTOCHAN'],
            ['405', 'ERR_TOOMANYCHANNELS'],
            ['412', 'ERR_NOTEXTTOSEND'],
            ['421', 'ERR_UNKNOWNCOMMAND'],
            ['432', 'ERR_ERRONEUSNICKNAME'],
            ['433', 'ERR_NICKNAMEINUSE'],
            ['441', 'ERR_USERNOTINCHANNEL'],
            ['461', 'ERR_NEEDMOREPARAMS']
            ]
        self.errorID = id

        # Return error name corresponding to error ID
        for i in replies:
            if i[0] == self.errorID:
                self.errorMessage = i[1]

    # returns message to be sent
    def getMessage(self):
        return (self.errorMessage)
    
# Channel class holds information about the channels on a server
class Channel:
    
    # Constructor
    def __init__(self, name):
        self.channelName = name
        self.clientList = [] # Stores list of clients connected to channel

    def getChannelName(self):
        return self.channelName

    def addClient(self, client):
        self.clientList.append(client)
        print('Added ' + client.getNickname() + ' to ' + self.channelName)

    def removeClient(self, client):
        if client in self.clientList:
            self.clientList.remove(client)
            print('Removed ' + client.getNickname() + ' from ' + self.channelName)

    def getClientList(self):
        return self.clientList

    def isEmpty(self): # Check if channel has no users
        if len(self.clientList) == 0:
            return True
        else:
            return False

server = Server("Team5") # Creates instance of our test server
