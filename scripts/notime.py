from os import fork, pipe, close, read, write
from signal import signal, SIGCHLD
from sys import argv, stderr
from time import sleep
from subprocess import Popen, DEVNULL, PIPE

STATUS = 'PARENT'

child = None


def handle_sigchild(sig_no, stack_frame=None):
    if STATUS == 'PARENT':
        print("Process returned unexpectedly.")
    exit(1)


if __name__ == '__main__':
    signal(SIGCHLD, handle_sigchild)

    pid = fork()

    if pid:
        sleep(2)
        exit(0)

    STATUS = 'CHILD'
    delay = int(argv[1])

    print("Running '%s' for %d seconds as a background process" %
          (" ".join(argv[2:]), delay))

    child = Popen(argv[2:], stdout=DEVNULL)
    sleep(delay)
    child.kill()
