from clove.network.bitcoin.base import BitcoinBaseNetwork
from clove.block_explorer.graphql import GraphQL


class DrivechainTestDrive(GraphQL, BitcoinBaseNetwork):
    """
    Class with all the necessary Drivechain Testdrive network information based on
    https://github.com/DriveNetTESTDRIVE/DriveNet/blob/TESTDRIVE/src/chainparams.cpp
    """
    name = 'Drivechain'
    symbols = ('BTC', )
    seeds = ()
    nodes = ('52.36.174.43', '96.126.122.144')
    port = 8451
    message_start = b'\xfe\xee\xee\xef'
    base58_prefixes = {
        'PUBKEY_ADDR': 0,
        'SCRIPT_ADDR': 5,
        'SECRET_KEY': 128
    }
    source_code_url = 'https://github.com/DriveNetTESTDRIVE/DriveNet/blob/TESTDRIVE/src/chainparams.cpp'

    api_url = 'https://dn.drivechain.ai'

# Has no testnet
