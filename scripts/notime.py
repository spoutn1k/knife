from os import fork, pipe, close, read, write
from signal import signal, SIGCHLD
from sys import argv, stderr
from time import sleep
from subprocess import Popen, DEVNULL, PIPE

STATUS = 'PARENT'
errpipe_read, errpipe_write = (None, None)
child = None

def handle_sigchild(sig_no, stack_frame=None):
    if STATUS == 'CHILD':
        if child:
            write(errpipe_write, child.stderr.read())

    if STATUS == 'PARENT':
        error = read(errpipe_read, 1024**3)
        print(error.decode('utf-8'), file=stderr, end='')

    exit(1)


if __name__ == '__main__':
    if len(argv) < 3:
        print("Usage: %s <time> <command>" % argv[0])

    signal(SIGCHLD, handle_sigchild)

    errpipe_read, errpipe_write = pipe()
    pid = fork()

    if pid:
        close(errpipe_write)
        sleep(2)
        close(errpipe_read)
        exit(0)

    close(errpipe_read)
    STATUS = 'CHILD'
    delay = int(argv[1])

    print("Running '%s' for %d seconds as a background process" %
          (" ".join(argv[2:]), delay))

    child = Popen(argv[2:], stdout=DEVNULL, stderr=PIPE)
    sleep(delay)
    child.terminate()
    close(errpipe_write)
