class Transaction:

    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    def __init__(self, sender, sender_name, receiver, receiver_name, amount, reward=False, status=STATUS_PENDING):
        self.sender = sender
        self.sender_name = sender_name
        self.receiver = receiver
        self.receiver_name = receiver_name
        self.amount = amount
        self.reward = reward
        self.status = status

    def to_json(self):
        return self.__dict__

    @staticmethod
    def from_json(transaction_json):
        transaction = Transaction(**transaction_json)
        return transaction
