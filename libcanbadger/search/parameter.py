

class Parameter(object):
    """
    defines the interface for parameter subclasses
    parameters define ranges (search spaces) of values, only
    searching through the spaces is implemented using Search classes
    """
    def __init__(self, name):
        self.name = name

    def length(self) -> int:
        """
        determines how many values are in the parameter space
        :return:  parameter length
        """
        pass

    def get(self, index, context: dict = None):
        """
        retrieves a value, given its index
        the index 0 is always the first value, with index=length()-1 being the last
        indices have nothing to do with the values returned by get(), they only represent a valid 'choice'

        :param index: parameter-dependent index
        :param context: optional context dictionary for latent parameters
        :return: a value
        """
        pass