import os
import bcrypt

PEPPER = os.getenv("Pepper")

def make_hash(password):
    password = (password + PEPPER).encode()

    salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(password, salt)

    return hashed.decode()

def check_hash(password, hashed):
    password = (password + PEPPER).encode()
    hashed = hashed.encode()

    return bcrypt.checkpw(password, hashed)