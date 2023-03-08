#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: python3 -*- 

 
from bitcoin.bitcoin import Point
from bitcoin.bitcoin import curve_secp256k1 as curve
from bitcoin.bitcoin import ser_to_point
from bitcoin.bitcoin import sha256
from hkdf2.hkdf import * 
from binascii import unhexlify
from Crypto.Cipher import AES

def get_shared_key(private_key, public_key):
    """Expect Hex string arguments for private_key and public_key"""
  
    # Convert private key to int and public key to bytes
    private_key_int = int(private_key,16)
    public_key_bytes = bytes.fromhex(public_key)
    
    
    # Public key is expected to be compressed.  Change into a point object.
    pubkey_point = ser_to_point(public_key_bytes)
    ecdsa_point = Point(curve, pubkey_point.x(), pubkey_point.y())

    # Multiply the public and private points together
    ecdh_product = ecdsa_point * private_key_int
    ecdh_x = int(ecdh_product.x())
    ecdh_x_bytes = ecdh_x.to_bytes(33, byteorder="big")
 
    # Get the raw shared secret
    my_bytes = ecdh_x_bytes
    shared_secret = sha256(my_bytes)
    
    # Add some salt  
    salt_phrase="A decentralized social network with a chance of working."
    salt_hex=salt_phrase.encode('ascii').hex()
    salt = sha256(salt_hex)  

    # Apply the HKDF
    kdf = Hkdf(unhexlify(salt.hex()), shared_secret, hash=hashlib.sha512)
   
    # Generate the key. 32 bytes = 256 bits
    key = kdf.expand(b"context1", 32)
    
    # Return the key
    return key


def encrypt (msg, key):
 
    cipher = AES.new(key, AES.MODE_GCM)      
    nonce = cipher.nonce
    ciphertext, tag = cipher.encrypt_and_digest(msg.encode(encoding='UTF-8'))
    return ciphertext, nonce, tag
    
def decrypt (ciphertext, key,nonce,tag):

    plaintext=""
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt(ciphertext)
    try:
        cipher.verify(tag)
    except ValueError:
        print("Key incorrect or message corrupted")
    return plaintext

def run_test():

    alice_shared_key=get_shared_key("9b019cfe0f51b440e4a5bbf491438a933016e5fc50d05c85c5ecf439bd3dc9dd","025ce742248cd4beea6438d8f90515fb7b4e6ca5417a54e5e7e024decdd32fbd49")
    bob_shared_key =get_shared_key("6e4f831b8a27aa16ad91e618ae6c857b9dcedba72ec2e1bbc5c58b307fd4dfe4","02f168dc06f3133bfe4afe3c235a727c3a99b6fc96f61ca6c2b013091e06886422")
    if alice_shared_key == bob_shared_key:
        print ("ALICE'S KEY AND BOB'S KEY MATCH AS EXPECTED.")
    else:
        print ("THERE WAS A PROBLEM GENERATING THE SHARED SECRET.")
        exit()
    
    alice_plaintext_msg = "Hi Bob, it's me, Alice."
    print ("ALICE'S PLAINTEXT MESSAGE: ",alice_plaintext_msg)
    alice_encrypted_msg,alice_nonce,alice_tag = encrypt(alice_plaintext_msg,alice_shared_key)
    print ("ALICE'S ENCRYPTED MESSAGE: ",alice_encrypted_msg.hex())
    print ("ALICE'S NONCE: ",alice_nonce.hex())
    print ("ALICE'S TAG: ",alice_tag.hex())
    bob_decrypts_alice_msg = decrypt (alice_encrypted_msg,bob_shared_key,alice_nonce,alice_tag)
    print ("BOB DECRYPTS ALICE'S MESSAGE AS: ", bob_decrypts_alice_msg.decode('utf-8'))
    
    
    
    bob_plaintext_msg = "Hi Alice, it's me, Bob."
    print ("BOB'S PLAINTEXT MESSAGE: ",bob_plaintext_msg)
    bob_encrypted_msg,bob_nonce,bob_tag = encrypt(bob_plaintext_msg,bob_shared_key)
    print ("BOB'S ENCRYPTED MESSAGE: ",bob_encrypted_msg.hex())
    print ("BOB'S NONCE: ",bob_nonce.hex())
    print ("BOB'S TAG: ",bob_tag.hex())
    alice_decrypts_bob_msg = decrypt (bob_encrypted_msg,alice_shared_key,bob_nonce,bob_tag)
    print ("ALICE DECRYPTS BOB'S MESSAGE AS: ", alice_decrypts_bob_msg.decode('utf-8'))
    


run_test() 

#################################TEST DATA#####################################
##created profile: Alice1
##**private**
##hex       9b019cfe0f51b440e4a5bbf491438a933016e5fc50d05c85c5ecf439bd3dc9dd
##bech32    nsec1nvqeels02x6ype99h06fzsu2jvcpde0u2rg9epw9an6rn0fae8wsqlttmv
##**public**
##hex       f168dc06f3133bfe4afe3c235a727c3a99b6fc96f61ca6c2b013091e06886422
##bech32    npub1795dcphnzvalujh78s345unu82vmdlyk7cw2ds4szvy3up5gvs3q0q083x

##created profile: Bob1
##**private**
##hex       6e4f831b8a27aa16ad91e618ae6c857b9dcedba72ec2e1bbc5c58b307fd4dfe4
##bech32    nsec1de8cxxu2y74pdtv3ucv2umy90wwuaka89mpwrw79ck9nql75mljqcmnzre
##**public**
##hex       5ce742248cd4beea6438d8f90515fb7b4e6ca5417a54e5e7e024decdd32fbd49
##bech32    npub1tnn5yfyv6jlw5epcmrus290m0d8xef2p0f2wtelqyn0vm5e0h4ysgusfjd
###############################################################################


