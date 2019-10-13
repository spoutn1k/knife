import curses
import json
from math import ceil
import requests

URL='http://192.168.1.1/knife'
#URL='http://127.0.0.1:5000'

class Connexion:
    def __init__(self, address):
        self.address = address

    @property
    def dish_list(self):
        return requests.get("{}/dishes/".format(URL)).json()['dishes']

    def dish(self, hashid):
        return requests.get("{}/dishes/{}".format(URL, hashid)).json()

class UI:
    def __init__(self, screen, connexion):
        self.screen = screen
        self.connexion = connexion
        self._dishes = None
        self._cursor = 0
        self._shown = None
        self._scroll_top = 0

        curses.use_default_colors()
        curses.curs_set(0)
        screen.addstr(0, 0, "Knife client v0.0")
        screen.addstr(0, curses.COLS - len(URL), URL)

        begin_x = 0
        begin_y = 2
        height = curses.LINES - 3
        width = int(curses.COLS/3)
        self.window_list = curses.newwin(height, width, begin_y, begin_x)
        self.window_detail = curses.newwin(height, curses.COLS - width, begin_y, begin_x + width)
    
    @property
    def dishes(self):
        return self._dishes

    @dishes.setter
    def dishes(self, dictionnary):
        dictionnary.sort(key=lambda dish: dish.get('name'))
        self._dishes = dictionnary

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, position):
        _, line = self.window_list.getmaxyx()
        if position == None:
            self.window_list.chgat(2 + self._cursor, 0, line, curses.A_NORMAL)
        else:
            self.window_list.chgat(2 + self._cursor, 0, line, curses.A_NORMAL)
            self._cursor = position%len(self.dishes)
            self.window_list.chgat(2 + self._cursor, 0, line, curses.A_REVERSE | curses.A_BOLD)

    @property
    def shown(self):
        return self._shown.get('id') if self._shown else None

    @shown.setter
    def shown(self, index):
        if index != None:
            if self.shown and self.shown.get('id') == self.dishes[index].get('id'):
                return
            data = self.connexion.dish(self.dishes[index].get('id'))
            self._shown = data
            self.show_dish(dish_data=data)
        else:
            self._shown = None

    @property
    def scroll(self):
        return self._scroll_top

    @scroll.setter
    def scroll(self, lineno):
        self._scroll_top = lineno if lineno > 0 else 0

    def input(self):
        exited = False
        while not exited:
            key = self.screen.getch()

            if key == ord('q'):
                exited = True
            elif key == ord('r'):
                self.show_list(self.connexion.dish_list)
            elif key == curses.KEY_UP:
                self.cursor = self.cursor - 1
            elif key == curses.KEY_DOWN:
                self.cursor = self.cursor + 1
            elif key == ord('j'):
                self.scroll = self.scroll + 1
                self.show_dish()
            elif key == ord('k'):
                self.scroll = self.scroll - 1
                self.show_dish()
            elif key == curses.KEY_RIGHT:
                self.cursor = None
            elif key == curses.KEY_LEFT:
                self.cursor = self.cursor
            elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                self.shown = self.cursor
            else:
                None

            self.refresh()

    def refresh(self):
        self.screen.noutrefresh()
        self.window_list.noutrefresh()
        self.window_detail.noutrefresh()
        curses.doupdate()

    def show_list(self, dish_list):
        self.dishes = dish_list
        height, width = self.window_list.getmaxyx()

        self.window_list.erase()
        self.window_list.addstr(0,0,"Dish list", curses.A_BOLD)
        self.window_list.addstr(1,0,"".join(["─" for _ in range(width)]), curses.A_BOLD)

        line = 2
        for dish in self.dishes:
            self.window_list.addstr(line, 0, dish.get('name')[:width])
            line+=1

    def show_dish(self, dish_data=None):
        if not dish_data:
            dish_data = self._shown
        height, width = self.window_detail.getmaxyx()
        cursory = 1

        self.window_detail.erase()
        self.window_detail.border()

        formatted_text = format_dish(dish_data, width)

        if height - 2 + self.scroll > len(formatted_text):
            self.scroll = len(formatted_text) - height + 2

        for element in formatted_text[self.scroll:self.scroll+height-2]:
            self.window_detail.addstr(cursory, 2, *element)
            cursory += 1

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
    interface = UI(stdscreen, Connexion(URL))
    interface.refresh()
    interface.input()

curses.wrapper(main)
