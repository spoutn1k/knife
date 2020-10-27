from os import fork
from sys import argv
from time import sleep
from subprocess import Popen, DEVNULL

if __name__ == '__main__':
    pid = fork()

    if pid:
        sleep(2)
        exit(0)

    delay = int(argv[1])

    print("Running '%s' for %d seconds as a background process" %
          (" ".join(argv[2:]), delay))

    child = Popen(argv[2:], stdout=DEVNULL, stderr=DEVNULL)
    sleep(delay)
    child.kill()
