from libcanbadger.search.strategy import Strategy

class Search(object):
    def __init__(self, strategy: Strategy):
        if strategy is None:
            raise RuntimeError('Please provide a strategy when instantiating Search!')
        self.strategy = strategy
        self.parameters = []


    def add_param(self, param: object):
        """
        add a parameter to the search
        :param param: the parameter you'd like to add
        :return: no return value
        """
        self.parameters.append(param)
        self.strategy.update(self.parameters)

    def reset(self) -> None:
        """
        resets the strategy state
        with this, you can discard all state and start from scratch
        :return: no return value
        """
        self.strategy.reset()

    def reset_all(self) -> None:
        """
        removes all assigned params
        :return: no return value
        """
        self.parameters = []

    def length(self) -> int:
        """
        length of the combined search space
        depends on the parameters and on the strategy
        :return: number of combinations or values that this Search has
        """
        return self.strategy.length()

    def progress(self) -> float:
        return self.strategy.progress() / self.length()

    def has_completed(self) -> bool:
        """
        checks if the search is done or not
        :return: True if search has exhausted all parameters/stragies. False, if not done yet.
        """
        pass

    def peek_next(self) -> list:
        """
        :return: next value combination, without incrementing the progress
        """
        return self.strategy.peek_next()

    def increment(self) -> None:
        """
        increment the search by one step.
        :return: no return value
        """

    def next(self) -> list:
        """
        chooses a suitable value combination and returns it
        this automatically increments our progress and moves on to the next combination of values
        if you don't like this, use peek_next() and increment() in combination
        :return: a tuple, containing all parameter choices
        """
        return self.strategy.get_next()


    def serialize(self) -> str:
        """
        serializes the search to json, including current state of all parameters
        :return: a json string
        """
        pass

    def unserialize(self, json_string: str) -> None:
        """
        reads a serialized Search from json_string
        this implicitly calls reset_all() and overwrites all attributes with the serialized attributes
        :param json_string: json-serialized search
        :return: nothing
        """
        pass