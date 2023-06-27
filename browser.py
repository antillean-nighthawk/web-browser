import socket, sys, ssl, os
from dotenv import load_dotenv

def parse(url):
    if url.startswith("data:text/html"):
        return "data:text/html", url[15:]
    
    for schema in ["https", "http", "file"]:
        if url.startswith(schema):
            return url.split("://",1)   
        
    print("Unknown scheme {}".format(url.split("://",1)))
    sys.exit("Exiting...")
        
def request(url):
    # url scheme parsing
    scheme, url = parse(url)
    if scheme == "file": 
        with open(url[1:], "r+") as file:
            return '', file.read()
    elif scheme == "data:text/html":
        return '', url
    else: # http/https
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

def show(body):
    # print out body (not tags)
    in_angle = False
    in_body = False
    in_entity = False
    view_source = True
    tag = ""
    entity = ""

    for c in body:
        if c == "<": # enter tag
            in_angle = True
            tag = ""
        elif c == ">": # exit tag
            in_angle = False
            if tag == "body":
                in_body = True
            elif tag == "/body":
                in_body == False
        elif in_angle:
            view_source = False
            tag += c
        elif not in_angle:
            if c == "&": # enter entity
                in_entity = True
                entity += c
            elif in_entity: 
                entity += c
                if len(entity) == 4: # exit entity
                    if entity == "&lt;":
                        print("<", end="")
                    elif entity == "&gt;":
                        print(">", end="")
                    entity = ""
                    in_entity = False
            elif in_body or view_source:
                print(c, end="")

def transform(body):
    # view source
    lt = body.replace("<","&lt;")
    gt = lt.replace(">","&gt;")
    return gt

def load(url):
    headers, body = request(url)
    show(body)
    # show(transform(body))

if __name__ == "__main__":
    # if no url provided open default file
    
    load_dotenv()
    DEFAULT_SITE = os.getenv("DEFAULT_SITE")
    if len(sys.argv) == 1:
        load(DEFAULT_SITE)
    else:
        load(sys.argv[1])
    # load("https://example.com/")
    # load("https://browser.engineering/index.html")