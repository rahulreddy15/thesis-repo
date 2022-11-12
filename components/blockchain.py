import time
from components.block import Block


class Blockchain:
    DIFFICULTY = 5

    def __init__(self, chain=[]):
        self.chain = chain
        self.length = len(self.chain)

    def get_last_block(self):
        return self.chain[-1]

    def to_json(self):
        return {
            'chain': [block.to_json() for block in self.chain],
            'length': self.length
        }

    @staticmethod
    def from_json(blockchain_json):
        chain = [Block.from_json(block_json)
                 for block_json in blockchain_json['chain']]
        return Blockchain(chain)

    def add_block(self, block):
        self.chain.append(block)
        self.length = len(self.chain)

    def mine_block(self, transactions, mined_by):
        block_json = {
            'index': len(self.chain),
            'timestamp': time.time_ns(),
            'previous_hash': self.get_last_block().hash,
            'transactions': transactions,
            'nonce': 0,
            'hash': None,
            'mined_by': mined_by
        }
        block = Block.from_json(block_json)

        while Block.hash_block(block)[:Blockchain.DIFFICULTY] != '0' * Blockchain.DIFFICULTY:
            block.nonce = block.nonce + 1

        block.hash = Block.hash_block(block)
        self.add_block(block)
        return block
