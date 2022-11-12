import logging
import time
import random
import requests
import json
from argparse import ArgumentParser
from urllib.parse import urlparse
from flask import Flask, request, render_template, flash, redirect, session
from pymongo import MongoClient
from bson.objectid import ObjectId

from components.wallet import Wallet
from components.block import Block
from components.blockchain import Blockchain
from components.node import Node
from components.transaction import Transaction


# Get the port
parser = ArgumentParser()
parser.add_argument(
    '-p', '--port', default=5000, type=int, help='port to listen on'
)
args = parser.parse_args()
port = args.port

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.secret_key = '12345'

app.config.update(SESSION_COOKIE_NAME=f'session_{port}')

# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = 'login'

# Connect to mongo server
client = MongoClient('localhost', 27017)

# Access the db
db = client['blocks']

# Reference to the collections
transactions = db['transactions']
nodes = db['nodes']


# Provide login manager with load_user callback
# @login_manager.user_loader
# def load_user(private_key):
#     return nodes.find_one(
#         {'wallet.private_key': private_key}
#     )


@app.route('/', methods=['GET', 'POST'])
# @login_required
def index():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')

    url = urlparse(request.base_url).netloc

    if request.method == 'POST':
        blockchain = update_blockchain()
        nodes.update_one(
            {'url': url},
            {'$set': {'blockchain': blockchain.to_json()}},
            upsert=False
        )
        flash('Blockchain updated successfully!')
    # else:
        # create_node(url)

    # Retrieve the blockchain from the current node
    node_json = nodes.find_one({'url': url})
    blockchain_json = node_json['blockchain']
    blockchain = Blockchain.from_json(blockchain_json)
    return render_template('blockchain_new.html', blockchain=blockchain, current_user=session.get('username'))


@app.route('/wallet')
# @login_required
def get_wallet_details():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')

    node_json = nodes.find_one({'_id': ObjectId(session.get('node_id'))})
    wallet_json = node_json['wallet']
    wallet = Wallet.from_json(wallet_json)
    return render_template('wallet.html', wallet=wallet, current_user=session.get('username'))


@app.route('/nodes')
# @login_required
def get_all_nodes():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')
    url = urlparse(request.base_url).netloc
    node_urls = nodes.find({'url': {'$ne': url}}, {'url': 1})
    return render_template('nodes.html', nodes=node_urls, current_user=session.get('username'))


@app.route('/transaction', methods=['GET', 'POST'])
# @login_required
def transaction():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')

    if request.method == 'POST':
        sender = request.form.get('sender')
        sender_name = request.form.get('sender-name')
        receiver = request.form.get('receiver')
        receiver_name = request.form.get('receiver-name')
        amount = request.form.get('amount')

        transaction_json = {
            'sender': sender,
            'sender_name': sender_name,
            'receiver': receiver,
            'receiver_name': receiver_name,
            'amount': float(amount)
        }

        # if validate_transaction(sender, amount):
        transaction = Transaction.from_json(transaction_json)

        # Add transaction to the collection
        transactions.insert_one(transaction.to_json())
        flash('Transaction added successfully')
        # else:
        #     flash('Insufficient Balance')

    wallets = nodes.find({}, {'wallet': 1})
    wallets_except_self = []
    my_wallet = None
    for wallet in wallets:
        if wallet['wallet']['public_key'] == session['wallet']['public_key']:
            my_wallet = wallet['wallet']
            continue
        wallets_except_self.append(wallet['wallet'])

    total_transactions = transactions.find(
        {'$or': [
            {'sender': session['wallet']['public_key']},
            {'receiver': session['wallet']['public_key']}
        ]},
        {'_id': 0}
    )
    txs = []
    for i in total_transactions:
        if i['sender'] == session['wallet']['public_key']:
            txs.append({
                'wallet': i['receiver'],
                'user': i['receiver_name'],
                'amount': -i['amount'],
                'status': i['status']
            })
        else:
            txs.append({
                'wallet': i['sender'],
                'user': i['sender_name'],
                'amount': i['amount'],
                'status': i['status']
            })
    return render_template('transaction_new.html', wallets=wallets_except_self, my_wallet=my_wallet, Transactions=txs, current_user=session.get('username'))


@app.route('/mine_block', methods=['GET', 'POST'])
# @login_required
def mine_block():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')
    url = urlparse(request.base_url).netloc

    if request.method == 'POST':
        # Send Mining Request To All Nodes
        # print("Started Mining at Time: " + str(time.time()))
        winner, winner_url, winner_name = send_messsage()

        # Get updated blockchain
        blockchain = update_blockchain()
        nodes.update_one(
            {'_id': ObjectId(session.get('node_id'))},
            {'$set': {'blockchain': blockchain.to_json()}},
            upsert=False
        )

        # Get genesis block hash
        node = nodes.find_one({'_id': ObjectId(session.get('node_id'))})
        chain = node['blockchain']['chain']
        genesis_block = chain[0]
        genesis_block_hash = genesis_block['hash']

        pending_transactions = transactions.find(
            {'status': Transaction.STATUS_PENDING}
        )

        if pending_transactions:
            list_of_transactions = []

            # update the status of all the transactions
            for tx in pending_transactions:
                sender_public_key = tx['sender']
                sender_name = tx['sender_name']
                receiver_public_key = tx['receiver']
                receiver_name = tx['receiver_name']
                amount = tx['amount']
                reward = tx['reward']

                # Check if the transaction is from genesis or another user
                if sender_public_key == genesis_block_hash:
                    # Genesis block transaction
                    if reward:
                        nodes.update_one(
                            {'wallet.public_key': receiver_public_key},
                            {'$inc': {'wallet.amount': amount}}
                        )
                        transactions.update_one(
                            {'_id': tx['_id']},
                            {'$set': {'status': Transaction.STATUS_SUCCESS}},
                            upsert=False
                        )
                        transactions_json = {
                            'sender': sender_public_key,
                            'sender_name': sender_name,
                            'receiver': receiver_public_key,
                            'receiver_name': receiver_name,
                            'amount': amount,
                            'status': Transaction.STATUS_SUCCESS
                        }
                        list_of_transactions.append(transactions_json)
                    else:
                        random_number = random.uniform(0, 1)
                        if random_number < 0.5:
                            transactions.update_one(
                                {'_id': tx['_id']},
                                {'$set': {'status': Transaction.STATUS_FAILED}},
                                upsert=False
                            )
                        else:
                            # update receiver wallet
                            nodes.update_one(
                                {'wallet.public_key': receiver_public_key},
                                {'$inc': {'wallet.amount': amount}}
                            )

                            transactions.update_one(
                                {'_id': tx['_id']},
                                {'$set': {'status': Transaction.STATUS_SUCCESS}},
                                upsert=False
                            )

                            transactions_json = {
                                'sender': sender_public_key,
                                'sender_name': sender_name,
                                'receiver': receiver_public_key,
                                'receiver_name': receiver_name,
                                'amount': amount,
                                'status': Transaction.STATUS_SUCCESS
                            }
                            list_of_transactions.append(
                                transactions_json
                            )
                else:
                    # Regular transaction

                    # Validate the transaction
                    if validate_transaction(sender_public_key, amount):
                        # update sender wallet
                        nodes.update_one(
                            {'wallet.public_key': sender_public_key},
                            {'$inc': {'wallet.amount': -amount}}
                        )

                        # update receiver wallet
                        nodes.update_one(
                            {'wallet.public_key': receiver_public_key},
                            {'$inc': {'wallet.amount': amount}}
                        )

                        transactions.update_one(
                            {'_id': tx['_id']},
                            {'$set': {'status': Transaction.STATUS_SUCCESS}},
                            upsert=False
                        )

                        transactions_json = {
                            'sender': sender_public_key,
                            'sender_name': sender_name,
                            'receiver': receiver_public_key,
                            'receiver_name': receiver_name,
                            'amount': amount,
                            'status': Transaction.STATUS_SUCCESS
                        }
                        list_of_transactions.append(
                            transactions_json
                        )
                    else:
                        transactions.update_one(
                            {'_id': tx['_id']},
                            {'$set': {'status': Transaction.STATUS_FAILED}},
                            upsert=False
                        )

            # Mine the block ( important )

            latest_block = blockchain.mine_block(list_of_transactions, winner)
            nodes.update_one(
                {'url': url},
                {'$set': {'blockchain': blockchain.to_json()}},
                upsert=False
            )
            send_block_found_message(latest_block.to_json())
            # Adding Reward
            
            transaction_json = {
                'sender': genesis_block_hash,
                'sender_name': "genesis (mining reward)",
                'receiver': winner,
                'receiver_name': winner_name,
                'amount': float(100),
                'reward': True
            }

            # if validate_transaction(sender, amount):
            transaction = Transaction.from_json(transaction_json)
            # Add transaction to the collection
            transactions.insert_one(transaction.to_json())

    # Get all pending transactions
    pending_transactions = transactions.find(
        {'status': Transaction.STATUS_PENDING},
        {'_id': 0}
    )

    # Convert all transactions from json to python objects
    txs = []
    for tx in pending_transactions:
        txs.append(Transaction.from_json(tx))

    return render_template('mine_new.html', transactions=txs, current_user=session.get('username'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        public_key = request.form.get('public-key')
        private_key = request.form.get('private-key')
        node = nodes.find_one({
            'wallet.public_key': public_key,
            'wallet.private_key': private_key
        })
        if not node:
            flash('Authentication Failed!')
            return render_template('login_new.html')

        # Set node_id and wallet object as session variables
        session['node_id'] = str(node['_id'])
        session['wallet'] = node['wallet']
        session['username'] = node['wallet']['name']
        session['logged_in'] = True
        session.permanent = True

        return redirect('/')
    return render_template('login_new.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Clear all the session variables
        session.clear()

        username = request.form.get('name')

        # Create a new node
        url = urlparse(request.base_url).netloc
        node_id = create_node(url, username)
        node = nodes.find_one({'_id': ObjectId(node_id)})

        if node:
            # Set the session variables
            session['node_id'] = str(node_id)
            session['wallet'] = node['wallet']
            session['username'] = username
            session['logged_in'] = True
            session.permanent = True
            return redirect('/wallet')
        else:
            flash('Could not create a wallet at this time')
            # return redirect('/register.html')
    return render_template('register.html')


@app.route('/logout', methods=['GET'])
def logout():
    # Clear session variables
    session.clear()

    return redirect('/login')


@app.route('/buy', methods=['GET', 'POST'])
def buy():
    # Is logged in
    if not session.get('logged_in', False):
        return redirect('/login')

    if request.method == 'POST':
        amount = request.form.get('amount')
        amount = float(amount)

        # Get genesis block hash
        node = nodes.find_one({'_id': ObjectId(session.get('node_id'))})
        chain = node['blockchain']['chain']
        genesis_block = chain[0]
        genesis_block_hash = genesis_block['hash']

        # Get wallet's public key
        wallet = session.get('wallet')
        public_key = wallet.get('public_key')
        username = session.get('username')

        # Create a transaction from genesis to the current wallet
        transaction_json = {
            'sender': genesis_block_hash,
            'sender_name': 'Genesis',
            'receiver': public_key,
            'receiver_name': username,
            'amount': float(amount)
        }

        transaction = Transaction.from_json(transaction_json)

        # Add transaction to the collection
        transactions.insert_one(transaction.to_json())
        flash('Transaction added successfully')

    return render_template('buy_new.html', current_user=session.get('username'))


@app.route('/start_mining')
def start_mining():
    print("Started Mining at Time: " + str(time.time()))
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


@app.route('/end_mining', methods=['GET', 'POST'])
def end_mining():
    if request.method == 'POST':
        
        data = request.get_json(force=True)
        winner = data['mined_by']
        session_pubkey=data['public_key']

        if (session_pubkey == winner):
            print("Hash found at: " + str(time.time()))
            print("Block: ")
            print(json.dumps(data, indent=2))
            print("Block published to all remaining nodes")
            return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
        else:
            print("Node: " + winner + "mined the block.")
            print("Block Recieved at: " + str(time.time()))
            print(json.dumps(data, indent=2))
            print("Print Block Verified")
            print("Block added to Blockchain")
            return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

    #return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


def update_blockchain():
    blockchain = None
    max_length = 0

    for node in nodes.find():
        blockchain_json = node['blockchain']
        if blockchain_json['length'] > max_length:
            blockchain = Blockchain.from_json(blockchain_json)
            max_length = blockchain_json['length']

    return blockchain


def validate_transaction(sender, send_amount):
    wallet = nodes.find_one({"wallet.public_key": sender},
                            {"_id": 0, "wallet.amount": 1})
    wallet_balance = wallet["wallet"]["amount"]
    if float(send_amount) > float(wallet_balance):
        return False
    else:
        return True


def find_mining_node(objects, urls):
    w = random.choice(range(len(objects)))
    winner = None
    winner_name = None
    if w == 0:
        winner = session['wallet']['public_key']
        winner_name = session['wallet']['name']
    else:
        node_json = nodes.find_one({'_id': ObjectId(objects[urls[w]])})
        winner = node_json['wallet']['public_key']
        winner_name = node_json['wallet']['name']
    return winner, urls[w], winner_name


def send_messsage():
    wallets = nodes.find({})
    objects = {}
    urls = []
    for val in wallets:
        objects[val['url']] = val['_id']
        urls.append(val['url'])
    winner, winner_url, winner_name = find_mining_node(objects, urls)

    for url in urls:
        fix = "http://"+url + "/start_mining"
        requests.get(fix)
    return winner, winner_url, winner_name


def send_block_found_message(latest_block):
    print(type(latest_block))

    wallets = nodes.find({})
    objects = {}
    urls = []
    for val in wallets:
        objects[val['url']] = val['_id']
        urls.append(val['url'])
    
    for url in urls:
        fix = "http://"+url + "/end_mining"
        node_json = nodes.find_one({'_id': ObjectId(objects[url])})
        public_key = node_json['wallet']['public_key']
        latest_block['public_key'] = public_key
        requests.post(fix, json=latest_block)
    return

def create_node(url, username):
    # url = request.base_url
    # Check if the node already exists in the db
    # node = nodes.find_one({'url': url})

    # if not node:
    # If the node does not exist
    # Create a wallet
    wallet = Wallet(url, username)
    wallet.create_keys()
    wallet.amount = 100

    blockchain = update_blockchain()
    if not blockchain:
        # If there is no blockchain
        # Create one with genesis block
        blockchain = Blockchain()
        genesis_block = Block(
            index=0,
            timestamp=time.time_ns(),
            previous_hash='0',
            transactions=[],
            nonce=0,
        )
        genesis_block.hash = Block.hash_block(genesis_block)
        blockchain.add_block(genesis_block)

    # Create a node
    parsed_url = urlparse(url)
    node = Node(
        url=url,
        blockchain=blockchain,
        wallet=wallet
    )
    node_id = nodes.insert_one(node.to_json()).inserted_id
    return node_id
    # else:
    #     # If the node exists
    #     node = Node.from_json(node)


if __name__ == '__main__':
    # main()
    app.run(debug=True, port=port)
