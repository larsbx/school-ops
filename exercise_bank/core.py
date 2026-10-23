"""Shared deterministic sampling, form identity and timing conventions."""
import hashlib
import json
import time

VERSION = '1.0.0'
SCHEMA = 1


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n'


class Sampler:
    """SHA-256 counter stream with rejection sampling, independent of random module."""
    def __init__(self, namespace, seed):
        self.prefix = canonical([VERSION, namespace, seed]).encode()
        self.counter = 0

    def integer(self, low, high):
        width = high - low + 1
        if width <= 0 or width > 2**256:
            raise ValueError('invalid sampling interval')
        limit = 2**256 - (2**256 % width)
        while True:
            digest = hashlib.sha256(self.prefix + str(self.counter).encode()).digest()
            self.counter += 1
            value = int.from_bytes(digest, 'big')
            if value < limit:
                return low + value % width


def seal(form):
    form = dict(form)
    form.pop('form_id', None)
    form['form_id'] = hashlib.sha256(canonical(form).encode()).hexdigest()
    return form


def seconds(value):
    if type(value) is not int or not 1 <= value <= 86400:
        raise ValueError('duration must be an integer from 1 to 86400 seconds')
    return value


def countdown(duration, clock=time.monotonic, sleep=time.sleep, emit=print):
    """Wall-clock countdown; no responses, results, or identities are collected."""
    duration = seconds(duration)
    deadline = clock() + duration
    emit(f'Start: {duration} seconds')
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            break
        sleep(min(1, remaining))
    emit('Time. Stop this fluency drill; review afterwards.')
