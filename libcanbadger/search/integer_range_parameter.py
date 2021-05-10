from libcanbadger.search.parameter import Parameter


class IntegerRangeParameter(Parameter):
    def __init__(self, name, start: int = 0, stop: int = 0, step: int = 1):
        super(IntegerRangeParameter, self).__init__(name)
        if step == 0:
            raise Exception("IntegerRangeParameter: Step can't be zero!")
        if start == stop:
            raise Exception("IntegerRangeParameter: Start can't be Stop!")
        self.start = start
        self.stop = stop
        self.step = step

    def length(self) -> int:
        return int((self.stop - self.start) / self.step)

    def get(self, index, context: dict = None):
        return self.start + (index * self.step)

