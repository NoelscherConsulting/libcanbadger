from libcanbadger.search.parameter import Parameter


class IntegerChoiceParameter(Parameter):
    def __init__(self, name, values: list=[]):
        super(IntegerChoiceParameter, self).__init__(name)
        self.values = values

    def length(self) -> int:
        return len(self.values)

    def get(self, index, context: dict = None):
        return self.values[index]

