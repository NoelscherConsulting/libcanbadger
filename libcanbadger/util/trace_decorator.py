import functools


def bytes_to_hex_str(bytes):
    """
    turns a bytes/bytestring/bytearray into a python-compatible hex string
    it's sad that we have to do it this way
    """
    x_values = "\\x".join(["{:02x}".format(i) for i in bytes])
    return f"b'\\x{x_values}'"

def generate_class_instance_name(classname: str, count=0):
    return classname.lower() + str(count) # this has to do for now

class Trace:
    """
    use this to trace function calls
    when you're done, you can call trace.save()
    """
    def __init__(self):
        self.call_sequence = []
        # try to generate meaningful names for classes and map their instances here, using class_to_instance_map
        self.class_to_instance_map = {}
        # remember how many instances we have for each class
        self.class_instance_count = {}
        self.enable = False

    def start(self):
        self.enable = True

    def stop(self):
        self.enable = False

    def trace_call(self, func, args, kwargs):
        if self.enable:
            current_trace.call_sequence.append({'function': func, 'args': args, 'kwargs': kwargs, 'is_method': False})

    def trace_method_call(self, func, args, kwargs):
        if self.enable:
            current_trace.call_sequence.append({'function': func, 'args': args, 'kwargs': kwargs, 'is_method': True})

    def type_to_code(self, value):
        """
        returns a code-friendlier representation of the value, if possible
        """
        if type(value) == str:
            return f"'{value}'"
        elif type(value) == bytes:
            return bytes_to_hex_str(value)
        elif type(value) == bytearray:
            return bytes_to_hex_str(value)
        else:
            return str(value) # best we can do


    def format_args(self, args, kwargs) -> str:
        """
        format args and kwargs as function call string
        example (123, keyword_arg='some_value')
        """
        result = '('
        # format all positional arguments
        pos_args = [self.type_to_code(a) for a in args]
        kw_args = [str(k) + '=' + self.type_to_code(v) for k, v in kwargs.items()]
        if len(pos_args) > 0:
            result += ', '.join(pos_args)
            if len(kw_args) > 0:
                result += ', '
        if len(kw_args):
            result += ', '.join(kw_args)
        return result +  ')'

    def get_code_lines(self) -> list:
        """
        generate the code from this trace
        :return: a list of strings
        """
        code_lines = []
        for t in self.call_sequence:
            if not t['is_method']:
                code_lines.append(f"{t['function'].__name__}{self.format_args(t['args'], t['kwargs'])}")
            else:
                if t['function'].__name__ == '__init__':
                    # handle constructor. first argument is 'self'
                    classname = t['args'][0].__class__.__name__
                    # create new name for this instance
                    if classname not in self.class_instance_count.keys():
                        self.class_instance_count[classname] = 0
                    instance_name = generate_class_instance_name(classname, self.class_instance_count[classname])
                    # remember that this class belongs to this name
                    # args[0] is 'self'
                    self.class_to_instance_map[t['args'][0]] = instance_name
                    # format instantiation call
                    code_lines.append(f"{instance_name} = {classname}{self.format_args(t['args'][1:], t['kwargs'])}")
                else:
                    # ignore static methods for now. you can use trace_func_call if you really have to
                    instance_name = self.class_to_instance_map[t['args'][0]]
                    code_lines.append(f"{instance_name}.{t['function'].__name__}{self.format_args(t['args'][1:], t['kwargs'])}")

        return code_lines

    def print_as_code(self):
        """
        print the recorded trace as code string
        you can copy and paste it to reproduce whatever happened in this trace
        """
        for line in self.get_code_lines():
            print(line)

current_trace = Trace()

def get_current_trace():
    return current_trace

def trace_func_call(func):
    """
    use this to trace function calls, only
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        trace = get_current_trace()
        trace.trace_call(func, args, kwargs)
        return func(*args, **kwargs)
    return wrapper


def trace_method_call(func):
    """
    use this for class methods
    namely, class methods first implicit argument is 'self' and this requires different handling
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        trace = get_current_trace()
        trace.trace_method_call(func, args, kwargs)
        return func(*args, **kwargs)

    return wrapper