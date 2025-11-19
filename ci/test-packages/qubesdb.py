class QubesDB:
    def read(self, key):
        return b'testvm'

    def rm(self, key):
        pass

    def write(self, key, value):
        pass

class Error(Exception):
    pass
