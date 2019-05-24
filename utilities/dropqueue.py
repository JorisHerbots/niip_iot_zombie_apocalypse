class DropQueue: # Crude implementation, not all list operators are available
    def __init__(self, size):
        if not isinstance(size, int) or size <= 0:
            raise ValueError("Size has to be an integer >0")

        self._items = []
        self._size = size

    def __contains__(self, item):
        return item in self._items

    def __repr__(self):
        return self._items.copy()

    def __str__(self):
        return str(self.__repr__())

    def __copy__(self):
        obj = DropQueue(self._size)
        obj._items += self._items
        return obj

    def append(self, item):
        if len(self._items) >= self._size:
            del self._items[:1]
        self._items.append(item)