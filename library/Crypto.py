from Crypto.Cipher import AES

import config.env as memory
import base64
import os

class CBC:
    
    def __init__(self):
        self.BLOCK_SIZE = 16

    def __pad(self, byte_array):
        pad_len = self.BLOCK_SIZE - len(byte_array) % self.BLOCK_SIZE

        return byte_array + (bytes([pad_len]) * pad_len)

    def unpad(self, byte_array):
        last_byte = byte_array[-1]

        return byte_array[0:-last_byte]

    def encrypt(self, message):
        key = memory.crypto["KEY"]
        byte_array = message.encode("UTF-8")
        padded = self.__pad(byte_array)
        iv = os.urandom(AES.block_size)
        cipher = AES.new(key.encode("UTF-8"), AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded)

        return base64.b64encode(iv + encrypted).decode("UTF-8")

    def decrypt(self, message):
        key = memory.crypto["KEY"]
        byte_array = base64.b64decode(message)
        iv = byte_array[0:16]
        messagebytes = byte_array[16:]
        cipher = AES.new(key.encode("UTF-8"), AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(messagebytes)
        decrypted = self.unpad(decrypted_padded)

        return decrypted.decode("UTF-8")