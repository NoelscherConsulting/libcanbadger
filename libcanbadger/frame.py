

class Frame(object):
    """
    A can(-fd) frame
    """
    def __init__(self, arb_id=None, payload=None):
        self.arb_id = arb_id
        if self.arb_id is not None:
            self.is_extended_id = self.arb_id > 0x7ff
        else:
            self.is_extended_id = False
        self.payload = payload

    def payload_length(self):
        return len(self.payload)

    def __getitem__(self, item):
        return self.payload[item]

    def __len__(self):
        return len(self.payload)
