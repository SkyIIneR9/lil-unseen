"""Read Ren'Py data without importing Ren'Py or running embedded game code."""
import builtins
import collections
import io
import pickle
import struct
import zlib


class Record:
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, *args, **kwargs):
        pass

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        elif isinstance(state, tuple) and len(state) == 2:
            for part in state:
                if isinstance(part, dict):
                    self.__dict__.update(part)
        else:
            self.pickle_state = state


class PyExpr(str):
    def __new__(cls, value='', *args):
        return str.__new__(cls, value)

    __setstate__ = Record.__setstate__


class PyCode(Record):
    def __setstate__(self, state):
        if isinstance(state, tuple) and len(state) in (4, 5):
            self.source, self.location, self.mode = state[1:4]
        else:
            super().__setstate__(state)


class RevertableDict(dict):
    __setstate__ = Record.__setstate__


class RevertableList(list):
    __setstate__ = Record.__setstate__


class RevertableSet(set):
    __setstate__ = Record.__setstate__


CLASSES = {}


def inert_reconstructor(cls, base, state):
    if not isinstance(cls, type) or not issubclass(cls, (Record, PyExpr, RevertableDict, RevertableList, RevertableSet)):
        raise pickle.UnpicklingError('Unexpected reconstruction target')
    if issubclass(cls, str):
        return cls(state or '')
    return cls()


class DataReader(pickle.Unpickler):
    def find_class(self, module, name):
        if module in ('builtins', '__builtin__') and name in ('set', 'frozenset', 'dict', 'list', 'tuple', 'str', 'bytes', 'object'):
            return getattr(builtins, name)
        if module == 'collections' and name in ('defaultdict', 'OrderedDict'):
            return getattr(collections, name)
        if module in ('copy_reg', 'copyreg') and name == '_reconstructor':
            return inert_reconstructor
        if module == '_codecs' and name == 'encode':
            return lambda text, encoding='latin1': text.encode(encoding)
        if module.startswith('renpy.') or module == 'store' or module.startswith('store.'):
            if name == 'PyExpr':
                return PyExpr
            if name == 'PyCode':
                return PyCode
            if name in ('RevertableDict', 'RevertableList', 'RevertableSet'):
                return globals()[name]
            key = (module, name)
            if key not in CLASSES:
                CLASSES[key] = type(name, (Record,), {'original_module': module})
            return CLASSES[key]
        raise pickle.UnpicklingError('Unsupported global: %s.%s' % (module, name))


def loads(data):
    return DataReader(io.BytesIO(data), encoding='utf-8', errors='strict').load()


def rpyc_load(data, slot=2):
    if not data.startswith(b'RENPY RPC2'):
        return loads(zlib.decompress(data))
    pos = len(b'RENPY RPC2')
    slots = {}
    while True:
        number, offset, length = struct.unpack_from('<III', data, pos)
        pos += 12
        if not number:
            break
        slots[number] = (offset, length)
    offset, length = slots.get(slot, slots[1])
    return loads(zlib.decompress(data[offset:offset + length]))


class Archive:
    def __init__(self, path):
        self.path = path
        with path.open('rb') as stream:
            header = stream.readline().split()
            if header[0] not in (b'RPA-2.0', b'RPA-3.0'):
                raise ValueError('Unsupported archive: ' + str(path))
            self.key = int(header[2], 16) if header[0] == b'RPA-3.0' else 0
            stream.seek(int(header[1], 16))
            self.index = loads(zlib.decompress(stream.read()))

    def read(self, name):
        chunks = []
        with self.path.open('rb') as stream:
            for offset, length, *prefix in self.index[name]:
                stream.seek(offset ^ self.key)
                start = prefix[0] if prefix else b''
                if isinstance(start, str):
                    start = start.encode('latin1')
                chunks.append(start + stream.read(length ^ self.key))
        return b''.join(chunks)


def walk_objects(root):
    """Inspect object state; never follow live properties or evaluate expressions."""
    pending, visited = [root], set()
    while pending:
        obj = pending.pop()
        if id(obj) in visited:
            continue
        visited.add(id(obj))
        yield obj
        if isinstance(obj, dict):
            pending.extend(obj.values())
        elif isinstance(obj, (tuple, list, set, frozenset)):
            pending.extend(obj)
        if isinstance(obj, (Record, PyExpr)):
            pending.extend(vars(obj).values())
