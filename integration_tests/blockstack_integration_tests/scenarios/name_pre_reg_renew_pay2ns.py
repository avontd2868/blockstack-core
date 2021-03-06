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

# activate F-day 2017
"""
TEST ENV BLOCKSTACK_EPOCH_1_END_BLOCK 682
TEST ENV BLOCKSTACK_EPOCH_2_END_BLOCK 683
TEST ENV BLOCKSTACK_EPOCH_2_NAMESPACE_LIFETIME_MULTIPLIER 1
"""


import testlib
import virtualchain

wallets = [
    testlib.Wallet( "5JesPiN68qt44Hc2nT8qmyZ1JDwHebfoh9KQ52Lazb1m1LaKNj9", 100000000000 ),
    testlib.Wallet( "5KHqsiU9qa77frZb6hQy9ocV7Sus9RWJcQGYYBJJBb2Efj1o77e", 100000000000 ),
    testlib.Wallet( "5Kg5kJbQHvk1B64rJniEmgbD83FpZpbw2RjdAZEzTefs9ihN3Bz", 100000000000 ),
    testlib.Wallet( "5JuVsoS9NauksSkqEjbUZxWwgGDQbMwPsEfoRBSpLpgDX1RtLX7", 100000000000 ),
    testlib.Wallet( "5KEpiSRr1BrT8vRD7LKGCEmudokTh1iMHbiThMQpLdwBwhDJB1T", 100000000000 )
]

consensus = "17ac43c1d8549c3181b200f1bf97eb7d"

def scenario( wallets, **kw ):

    testlib.blockstack_namespace_preorder( "test", wallets[1].addr, wallets[0].privkey )
    testlib.next_block( **kw )

    testlib.blockstack_namespace_reveal( "test", wallets[1].addr, 52595, 250, 4, [6,5,4,3,2,1,0,0,0,0,0,0,0,0,0,0], 10, 10, wallets[0].privkey, version_bits=2)
    testlib.next_block( **kw )

    testlib.blockstack_namespace_ready( "test", wallets[1].privkey )
    testlib.next_block( **kw )

    namespace_rec = testlib.blockstack_cli_get_namespace_blockchain_record("test")
    if 'error' in namespace_rec:
        print namespace_rec
        return False

    namespace_balance = testlib.get_balance(namespace_rec['address'])

    testlib.blockstack_name_preorder( "foo.test", wallets[2].privkey, wallets[3].addr )
    testlib.next_block( **kw )

    testlib.blockstack_name_register( "foo.test", wallets[2].privkey, wallets[3].addr )
    testlib.next_block( **kw )

    # renew/xfer/update
    res = testlib.blockstack_name_renew("foo.test", wallets[3].privkey, zonefile_hash="22" * 20, recipient_addr=wallets[4].addr)
    if 'error' in res:
        print res
        return False

    testlib.next_block(**kw)

    # renew/update 
    res = testlib.blockstack_name_renew("foo.test", wallets[4].privkey, zonefile_hash="33" * 20, recipient_addr=wallets[4].addr)
    if 'error' in res:
        print res
        return False

    testlib.next_block(**kw)

    # renew/xfer 
    res = testlib.blockstack_name_renew("foo.test", wallets[4].privkey, recipient_addr=wallets[1].addr)
    if 'error' in res:
        print res
        return False

    testlib.next_block(**kw)

    # renew 
    res = testlib.blockstack_name_renew("foo.test", wallets[1].privkey)
    if 'error' in res:
        print res
        return False

    testlib.next_block(**kw)

    new_namespace_balance = testlib.get_balance(namespace_rec['address'])
    name_rec = testlib.get_name_blockchain_record('foo.test')
    name_cost = name_rec['op_fee']

    if new_namespace_balance - namespace_balance != name_cost * 5:
        print 'address {} did not get credited'.format(namespace_rec['address'])
        print '{} != {} + {}'.format(new_namespace_balance, namespace_balance, name_cost * 5)
        return False


def check( state_engine ):

    # not revealed, but ready 
    ns = state_engine.get_namespace_reveal( "test" )
    if ns is not None:
        print "namespace reveal exists"
        return False 

    ns = state_engine.get_namespace( "test" )
    if ns is None:
        print "no namespace"
        return False 

    if ns['namespace_id'] != 'test':
        print "wrong namespace"
        return False 

    # not preordered
    preorder = state_engine.get_name_preorder( "foo.test", virtualchain.make_payment_script(wallets[2].addr), wallets[3].addr )
    if preorder is not None:
        print "preorder exists"
        return False
    
    # registered 
    name_rec = state_engine.get_name( "foo.test" )
    if name_rec is None:
        print "name does not exist"
        return False 

    # owned by
    if name_rec['address'] != wallets[1].addr or name_rec['sender'] != virtualchain.make_payment_script(wallets[1].addr):
        print "sender is wrong"
        return False 

    # value hash 
    if name_rec['value_hash'] != '33' * 20:
        print 'value hash is wrong'
        return False

    return True
