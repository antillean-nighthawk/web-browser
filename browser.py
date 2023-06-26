import socket, sys, ssl, os, pprint
from dotenv import load_dotenv

def parse(url):
    if url.startswith("data:text/html"):
        return "data:text/html", url[15:]
    elif url.startswith("https"):
        return url.split("://",1)   
    elif url.startswith("http"):
        return url.split("://",1)
    elif url.startswith("file"):
        return url.split("://",1)
    else:
        print("Unknown scheme {}".format(url.split("://",1)))
        sys.exit("Exiting...")
        
def request(url):
    # url scheme parsing
    scheme, url = parse(url)
    if scheme == "file": 
        file(url)
    elif scheme == "data:text/html":
        return '', url
    host, path = url.split("/",1)
    path = "/" + path

    # define default or custom port
    port = 80 if scheme == "http" else 443
    if ":" in host:
        host, port = host.split(":",1)
        port = int(port)

    # create and connect to socket
    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )

    s.connect((host,port))

    # ssl encryption 
    if scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=host)
    
    # request + response
    s.send("GET {} HTTP/1.1\r\n".format(path).encode("utf8") +
        "Host: {}\r\n\r\n".format(host).encode("utf8") +
        "Connection: close".encode("utf8") +
        "User-Agent: python test browser :3".encode("utf8"))
    response = s.makefile("r", encoding="utf8", newline="\r\n")

    statusline = response.readline()
    version, status, explanation = statusline.split(" ",2)
    assert status == "200", "{}: {}".format(status, explanation)

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n": break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    # check for weird stuff
    assert "transfer-encoding" not in headers
    assert "content-encoding" not in headers

    body = response.read()
    s.close()

    return headers,body

# show local files
def file(url):
    with open(url, "r+") as file:
        print(file.read())
    sys.exit()

def show(body):
    # print out everything between '<' and '>'
    in_angle = False
    for c in body:
        if c == "<":
            in_angle = True
        elif c == ">":
            in_angle = False
        elif not in_angle:
            print(c, end="")

def load(url):
    headers, body = request(url)
    show(body)

if __name__ == "__main__":
    # if no url provided open default file
    load_dotenv()
    DEFAULT_SITE = os.getenv("DEFAULT_SITE")
    if len(sys.argv) == 1:
        load(DEFAULT_SITE)

    load(sys.argv[1])