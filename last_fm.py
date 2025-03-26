from datetime import datetime
import pylast
import webbrowser
import time
import os
from dotenv import load_dotenv
import threading

class LastFMClient:
    API_ROOT = 'https://ws.audioscrobbler.com/2.0/'

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('LASTFM_API_KEY')
        self.api_secret = os.getenv('LASTFM_API_SECRET')
        self.session_key = os.getenv('SESSION_KEY')
        self.network = pylast.LastFMNetwork(self.api_key, self.api_secret)
        print(self.session_key)

    def authenticate(self):
        print("login")
        try:
         if not self.session_key:
          skg=pylast.SessionKeyGenerator(self.network)
          url=skg.get_web_auth_url()
          print(f"Please authorize this script to access your account: {url}\n")
          threading.Thread(
            target=webbrowser.open,
            args=(url,),
            daemon=True
          ).start()
          while True:
              try:
                  session_key=skg.get_web_auth_session_key(url)
                  self._update_env_file(session_key)
                  self.session_key=session_key
                  self.network.session_key=self.session_key
                  self._update_env_file(session_key=self.session_key)
                  return True
              except pylast.WSError:
                  time.sleep(1)
                  
         else:
             self.network.session_key=self.session_key

             return True
                  
            

        except Exception as e:
            print(f"AUTH FAILURE: {str(e)}")
            return False

    def _update_env_file(self, session_key):
     env_file = '.env'
     updated = False
     lines = []
 
     if os.path.exists(env_file):
         with open(env_file, 'r') as file:
             lines = file.readlines()
 
     with open(env_file, 'w') as file:
         for line in lines:
             if line.startswith('SESSION_KEY='):
                 file.write(f'SESSION_KEY={session_key}\n')
                 updated = True
             else:
                 file.write(line)
 
         if not updated:
            file.write(f'SESSION_KEY={session_key}\n')
            
    def logout(self):
        print("logout")
        self._remove_session_key_from_env()
        self.session_key = None
        self.network.session_key = None
        print("Successfully logged out from Last.fm")

 

    def _remove_session_key_from_env(self):
     env_path = '.env'
 
     if os.path.exists(env_path):
         with open(env_path, 'r') as f:
             lines = f.readlines()
 
         new_lines = [line for line in lines if not line.lstrip().startswith('SESSION_KEY')]
         print(new_lines)
         if len(new_lines) != len(lines):
             with open(env_path, 'w') as f:
                 f.writelines(new_lines) 
    
