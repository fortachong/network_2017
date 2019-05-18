from threading import Thread
import socket
import queue
import logging
import netutils

class ConnectionHandler(Thread):

    def __init__(self, in_queue, out_queue, orch_dict):
        # Initialise the thread
        Thread.__init__(self)
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.orch_dict = orch_dict
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.listener = Thread(target=self._connection_listener, args=(self.out_queue,))


    def run(self):
        self.listener.start()
        while True:
            logging.info('CON HANDLER: Looking at connection handler queue')
            message = self.in_queue.get()

            if message['msg'] == 'CLOSE':
                try:
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                    self.server_socket.close()
                except socket.error as er:
                    logging.warning('CON HANDLER: Exception shutting down server socket %s', er)
                    try:
                        self.server_socket.close()
                    except socket as er:
                        logging.warning('CON HANDLER: Exception closing down server socket %s', er)
                self.listener.join(timeout=1)
                return

            elif message['msg'] == 'CRTCON':
                ip = message['ip']
                port = int(message['port'])
                logging.info('CON HANDLER: %s %s %s %s', 'Connection to ip:', ip, 'port', port)

                clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Set a short timeout to ensure we poll through the IPs quickly
                clientsocket.settimeout(1)
                try:
                    clientsocket.connect((ip, port))
                    (ip, _) = clientsocket.getsockname()
                    (ip2, _) = clientsocket.getpeername()
                    logging.info('CON HANDLER: ip1 %s %s %s', ip, 'ip2', ip2)
                    if ip == ip2:
                        logging.warning('CON HANDLER: CON HANDLER trying to connect to self')
                        continue
                    message = {'msg': 'NEWCON', 'sock': clientsocket}
                    # Set the timeout to blocking for recieving data
                    clientsocket.settimeout(None)
                    self.out_queue.put(message)

                except socket.error as er:
                    logging.warning('CON HANDLER: %s', er)

                finally:
                    logging.info('CON HANDLER: Exception connecting to %s %i', ip, port)
            elif message['msg'] == 'COND_IPS':
                ip_list = []

                cond_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cond_socket.settimeout(1)
                try:
                    ip = str.split(self.orch_dict['conductor_ip'], ':')[0]
                    port = str.split(self.orch_dict['conductor_ip'], ':')[1]

                    cond_socket.connect((ip, int(port)))

                    proto_down_msg = '{}\r\n{}\r\n{}\r\n{}\r\n'.format('DOWN',
                                                                       self.orch_dict['composition_name'],
                                                                       self.orch_dict['full_checksum'],
                                                                       '10001')
                    cond_socket.sendall(proto_down_msg.encode())

                    reply_msg = netutils.read_line(cond_socket)
                    if reply_msg == 'NONE':
                        filename = netutils.read_line(cond_socket)
                        checksum = netutils.read_line(cond_socket)
                        if filename != self.orch_dict['composition_name']:
                            logging.info('CON HANDLER: Error in filename')
                            cond_socket.shutdown(socket.SHUT_RDWR)
                            cond_socket.close()
                            return
                        if checksum != self.orch_dict['full_checksum']:
                            logging.info('CON HANDLER: Error in checksum name')
                            cond_socket.shutdown(socket.SHUT_RDWR)
                            cond_socket.close()
                            return
                    elif reply_msg == 'SEND':
                        filename = netutils.read_line(cond_socket)
                        checksum = netutils.read_line(cond_socket)
                        num_ips = netutils.read_line(cond_socket)
                        if filename != self.orch_dict['composition_name']:
                            logging.info('CON HANDLER: Error in filename')
                            cond_socket.shutdown(socket.SHUT_RDWR)
                            cond_socket.close()
                            return
                        if checksum != self.orch_dict['full_checksum']:
                            logging.info('CON HANDLER: Error in checksum name')
                            cond_socket.shutdown(socket.SHUT_RDWR)
                            cond_socket.close()
                            return
                        if int(num_ips) < 0 or int(
                                num_ips) > 1000000:  # I very much doubt we will have more than 1 million
                            logging.info('CON HANDLER: Error in num_ips')
                            cond_socket.shutdown(socket.SHUT_RDWR)
                            cond_socket.close()
                            return

                        for i in range(int(num_ips)):
                            ip_port = netutils.read_line(cond_socket)
                            ip_list.append(ip_port)
                            logging.info('CON HANDLER: Received ip: %s', ip_port)

                    else:
                        logging.info('Error in getting IPs from conductor')

                except socket.error as er:
                    logging.warning('CON HANDLER: Exception %s', er)
                finally:
                    try:
                        logging.info('CON HANDLER: trying to closing connection')
                        cond_socket.shutdown(socket.SHUT_RDWR)
                        cond_socket.close()
                    except socket.error as er:
                        logging.warning(er)
                    finally:
                        logging.info('CON HANDLER: Connection closed')

                message = {'msg': 'COND_IPS', 'ip_list': ip_list}
                self.out_queue.put(message)

            else:
                logging.info('CON HANDLER: Message is not understood')

    def _connection_listener(self, out_queue):
        logging.info('CON HANDLER: Starting listener')
        try:
            #server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', 10001))
            self.server_socket.listen(5)

            while True:
                logging.info('CON HANDLER: Trying to accept')
                (clientsocket, addr) = self.server_socket.accept()
                logging.info('Client connected at %s', addr)
                # Check socket send and recv addresses are not the same
                (ip, _) = clientsocket.getsockname()
                (ip2, _) = clientsocket.getpeername()
                logging.info('CON HANDLER: ip1 %s %s %s', ip, 'ip2', ip2)
                if ip == ip2:
                    logging.info('CON HANDLER: CON HANDLER trying to connect to self')
                    continue
                message = {'msg': 'NEWCON', 'sock': clientsocket}

                out_queue.put(message)
        except socket.error as er:
            logging.warning('CON HANDLER:%s', er)
        finally:
            logging.info('CON HANDLER: Exception in connection listener')
            return





