#!/usr/bin/python

"""Configuration of the services' addresses

"""

from Utils import Address, ServiceCoord

class Config:
    """This class just contains the addresses configurations.

    """
    services = {
        ServiceCoord("WebServiceA", 0): Address("localhost", 23000),
        ServiceCoord("Checker", 0): Address("localhost", 22000),
        ServiceCoord("ServiceA", 0): Address("localhost", 20000),
        ServiceCoord("ServiceB", 0): Address("localhost", 21000),
        ServiceCoord("ServiceB", 1): Address("localhost", 21001),
        }


def get_service_address(key):
    """Give the Address of a ServiceCoord.

    key (ServiceCoord): the service needed.
    returns (Address): listening address of key.

    """
    if key in Config.services:
        return Config.services[key]
    else:
        raise KeyError
