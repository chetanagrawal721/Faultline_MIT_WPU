"""Connection pool (Faultline fixture, Hint severity). It refers to no package whose version differs, and its tests need a database driver that"""
def connect(dsn="db://local"):
    return {"dsn": dsn}
