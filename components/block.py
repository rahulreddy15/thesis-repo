import json
import hashlib
from components.transaction import Transaction


class Block:

    def __init__(self, index, timestamp, previous_hash, transactions, nonce, hash=None, mined_by=None):
        self.index = index
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.nonce = nonce
        self.hash = hash
        self.mined_by = mined_by

    def to_json(self):
        block_json = {
            'index': self.index,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'transactions': [tx.to_json() for tx in self.transactions],
            'nonce': self.nonce,
            'hash': self.hash,
            'mined_by': self.mined_by
        }
        return block_json

    @staticmethod
    def from_json(block_json):
        transactions = [Transaction.from_json(
            tx) for tx in block_json['transactions']]
        return Block(
            index=block_json['index'],
            timestamp=block_json['timestamp'],
            previous_hash=block_json['previous_hash'],
            transactions=transactions,
            nonce=block_json['nonce'],
            hash=block_json['hash'],
            mined_by=block_json['mined_by']
        )

    @staticmethod
    def hash_block(block):
        block_json = block.to_json()
        if 'hash' in block_json:
            del block_json['hash']
        encoded_block = json.dumps(block_json, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()
