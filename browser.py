import socket, sys, ssl, os
import tkinter, tkinter.font
from dotenv import load_dotenv
from emoji import UNICODE_EMOJI

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 20
FONTS = {}

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

class Layout:
    def __init__(self, tokens, size=16):
        self.tokens = tokens
        self.display_list = []
        self.line = []

        self.cursor_x = HSTEP
        self.cursor_y = VSTEP

        self.weight = "normal"
        self.style = "roman"
        self.size = size

        for tok in tokens:
            self.token(tok)
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            self.text(tok)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP

    def text(self, tok):
        font = get_font(self.size, self.weight, self.style)
        for word in tok.text.split(): # assume space-seperated language
            w = font.measure(word)
            if self.cursor_x + w > WIDTH - HSTEP:
                self.flush()
            self.line.append((self.cursor_x, word, font))
            self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        
        self.cursor_x = HSTEP
        self.line = []

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

class Browser:
    def __init__(self):
        self.scroll = 0
        self.display_list = []
        self.tokens = None
    
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind('<Configure>', self.resize)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<MouseWheel>", self.mousewheel)

    def load(self, url):
        scheme, headers, body = request(url)
        if scheme == "view-source:http":
            self.tokens = lex(transform(body))
        else:
            self.tokens = lex(body)
        self.display_list = Layout(self.tokens).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + font.metrics("linespace") < self.scroll: continue

            if word in UNICODE_EMOJI['en']:
                img_path = "{}{}.gif".format(os.getenv("EMOJI_PATH"), '{:X}'.format(ord(word[0])))
                self.img = tkinter.PhotoImage(file=img_path)
                self.canvas.create_image(x, y - self.scroll, image=self.img, anchor='nw')
            else:
                self.canvas.create_text(x, y - self.scroll, text=word, font=font, anchor='nw')

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
        self.display_list = Layout(self.tokens).display_list
        self.draw()

# textbook functions
def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]
  
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
    in_tag = False
    text = ""
    out = []
    in_body = False

    for c in body:
        if c == "<": # enter tag
            in_tag = True
            if text and in_body: out.append(Text(text))
            text = ""
        elif c == ">": # exit tag
            if "body" in text:
                in_body = True
            elif "/body" in text:
                in_body == False
            
            in_tag = False
            out.append(Tag(text))
            text = ""
        else:
            text += c

    if not in_tag and text and in_body:
        out.append(Text(text))

    return out

# my own helper functions
def parse(url): # get schema
    if url.startswith("data:text/html"):
        return "data:text/html", url[15:]
    
    for schema in ["https", "http", "file", "view-source:http", "view-source:https"]:
        if url.startswith(schema):
            return url.split("://",1)   
        
    print("Unknown scheme {}".format(url.split("://",1)))
    sys.exit("Exiting...")

def transform(token): # view source
    text = token.text.replace("<","&lt;")
    text = token.text.replace(">","&gt;")
    return text

if __name__ == "__main__":
    load_dotenv()
    Browser().load("https://www.gutenberg.org/cache/epub/1567/pg1567-images.html")
    # Browser().load(os.getenv("DEFAULT_SITE"))
    tkinter.mainloop()

    # if no url provided open default file
    # DEFAULT_SITE = os.getenv("DEFAULT_SITE")
    # if len(sys.argv) == 1:
    #     load(DEFAULT_SITE)
    # else:
    #     load(sys.argv[1])