#!/usr/bin/env python
# -*- coding: utf-8 -*-

TIMEFORMAT = '%Y-%m-%d %H:%M:%S %Z'

import threading
import time


class Scheduler(threading.Thread):

    def __init__(self, trigger, interval, fn, args=(), kwargs={}):
        super().__init__()
        if trigger not in ['delay', 'recur']:
            raise ValueError('trigger must be "delay" or "recur"')
        self.trigger = trigger
        self.interval = interval
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self._event = threading.Event()
        self._stopped = True
        self._result = []

    # Scheduler constructor
    @classmethod
    def create(cls, **scheduler_kwargs):
        return cls(**scheduler_kwargs)

    @property
    def stopped(self):
        return self._stopped

    @property
    def result(self):
        return dict(self._result)

    def run(self):
        self._stopped = self._event.is_set()  # False
        if self.trigger == 'delay':
            self._delay()
        elif self.trigger == 'recur':
            self._recur()

    def _delay(self):
        if not self._stopped:
            self._event.wait(timeout=self.interval)
            self._execute()

    def _recur(self):
        while not self._stopped:
            self._execute()
            self._event.wait(timeout=self.interval)

    def _execute(self):
        self._fn(self.args, self.kwargs)

    def _fn(self, args, kwargs):
        return_value = self.fn(*args, **kwargs)
        if return_value:
            timestamp = time.strftime(TIMEFORMAT, time.localtime())
            self._result.append( (timestamp, return_value) )

    # threads can only be started once
    # i.e., cannot start again once cancelled
    def cancel(self):
        self._event.set()
        self._stopped = self._event.is_set()  # True
