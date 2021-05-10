from libcanbadger.frame import Frame


def test_frame():
    # it should store arb_id and payload
    f = Frame(arb_id=0x123, payload=b'\x01\x02\x03')
    assert(f.arb_id == 0x123)
    assert(f.payload == b'\x01\x02\x03')

    # it should detect extended ID flags
    assert(not f.is_extended_id)
    f = Frame(arb_id=0x12345, payload=b'\x01\x02\x03')
    assert(f.is_extended_id)

    # it should implement __getitem__
    a = f[1]
    assert(a == 0x02)

    # it should implement __len__
    assert(len(f) == 3)