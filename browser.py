import socket, sys, ssl, os
import tkinter
from dotenv import load_dotenv
from emoji import UNICODE_EMOJI

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 20

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind('<Configure>', self.resize)
        self.scroll = 0
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<MouseWheel>", self.mousewheel)

    def load(self, url):
        scheme, headers, body = request(url)
        if scheme == "view-source:http":
            self.text = lex(transform(body))
        else:
            self.text = lex(body)
        self.display_list = layout(self.text)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            if c in UNICODE_EMOJI['en']:
                img_path = "{}{}.gif".format(os.getenv("EMOJI_PATH"), '{:X}'.format(ord(c)))
                self.img = tkinter.PhotoImage(file=img_path)
                self.canvas.create_image(x, y - self.scroll, image=self.img)
            else:
                self.canvas.create_text(x, y - self.scroll, text=c)

    def scrolldown(self, e):
        self.scroll += SCROLL_STEP
        self.draw()

    def scrollup(self, e):
        if self.scroll - SCROLL_STEP > 0:
            self.scroll -= SCROLL_STEP
        else:
            self.scroll = 0
        self.draw()

    def mousewheel(self, e):
        if self.scroll + -1*(e.delta/120)*SCROLL_STEP > 0:
            self.scroll += -1*(e.delta/120)*SCROLL_STEP
        else: 
            self.scroll = 0
        self.draw()

    def resize(self, e):
        global WIDTH, HEIGHT
        WIDTH, HEIGHT = e.width, e.height
        self.canvas.config(width=WIDTH, height=HEIGHT)
        self.display_list = layout(self.text)
        self.draw()
        
def layout(text):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        display_list.append((cursor_x, cursor_y, c))

        if c == '\n':
            cursor_y += (VSTEP + 5)
            cursor_x = 0

        cursor_x += HSTEP
        if cursor_x >= WIDTH - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP

    return display_list

# textbook functions        
def request(url):
    # url scheme parsing
    scheme, url = parse(url)

    if scheme == "file": 
        with open(url[1:], 'r+', encoding="utf8") as file:
            return scheme, '', file.read()
    elif scheme == "data:text/html":
        return scheme, '', url
    
    host, path = url.split("/",1)
    path = "/" + path

    # define default or custom port
    port = 443 if "https" in scheme else 80
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
    # assert status == "200", "{}: {}".format(status, explanation)

    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n": break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    # redirect checking
    if status[0] == '3': # 300 range status code
        try:
            for i in range(3):
                if headers["location"][0] == '/':
                    scheme, headers, body = request("{}{}".format(host, headers["location"]))
                else:
                    scheme, headers, body = request(headers["location"])
                return scheme, headers, body
        except:
            sys.exit("Too many redirects, aborted")

    # check for weird stuff
    # assert "transfer-encoding" not in headers
    # assert "content-encoding" not in headers

    body = response.read()
    s.close()

    return scheme, headers, body

def lex(body):
    # print out body (not tags)
    in_angle = False
    in_body = False
    in_entity = False
    view_source = True
    tag = ""
    entity = ""
    text = ""

    for c in body:
        if c == "<": # enter tag
            in_angle = True
            tag = ""
        elif c == ">": # exit tag
            in_angle = False
            if "body" in tag:
                in_body = True
            elif "/body" in tag:
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
                        text += '<'
                    elif entity == "&gt;":
                        text += '>'
                    entity = ""
                    in_entity = False
            elif in_body or view_source:
                text += str(c)

    return text

# my own helper functions
def parse(url):
    if url.startswith("data:text/html"):
        return "data:text/html", url[15:]
    
    for schema in ["https", "http", "file", "view-source:http", "view-source:https"]:
        if url.startswith(schema):
            return url.split("://",1)   
        
    print("Unknown scheme {}".format(url.split("://",1)))
    sys.exit("Exiting...")

def transform(body):
    # view source
    lt = body.replace("<","&lt;")
    gt = lt.replace(">","&gt;")
    return gt

if __name__ == "__main__":
    load_dotenv()
    
    # journey to the west !
    Browser().load("https://browser.engineering/examples/xiyouji.html")
    #Browser().load(os.getenv("DEFAULT_SITE"))
    tkinter.mainloop()

    # if no url provided open default file
    # DEFAULT_SITE = os.getenv("DEFAULT_SITE")
    # if len(sys.argv) == 1:
    #     load(DEFAULT_SITE)
    # else:
    #     load(sys.argv[1])