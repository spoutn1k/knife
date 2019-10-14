import curses
from editor import Editor
import json
import requests

URL='http://192.168.1.1/knife'
#URL='http://127.0.0.1:5000'

ERROR_DISH_EXISTS = "Dish already exists"

class Connexion:
    def __init__(self, address):
        self.address = address

    @property
    def dish_list(self):
        return requests.get("{}/dishes/".format(URL)).json()['dishes']

    def dish(self, hashid):
        return requests.get("{}/dishes/{}".format(URL, hashid)).json()

    def save(self, dish_data):
        res = requests.post("{}/dishes/import".format(URL), data={'json': json.dumps(dish_data)})
        if res.ok:
            return res.json().get('accept'), res.json().get('error')
        return False, res.status_code

    def delete(self, hashid):
        return requests.get("{}/dishes/{}/delete".format(URL, hashid)).json().get('accept')

class ListWindow:
    def __init__(self, parent):
        self.parent = parent
        self.dishes = []
        self.window = None

    def win_init(self):
        full_height, full_width = self.parent.screen.getmaxyx()
        self.height = full_height - 1
        self.width = int(full_width/3)
        begin_x = 0
        begin_y = 2

        self.buffer_size = self.height - 3
        self.cursor_index = 0

        self.window = curses.newwin(self.height, self.width, begin_y, begin_x)
        self.draw()
        self.window.refresh()

    def draw(self):
        self.window.erase()
        self.window.addstr(0,0,"Dish list", curses.A_BOLD)
        self.window.addstr(1,0,"".join(["=" for _ in range(self.width)]), curses.A_BOLD)

        line = 2
        for dish in self.dishes:
            self.window.addstr(line, 0, dish.get('name')[:self.width])
            line+=1

        if len(self.dishes):
            self.show_cursor()

    @property
    def keys(self):
        return {curses.KEY_UP:      self.scroll_up,
                curses.KEY_DOWN:    self.scroll_down,
                ord('r'):           self.refresh_data,
                ord('\n'):          self.select,
                ord('\r'):          self.select,
                ord('q'):           self.terminate,
                curses.KEY_RIGHT:   self.switch}

    @property
    def cursor_y(self):
        return self.cursor_index + 2

    @property
    def selected(self):
        return self.dishes[self.cursor_index]

    def hide_cursor(self):
        self.window.chgat(self.cursor_y, 0, curses.A_NORMAL)

    def show_cursor(self):
        self.window.chgat(self.cursor_y, 0, curses.A_REVERSE | curses.A_BOLD)

    def _scroll(self, increment):
        # TODO Scroll the list along with the cursor
        scrolling = min(self.buffer_size, len(self.dishes))
        if not scrolling:
            return
        self.hide_cursor()
        self.cursor_index = (self.cursor_index + increment)%scrolling
        self.show_cursor()
        self.window.refresh()

    def scroll_up(self):
        self._scroll(-1)

    def scroll_down(self):
        self._scroll(1)

    def refresh_data(self):
        self.dishes = self.parent.connexion.dish_list
        self.draw()
        self.window.refresh()

    def select(self):
        self.parent.show(self.selected)
    
    def terminate(self):
        curses.ungetch(ord('q'))
        self.yield_input()

    def switch(self):
        curses.ungetch(curses.KEY_RIGHT)
        self.yield_input()

    def yield_input(self):
        self.hide_cursor()
        self.window.refresh()
        self.focused = False

    def __call__(self):
        self.focused = True
        self.draw()
        self.window.refresh()

        while self.focused:
            ch = self.parent.screen.getch()
            method = self.keys.get(ch)

            if method:
                method()

class DetailWindow:
    def __init__(self, parent):
        self.parent = parent
        self.lines = []
        self.scroll = 0
        self.window = None

    def win_init(self):
        full_height, full_width = self.parent.screen.getmaxyx()
        self.height = full_height - 3
        self.width = full_width - int(full_width/3)
        self.begin_x = int(full_width/3)
        self.begin_y = 2

        self.window = curses.newwin(self.height, self.width, self.begin_y, self.begin_x)

        self.draw()
        self.window.refresh()

    def draw(self, data=None, scroll_reset=True):
        cursory = 1

        self.window.erase()
        self.window.border()

        if scroll_reset:
            self.scroll = 0

        if data:
            self.lines = format_dish(data, self.width) if data else []

        for element in self.lines[self.scroll:self.scroll+self.height-2]:
            self.window.addstr(cursory, 2, *element)
            cursory += 1

    @property
    def keys(self):
        return {curses.KEY_UP:      self.scroll_up,
                curses.KEY_DOWN:    self.scroll_down,
                ord('r'):           self.refresh_data,
                ord('e'):           self.edit,
                ord('q'):           self.terminate,
                curses.KEY_LEFT:    self.switch}

    def scroll_up(self):
        if self.scroll > 0:
            self.scroll -= 1
        self.draw(scroll_reset = False)
        self.window.refresh()

    def scroll_down(self):
        max_scroll = len(self.lines) - (self.height - 2)
        if self.scroll < max_scroll:
            self.scroll += 1
        self.draw(scroll_reset = False)
        self.window.refresh()

    def refresh_data(self):
        None

    def edit(self):
        Editor(self.parent.screen, win_location=(self.begin_y, self.begin_x), win_size=(10, self.width))()
        self.draw()
        self.window.refresh()

    def terminate(self):
        curses.ungetch(ord('q'))
        self.yield_input()

    def switch(self):
        curses.ungetch(curses.KEY_LEFT)
        self.yield_input()

    def yield_input(self):
        self.focused = False

    def __call__(self):
        self.focused = True
        self.draw()
        self.window.refresh()

        while self.focused:
            ch = self.parent.screen.getch()
            method = self.keys.get(ch)

            if method:
                method()

class KnifeScreen:
    def __init__(self, screen, connexion):
        self.screen = screen
        self.connexion = connexion

        curses.use_default_colors()
        curses.curs_set(0)

        self.refresh()
        self.window_list = ListWindow(self)
        self.window_list.win_init()
        self.window_detail = DetailWindow(self)
        self.window_detail.win_init()

    def draw(self):
        height, width = self.screen.getmaxyx()
        rpart = "Knife client v0.0"
        lpart = URL
        filler = "".join([' ' for _ in range(width - len(rpart) - len(lpart) - 4)])
        header = " {} {} {} ".format(rpart, filler, lpart)
        self.screen.addstr(0, 0, header, curses.A_REVERSE | curses.A_BOLD)

    def show(self, dish_listing):
        identifier = dish_listing.get('id')

        if identifier:
            self._fetched_dish_data = self.connexion.dish(identifier)

        self.window_detail.draw(self._fetched_dish_data)
        self.window_detail.window.refresh()

    def keys(self):
        return {ord('q'):           self.exit,
                curses.KEY_RIGHT:   self.hide_cursor,
                curses.KEY_LEFT:    self.window_list(),
                330:                self.delete}

    def input(self):
        selected = {}
        exited = False
        while not exited:
            key = self.screen.getch()

            if key == ord('q'):
                exited = True
            elif key == curses.KEY_RIGHT:
                self.window_detail()
            elif key == curses.KEY_LEFT:
                self.window_list()
            elif key == 330:
                query = self.prompt("Delete {} ? [yes/No]".format(self._shown.get('name')))
                if query == 'yes':
                    res = self.connexion.delete(self.shown)

    def refresh(self):
        self.draw()
        self.screen.noutrefresh()
        curses.doupdate()

    def edit_dish(self, dish_build):
        self.show_dish(dish_data=dish_build)
        self.refresh()

        exited = False
        while not exited:
            key = self.screen.getch()

            if key == ord('q'):
                exited = True
            elif key == ord('n'):
                name = self.prompt('Name:')
                if name != '':
                    dish_build['name'] = name
            elif key == ord('i'):
                ingredient = self.prompt('Ingredient:')
                quantity = self.prompt('Quantity:')
                if ingredient != '' and quantity != '':
                    dish_build['ingredients'].append({'ingredient': ingredient, 'quantity': quantity})
            elif key == ord('e'):
                line = self.prompt('Instruction:')
                if line != '':
                    dish_build['directions'] += "{}\n".format(line)
            elif key == ord('s'):
                status, error = self.connexion.save(dish_build)
                if status:
                    self.prompt("Dish saved successfully")
                    exited = True
                else:
                    if error == ERROR_DISH_EXISTS:
                        if self.prompt("{}. Overwrite ? [yes/No]".format(error)) == 'yes':
                            self.connexion.delete(dish_build['_id'])
                            self.connexion.save(dish_build)
                            exited = True
                    else:
                        self.prompt("There was an error saving the dish: {}".format(error))
            self.show_dish(dish_data=dish_build)
            self.refresh()

    def prompt(self, text):
        height, width = self.screen.getmaxyx()
        self.screen.addstr(height-1, 0, "{} ".format(text), curses.A_BOLD)

        curses.curs_set(1)
        user_input = input_edit(self.screen, width)
        curses.curs_set(0)
        self.screen.deleteln()

        return user_input

def input_edit(window, max_x):
    exited = False
    orig_y, orig_x = window.getyx()
    y, x = orig_y, orig_x
    string = []

    while not exited:
        key = window.get_wch()

        if key in ['\n']:
            exited = True

        elif key in ['\x7f']:
            if x > orig_x:
                window.delch(y, x-1)
                if len(string) > (max_x - orig_x - 1):
                    char = string[::-1][max_x - orig_x - 1]
                    # insch is broken when trying to input a special character.
                    # This workaround allows the app not to crash by writing X instead
                    try:
                        window.insch(orig_y, orig_x, char)
                    except:
                        window.insch(orig_y, orig_x, 'X')
                    window.move(y, x)
                else:
                    x -= 1
                string.pop()
            elif x == orig_x:
                return ""

        else:
            if x == max_x-1:
                window.delch(y, orig_x)
                window.move(y, x-1)
            else:
                x += 1
            window.addch(key)
            string.append(key)

    return ''.join(string)

def format_dish(dish_data, width):
    print_lines = []

    print_lines.append( (dish_data.get('name'), curses.A_BOLD) )
    print_lines.append( ("by {}".format(dish_data.get('author')), curses.A_NORMAL) )
    print_lines.append( ("",  curses.A_NORMAL) )
    print_lines.append( ("Ingredients", curses.A_BOLD) )
    print_lines += [("- {}, {}".format(ingredient['ingredient'], ingredient['quantity']),  curses.A_NORMAL) for ingredient in dish_data.get('ingredients')]
    print_lines.append( ("",  curses.A_NORMAL) )
    print_lines.append( ("Directions", curses.A_BOLD) )

    if dish_data.get('directions'):
        print_lines += [(segment, curses.A_NORMAL) for segment in dish_data.get('directions').split('\n')]

    formatted_text = []
    for text,attribute in print_lines:
        for segment in cut(text, width - 4):
            formatted_text.append((segment, attribute))

    return formatted_text

def cut(string, width):
    if len(string) < width:
        return [string]
    space_index = string[width - 8:width][::-1].find(' ')
    if space_index == -1:
        space_index = 0
    return [string[:width-space_index]] + cut(string[width-space_index:], width)

def main(stdscreen):
    interface = KnifeScreen(stdscreen, Connexion(URL))
    interface.input()

curses.wrapper(main)
