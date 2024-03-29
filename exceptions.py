# TODO: Don't mix logic and localization
class MessageException(Exception):
    """Exceptions that can be handled by wrapper"""
    def __init__(self, message):
        self.message = message
