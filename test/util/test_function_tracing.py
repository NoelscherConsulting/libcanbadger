from libcanbadger.util.trace_decorator import trace_method_call, trace_func_call, get_current_trace

class SomeClass:
    @trace_method_call
    def __init__(self):
        self.some_state = 123

    @trace_method_call
    def some_method(self, arg):
        print(self)
        print(arg)

def test_function_trace():
    @trace_func_call
    def some_function(lol):
        print(lol)

    @trace_func_call
    def some_other_function(lol, soem_arg=None):
        print(lol)
        print(soem_arg)

    trace = get_current_trace()
    assert(trace is not None)
    # trace should be a singleton
    trace2 = get_current_trace()
    assert(trace == trace2)


    trace.start()
    someclass0 = SomeClass() # it should generate sort-of-readable class instance names
    someclass0.some_method(";lsjdhf")
    some_function("test")
    some_other_function("asdf", soem_arg=123)
    some_function(b'\x41\x42\x00') # 0x41 should not be printed in ascii
    trace.stop()
    some_function(123) # this should not get logged
    lines = trace.get_code_lines()
    assert(
        lines == ["someclass0 = SomeClass()",
                  "someclass0.some_method(';lsjdhf')",
                  "some_function('test')",
                  "some_other_function('asdf', soem_arg=123)",
                  "some_function(b'\\x41\\x42\\x00')"]
    )