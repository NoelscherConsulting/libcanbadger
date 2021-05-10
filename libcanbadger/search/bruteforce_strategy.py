from functools import reduce
from typing import List

from libcanbadger.search.strategy import Strategy
from libcanbadger.search.parameter import Parameter


class BruteforceStrategy(Strategy):
    """
    a depth-first-search bruteforce variant
    """
    def __init__(self):
        super(BruteforceStrategy, self).__init__()
        self.total_combination_count = 0
        self.total_parameter_count = 0
        self.parameters = []
        self.indices = {}

    def reset(self):
        self.update(self.parameters)

    def reset_all(self):
        self.total_returned_cnt = 0
        self.indices = {}
        self.parameters = []

    def update(self, parameters: List[Parameter]):
        self.reset_all()
        self.parameters = parameters
        self.total_combination_count = reduce(lambda x, y: x*y, [p.length() for p in parameters])
        self.total_parameter_count = len(parameters)
        for p in self.parameters:
            self.indices[p] = 0

    def move_indices(self, indices) -> list:
        # select "deepest" parameter
        current_param_index = len(self.parameters) - 1
        current_param = self.parameters[current_param_index]
        indices[current_param] += 1
        while indices[self.parameters[current_param_index]] >= self.parameters[current_param_index].length():
            indices[self.parameters[current_param_index]] = 0
            current_param_index -= 1
            indices[self.parameters[current_param_index]] += 1

            if current_param_index == 0 and indices[self.parameters[0]] > self.parameters[0].length():
                # we're done!
                self.total_returned_cnt= 1
                return [p.length()-1 for p in self.parameters]

        self.total_returned_cnt += 1
        return list(self.indices.values())

    def get_next(self) -> list:
        values = []
        for k, v in self.indices.items():
            values.append(k.get(v))
        self.move_indices(self.indices)
        return values

    def peek_next(self) -> list:
        values = []
        for k, v in self.indices.items():
            values.append(k.get(v))
        return values

    def length(self) -> int:
        if len(self.parameters) > 0:
            param_lengths = [p.length() for p in self.parameters]
            total_count = param_lengths[0]
            for l in param_lengths[1:]:
                total_count *= l
            return total_count

        return 0

