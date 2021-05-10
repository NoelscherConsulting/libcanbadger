from libcanbadger.search.search import Search
from libcanbadger.search.integer_range_parameter import IntegerRangeParameter
from libcanbadger.search.integer_choice_parameter import IntegerChoiceParameter
from libcanbadger.search.bruteforce_strategy import BruteforceStrategy

def test_parameters():
    param = IntegerRangeParameter(name='test', start=0, stop=10, step=1)
    for i in range(0,10):
        assert(param.get(i) == i)

    # it should provide the number of values
    assert(param.length() == 10)

    # it should respect the step values
    param = IntegerRangeParameter(name='test', start=0, stop=20, step=10)
    for i in range(0, 10):
        assert (param.get(i) == i*10)

    # integer choice provides fixed choices of integers
    param = IntegerChoiceParameter(name='choices', values=[4, 2, 9])
    assert(param.length() == 3)
    # it should keep the original order
    assert(param.get(0) == 4)
    assert(param.get(2) == 9)



def test_bruteforce_search():
    search = Search(strategy=BruteforceStrategy())

    # it should accept parameters
    param1 = IntegerRangeParameter(name='address', start=0x0, stop=0xffff, step=0x10)
    param2 = IntegerChoiceParameter(name='transfer_flags', values=[0x55, 0xff])
    search.add_param(param1)
    search.add_param(param2)

    # it should provide a count of combinations
    total_count = search.length()
    assert(total_count == (2*int(0xffff / 0x10)))

    # it should move through the parameters
    p_1, p_2 = search.next()
    assert(p_1 == 0)
    assert(p_2 == 0x55)
    p_1, p_2 = search.next()
    assert(p_1 == 0)
    assert (p_2 == 0xff)

    # peek_next should provide the next value, without incrementing the progress
    p_1, p_2 = search.peek_next()
    assert(p_1 == 0x10)
    assert(p_2 == 0x55)
    p_1, p_2 = search.peek_next()
    assert(p_1 == 0x10)
    assert(p_2 == 0x55)
    # it keeps track of its own progress
    assert(search.progress() > 0)

    # search.reset resets our progress
    search.reset()
    assert(search.progress() == 0.0)

    # when exhausted, it should have progress = 1

    for i in range(0, search.length()):
        assert(search.strategy.total_returned_cnt == i)
        search.next()

    assert(search.progress() == 1.0)

if __name__ == "__main__":
    test_parameters()
    test_bruteforce_search()