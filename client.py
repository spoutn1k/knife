import curses
import os
import subprocess
from textwrap import wrap
from connexion import Connexion
import tempfile

URL='http://192.168.1.1/knife'
#URL='http://127.0.0.1:5000'

class ListWindow:
    def __init__(self, parent):
        self.parent = parent
        self.dishes = []
        self.window = None

    def win_init(self):
        """
        Compute sizes and create the window object accordingly.
        """
        full_height, full_width = self.parent.screen.getmaxyx()
        self.height = full_height - 3
        self.width = int(full_width/3)
        begin_x = 0
        begin_y = 2

        self.buffer_size = self.height - 2
        self.cursor_index = 0
        self.scroll_index = 0

        self.window = curses.newwin(self.height, self.width, begin_y, begin_x)
        self.draw()
        self.window.refresh()

    def draw(self):
        """
        Re-draw the windows contents from stored data
        """
        self.window.erase()
        self.window.addstr(0,0,"Dish list", curses.A_BOLD)
        self.window.addstr(1,0,"".join(["=" for _ in range(self.width)]), curses.A_BOLD)

        line = 2
        for index in range(min(self.buffer_size, len(self.dishes))):
            dish = self.dishes[self.scroll_index + index]
            self.window.addstr(line, 0, dish.get('name')[:self.width-1])
            line+=1

    @property
    def keys(self):
        """
        A dictionnary of the defined inputs.
        Keys are keycodes, and values are the associated methods.
        """
        return {curses.KEY_UP:      self.scroll_up,
                curses.KEY_DOWN:    self.scroll_down,
                ord('r'):           self.refresh_data,
                ord('\n'):          self.select,
                ord('\r'):          self.select,
                ord('n'):           self.parent.create,
                330:                self.delete,
                ord('q'):           self.terminate,
                curses.KEY_RIGHT:   self.switch}

    @property
    def cursor_y(self):
        """
        The position of the window's cursor on the screen, calculated from the internal cursor
        """
        return self.cursor_index + 2

    @property
    def selected(self):
        """
        Hash corresponding to the dish hovered on by the user
        """
        return self.dishes[self.scroll_index + self.cursor_index]

    def hide_cursor(self):
        """
        Hide the window's cursor
        """
        self.window.chgat(self.cursor_y, 0, curses.A_NORMAL)

    def show_cursor(self):
        """
        Show the window's cursor
        """
        if len(self.dishes):
            self.window.chgat(self.cursor_y, 0, curses.A_REVERSE | curses.A_BOLD)

    def _scroll(self, increment):
        """
        Move the internal cursor tracker by `increment`
        """
        scrolling = min(self.buffer_size, len(self.dishes))

        if not scrolling:
            return

        self.hide_cursor()
        new_index = self.cursor_index + increment

        # If the users goes oob up
        if new_index == -1:
            # If the list is maxed out
            if self.scroll_index == 0:
                self.scroll_index = max(len(self.dishes) - self.buffer_size, 0)
                self.cursor_index = min(self.buffer_size, len(self.dishes)) - 1
            else:
                self.scroll_index -= 1
            self.draw()
        elif new_index == self.buffer_size:
            if self.scroll_index + self.buffer_size == len(self.dishes):
                self.scroll_index = 0
                self.cursor_index = 0
            else:
                self.scroll_index += 1
            self.draw()
        else:
            self.cursor_index = (self.cursor_index + increment)%scrolling

        self.show_cursor()
        self.window.refresh()

    def scroll_up(self):
        """
        Move the cursor up
        """
        self._scroll(-1)

    def scroll_down(self):
        """
        Move the cursor down
        """
        self._scroll(1)

    def refresh_data(self):
        """
        Fetch dish list from the server then redraw and refresh the window.
        """
        self.dishes = self.parent.dish_list
        self.draw()
        self.window.refresh()

    def select(self):
        """
        Call the parent's show method with the hovered dish
        """
        self.parent.show(self.selected)

    def delete(self):
        """
        Call the parent's delete method with the hovered dish
        """
        self.parent.delete(self.selected)

    def terminate(self):
        """
        Yield input making sure the parent will quit too
        """
        curses.ungetch(ord('q'))
        self.yield_input()

    def switch(self):
        """
        Yield input and make sure the parent will call the other window next
        """
        curses.ungetch(curses.KEY_RIGHT)
        self.yield_input()

    def yield_input(self):
        """
        Method called when the window is unfocused
        """
        self.hide_cursor()
        self.window.refresh()
        self.focused = False

    def __call__(self):
        """
        Loop until a yield event is received
        """
        self.focused = True
        self.draw()
        self.show_cursor()
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
        """
        Compute sizes and create the window object accordingly.
        """
        full_height, full_width = self.parent.screen.getmaxyx()
        self.height = full_height - 3
        self.width = full_width - int(full_width/3)
        self.begin_x = int(full_width/3)
        self.begin_y = 2

        self.window = curses.newwin(self.height, self.width, self.begin_y, self.begin_x)

        self.draw()
        self.window.refresh()

    def draw(self, scroll_reset=True):
        """
        Re-draw the windows contents from stored data
        """
        cursory = 1
        data = self.parent._fetched_dish_data

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
        """
        A dictionnary of the defined inputs.
        Keys are keycodes, and values are the associated methods.
        """
        return {curses.KEY_UP:      self.scroll_up,
                curses.KEY_DOWN:    self.scroll_down,
                ord('r'):           self.refresh_data,
                ord('e'):           self.edit,
                ord('i'):           self.parent.set_ingredient,
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
        with tempfile.NamedTemporaryFile(mode="w+") as temp:
            original = self.parent._fetched_dish_data.get('directions', "")
            if original:
                temp.write(original)
                temp.seek(0, 0)
            FNULL = open(os.devnull, 'w')
            subprocess.run(["gnome-terminal", "--wait", "--", "vim", temp.name], stdout=None, stderr=FNULL)

            temp.seek(0, 0)
            data = temp.read()
        curses.flushinp()

        self.parent._fetched_dish_data['directions'] = data
        self.parent.save()
        self.draw()
        self.window.refresh()

    def save(self):
        status, dish, error = self.parent.save()

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
        self._fetched_dish_data = None

        curses.use_default_colors()
        curses.curs_set(0)
        self.refresh()
        self.window_list = ListWindow(self)
        self.window_list.win_init()
        self.window_list.refresh_data()
        self.window_detail = DetailWindow(self)
        self.window_detail.win_init()

    def draw(self):
        """
        Re-draw the windows contents from stored data
        """
        height, width = self.screen.getmaxyx()
        rpart = "Knife client v0.0"
        lpart = URL
        filler = "".join([' ' for _ in range(width - len(rpart) - len(lpart) - 4)])
        header = " {} {} {} ".format(rpart, filler, lpart)
        self.screen.addstr(0, 0, header, curses.A_REVERSE | curses.A_BOLD)

    def show(self, dish_listing):
        """
        Show a dish from its identifier in dish_listing
        """
        identifier = dish_listing.get('id')

        if identifier:
            self._fetched_dish_data = self.connexion.dish(identifier)

        self.window_detail.draw()
        self.window_detail.window.refresh()

    @property
    def dish_list(self):
        """
        Outputs a list of dishes, fetching it first from the server, then sorting it.
        Returns an empty list when the fetch was unsuccessful.
        """
        dishes, status, error = self.connexion.dish_list()

        if not status:
            self.prompt(error, wait_input=False)
            return []
        else:
            dishes.sort(key=lambda dish: dish.get('name').lower())
            return dishes

    def create(self):
        """
        Asks for a name to the user then launch a dish creation query.
        Prints an error if unsuccessful.
        """
        name = self.prompt('Name:')
        if name == '':
            return

        dish, status, error = self.connexion.create(name)

        if status:
            self._fetched_dish_data = dish
            self.window_list.refresh_data()

        else:
            self.prompt(error, wait_input=False)

    def delete(self, dish_data):
        """
        Delete a dish from its identifier in dish_data
        """
        if self.prompt("Delete {} ? yes/No".format(dish_data.get('name'))) != 'yes':
            return
        status, error = self.connexion.delete(dish_data.get('id'))
        if not status:
            self.prompt(error, wait_input=False)
        if status:
            self.window_list.refresh_data()

    def save(self):
        """
        Save the internal dish data to the database
        Delete first if an identifier is present
        """
        if self._fetched_dish_data.get('id'):
            self.connexion.delete(self._fetched_dish_data.get('id'))

        self.connexion.save(self._fetched_dish_data)
        self.window_list.refresh_data()

    def set_ingredient(self):
        """
        Set an ingredient in the database
        """
        name, quantity = self.prompt('Ingredient:'), self.prompt('Quantity:')
        if '' in [name, quantity]:
            return
        self.connexion.set_ingredient(self._fetched_dish_data, name, quantity)
        self.show(self._fetched_dish_data)

    @property
    def keys(self):
        """
        A dictionnary of the defined inputs.
        Keys are keycodes, and values are the associated methods.
        """
        return {ord('q'):           self.exit,
                ord('c'):           self.connect,
                curses.KEY_RIGHT:   self.window_detail,
                curses.KEY_LEFT:    self.window_list}

    def input(self):
        """
        Loop until a exit event is received
        """
        self.focused = True

        while self.focused:
            ch = self.screen.getch()
            method = self.keys.get(ch)

            if method:
                method()

    def exit(self):
        self.focused = False

    def connect(self):
        url = self.prompt("Server:")
        self.connexion = Connexion(url)

    def refresh(self):
        self.draw()
        self.screen.noutrefresh()
        curses.doupdate()

    def prompt(self, text, wait_input=True):
        height, width = self.screen.getmaxyx()
        self.screen.move(height-1, 0)
        self.screen.deleteln()
        self.screen.addstr(height-1, 0, "{} ".format(text), curses.A_BOLD)

        if not wait_input:
            return None

        curses.curs_set(1)
        user_input = input_edit(self.screen, width)
        curses.curs_set(0)
        self.screen.deleteln()

        return user_input

def input_edit(window, max_x):
    """
    Creates a text field of with max_x at the position of the cursor
    """
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
    """
    Uses `dish_data` to construct a list of strings 
    describing the dish, of at most `width` characters.
    """
    print_lines = []

    print_lines.append( (dish_data.get('name'), curses.A_BOLD) )
    print_lines.append( ("by {}".format(dish_data.get('author')), curses.A_NORMAL) )
    print_lines.append( (None,  curses.A_NORMAL) )
    print_lines.append( ("Ingredients", curses.A_BOLD) )
    print_lines += [("- {}, {}".format(ingredient['ingredient'], ingredient['quantity']),  curses.A_NORMAL) for ingredient in dish_data.get('ingredients')]
    print_lines.append( (None,  curses.A_NORMAL) )
    print_lines.append( ("Directions", curses.A_BOLD) )

    if dish_data.get('directions'):
        print_lines += [(segment, curses.A_NORMAL) for segment in dish_data.get('directions').split('\n')]

    formatted_text = []
    for text,attribute in print_lines:
        if not text:
            formatted_text.append(("", curses.A_NORMAL))
            continue
        for segment in wrap(text, width - 4):
            formatted_text.append((segment, attribute))

    return formatted_text

def main(stdscreen):
    interface = KnifeScreen(stdscreen, Connexion(URL))
    curses.ungetch(curses.KEY_LEFT)
    interface.input()

if __name__ == "__main__":
    curses.wrapper(main)
