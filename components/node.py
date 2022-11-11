from components.blockchain import Blockchain
from components.wallet import Wallet


class Node:

    def __init__(self, url, blockchain, wallet):
        self.url = url
        self.blockchain = blockchain
        self.wallet = wallet

    def to_json(self):
        node_json = {
            'url': self.url,
            'blockchain': self.blockchain.to_json(),
            'wallet': self.wallet.to_json()
        }
        return node_json

    @staticmethod
    def from_json(node_json):
        blockchain = Blockchain.from_json(node_json['blockchain'])
        wallet = Wallet.from_json(node_json['wallet'])
        return Node(
            url=node_json['url'],
            blockchain=blockchain,
            wallet=wallet
        )
