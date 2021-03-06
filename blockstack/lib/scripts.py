#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
    Blockstack
    ~~~~~
    copyright: (c) 2014-2015 by Halfmoon Labs, Inc.
    copyright: (c) 2016 by Blockstack.org

    This file is part of Blockstack

    Blockstack is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Blockstack is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with Blockstack. If not, see <http://www.gnu.org/licenses/>.
"""

import virtualchain
import keylib
log = virtualchain.get_logger("blockstack-server")
import re
import traceback

from .config import *
from .b40 import *
from .schemas import *

def is_name_valid(fqn):
    """
    Is a fully-qualified name acceptable?
    Return True if so
    Return False if not

    >>> is_name_valid('abcd')
    False
    >>> is_name_valid('abcd.')
    False
    >>> is_name_valid('.abcd')
    False
    >>> is_name_valid('Abcd.abcd')
    False
    >>> is_name_valid('abcd.abc.d')
    False
    >>> is_name_valid('abcd.abc+d')
    False
    >>> is_name_valid('a.b.c')
    False
    >>> is_name_valid(True)
    False
    >>> is_name_valid(123)
    False
    >>> is_name_valid(None)
    False
    >>> is_name_valid('')
    False
    >>> is_name_valid('abcdabcdabcdabcdabcdabcdabcdabcda.bcd')
    True
    >>> is_name_valid('abcdabcdabcdabcdabcdabcdabcdabcdab.bcd')
    False
    >>> is_name_valid('abcdabcdabcdabcdabcdabcdabcdabcdabc.d')
    True
    >>> is_name_valid('a+b.c')
    False
    >>> is_name_valid('a_b.c')
    True
    """

    if not isinstance(fqn, (str,unicode)):
        return False

    if fqn.count( "." ) != 1:
        return False

    name, namespace_id = fqn.split(".")

    if len(name) == 0 or len(namespace_id) == 0:
        return False 

    if not is_b40( name ) or "+" in name or "." in name:
        return False 
   
    if not is_namespace_valid( namespace_id ):
        return False

    if len(fqn) > LENGTHS['blockchain_id_name']:
       # too long
       return False 

    return True


def is_namespace_valid( namespace_id ):
    """
    Is a namespace ID valid?

    >>> is_namespace_valid('abcd')
    True
    >>> is_namespace_valid('+abcd')
    False
    >>> is_namespace_valid('abc.def')
    False
    >>> is_namespace_valid('.abcd')
    False
    >>> is_namespace_valid('abcdabcdabcdabcdabcd')
    False
    >>> is_namespace_valid('abcdabcdabcdabcdabc')
    True
    """
    if not is_b40( namespace_id ) or "+" in namespace_id or namespace_id.count(".") > 0:
        return False

    if len(namespace_id) == 0 or len(namespace_id) > LENGTHS['blockchain_id_namespace_id']:
        return False

    return True


def get_namespace_from_name( name ):
    """
    Get a fully-qualified name's namespace, if it has one.
    It's the sequence of characters after the last "." in the name.
    If there is no "." in the name, then it belongs to the null
    namespace (i.e. the empty string will be returned)

    >>> get_namespace_from_name('abcd.efgh')
    'efgh'
    >>> get_namespace_from_name('abc')
    ''
    >>> get_namespace_from_name('a.b.c')
    'c'
    """

    if "." not in name:
        # empty namespace
        return ""

    return name.split(".")[-1]


def get_name_from_fq_name( name ):
    """
    Given a fully-qualified name, get the name part.
    It's the sequence of characters before the last "." in the name.
 
    Return None if malformed

    >>> get_name_from_fq_name('abc.def')
    'abc'
    >>> get_name_from_fq_name('abc.def.ghi')
    'abc.def'
    >>> get_name_from_fq_name('abc')
    """
    if "." not in name:
        # malformed
        return None
 
    return ".".join(name.split(".")[:-1])


def is_address_subdomain(fqa):
    """
    Tests whether fqa is a fully-qualified subdomain name
    @fqa must be a string
    If it isn't, returns False, None, None.
    If it is, returns True and a tuple (subdomain_name, domain)

    >>> is_address_subdomain('abc')
    (False, None, None)
    >>> is_address_subdomain('abc.def')
    (False, None, None)
    >>> is_address_subdomain('abc.def.ghi')
    (True, 'abc', 'def.ghi')
    >>> is_address_subdomain('abc.def.ghi.jkl')
    (False, None, None)
    >>> is_address_subdomain('Abc.def.ghi')
    (False, None, None)
    >>> is_address_subdomain('abc.Def.ghi')
    (False, None, None)
    >>> is_address_subdomain('abc.def.g+hi')
    (False, None, None)
    >>> is_address_subdomain('..')
    (False, None, None)
    """
    # do these checks early to avoid pathological names that make re.match take forever
    if fqa.count(".") != 2:
        return False, None, None

    grp = re.match(OP_SUBDOMAIN_NAME_PATTERN, fqa)
    if grp is None:
        return False, None, None

    subdomain_name, domain = grp.groups()
    if not is_name_valid(domain):
        return False, None, None

    return True, subdomain_name, domain


def is_subdomain(fqn):
    """
    Short-hand of is_address_subdomain(), but only returns True/False
    """
    return is_address_subdomain(fqn)[0]


def price_name( name, namespace, block_height ):
    """
    Calculate the price of a name (without its namespace ID), given the
    namespace parameters.
    """
    base = namespace['base']
    coeff = namespace['coeff']
    buckets = namespace['buckets']

    bucket_exponent = 0
    discount = 1.0

    if len(name) < len(buckets):
        bucket_exponent = buckets[len(name)-1]
    else:
        bucket_exponent = buckets[-1]

    # no vowel discount?
    if sum( [name.lower().count(v) for v in ["a", "e", "i", "o", "u", "y"]] ) == 0:
        # no vowels!
        discount = max( discount, namespace['no_vowel_discount'] )

    # non-alpha discount?
    if sum( [name.lower().count(v) for v in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "_"]] ) > 0:
        # non-alpha!
        discount = max( discount, namespace['nonalpha_discount'] )

    price = (float(coeff * (base ** bucket_exponent)) / float(discount)) * NAME_COST_UNIT
    if price < NAME_COST_UNIT:
        price = NAME_COST_UNIT

    price_multiplier = get_epoch_price_multiplier( block_height, namespace['namespace_id'] )
    return price * price_multiplier


def price_namespace( namespace_id, block_height ):
    """
    Calculate the cost of a namespace.
    Returns the price on success
    Returns None if the namespace is invalid
    """
    price_table = get_epoch_namespace_prices( block_height )
    if price_table is None:
        return None

    if len(namespace_id) >= len(price_table) or len(namespace_id) == 0:
        return None

    return price_table[len(namespace_id)]


def find_by_opcode( checked_ops, opcode ):
    """
    Given all previously-accepted operations in this block,
    find the ones that are of a particular opcode.

    @opcode can be one opcode, or a list of opcodes
    
    >>> find_by_opcode([{'op': '+'}, {'op': '>'}], 'NAME_UPDATE')
    [{'op': '+'}]
    >>> find_by_opcode([{'op': '+'}, {'op': '>'}], ['NAME_UPDATE', 'NAME_TRANSFER'])
    [{'op': '+'}, {'op': '>'}]
    >>> find_by_opcode([{'op': '+'}, {'op': '>'}], ':')
    []
    >>> find_by_opcode([], ':')
    []
    """

    if type(opcode) != list:
        opcode = [opcode]

    ret = []
    for opdata in checked_ops:
        if op_get_opcode_name(opdata['op']) in opcode:
            ret.append(opdata)

    return ret 
    

def get_public_key_hex_from_tx( inputs, address ):
    """
    Given a list of inputs and the address of one of the inputs,
    find the public key.

    This only works for p2pkh scripts.

    We only really need this for NAMESPACE_REVEAL, but we included 
    it in other transactions' consensus data for legacy reasons that
    now have to be supported forever :(
    """

    ret = None
    for inp in inputs:
        input_scriptsig = inp['script']
        input_script_code = virtualchain.btc_script_deserialize(input_scriptsig)
        if len(input_script_code) == 2:
            # signature pubkey
            pubkey_candidate = input_script_code[1]
            pubkey = None
            try:
                pubkey = virtualchain.BitcoinPublicKey(pubkey_candidate)
            except Exception as e:
                traceback.print_exc()
                log.warn("Invalid public key {}".format(pubkey_candidate))
                continue

            if address != pubkey.address():
                continue

            # success!
            return pubkey_candidate

    return None


def check_name(name):
    """
    Verify the name is well-formed

    >>> check_name(123)
    False
    >>> check_name('')
    False
    >>> check_name('abc')
    False
    >>> check_name('abc.def')
    True
    >>> check_name('abc.def.ghi')
    False
    >>> check_name('abc.d-ef')
    True
    >>> check_name('abc.d+ef')
    False
    >>> check_name('.abc')
    False
    >>> check_name('abc.')
    False
    >>> check_name('abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd.abcd')
    False
    >>> check_name('abcdabcdabcdabcdabcdabcdabcdabcdabc.d')
    True
    """
    if type(name) not in [str, unicode]:
        return False

    if not is_name_valid(name):
        return False

    return True


def check_namespace(namespace_id):
    """
    Verify that a namespace ID is well-formed

    >>> check_namespace(123)
    False
    >>> check_namespace(None)
    False
    >>> check_namespace('')
    False
    >>> check_namespace('abcd')
    True
    >>> check_namespace('Abcd')
    False
    >>> check_namespace('a+bcd')
    False
    >>> check_namespace('.abcd')
    False
    >>> check_namespace('abcdabcdabcdabcdabcd')
    False
    >>> check_namespace('abcdabcdabcdabcdabc')
    True
    """
    if type(namespace_id) not in [str, unicode]:
        return False

    if not is_namespace_valid(namespace_id):
        return False

    return True


def check_subdomain(fqn):
    """
    Verify that the given fqn is a subdomain

    >>> check_subdomain('a.b.c')
    True
    >>> check_subdomain(123)
    False
    >>> check_subdomain('a.b.c.d')
    False
    >>> check_subdomain('A.b.c')
    False
    >>> check_subdomain('abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd.a.b')
    True
    >>> check_subdomain('a.abcdabcdabcdabcdabcdabcdabcdabcdabcdabcd.a')
    False
    >>> check_subdomain('a.b.cdabcdabcdabcdabcdabcdabcdabcdabcd')
    False
    >>> check_subdomain('a.b')
    False
    """
    if type(fqn) not in [str, unicode]:
        return False

    if not is_subdomain(fqn):
        return False

    return True


def check_block(block_id):
    """
    Verify that a block ID is valid

    >>> check_block(FIRST_BLOCK_MAINNET)
    True
    >>> check_block(FIRST_BLOCK_MAINNET-1)
    False
    >>> check_block(-1)
    False
    >>> check_block("abc")
    False
    >>> check_block(int(1e7) + 1)
    False
    >>> check_block(int(1e7) - 1)
    True
    """
    if type(block_id) not in [int, long]:
        return False

    if BLOCKSTACK_TEST:
        if block_id <= 0:
            return False

    else:
        if block_id < FIRST_BLOCK_MAINNET:
            return False

    if block_id > 1e7:
        # 1 million blocks? not in my lifetime
        return False

    return True


def check_offset(offset, max_value=None):
    """
    Verify that an offset is valid

    >>> check_offset(0)
    True
    >>> check_offset(-1)
    False
    >>> check_offset(2, max_value=2)
    True
    >>> check_offset(0)
    True
    >>> check_offset(2, max_value=1)
    False
    >>> check_offset('abc')
    False
    """
    if type(offset) not in [int, long]:
        return False

    if offset < 0:
        return False

    if max_value and offset > max_value:
        return False

    return True


def check_count(count, max_value=None):
    """
    verify that a count is valid
    
    >>> check_count(None)
    False
    >>> check_count('abc')
    False
    >>> check_count({})
    False
    >>> check_count([])
    False
    >>> check_count(True)
    False
    >>> check_count(0)
    True
    >>> check_count(-1)
    False
    >>> check_count(1)
    True
    >>> check_count(2, max_value=2)
    True
    >>> check_count(2, max_value=1)
    False
    """
    if type(count) not in [int, long]:
        return False

    if count < 0:
        return False

    if max_value and count > max_value:
        return False

    return True


def check_string(value, min_length=None, max_length=None, pattern=None):
    """
    verify that a string has a particular size and conforms
    to a particular alphabet

    >>> check_string(1)
    False
    >>> check_string(None)
    False
    >>> check_string(True)
    False
    >>> check_string({})
    False
    >>> check_string([])
    False
    >>> check_string((1,2))
    False
    >>> check_string('abc')
    True
    >>> check_string('')
    True
    >>> check_string(u'')
    True
    >>> check_string('abc', min_length=0, max_length=3)
    True
    >>> check_string('abc', min_length=3, max_length=3)
    True
    >>> check_string('abc', min_length=4, max_length=5)
    False
    >>> check_string('abc', min_length=0, max_length=2)
    False
    >>> check_string('abc', pattern='^abc$')
    True
    >>> check_string('abc', pattern='^abd$')
    False
    """
    if type(value) not in [str, unicode]:
        return False

    if min_length and len(value) < min_length:
        return False

    if max_length and len(value) > max_length:
        return False

    if pattern and not re.match(pattern, value):
        return False

    return True


def check_address(address):
    """
    verify that a string is an address

    >>> check_address('16EMaNw3pkn3v6f2BgnSSs53zAKH4Q8YJg')
    True
    >>> check_address('16EMaNw3pkn3v6f2BgnSSs53zAKH4Q8YJh')
    False
    >>> check_address('mkkJsS22dnDJhD8duFkpGnHNr9uz3JEcWu')
    True
    >>> check_address('mkkJsS22dnDJhD8duFkpGnHNr9uz3JEcWv')
    False
    >>> check_address('MD8WooqTKmwromdMQfSNh8gPTPCSf8KaZj')
    True
    >>> check_address('SSXMcDiCZ7yFSQSUj7mWzmDcdwYhq97p2i')
    True
    >>> check_address('SSXMcDiCZ7yFSQSUj7mWzmDcdwYhq97p2j')
    False
    >>> check_address('16SuThrz')
    False
    >>> check_address('1TGKrgtrQjgoPjoa5BnUZ9Qu')
    False
    >>> check_address('1LPckRbeTfLjzrfTfnCtP7z2GxFTpZLafXi')
    True
    """
    if not check_string(address, min_length=26, max_length=35, pattern=OP_ADDRESS_PATTERN):
        return False

    try:
        keylib.b58check_decode(address)
        return True
    except:
        return False

if __name__ == '__main__':
    import doctest
    doctest.testmod()
