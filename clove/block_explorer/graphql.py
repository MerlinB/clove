from typing import Optional
import json

from bitcoin.core import CTxOut, script

from clove.block_explorer.base import BaseAPI
from clove.network.bitcoin.utxo import Utxo
from clove.utils.bitcoin import from_base_units, to_base_units
from clove.utils.external_source import clove_req_json
from clove.utils.logging import logger


class GraphQL(BaseAPI):
    '''
    Wrapper for block explorers that runs on GraphQL engine.
    '''

    api_url = None
    ui_url = None

    @classmethod
    def get_latest_block(cls) -> Optional[int]:
        '''Returns the number of the latest block.'''

        query = '''
        {
            allBlocks(orderBy: HEIGHT_DESC, first: 1) {
                nodes {
                    height
                }
            }
        }
        '''

        try:
            json_response = clove_req_json(f'{cls.api_url}/graphql', post_data={'query': query})
            latest_block = json_response['data']['allBlocks']['nodes'][0]['height']
        except (TypeError, KeyError):
            logger.error(f'Cannot get latest block, bad response ({cls.symbols[0]})')
            return
        if not latest_block:
            logger.debug(f'Latest block not found ({cls.symbols[0]})')
            return
        logger.debug(f'Latest block found: {latest_block}')
        return latest_block

    @classmethod
    def get_transaction(cls, tx_address: str) -> dict:
        query = '''
        {
          txByTxId(txId: "%s") {
            txId
            version
            locktime
            vinsByTxId {
              nodes {
                txId
                vout
                n
                scriptSig
                address
                value
              }
            }
            voutsByTxId {
                nodes {
                    txId
                    n
                    value
                    scriptPubKey
                    spendingN
                    spendingTxId
                }
            }
            blockHash
            blockByBlockHash {
              hash
              height
            }
          }
        }
        ''' % (tx_address)
        json_response = clove_req_json(f'{cls.api_url}/graphql', post_data={'query': query})
        return json_response['data']['txByTxId']

    @classmethod
    def get_utxo(cls, address, amount):
        query = """
        {
            getAddressTxs(_address: "%s") {
                nodes {
                    voutsByTxId(condition: { spendingN: null }) {
                        nodes {
                            txId
                            n
                            value
                            scriptPubKey
                        }
                    }
                }
            }
        }
        """ % (address)

        data = clove_req_json(f'{cls.api_url}/graphql', post_data={'query': query})
        vouts = []
        for node in data['data']['getAddressTxs']['nodes']:
            for vout in node['voutsByTxId']['nodes']:
                vouts.append(vout)

        unspent = sorted(vouts, key=lambda k: k['value'], reverse=True)

        utxo = []
        total = 0

        for output in unspent:
            value = float(output['value'])
            utxo.append(
                Utxo(
                    tx_id=output['txId'],
                    vout=output['n'],
                    value=value,
                    tx_script=output['scriptPubKey'],
                )
            )
            total += value
            if total > amount:
                return utxo

        logger.debug(f'Cannot find enough UTXO\'s. Found %.8f from %.8f.', total, amount)

    @classmethod
    def extract_secret_from_redeem_transaction(cls, contract_address: str) -> Optional[str]:

        query = """
        {
            allAddressTxes(orderBy: TIME_ASC, condition: { address: "%s" }) {
                nodes {
                    txId
                }
            }
        }
        """ % (contract_address)

        data = clove_req_json(f'{cls.api_url}/graphql', post_data={'query': query})
        contract_transactions = data['data']['allAddressTxes']['nodes']

        if not contract_transactions:
            logger.error(f'Cannot get contract transactions ({cls.symbols[0]})')
            return
        if len(contract_transactions) < 2:
            logger.debug('There is no redeem transaction on this contract yet.')
            return

        redeem_transaction = cls.get_transaction(contract_transactions[1]['txId'])
        if not redeem_transaction:
            logger.error(f'Cannot get redeem transaction ({cls.symbols[0]})')
            return

        return cls.extract_secret(scriptsig=redeem_transaction['vinsByTxId']['nodes'][0]['scriptSig'])

    @classmethod
    def get_balance(cls, wallet_address: str) -> float:
        '''
        Returns wallet balance without unconfirmed transactions.

        Args:
            wallet_address (str): wallet address

        Returns:
            float: amount converted from base units

        Example:
            >>> from clove.network import Ravencoin
            >>> r = Ravencoin()
            >>> r.get_balance('RM7w75BcC21LzxRe62jy8JhFYykRedqu8k')
            >>> 18.99
        '''

        query = """
        {
            getAddressTxs(_address: "%s") {
                nodes {
                    voutsByTxId(condition: { spendingN: null }) {
                        nodes {
                            value
                        }
                    }
                }
            }
        }
        """ % (wallet_address)

        data = clove_req_json(f'{cls.api_url}/graphql', post_data={'query': query})
        total = 0
        for node in data['data']['getAddressTxs']['nodes']:
            for vout in node['voutsByTxId']['nodes']:
                total += float(vout['value'])

        return total

    @classmethod
    def get_transaction_url(cls, tx_hash: str) -> Optional[str]:
        return cls.api_url

    @classmethod
    def _get_block_hash(cls, block_number: int) -> str:
        '''Getting block hash by its number'''
        try:
            block_hash = clove_req_json(f'{cls.api_url}/block-index/{block_number}')['blockHash']
        except (TypeError, KeyError):
            logger.error(f'Cannot get block hash for block {block_number} ({cls.symbols[0]})')
            return
        logger.debug(f'Found hash for block {block_number}: {block_hash}')
        return block_hash

    @classmethod
    def get_fee(cls) -> Optional[float]:
        return 0.0001

    @classmethod
    def get_first_vout_from_tx_json(cls, tx_json: dict) -> CTxOut:
        vout = tx_json['voutsByTxId']['nodes'][0]
        cscript = script.CScript.fromhex(json.loads(vout['scriptPubKey'])['hex'])
        return CTxOut(float(vout['value']), cscript)
