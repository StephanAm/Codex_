#! /bin/python Python3
from src.mypackage.logger import get_logger

log = get_logger("main")

if __name__ == "__main__":
    # configure args

    # parse args

    # invoke something from the src/ package
    log.info("Hello World")
