from typing import List

from libcanbadger.search.parameter import Parameter


class Strategy(object):
    def __init__(self):
        # initialize internal state here
        self.total_returned_cnt = 0

    def reset(self):
        """
        forget our progress and all other state
        :return: nothing
        """
        pass

    def reset_all(self):
        """
        forget all parameters and state
        :return: nothing
        """
        pass

    def update(self, parameters: List[Parameter]):
        """
        :param parameters: an array of all parameters
        """
        pass

    def get_next(self) -> list:
        """
        :return: the next choice of parameters
        """
        pass

    def peek_next(self) -> list:
        """
        :return: the next choice of parameters, without incrementing the progress
        """

    def length(self) -> int:
        """
        :return: total number of entries/parameter combinations performed by this search
        """
        pass

    def progress(self) -> int:
        """
        :return: the raw count of items we've returned already.
        """
        return self.total_returned_cnt