"""pyhomely exceptions."""


class HomelyBaseError(Exception):
    """Base pyhomely exception."""


class HomelyAuthenticationError(HomelyBaseError):
    """pyhomely authentication error."""


class HomelyConnectionError(HomelyBaseError):
    """pyhomely connection error."""


class HomelyError(HomelyBaseError):
    """pyhomely generic error."""
