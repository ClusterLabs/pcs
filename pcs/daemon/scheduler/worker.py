def worker_init():
    import signal

    def ignore_signals(sig_num, frame):
        pass

    signal.signal(signal.SIGINT, ignore_signals)

def worker_error():
    pass

def task_executor():
    pass