import base64
import os

nonce = base64.b64encode(os.urandom(16)).decode("utf-8")
