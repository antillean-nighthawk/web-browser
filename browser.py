import socket, sys, ssl, os
import tkinter, tkinter.font
from dotenv import load_dotenv
from emoji import UNICODE_EMOJI

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 20
ZOOM_RATIO = 1
FONTS = {}

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        attrs = [" " + k + "=\"" + v + "\"" for k, v  in self.attributes.items()]
        attr_str = ""
        for attr in attrs:
            attr_str += attr
        return "<" + self.tag + ">"

class Layout:
    def __init__(self, tree):
        self.display_list = []
        self.line = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP

        self.weight = "normal"
        self.style = "roman"
        self.size = 16 * ZOOM_RATIO
        self.abbr = False
        self.pre = False
        self.pre_font = tkinter.font.Font(size=self.size, weight=self.weight, 
                                          slant=self.style, family="Courier")

        self.recurse(tree)
        self.flush()

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "abbr":
            self.size -= 4
            self.weight = "bold"
            self.abbr = True
        elif tag == "pre":
            self.pre = True
        elif tag == "sub":
            self.size -= int(self.size/2)
        elif tag == "br":
            self.flush()

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "abbr":
            self.size += 4
            self.weight = "normal"
            self.abbr = False
        elif tag == "pre":
            self.pre = False
        elif tag == "sub":
            self.size *= 2
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > WIDTH:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

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
        self.nodes = None
    
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind('<Configure>', self.resize)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<MouseWheel>", self.mousewheel)
        self.window.bind("<plus>", self.zoom)
        self.window.bind("<minus>", self.zoom)

    def load(self, url):
        scheme, headers, body = request(url)
        if scheme == "view-source:http":
            body = transform(body)
        self.nodes = HTMLParser(body).parse()
        self.display_list = Layout(self.nodes).display_list
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
        self.display_list = Layout(self.nodes).display_list
        self.draw()

    def zoom(self, e):
        global ZOOM_RATIO, HSTEP, VSTEP, SCROLL_STEP
        if e.keysym == "plus" and ZOOM_RATIO <= 3: ZOOM_RATIO += 1
        elif e.keysym == "minus" and ZOOM_RATIO >= 1: ZOOM_RATIO -= 1
        else: ZOOM_RATIO = 1
        HSTEP, VSTEP, SCROLL_STEP = HSTEP*ZOOM_RATIO, VSTEP*ZOOM_RATIO, SCROLL_STEP*ZOOM_RATIO
        self.display_list = Layout(self.nodes).display_list
        self.draw()

class HTMLParser:
    SELF_CLOSING_TAGS = [ 
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]
    
    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        in_tag = False
        text = ""
        entity = ""
        in_body = False

        for c in self.body:
            if c == "<": # enter tag
                in_tag = True
                if text and in_body: 
                    self.add_text(text)
                text = ""
            elif c == ">": # exit tag
                if "body" in text:
                    in_body = True
                elif "/body" in text:
                    in_body == False
                in_tag = False
                self.add_tag(text)
                text = ""
            elif c == "&" or entity:
                entity += c
                if c == ";":
                    if entity == "&lt;":
                        entity = "<"
                    elif entity == "&gt;":
                        entity = ">"
                    elif entity == "&shy;":
                        entity = "-"
                    text += entity
                    entity = ""
            else:
                text += c
                if entity:
                    text += entity
                    entity = ""

        if not in_tag and text and in_body:
            self.add_text(text)

        return self.finish()
    
    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)

        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] \
              and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] \
              and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else: 
                break

    def finish(self):
        if len(self.unfinished) == 0:
                self.add_tag("html")

        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)

        return self.unfinished.pop()
    
    def get_attributes(self, text):
        parts = text.split()
        try:
            tag = parts[0].lower()
        except:
            tag = ''
        attributes = {}

        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.lower()] = value
            else:
                attributes[attrpair.lower()] = ""

        return tag, attributes

# textbook functions
def get_font(size, weight, slant):
    key = (size, weight, slant)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        FONTS[key] = font
    return FONTS[key]
  
def request(url):
    # url scheme parsing
    scheme, url = schema(url)

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

def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

# my own helper functions
def schema(url): # get schema
    if url.startswith("data:text/html"):
        return "data:text/html", url[15:]
    
    for schema in ["https", "http", "file", "view-source:http", "view-source:https"]:
        if url.startswith(schema):
            return url.split("://",1)   
        
    print("Unknown scheme {}".format(url.split("://",1)))
    sys.exit("Exiting...")

def transform(node): # view source
    text = node.text.replace("<","&lt;")
    text = node.text.replace(">","&gt;")
    return text

if __name__ == "__main__":
    load_dotenv()
    Browser().load("https://browser.engineering/html.html")
    # Browser().load(os.getenv("DEFAULT_SITE"))
    tkinter.mainloop()

    # if no url provided open default file
    # DEFAULT_SITE = os.getenv("DEFAULT_SITE")
    # if len(sys.argv) == 1:
    #     load(DEFAULT_SITE)
    # else:
    #     load(sys.argv[1])