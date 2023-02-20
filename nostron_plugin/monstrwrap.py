"""Wrapper class to import monstr_terminal"""


from . import monstr_terminal 
class monstrwrap():
    def __init__(self,ui_window=None):
        self.Terminal= monstr_terminal
        self.ui_window=ui_window
        
    def receive_event_message(self, data):
        self.ui_window.receive_chat_message(str(data))
