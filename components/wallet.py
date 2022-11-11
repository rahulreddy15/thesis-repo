import binascii
from Crypto.PublicKey import RSA


class Wallet:

    def __init__(self, url, name, public_key=None, private_key=None, amount=0):
        self.name = name
        self.public_key = public_key
        self.private_key = private_key
        self.amount = amount
        self.url = url

    def to_json(self):
        return self.__dict__

    @staticmethod
    def from_json(wallet_json: dict):
        wallet = Wallet(**wallet_json)
        return wallet

    def create_keys(self):
        """
        Create a new pair of private and public keys.
        """
        private_key, public_key = self.generate_keys()
        self.private_key = private_key
        self.public_key = public_key

    def generate_keys(self):
        """
        Generate a new pair of private and public key
        """
        private_key = RSA.generate(1024)
        public_key = private_key.publickey()
        return (
            binascii.hexlify(private_key.exportKey(
                format='DER')).decode('ascii'),
            binascii.hexlify(public_key.exportKey(
                format='DER')).decode('ascii')
        )
