from datetime import datetime

from eth_abi import decode_abi
from ethereum.transactions import Transaction
from web3 import Web3
from web3.utils.abi import get_abi_input_names, get_abi_input_types
from web3.utils.contracts import find_matching_fn_abi

from clove.constants import ETH_REDEEM_GAS_LIMIT, ETH_REFUND_GAS_LIMIT
from clove.network.ethereum.transaction import EthereumTransaction


class EthereumContract(object):

    def __init__(self, network, tx_dict):

        self.network = network
        self.tx_dict = tx_dict
        self.method_id = self.network.extract_method_id(tx_dict['input'])
        self.type = self.network.get_method_name(self.method_id)
        self.token = None

        if not self.is_initiate:
            raise ValueError('Not a contract transaction.')

        if self.is_token_contract:
            self.abi = self.network.token_abi
        else:
            self.abi = self.network.abi

        input_types = get_abi_input_types(find_matching_fn_abi(self.abi, fn_identifier=self.type))
        input_names = get_abi_input_names(find_matching_fn_abi(self.abi, fn_identifier=self.type))
        input_values = decode_abi(input_types, Web3.toBytes(hexstr=self.tx_dict['input'][10:]))
        self.inputs = dict(zip(input_names, input_values))

        self.locktime = datetime.utcfromtimestamp(self.inputs['_expiration'])
        self.recipient_address = Web3.toChecksumAddress(self.inputs['_participant'])
        self.refund_address = self.tx_dict['from']
        self.secret_hash = self.inputs['_hash'].hex()
        self.contract_address = Web3.toChecksumAddress(self.tx_dict['to'])

        if self.is_token_contract:
            self.value = self.inputs['_value']
            self.token_address = Web3.toChecksumAddress(self.inputs['_token'])
            self.token = self.network.get_token_by_address(self.token_address)
            self.symbol = self.token.symbol
        else:
            self.value = self.tx_dict['value']
            self.symbol = self.network.default_symbol

    @property
    def is_eth_contract(self):
        return self.tx_dict['to'] == self.network.eth_swap_contract_address

    @property
    def is_initiate(self):
        return self.method_id in (self.network.initiate, self.network.initiate_token)

    @property
    def is_token_contract(self):
        return self.method_id == self.network.initiate_token

    def participate(
        self,
        symbol: str,
        sender_address: str,
        recipient_address: str,
        value: int,
        utxo: list=None,
        token_address: str=None,
    ):
        network = self.network.get_network_by_symbol(symbol)
        if network.ethereum_based:
            return network.atomic_swap(
                sender_address,
                recipient_address,
                value,
                self.secret_hash,
                token_address,
            )
        return network.atomic_swap(
            sender_address,
            recipient_address,
            value,
            utxo,
            self.secret_hash,
        )

    def redeem(self, secret: str) -> EthereumTransaction:
        contract = self.network.web3.eth.contract(address=self.contract_address, abi=self.network.abi)
        redeem_func = contract.functions.redeem(secret)
        tx_dict = {
            'nonce': self.network.web3.eth.getTransactionCount(self.recipient_address),
            'value': 0,
            'gas': ETH_REDEEM_GAS_LIMIT,
        }

        tx_dict = redeem_func.buildTransaction(tx_dict)

        transaction = EthereumTransaction(network=self.network)
        transaction.tx = Transaction(
            nonce=tx_dict['nonce'],
            gasprice=tx_dict['gasPrice'],
            startgas=tx_dict['gas'],
            to=tx_dict['to'],
            value=tx_dict['value'],
            data=Web3.toBytes(hexstr=tx_dict['data']),
        )
        return transaction

    def refund(self):
        contract = self.network.web3.eth.contract(address=self.contract_address, abi=self.network.abi)

        if self.locktime > datetime.utcnow():
            locktime_string = self.locktime.strftime('%Y-%m-%d %H:%M:%S')
            raise RuntimeError(f"This contract is still valid! It can't be refunded until {locktime_string} UTC.")

        refund_func = contract.functions.refund(self.secret_hash)
        tx_dict = {
            'nonce': self.network.web3.eth.getTransactionCount(self.refund_address),
            'value': 0,
            'gas': ETH_REFUND_GAS_LIMIT,
        }

        tx_dict = refund_func.buildTransaction(tx_dict)

        transaction = EthereumTransaction(network=self.network)
        transaction.tx = Transaction(
            nonce=tx_dict['nonce'],
            gasprice=tx_dict['gasPrice'],
            startgas=tx_dict['gas'],
            to=tx_dict['to'],
            value=tx_dict['value'],
            data=Web3.toBytes(hexstr=tx_dict['data']),
        )
        return transaction

    def show_details(self):
        value_text = self.network.value_to_decimal(self.value)
        details = {
            'contract_address': self.contract_address,
            'locktime': self.locktime,
            'recipient_address': self.recipient_address,
            'refund_address': self.refund_address,
            'secret_hash': self.secret_hash,
            'transaction_address': self.tx_dict['hash'].hex(),
            'value': self.value,
            'value_text': f'{value_text:.18f} {self.symbol}',
        }
        if self.token:
            details['token_address'] = self.token_address
        return details