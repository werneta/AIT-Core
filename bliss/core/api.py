"""
BLISS API

The bliss.core.api module provides an Application Programming
Interface (API) to your instrument by bringing together the core.cmd
and core.tlm modules in a complementary whole, allowing you to
script instrument interactions, e.g.:

.. code-block:: python

    # TBA
"""


import gevent.monkey; gevent.monkey.patch_all()
import gevent
import gevent.event
import gevent.server


import collections
import inspect
import socket
import time

from bliss.core import cmd, gds, log, tlm


class CmdAPI:
    """CmdAPI

    Provides an API to send commands to your Instrument via User
    Datagram Protocol (UDP) packets.
    """
    def __init__ (self, destination, cmddict=None, verbose=False):
        if type(destination) is int:
            destination = ('127.0.0.1', destination)

        if cmddict is None:
            cmddict = cmd.getDefaultCmdDict()

        self._host    = destination[0]
        self._port    = destination[1]
        self._cmddict = cmddict
        self._verbose = verbose
        self._socket  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


    def send (self, command, *args, **kwargs):
        """Creates, validates, and sends the given command as a UDP
        packet to the destination (host, port) specified when this
        CmdAPI was created.

        Returns True if the command was created, valid, and sent,
        False otherwise.
        """
        status   = False
        cmdobj   = self._cmddict.create(command, *args, **kwargs)
        messages = []

        if not cmdobj.validate(messages):
            for msg in messages:
                log.error(msg)
        else:
            encoded = cmdobj.encode()

            if self._verbose:
                size = len(cmdobj.name)
                pad  = (size - len(cmdobj.name) + 1) * ' '
                gds.hexdump(encoded, preamble=cmdobj.name + ':' + pad)

            try:
                values = (self._host, self._port, cmdobj.name)
                log.info('Sending to %s:%d: %s' % values)
                self._socket.sendto(encoded, (self._host, self._port))
                status = True
            except socket.error as e:
                log.error(e.message)
            except IOError as e:
                log.error(e.message)

        return status


class GeventDeque (object):
    """GeventDeque

    A Python collections.deque that can be used in a Gevent context.
    """

    def __init__(self, iterable=None, maxlen=None):
        """Returns a new GeventDeque object initialized left-to-right
        (using append()) with data from *iterable*. If *iterable* is
        not specified, the new GeventDeque is empty.

        If *maxlen* is not specified or is ``None``, GeventDeques may
        grow to an arbitrary length.  Otherwise, the GeventDeque is
        bounded to the specified maximum length.  Once a bounded
        length GeventDeque is full, when new items are added, a
        corresponding number of items are discarded from the opposite
        end.
        """
        if iterable is None:
            self._deque = collections.deque(maxlen=maxlen)
        else:
            self._deque = collections.deque(iterable, maxlen)

        self.notEmpty = gevent.event.Event()

        if len(self._deque) > 0:
            self.notEmpty.set()

    def _pop(self, block=True, timeout=None, left=False):
        """Removes and returns the an item from this GeventDeque.

        This is an internal method, called by the public methods
        pop() and popleft().
        """
        item  = None
        timer = None
        deque = self._deque
        empty = IndexError('pop from an empty deque')

        if block is False:
            if len(self._deque) > 0:
                item = deque.popleft() if left else deque.pop()
            else:
                raise empty
        else:
            try:
                if timeout is not None:
                    timer = gevent.Timeout(timeout, empty)
                    timer.start()

                    while True:
                        self.notEmpty.wait()
                        if len(deque) > 0:
                            item = deque.popleft() if left else deque.pop()
                            break
            finally:
                if timer is not None:
                    timeout.cancel()

        if len(deque) == 0:
            self.notEmpty.clear()

        return item

    def __copy__(self):
        """Creates a new copy of this GeventDeque."""
        return GeventDeque(self._deque, self.maxlen)

    def __eq__(self, other):
        """True if other is equal to this GeventDeque, False otherwise."""
        return self._deque == other

    def __getitem__(self, index):
        """Returns GeventDeque[index]"""
        return self._deque.__getitem__(index)

    def __iter__(self):
        """Returns an iterable of items in this GeventDeque."""
        return self._deque.__iter__()

    def __len__(self):
        """The number of items in this GeventDeque."""
        return len(self._deque)

    @property
    def maxlen(self):
        """Maximum size of this GeventDeque or None if unbounded."""
        return self.maxlen

    def append(self, item):
        """Add item to the right side of the GeventDeque.

        This method does not block.  Either the GeventDeque grows to
        consume available memory, or if this GeventDeque has and is at
        maxlen, the leftmost item is removed.
        """
        self._deque.append(item)
        self.notEmpty.set()

    def appendleft(self, item):
        """Add item to the left side of the GeventDeque.

        This method does not block.  Either the GeventDeque grows to
        consume available memory, or if this GeventDeque has and is at
        maxlen, the rightmost item is removed.
        """
        self._deque.appendleft(item)
        self.notEmpty.set()

    def clear(self):
        """Remove all elements from the GeventDeque leaving it with
        length 0.
        """
        self._deque.clear()
        self.notEmpty.clear()

    def count(self, item):
        """Count the number of GeventDeque elements equal to item."""
        return self._deque.count(item)

    def extend(self, iterable):
        """Extend the right side of this GeventDeque by appending
        elements from the iterable argument.
        """
        self._deque.extend(iterable)
        if len(self._deque) > 0:
            self.notEmpty.set()

    def extendleft(self, iterable):
        """Extend the left side of this GeventDeque by appending
        elements from the iterable argument.  Note, the series of left
        appends results in reversing the order of elements in the
        iterable argument.
        """
        self._deque.extendleft(iterable)
        if len(self._deque) > 0:
            self.notEmpty.set()

    def pop(self, block=True, timeout=None):
        """Remove and return an item from the right side of the
        GeventDeque. If no elements are present, raises an IndexError.

        If optional args *block* is True and *timeout* is ``None``
        (the default), block if necessary until an item is
        available. If *timeout* is a positive number, it blocks at
        most *timeout* seconds and raises the :class:`IndexError`
        exception if no item was available within that time. Otherwise
        (*block* is False), return an item if one is immediately
        available, else raise the :class:`IndexError` exception
        (*timeout* is ignored in that case).
        """
        return self._pop(block, timeout)

    def popleft(self, block=True, timeout=None):
        """Remove and return an item from the right side of the
        GeventDeque. If no elements are present, raises an IndexError.

        If optional args *block* is True and *timeout* is ``None``
        (the default), block if necessary until an item is
        available. If *timeout* is a positive number, it blocks at
        most *timeout* seconds and raises the :class:`IndexError`
        exception if no item was available within that time. Otherwise
        (*block* is False), return an item if one is immediately
        available, else raise the :class:`IndexError` exception
        (*timeout* is ignored in that case).
        """
        return self._pop(block, timeout, left=True)

    def remove(item):
        """Removes the first occurrence of *item*. If not found,
        raises a ValueError.

        Unlike ``pop()`` and ``popleft()`` this method does not have
        an option to block for a specified period of time (to wait for
        item).
        """
        self._deque.remove(item)

    def reverse(self):
        """Reverse the elements of the deque in-place and then return
        None."""
        self._deque.reverse()

    def rotate(self, n):
        """Rotate the GeventDeque *n* steps to the right. If *n* is
        negative, rotate to the left.  Rotating one step to the right
        is equivalent to: ``d.appendleft(d.pop())``.
        """
        self._deque.rotate(n)


class PacketBuffers (dict):
    def __init__(self):
        super(PacketBuffers, self).__init__()


    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def create(self, name, capacity=60):
        created = False

        if name not in self:
            self[name] = GeventDeque(maxlen=capacity)
            created    = True

        return created


    def insert(self, name, packet):
        if name not in self:
            self._create(name)
        self[name].appendleft(packet)


class TlmWrapper (object):
    def __init__ (self, packets):
        self._packets = packets

    def __getattr__(self, name):
        return self._packets[0].__getattr__(name)

    def __getitem__(self, index):
        return self._packets[index]

    def __len__(self):
        return len(self._packets)



class TlmWrapperAttr (object):
    def __init__(self, buffers):
        super(TlmWrapperAttr, self).__init__()
        self._buffers = buffers

    def __getattr__(self, name):
        return TlmWrapper(self._buffers[name])



class UdpTelemetryServer (gevent.server.DatagramServer):
    """UdpTelemetryServer

    Listens for telemetry packets delivered via User Datagram Protocol
    (UDP) to a particular (host, port).
    """

    def __init__ (self, listener, pktbuf, defn=None):
        """Creates a new UdpTelemetryServer.

        The server listens for UDP packets matching the given
        ``PacketDefinition`` *defn*.

        The *listener* is either a port on localhost, a tuple
        containing ``(hostname, port)``, or a
        ``gevent.socket.socket``.

        If the optional *defn* is not specified, the first
        ``PacketDefinition`` (alphabetical by name) in the default
        telemetry dictionary (i.e. ``tlm.getDefaultDict()``) is used.
        """
        if type(listener) is int:
            listener = ('127.0.0.1', listener)

        super(UdpTelemetryServer, self).__init__(listener)
        self._defn   = defn
        self._pktbuf = pktbuf

    @property
    def packets (self):
        """The packet buffer."""
        return self._pktbuf

    def handle (self, data, address):
        self._pktbuf.appendleft( tlm.Packet(self._defn, data) )

    def start (self):
        """Starts this UdpTelemetryServer."""
        values = self._defn.name, self.server_host, self.server_port
        log.info('Listening for %s telemetry on %s:%d (UDP)' % values)
        super(UdpTelemetryServer, self).start()



class Instrument (object):
    def __init__ (self, cmdport=3075, tlmport=3076, defn=None):
        if defn is None:
            tlmdict = tlm.getDefaultDict()
            names   = sorted( tlmdict.keys() )

            if len(names) == 0:
                msg = 'No packets defined in default TLM dictionary.'
                raise TypeError(msg)

            defn = tlmdict[ names[0] ]

        self._packets = PacketBuffers()
        self._cmd     = CmdAPI(cmdport)

        self._packets.create(defn.name)
        pktbuf        = self._packets[defn.name]
        self._tlm     = UdpTelemetryServer(tlmport, pktbuf, defn)
        self._tlm.start()

    @property
    def cmd (self):
        return self._cmd

    @property
    def tlm (self):
        return TlmWrapperAttr(self._packets)


def wait (cond, timeout=None):
    status = False
    n      = 0

    if type(cond) in (int, float):
        gevent.sleep(cond)
        status = True
    else:
        while True:
            if n == timeout:
                status = False
                break

            if type(cond) is str:
                caller = inspect.stack()[1][0]
                status = eval(cond, caller.f_globals, caller.f_locals)
            elif callable(cond):
                status = cond()
            else:
                status = cond

            if status:
                break

            gevent.sleep(1)
            n += 1

    return status
