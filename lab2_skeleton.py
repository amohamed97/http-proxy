# Don't forget to change this file's name before submission.
import sys
import os
import enum
import socket
import select

cache = {}

class HttpRequestInfo(object):
    """
    Represents a HTTP request information

    Since you'll need to standardize all requests you get
    as specified by the document, after you parse the
    request from the TCP packet put the information you
    get in this object.

    To send the request to the remote server, call to_http_string
    on this object, convert that string to bytes then send it in
    the socket.

    client_address_info: address of the client;
    the client of the proxy, which sent the HTTP request.

    requested_host: the requested website, the remote website
    we want to visit.

    requested_port: port of the webserver we want to visit.

    requested_path: path of the requested resource, without
    including the website name.

    NOTE: you need to implement to_http_string() for this class.
    """

    def __init__(self, client_info, method: str, requested_host: str,
                 requested_port: int,
                 requested_path: str,
                 headers: list):
        self.method = method
        self.client_address_info = client_info
        self.requested_host = requested_host
        self.requested_port = requested_port
        self.requested_path = requested_path
        # Headers will be represented as a list of tuples
        # for example ("Host", "www.google.com")
        # if you get a header as:
        # "Host: www.google.com:80"
        # convert it to ("Host", "www.google.com") note that the
        # port is removed (because it goes into the request_port variable)
        self.headers = headers

    def to_http_string(self):
        """
        Convert the HTTP request/response
        to a valid HTTP string.
        As the protocol specifies:

        [request_line]\r\n
        [header]\r\n
        [headers..]\r\n
        \r\n

        You still need to convert this string
        to byte array before sending it to the socket,
        keeping it as a string in this stage is to ease
        debugging and testing.
        """
        return "\r\n".join([f'{self.method} {self.requested_path} HTTP/1.0', "\r\n".join([f'{name}: {value}' for name, value in self.headers]),"\r\n"])
        # print("*" * 50)
        # print("[to_http_string] Implement me!")
        # print("*" * 50)

    def to_byte_array(self, http_string):
        """
        Converts an HTTP string to a byte array.
        """
        return bytes(http_string, "UTF-8")

    def display(self):
        print(f"Client:", self.client_address_info)
        print(f"Method:", self.method)
        print(f"Host:", self.requested_host)
        print(f"Port:", self.requested_port)
        stringified = [": ".join([k, v]) for (k, v) in self.headers]
        print("Headers:\n", "\n".join(stringified))
    
    def get_key(self):
        return self.requested_host+self.requested_path+":"+str(self.requested_port)


class HttpErrorResponse(object):
    """
    Represents a proxy-error-response.
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def to_http_string(self):
        """ Same as above """
        return f"{self.code} {self.message}"

    def to_byte_array(self, http_string):
        """
        Converts an HTTP string to a byte array.
        """
        return bytes(http_string, "UTF-8")

    def display(self):
        print(self.to_http_string())


class HttpRequestState(enum.Enum):
    """
    The values here have nothing to do with
    response values i.e. 400, 502, ..etc.

    Leave this as is, feel free to add yours.
    """
    INVALID_INPUT = 0
    NOT_SUPPORTED = 1
    GOOD = 2
    PLACEHOLDER = -1


def entry_point(proxy_port_number):
    """
    Entry point, start your code here.

    Please don't delete this function,
    but feel free to modify the code
    inside it.
    """

    server = setup_sockets(proxy_port_number)
    serve_clients(server)
    # print("*" * 50)
    # print("[entry_point] Implement me!")
    # print("*" * 50)
    return None


def setup_sockets(proxy_port_number):
    """
    Socket logic MUST NOT be written in the any
    class. Classes know nothing about the sockets.

    But feel free to add your own classes/functions.

    Feel free to delete this function.
    """
    print("Starting HTTP proxy on port:", proxy_port_number)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setblocking(0)
    s.bind((socket.gethostname(), proxy_port_number))
    # when calling socket.listen() pass a number
    # that's larger than 10 to avoid rejecting
    # connections automatically.
    # print("*" * 50)
    # print("[setup_sockets] Implement me!")
    # print("*" * 50)
    return s

def serve_clients(server):
    server.listen(15)
    inputs = [server]
    outputs = []
    # For tracking every client request in case the request isn't completely recieved in a single 'recv'
    client_requests = {}
    # For tracking every response from the remote host in case the response isn't completely recieved in a single 'recv'
    remote_responses = {}
    # A set for distinguishing clients from remote_hosts in readable sockets
    clients = set()
    # ( remote_socket: client_socket ) used to know which client should recieve the response that came from the remote host
    remote_to_client = {}
    # ( client_socket: key ) used to cache the response when the client is successfully served
    temporary_keys = {}
    while True:
        print("Waiting for any event...")
        readable, writable,_ = select.select(inputs, outputs, inputs)
        for s in readable:
            # If this readable is the server then it's ready for accepting a new connection
            if s is server:
                client_socket, client_address = s.accept()
                print(f"Connection with {client_address} established!")
                client_socket.setblocking(0)
                inputs.append(client_socket)
                clients.add(client_socket)
                client_requests[client_socket] = ""
            # If it's a client then recieve the next packet, if the request is complete, send it to the remote host
            elif s in clients:
                data = s.recv(1024)
                if data:
                    print(f"Recieved a packet {data} from {s.getpeername()}")
                    client_requests[s] += data.decode("utf-8")
                    # If request is completely recieved
                    if client_requests[s][-4:] == "\r\n\r\n":
                        request = client_requests[s]
                        parsed_request = http_request_pipeline(s.getpeername(), request)
                        validity = check_http_request_validity(parsed_request)
                        if validity == HttpRequestState.GOOD:
                            key = parsed_request.get_key()
                            if key in cache:
                                s.send(bytes(cache[key], "utf-8"))
                                end_connection(s, inputs)
                            else:
                                remote_host = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                send_request_to_remote(parsed_request, remote_host)
                                remote_responses[remote_host] = ""
                                inputs.append(remote_host)
                                remote_to_client[remote_host] = s
                                temporary_keys[s] = key
                        elif validity == HttpRequestState.INVALID_INPUT:
                            s.send(bytes(HttpErrorResponse(400, "Bad Request").to_http_string(), "utf-8"))
                            end_connection(s, inputs)
                        elif validity == HttpRequestState.NOT_SUPPORTED:
                            s.send(bytes(HttpErrorResponse(501, "Not Implemented").to_http_string(), "utf-8"))
                            end_connection(s, inputs)
                # If data is empty then the client has disconnected
                else:
                    print(f"Closing {s.getpeername()} after reading no data")
                    # Stop listening for input on the connection
                    end_connection(s, inputs)
                    # Remove message queue
                    del client_requests[s]
            else:
                response = s.recv(2048)
                if response:
                    remote_responses[s] += response.decode("utf-8")
                else:
                    full_response = remote_responses[s]
                    associated_client = remote_to_client[s]
                    associated_client.send(bytes(full_response, "utf-8"))
                    cache[temporary_keys[associated_client]] = full_response
                    end_connection(s, inputs)
                    end_connection(associated_client, inputs)
                    del remote_responses[s]
                    del remote_to_client[s]


def end_connection(s, inputs):
    inputs.remove(s)
    s.close()

def send_request_to_remote(parsed_request, remote_host):
    remote_host.connect((parsed_request.requested_host, parsed_request.requested_port))
    remote_host.setblocking(0)
    remote_host.sendall(bytes(parsed_request.to_http_string(), "utf-8"))

def http_request_pipeline(source_addr, http_raw_data):
    """
    HTTP request processing pipeline.

    - Parses the given HTTP request
    - Validates it
    - Returns a sanitized HttpRequestInfo or HttpErrorResponse
        based on request validity.

    returns:
     HttpRequestInfo if the request was parsed correctly.
     HttpErrorResponse if the request was invalid.

    Please don't remove this function, but feel
    free to change its content
    """
    # Parse HTTP request
    parsed = parse_http_request(source_addr, http_raw_data)

    # Validate, sanitize, return Http object.
    # print("*" * 50)
    # print("[http_request_pipeline] Implement me!")
    # print("*" * 50)
    return parsed


def parse_http_request(source_addr, http_raw_data) -> HttpRequestInfo:
    """
    This function parses an HTTP request into an HttpRequestInfo
    object.

    it does NOT validate the HTTP request.
    """
    lines = http_raw_data.split('\r\n')
    # Filters empty strings
    lines = list(filter(lambda line: line, lines))
    request_line = lines[0]
    if len(lines) > 1:
        headers = lines[1:]
        headers = [(name[:-1], value)
                   for name, value in [header.split() for header in headers]]
        host_port = int(headers[0][1].split(":")[1]) if len(
            headers[0][1].split(":")) > 1 else 80
        host_address = headers[0][1]
    else:
        headers = []
        host_address = ""
        host_port = -1
    request_line_parts = request_line.split()
    # print("*" * 50)
    # print("[parse_http_request] Implement me!")
    # print("*" * 50)
    # Replace this line with the correct values.
    ret = HttpRequestInfo(
        source_addr, request_line_parts[0], host_address, host_port, request_line_parts[1], headers)
    return sanitize_http_request(ret)


def check_http_request_validity(http_request_info: HttpRequestInfo) -> HttpRequestState:
    """
    Checks if an HTTP response is valid

    returns:
    One of values in HttpRequestState
    """
    valid_verbs = ("GET", "HEAD", "POST", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", "PATCH")
    # print("*" * 50)
    # print("[check_http_request_validity] Implement me!")
    # print("*" * 50)
    # return HttpRequestState.GOOD (for example)
    if http_request_info.requested_host == "":
        return HttpRequestState.INVALID_INPUT
    if http_request_info.method not in valid_verbs:
        return HttpRequestState.INVALID_INPUT
    elif http_request_info.method != "GET":
        return HttpRequestState.NOT_SUPPORTED
    else:
        return HttpRequestState.GOOD
    return HttpRequestState.PLACEHOLDER


def sanitize_http_request(request_info: HttpRequestInfo) -> HttpRequestInfo:
    """
    Puts an HTTP request on the sanitized (standard form)

    returns:
    A modified object of the HttpRequestInfo with
    sanitized fields

    for example, expand a URL to relative path + Host header.
    """
    if request_info.requested_host == "":
        request_info.requested_path = request_info.requested_path.replace(
            "http://", "")
        if not request_info.requested_path.startswith("/"):
            path_parts = request_info.requested_path.split("/")
            hostname_parts = path_parts[0].split(":")
            request_info.requested_port = int(
                hostname_parts[1]) if len(hostname_parts) > 1 else 80
            request_info.requested_host = hostname_parts[0]
            request_info.requested_path = "/" + "/".join(path_parts[1:])
            request_info.headers.append(("Host", request_info.requested_host))
    # print("*" * 50)
    # print("[sanitize_http_request] Implement me!")
    # print("*" * 50)
    return request_info
    # ret = HttpRequestInfo(None, None, None, None, None, None)
    # return ret

#######################################
# Leave the code below as is.
#######################################


def get_arg(param_index, default=None):
    """
        Gets a command line argument by index (note: index starts from 1)
        If the argument is not supplies, it tries to use a default value.

        If a default value isn't supplied, an error message is printed
        and terminates the program.
    """
    try:
        return sys.argv[param_index]
    except IndexError as e:
        if default:
            return default
        else:
            print(e)
            print(
                f"[FATAL] The comand-line argument #[{param_index}] is missing")
            exit(-1)    # Program execution failed.


def check_file_name():
    """
    Checks if this file has a valid name for *submission*

    leave this function and as and don't use it. it's just
    to notify you if you're submitting a file with a correct
    name.
    """
    script_name = os.path.basename(__file__)
    import re
    matches = re.findall(r"(\d{4}_){2}lab2\.py", script_name)
    if not matches:
        print(f"[WARN] File name is invalid [{script_name}]")


def main():
    """
    Please leave the code in this function as is.

    To add code that uses sockets, feel free to add functions
    above main and outside the classes.
    """
    print("\n\n")
    print("*" * 50)
    print(f"[LOG] Printing command line arguments [{', '.join(sys.argv)}]")
    check_file_name()
    print("*" * 50)

    # This argument is optional, defaults to 18888
    proxy_port_number = get_arg(1, 18888)
    entry_point(proxy_port_number)


if __name__ == "__main__":
    main()
