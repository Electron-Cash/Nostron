import threading
import asyncio
import datetime
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from electroncash.i18n import _
from electroncash_gui.qt.util import MyTreeWidget, MessageBoxMixin, WindowModalDialog, Buttons, CancelButton,OkButton
from electroncash import util 
from electroncash.util import print_error

import sys
import time
import os
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'monstr_terminal'))

from .monstrwrap import monstrwrap

 


class Ui2(MyTreeWidget, MessageBoxMixin):

    
    
    receive_refresh_feed_trigger = pyqtSignal(str)
    receive_refresh_groups_trigger = pyqtSignal(str)

    def __init__(self, parent, plugin, wallet_name):
        # An initial widget is required.
        MyTreeWidget.__init__(self, parent, self.create_menu, [], 0, [])

        import os.path
        self.my_monstrwrap = monstrwrap(ui_window = self) 

        self.chat_history =""

    
        self.timer=QTimer() 
        self.timer.timeout.connect(self.restartTimer)
        
        self.plugin = plugin
        self.wallet_name = wallet_name
        vbox = QVBoxLayout()
        vbox2 = QVBoxLayout()
        vbox3 = QVBoxLayout()
        vbox4 = QVBoxLayout()
        vbox5 = QVBoxLayout()
        vbox6 = QVBoxLayout()
        vbox7 = QVBoxLayout()
        vbox8 = QVBoxLayout()
        self.setLayout(vbox)
        
        
        label22 = QLabel(_("Available Groups:"))
        label22.setAlignment(Qt.AlignCenter)
        f = label22.font()
        f.setPointSize(18)  
        label22.setFont(f) 
        
        hbox22=QHBoxLayout()
        hbox22.addWidget(label22)
        vbox8.addLayout(hbox22)
        self.current_group_id = ""
        self.current_group_name= ""
        self.group_chat_listings_area= QTextBrowser()
         
        self.group_chat_listings_area.setOpenLinks(False)
        self.group_chat_listings_area.anchorClicked.connect(self.group_chat_anchor_clicked)
        
        hbox8 = QHBoxLayout()
        hbox8.addWidget(self.group_chat_listings_area)
        vbox8.addLayout(hbox8) 
       
        label15 = QLabel(_("CHOOSE A RELAY"))
        
        label15.setAlignment(Qt.AlignRight)
        hbox15=QHBoxLayout()
        hbox15.addWidget(label15) 
        self.relays_combo = QComboBox() 
        self.relays_combo.currentIndexChanged.connect(self.on_relay_change)
        hbox15.addWidget(self.relays_combo)
        vbox8.addLayout(hbox15)
       
        self.check_available_group_chats_button = QPushButton(_("FETCH LIST OF GROUPS"))
        
        self.check_available_group_chats_button.clicked.connect(self.fetch_group_chats)
        hbox10=QHBoxLayout()
        hbox10.addWidget(self.check_available_group_chats_button)
        
        
        self.create_new_group_button = QPushButton(_("CREATE NEW GROUP"))
        
        self.create_new_group_button.clicked.connect(self.new_group_dialog)
        hbox11=QHBoxLayout()
        hbox11.addWidget(self.create_new_group_button)
        
        
        vbox8.addLayout(hbox10)
        
        vbox8.addLayout(hbox11)
        
        label20 = QLabel(_("Group Chat:"))
        label20.setAlignment(Qt.AlignCenter)
        f = label20.font()
        f.setPointSize(18)  
        label20.setFont(f) 
        hbox20=QHBoxLayout()
        hbox20.addWidget(label20)
        vbox5.addLayout(hbox20)
        self.event_view_area= QTextEdit()
         
        
        hbox7 = QHBoxLayout()
        hbox7.addWidget(self.event_view_area)
        vbox5.addLayout(hbox7) 
        my_line = QFrame()
        my_line.setLineWidth(3)
        my_line.setMidLineWidth(3)
        my_line.setFrameShape(QFrame.HLine)
        my_line.setFrameShadow(QFrame.Sunken)
        vbox5.addWidget(my_line) 
    
        # Chat message widgets
        self.chatarea = QTextEdit()
        self.my_chat_msg = QLineEdit()
        self.message_button = QPushButton(_("Send Message"))
        hbox3 = QHBoxLayout()
        self.message_button.clicked.connect(self.send_nostr_kind42_msg)
        hbox4 = QHBoxLayout()
        my_line2 = QFrame()
        my_line2.setLineWidth(3)
        my_line2.setMidLineWidth(3)
        my_line2.setFrameShape(QFrame.HLine)
        my_line2.setFrameShadow(QFrame.Sunken)
        vbox6.addWidget(my_line2)
        label21 = QLabel(_("Post Your Messages"))
        label21.setAlignment(Qt.AlignCenter)
        f = label21.font()
        f.setPointSize(18)  
        label21.setFont(f) 
        vbox6.addWidget(label21)
        
        hbox23 = QHBoxLayout()
        self.chat_label_info = QLabel(_("Relay:   Group:   Posting as:"))
        self.update_chat_label_info() 
        hbox23.addWidget(self.chat_label_info) 
        
        hbox22 = QHBoxLayout()
        hbox22.addWidget(self.my_chat_msg)
        hbox22.addWidget(self.message_button)
        
        vbox6.addLayout(hbox23)
        vbox6.addLayout(hbox22)
        
        
        ######################################################
       
   
        # Add remaining widgets
        
        vbox.addLayout(vbox8)   
        vbox.addLayout(vbox5)   
          
        vbox.addLayout(vbox7) 
        vbox.addLayout(hbox3)
        vbox.addLayout(hbox4) 
        vbox.addLayout(vbox6)
        
        # Set up trigger so we can call back into the ui from the p2pnetwork threads. 
        self.receive_refresh_feed_trigger.connect(self.process_refresh_feed_message)
        self.receive_refresh_groups_trigger.connect(self.process_refresh_groups_message)
          
        
        self.update_relays_list()
        # This should go last.
        self.restartTimer()

  
    def restartTimer(self):
    
        self.auto_refresh_chat()
        self.timer.start(15000)
 
    def new_group_dialog(self):
        # This function creates a dialog window for creating a new group
        d = WindowModalDialog(self.top_level_window(), _("Create New Group"))
        vbox = QVBoxLayout(d) 
        grid = QGridLayout()
        line1 = QLineEdit()
        line1.setFixedWidth(350)
        line2 = QLineEdit()
        line2.setFixedWidth(350) 
        
        grid.addWidget(QLabel(_("Name")), 1, 0)
        grid.addWidget(line1, 1, 1)
        
        grid.addWidget(QLabel(_("Description")), 2, 0)
        grid.addWidget(line2, 2, 1)
        
        
        vbox.addLayout(grid)
        vbox.addLayout(Buttons(CancelButton(d), OkButton(d)))
        if d.exec_():
            name = line1.text().strip()[0:100]
            about = line2.text().strip()[0:100]
            self.send_nostr_kind40_msg(name,about)
            
  
 
    def group_chat_anchor_clicked(self,arg1):
      
        group_id_and_name = arg1.url()
        self.fetch_group_messages(group_id_and_name)
            
    def fetch_group_messages(self,group_id_and_name):
        # EXPECT A STRING WITH A SEPERATOR '---SEPERATOR---'
        chosen_relay_dict = self.parent.wallet.storage.get('nostron_chosen_relay')
        if chosen_relay_dict is None:
            return
        chosen_relay_name = chosen_relay_dict.get('chosen_relay')
        relay_list= []
        relay_list.append(str(chosen_relay_name))
        
        group_id_and_name_pieces = group_id_and_name.split("---SEPERATOR---")
        group_id = group_id_and_name_pieces[0]
        group_name = group_id_and_name_pieces[1]
        self.current_group_id = group_id
        self.current_group_name = group_name
        self.update_chat_label_info()
        try:
            
            events = asyncio.run( self.my_monstrwrap.Terminal.nostron_interface.fetch_group_chat_messages(relays=relay_list,e_tag=group_id))
                
        except:
            self.show_error("There was a problem fetching group chats from the relay.")
            return
             
            
        if events is not None:
            self.refresh_group_messages_view(events)
            
    def doBech32Copy(self,txt):
        # This is a helper function to get the pubkey in bech32 format.
        txt=self.my_monstrwrap.Terminal.monstr.encrypt.Keys.hex_to_bech32(str(txt))
        self.doCopy(txt)

    def doCopy(self,txt):
        # This is a helper function for cliboard copy. copy_to_clipboard should be available from main_window so just call parent.
        txt = txt.strip() 
        self.parent.copy_to_clipboard(txt)

    
    def copy_pubkey(self):
        # This is a helper function to copy a key to the clipboard.
        pubkey=""           
        my_alias_list = self.parent.wallet.storage.get('nostron_aliases')
        chosen_alias = self.parent.wallet.storage.get('nostron_chosen_alias')
        chosen_alias_name = chosen_alias.get('chosen_alias')
        for i in my_alias_list:
            alias_name = i.get('alias') 
            if alias_name == chosen_alias_name:
                pubkey=i.get('pubkey')
        # Copy to clipboard  
        self.doBech32Copy(pubkey)
               
    # Functions for the plugin architecture.
    def create_menu(self):
        pass

    def on_delete(self):
        pass

    def on_update(self):
        pass
        
        
    def send_nostr_kind40_msg(self,name,about):
        # This function sends a message to the network 
        
        if '"' in name or '\\' in name or '"' in about or '\\' in about:
            
                self.show_error("Inavlid characters in name or description.")
                return
        
        
        post_message = '{"name": "'+str(name).strip()+'", "about": "'+str(about).strip()+'", "picture": ""}'
         
        # Get the Relays
        post_relay_list = []
        counter = 0
        relays = self.parent.wallet.storage.get('nostron_chosen_relay') 
        if relays is None:
            return
        single_relay=relays.get('chosen_relay')
        post_relay_list.append(single_relay)
                   
        confirm_msg="Create group "+name+" on "+single_relay+" ?"
        if self.question(confirm_msg):
            # Get the private key
            privkey=""           
            my_alias_list = self.parent.wallet.storage.get('nostron_aliases')
            chosen_alias = self.parent.wallet.storage.get('nostron_chosen_alias')
            chosen_alias_name = chosen_alias.get('chosen_alias')
            for i in my_alias_list:
                alias_name = i.get('alias') 
                if alias_name == chosen_alias_name:
                    privkey=i.get('privkey')
            e_tag = None
            try:
                asyncio.run(self.my_monstrwrap.Terminal.poster.run_post(post_message=post_message,post_relay=post_relay_list,priv_k=privkey,e_tag=e_tag,kind=40))
            except:
                self.show_error("One or more relays failed to post.") 
        
        
    def send_nostr_kind42_msg(self):
        # This function sends a message to the network 
        post_message = self.my_chat_msg.text()
        
        # Do not post empty messages, just exit.
        if post_message == "":
            return
               
        confirm_msg="Post this message to the network?"
        if self.question(confirm_msg):
            # Get the private key
            privkey=""           
            my_alias_list = self.parent.wallet.storage.get('nostron_aliases')
            chosen_alias = self.parent.wallet.storage.get('nostron_chosen_alias')
            chosen_alias_name = chosen_alias.get('chosen_alias')
            for i in my_alias_list:
                alias_name = i.get('alias') 
                if alias_name == chosen_alias_name:
                    privkey=i.get('privkey')
        
            # Get the Relays
            post_relay_list = []
            counter = 0
            relays = self.parent.wallet.storage.get('nostron_chosen_relay') 
            if relays is None:
                return
            
            single_relay=relays.get('chosen_relay')
            post_relay_list.append(single_relay) 
             
            e_tag = self.current_group_id
            try:
                asyncio.run(self.my_monstrwrap.Terminal.poster.run_post(post_message=post_message,post_relay=post_relay_list,priv_k=privkey,e_tag=e_tag,kind=42))
            except:
                self.show_error("One or more relays failed to post.")
            self.my_chat_msg.setText("")
        
      
    def on_relay_change(self):
        # This is a function to update storage when the relays dropdown is selected.
        current_relay = self.relays_combo.currentText()
        nostron_chosen_relay=dict(chosen_relay = str(current_relay))
        self.parent.wallet.storage.put('nostron_chosen_relay', nostron_chosen_relay)
        self.parent.wallet.storage.write()
                     
    
    def update_relays_list(self):
        # This function updates the relays combo box widget
        my_relays_list = self.parent.wallet.storage.get('nostron_relays')
        relays_choices = []
        if my_relays_list is None: 
            return
        
        # Grab the selected choice from storage.
        chosen_relay_dict = self.parent.wallet.storage.get('nostron_chosen_relay')
        if chosen_relay_dict is None:
            chosen_relay_name = None
        else:
            chosen_relay_name = chosen_relay_dict.get('chosen_relay')
        
        # keep track of the qcombobox index so we can grab the right default value.
        my_index = 0
        chosen_index = 0
        
        for i in my_relays_list:
            relay_name = i.get('relay') 
            
            relays_choices.append(relay_name) 
            if relay_name == chosen_relay_name:
                chosen_index=my_index
            my_index +=1     
            
        self.relays_combo.clear()
        self.relays_combo.addItems(relays_choices)
        # Reflect chosen alias in the dropdown.
        self.relays_combo.setCurrentIndex(chosen_index)                 
        
        
    def update_chat_label_info(self):

        chosen_relay_dict = self.parent.wallet.storage.get('nostron_chosen_relay')
        if chosen_relay_dict is None:
            return
        chosen_relay_name = chosen_relay_dict.get('chosen_relay')
        chosen_alias_dict = self.parent.wallet.storage.get('nostron_chosen_alias')
        if chosen_alias_dict is None:
            return
        chosen_alias_name = chosen_alias_dict.get('chosen_alias')
        
        my_label = ""
        my_label = my_label + " Posting as: "
        my_label = my_label + chosen_alias_name
        my_label = my_label+ " to Group: "
        my_label = my_label + str(self.current_group_name)[0:30]
        my_label = my_label + " on Relay: "
        my_label = my_label+str(chosen_relay_name)[0:30]
       
        self.chat_label_info.setText(my_label)
        
    def fetch_group_chats(self):
    
        
        # Grab the selected relay from storage.
        chosen_relay_dict = self.parent.wallet.storage.get('nostron_chosen_relay')
        chosen_relay_name = chosen_relay_dict.get('chosen_relay')
        relay_list= []
        relay_list.append(str(chosen_relay_name))
        try:
            
            events = asyncio.run( self.my_monstrwrap.Terminal.nostron_interface.fetch_group_chats(relays=relay_list))
                
        except:
            self.show_error("There was a problem fetching group chats from the relay.")
            return

        all_events =""
        event_dict = []
        for c_evt in events:
            event_dict.append({"created_at":c_evt._created_at,  "content":c_evt._content,"id":c_evt._id})
        def get_created_at(msg):
            return msg.get('created_at')
            
            
        def get_content_pieces(msg):  
            group_name=""
            group_about =""
            try:
                ss1=msg.split('name":')
                ss2=ss1[1]
                ss3=ss2.split('"')
                group_name=ss3[1] 
                ss1=msg.split('about":')
                ss2=ss1[1]
                ss3=ss2.split('"')
                group_about=ss3[1]
            except:
                pass
            return group_name,group_about
            
              
        # Sort by date stamp
        event_dict.sort(key=get_created_at)
        for i in event_dict:
            event_text =""
            content = i.get('content')
            group_name,group_about = get_content_pieces(content)
            epoch_time=i.get('created_at')
            date_time = datetime.date.fromtimestamp( epoch_time )  
            if group_name.strip() == "":
                pass
            else:
                event_text = str(date_time) + "  | "   + ": "   + group_name + " | " + group_about  + " %%%START-KIND40-ID%%%" + i.get('id') + "---SEPERATOR---" + group_name + "%%%END-KIND40-ID%%%" + "\r\n"
            event_text = event_text + "\r\n"
            all_events = all_events + event_text
        
        self.receive_group_chat_list_message(all_events) 
            
    def refresh_group_messages_view(self,events): 
    
        # This function refreshes the group chat messages window.
        all_events = ""
        relay_list = []
        authors_list = []
        # Get the relays we are pulling from
        relays = self.parent.wallet.storage.get('nostron_relays')
 
        if relays is None:
            return
        for i in relays:
            relay_name = i.get('relay')
            relay_list.append(str(relay_name))
            
        # Get the pubkeys we are filtering on
        my_friend_list = self.parent.wallet.storage.get('nostron_friends')
        # Include our own aliases too...
        my_alias_list = self.parent.wallet.storage.get('nostron_aliases')
        my_friend_list = my_friend_list + my_alias_list
        if my_friend_list is None:
            pass
        for i in my_friend_list:
            pubkey=i.get('pubkey')          
            authors_list.append(pubkey)
        
        event_dict = []
        for c_evt in events:
            
            #Start with the pubkey. who is this?
            display_name = ""
            pubkey = str(c_evt._pub_key)
            l = [] 
            for i in my_friend_list:
                friend_name = i.get('name')
                alias_name = i.get('alias')
                friend_pubkey = i.get('pubkey')
                if alias_name is not None:
                    friend_name = alias_name + "(me)"
                if pubkey == friend_pubkey:
                    display_name = friend_name
            if display_name =="":
                #should upgrade to npub.
                display_name=pubkey[0:8]+"..."
            event_dict.append({"created_at":c_evt._created_at, "display_name":str(display_name), "content":c_evt._content})
        def get_created_at(msg):
            return msg.get('created_at')
        # Sort by date stamp
     
        event_dict.sort(key=get_created_at)
        for i in event_dict:
            epoch_time=i.get('created_at')
            date_time = datetime.datetime.fromtimestamp( epoch_time )  
            event_text = str(date_time) + "  | " + i.get('display_name') + ": " + i.get('content') + "\r\n"
            all_events = all_events + event_text
           
        self.receive_refresh_feed_message(all_events) 
          
    # DEAL WITH INCOMING MESSAGES 
       
    def receive_refresh_feed_message(self,incoming_message):
        self.receive_refresh_feed_trigger.emit(str(incoming_message))
    
    def receive_group_chat_list_message(self,incoming_message):
        self.receive_refresh_groups_trigger.emit(str(incoming_message))    
    
    def process_refresh_groups_message(self,incoming_message):
        #self.group_chat_list = incoming_message
        
        
        list_of_links = []
        processing_links = True
        while processing_links:
        ###
            token_occurance_start = incoming_message.find('%%%START-KIND40-ID%%%') 
            if token_occurance_start < 0:
                processing_links= False
                pass
            else:
                var1 = incoming_message.split('%%%START-KIND40-ID%%%')
                var2 = var1[1]
                var3 = var2.split('%%%END-KIND40-ID%%%')
                var4 = var3[0]
                var5 = '%%%START-KIND40-ID%%%' + var4 + '%%%END-KIND40-ID%%%'
                kind40_id_and_name = var4
                incoming_message = incoming_message.replace(var5,"")
                linkdict = { "position": token_occurance_start, "id" : kind40_id_and_name}
                list_of_links.append(linkdict)
        ###
        
        
        self.group_chat_listings_area.setText("")
        cursor = self.group_chat_listings_area.textCursor() 
        cursor.movePosition(QTextCursor.Start,QTextCursor.MoveAnchor)
        self.group_chat_listings_area.setText(incoming_message)
        counter = 0
        for i in list_of_links:
            position = i["position"]
            position = position + counter 
            kind40_id_and_name = i["id"] 
            cursor = self.group_chat_listings_area.textCursor() 
            cursor.movePosition(QTextCursor.Start,QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.Right,QTextCursor.MoveAnchor,position) 
            fmt = cursor.charFormat()
            fmt.setForeground(QColor('blue')) 
            fmt.setAnchor(True)
            fmt.setAnchorHref(kind40_id_and_name) 
            cursor.insertText("OPEN",fmt) 
            counter = counter + 2  # Not sure why!  Should be 4 for "OPEN" but...weirdness.
            
    def auto_refresh_chat(self): 
        if self.current_group_name is not None and self.current_group_id is not None: 
            if self.event_view_area.verticalScrollBar().value() ==  self.event_view_area.verticalScrollBar().maximum():            
                group_id_and_name = str(self.current_group_id) + "---SEPERATOR---" + str(self.current_group_name)
                self.fetch_group_messages(group_id_and_name) 
                
    def process_refresh_feed_message(self,incoming_message): 
        self.event_view_area.setText(incoming_message)
          
        self.event_view_area.verticalScrollBar().setValue(self.event_view_area.verticalScrollBar().maximum()-1)
        
                            
