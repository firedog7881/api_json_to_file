
"""Pull events from the enSilo API and store in a folder with each file as a separate file
"""
from os.path import isfile
import configparser
import json
import requests
import time
import datetime
import logging
import os
from collections import defaultdict
import getpass
from cryptography.fernet import Fernet
import base64
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class APICall:
    def __init__(self, request_type='none', eventId=0, organization='none'):
      self.request_type = request_type
      self.eventId = eventId
      self.organization = organization
      self.requests_dict = dict()
      self.requests_dict.setdefault('event',{}).setdefault('URL_Params',{'lastSeenFrom': latest_event_time, 'lastSeenTo': current_run_time})
      self.requests_dict['event'].update({'URLmod': 'events/list-events'})
      self.requests_dict.setdefault('organization',{}).setdefault('URL_Params',{})
      self.requests_dict['organization'].update({'URLmod': 'organizations/list-organizations'})
      self.requests_dict.setdefault('raw_event',{}).setdefault('URL_Params',{'eventId':eventId,'fullDataRequested':True})
      self.requests_dict['raw_event'].update({'URLmod': 'events/list-raw-data-items'})
      self.URLParams = self.requests_dict[request_type]['URL_Params']
      self.URLMod = self.requests_dict[self.request_type]['URLmod']
      customer_name = config.get('customer_name', 'setting')
      self.API_URL = f'https://{customer_name}.console.ensilo.com/management-rest/{self.URLMod}'
      self.eventJSON = self._sendRequest()

    def _sendRequest(self):
        global latest_event_time
        api_request = requests.get(self.API_URL, auth=requests.auth.HTTPBasicAuth(creds.un, creds.decrypt_pw()), verify=False, params=self.URLParams)
        logging.info(f'Request sent to {api_request.url}')
        print(f'Request sent to {api_request.url}')
        if api_request.status_code == 200:
            logging.info(f'Request successful - status code 200 received')
            returnJSON = api_request.json()
            return returnJSON

        else:
            error = f'Error in response while trying to retrieve. HTML Code {api_request.status_code} received'
            logging.info(error)
            print(error)
            return -1

class Event:
  def __init__(self,event_JSON):
    self.event_JSON = event_JSON
    self.eventId = event_JSON['eventId']
    self.firstSeen = event_JSON['firstSeen']
    self.lastSeen = event_JSON['lastSeen']
    self.rawEvents = ()
    if config.getboolean('retrieve_raw_items', 'setting'):
      self.rawEvents = self._getRawEvents()

  def _getRawEvents(self):
    api_call = APICall(request_type='raw_event', eventId=self.eventId)
    return api_call.eventJSON

class Credentials:
  def __init__(self):
    self.crypt_key = Fernet.generate_key()
    self.f = Fernet(self.crypt_key)
    self.un = input('Username (User must have Rest API role within WebGUI): ')
    self.pw = self.encrypt_pw()

  def encrypt_pw(self):
    pw = getpass.getpass(prompt='Password: ')
    pw_encrypted = self.f.encrypt(pw.encode())
    return pw_encrypted

  def decrypt_pw(self):
    return self.f.decrypt(self.pw)


#  call the settings by setting the Configuration Class

# ************GLOBAL VARIABLES***************
# This variable is used to store the eventIDs that have been retrieved from the API on this iteration
# These are used to create a new set of eventIDs that have not been saved yet
# Will use difference to compare the two sets and then the result will contain the events that need to saved
current_eventID_set = set()

# This variable will be populated with the file of eventIDs, if file exists
# This set will be exported as a file to provide persistence
historical_eventID_set = set()

# first_run is to track if this is the first time the script ran. This variable is set by the func_getEventIDsFromFile
# based on whether or not if found the file from existing events. If file is found it changes to false, no file found it sets to True
first_run = True

# The failed counter will be used to make sure we don't keep calliing the API if there is an error, once the counter reaches
# 6 errors (500 seconds * 6 = 30 minutes) until erroring out of program
failed_counter = 0

# keep track of the latest event pull
latest_event_time = datetime.datetime(year=2019,month=9,day=1)

# This set is used to compare the previous events pulled and the new events pulled
new_events = set()

# track if there are new events left to process
new_events_remaining = False


# ***************FUNCTIONS****************
# input is type - event or organization list or raw event (to be added)
# This function is used to build out the URL that will be making the API call
#

def func_listOrganizations(json_org):
  # Store the list of organziations pulled from API for access later
  org_list = [org['name'] for org in json_org]
  return org_list

# This function is needed when the program restarts it will be able to continue without getting the same events
# This reads in the list of eventIDs that have been saved to file. During the file creation the eventID will be...
# saved in multiple locations including this file as well as the variable this populates to make the lookup...
# faster at runtime
# Need to update this to SQLlite or something similar - should we encrypt the event IDs?
def func_getEventIDsFromFile():
  global first_run
  try:
    with open(event_tracking_file_location,'r') as file_data:    # Open historical file
      logging.info('Historical event file found - importing')
      if os.stat(event_tracking_file_location).st_size == 0:    # Make sure file has data and is not empty
        logging.info(f'File found but was empty, continuing as first run')
        first_run = True
        return
      counter = 0
      for line in file_data:
        eventID = int(line.rstrip())
        historical_eventID_set.add(eventID)
        counter+=1
      logging.info(f'Successfully imported {counter} events')
    first_run = False
  except FileNotFoundError:
    logging.info('Import File not found. Continuing as first time run')
    first_run = True


# This returns the difference between the two sets.
# The logic is that it outputs the difference between 'current' that is not in historical.
# This will omit any events that have already been processed.
def func_compareBothSets():
  if current_eventID_set:
    logging.info(f'Comparing both sets and return the difference')
    difference = current_eventID_set.difference(historical_eventID_set)
    if not difference:
      if current_eventID_set:
        logging.info(f'Difference set is empty, all {len(current_eventID_set)} events previously processed')
        return -1
    return difference
  else:
    logging.info(f'No new events to process')
    return -1

# This populates the current eventID set so that it can be compared to the historical set
def func_populateEventIdList(eventDataJSON):
  logging.info(f'Populating Event ID List')
  for eventData in eventDataJSON:
    current_eventID_set.add(eventData['eventId'])

# Pull the previous configuration from file
def func_getConfigurationFromFile(config_file_location):
  try:
    with open(config_file_location, 'r') as file_data:
        configJSON = json.load(file_data)
        logging.info(f'Config file found at {config_file_location}')
        return configJSON
  except (FileNotFoundError, IOError) as e:
    print(f'{e}')
    logging.info(f'Config file error')
    code = {'error':{'result':True,'code':'file error'}}
    return code

# convert user's y or n responses to boolean values
# This is used a lot to be able to take in y or n from user and store as bool
def func_getBoolAnswerFromUser(console_question):
  while True:
    question = input(console_question)
    if question in ('Y','y'):
      return 'true'
    if question in ('N','n'):
      return 'false'
    else:
      print(f'You must choose y or n. Please respond again')

# Ask the user configuration questions - if bool use bool function otherwise add input value
def func_askUserForConfiguration():
  satisfied = False    # Creates a loop to allow user to re-enter config if needed
  while not satisfied:
    config.set('customer_name', 'setting', input(config.get('customer_name', 'question')))
    print(f'Here is a list of your organizations to choose from:')
    organizations_json = APICall(request_type='organization').eventJSON
    list_organizations = func_listOrganizations(organizations_json)
    chosen_org = func_printOrgsGetResponse(list_organizations)
    config.set('organization','setting',chosen_org)
    for section in config.sections():
      if section not in ('customer_name','organization'):
        user_question = config.get(section,'question')
        if config.get(section,'setType') == 'bool':    # Does this question require a bool answer
          user_response = func_getBoolAnswerFromUser(user_question)
        if config.get(section,'setType') == 'text':    # Does this question require a text answer
          user_response = input(user_question)
        config.set(section,'setting',user_response)
    config_loaded = func_printConfig(config)    # Display the config for the user to confirm
    if config_loaded:
      satisfied = func_getBoolAnswerFromUser(f'Are you satisfied with your configuration? (y/n)')
    else:
      pass

# This is used to print out the list of organizations pulled from the API call
# The user will use this list to choose which organization to pull data from
def func_printConfig(configparser):
  if config.get('customer_name','setting') == 'none':
    print('Default config loaded, please answer configuration questions')
    return False
  else:
    org_name = config.get('organization', 'name')
    org_set = config.get('organization', 'setting')
    raw_name = config.get('retrieve_raw_items', 'name')
    raw_set = config.get('retrieve_raw_items', 'setting')
    all_name = config.get('retrieve_from_all','name')
    all_set = config.get('retrieve_from_all', 'setting')
    separate_name = config.get('separate_orgs', 'name')
    separate_set = config.get('separate_orgs','setting')
    cust_name = config.get('customer_name', 'name')
    cust_set = config.get('customer_name', 'setting')
    print(f'{org_name}: {org_set}')
    print(f'{raw_name}: {raw_set}')
    print(f'{all_name}: {all_set}')
    print(f'{separate_name}: {separate_set}')
    print(f'{cust_name}: {cust_set}')
    return True

def func_saveJSONtoFile(meta_json):
  logging.info(f'Preparing JSON to save to file for event ID {meta_json.eventId}')
  org_set = config.get('organization', 'setting')
  file_save=f'{event_save_file_location}json/{org_set.replace(" ", "")}-enSilo_event_{meta_json.eventId}.json'
  os.makedirs(os.path.dirname(file_save), exist_ok=True)
  data = meta_json.event_JSON
  try:
    with open(file_save, 'w+') as the_file:
      json.dump(data, the_file)
      logging.info(f'JSON for {meta_json.eventId} saved to {file_save}')
  except IOError:
    logging.info(f'Error writing EventID {meta_json.eventId} file to disk at location {file_save}')
  if config.getboolean('retrieve_raw_items','setting'):
    for event in meta_json.rawEvents:
      rawId = event['EventId']  #for the raw events they use capital E instead of lowercase as is everywhere else
      org_set = config.get('organization', 'setting')
      raw_file_save=f'{event_save_file_location}json/{org_set.replace(" ", "")}-enSilo_event_{meta_json.eventId}-rawID-{rawId}.json'
      os.makedirs(os.path.dirname(raw_file_save), exist_ok=True)
      try:
        with open(raw_file_save, 'w+') as raw_file:
          json.dump(event, raw_file)
          logging.info(f'JSON for {rawId} saved to {file_save}')
      except IOError:
        logging.info(f'Error writing raw EventID {rawId} file to disk at location {raw_file_save}')


# Print out the organizations for the user to choose which org to pull logs from
# Need to add the ability to choose ALL more elagantly than saying no to choosing
def func_printOrgsGetResponse(list_organizations):
  for (i, org) in enumerate(list_organizations):
    print(f'{i}: {org}')
  while True:
    user_input = input(f'Which organization would you like to pull logs for? Enter #: ')
    try:
      val = int(user_input)
      if val >= 0 and val < len(list_organizations):
        result = list_organizations[val]
        return result
    except ValueError:
      print(f'Please input a number.')

def func_getEvents(): # enable logic for first run outside of function
  Events = APICall(request_type='event', organization=config.get('organization','setting'))
  eventsJSON = Events.eventJSON
  eventsDict = {}
  for each in eventsJSON:
    eventsDict.update({each['eventId']:Event(each)})
  processed_events = []
  func_populateEventIdList(Events.eventJSON)
  new_events = func_compareBothSets()
  if new_events != -1:
    while len(new_events) > 0:    # Since we're popping events the list will dwindle to 0 eventually
      try:
        magic_eventId = new_events.pop() # This randomly pops and returns a value from the set, we'll use this to pull from the API data
        logging.info(f'Popping event ID {magic_eventId}')
      except KeyError:
        logging.info(f'Error in new_events Set - Set is Empty')
        return processed_events
      logging.info(f'Event ID {magic_eventId} was found, saving to file')
      func_saveJSONtoFile(eventsDict[magic_eventId])
      processed_events.append(magic_eventId)
  return processed_events

# ********END OF FUNCTIONS********

# *********LOGGING**********
logs_location = './log/ensilo_API_event_to_file.log'
os.makedirs(os.path.dirname(logs_location), exist_ok=True)

config_file_location = './config/ensilo_event.ini'
os.makedirs(os.path.dirname(config_file_location), exist_ok=True)

with open(logs_location,'a+') as outfile:
  current_run_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  outfile.write(f'{current_run_time} STARTING SCRIPT - Retrieve enSilo events and save to JSON\n')
logging.basicConfig(filename=logs_location, level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y %m %d %H:%M:%S')

# ********END OF LOGGING**********

# *********CONFIGURATION**********
def func_setDefaultConfig(config):
  config['organization'] = {'name': 'Organization Name',
                     'setType': 'text',
                     'setting': 'none',
                     'question': 'What is the name of the organization to pull events from - name must be exact: '}

  config['retrieve_raw_items'] = {'name': 'Retrieve Raw Data Files',
                      'setType': 'bool',
                      'setting': 'false',
                      'question': 'Do you want to retrieve the raw data files for events? (y/n): '}

  config['retrieve_from_all'] = {'name': 'Retrieve events from ALL organizations',
                      'setType': 'bool',
                      'setting': 'false',
                      'question': 'Do you want to retrieve events from all organizations? (y/n): '}

  config['separate_orgs'] = {'name': 'Separate events into folders',
                      'setType':'bool',
                      'setting': 'false',
                      'question': 'Do you want to separate events from different organizations into folders? (y/n): '}

  config['customer_name'] = {'name': 'enSilo Instance Name',
                      'setType':'text',
                      'setting': 'none',
                      'question': 'Name of enSilo console (HERE.console.ensilo.com): '}

config = configparser.ConfigParser()
if isfile(config_file_location):
  config.read(config_file_location)
else:
  func_setDefaultConfig(config)

creds = Credentials()

config_loaded = func_printConfig(config)
if config_loaded:
  user_input_view_config = input(f'Would you like to use this existing configuration? (y/n): ')
  if user_input_view_config in ('y','Y'):
    print(f'Using existing configuration')
    logging.info(f'Using existing configuration')
    use_existing_config = True
  if user_input_view_config in ('n','N'):
    func_askUserForConfiguration()
    use_existing_config = False
if not config_loaded:
  func_askUserForConfiguration()

with open(config_file_location, 'w+') as f:
  config.write(f)

if config.getboolean('separate_orgs','setting'):    # Used if set in config
  org_set = config.get('organization', 'setting')
  event_save_file_location=f'./events/{org_set.replace(" ", "")}/'
else:
  event_save_file_location = './events/'

event_tracking_file_location = './tracking/tracking.txt'
os.makedirs(os.path.dirname(event_tracking_file_location), exist_ok=True)
os.makedirs(os.path.dirname(event_save_file_location), exist_ok=True)

# ********END OF CONFIGURATION******


# Pull in historical EventIds if historical set is empty
# If set is empty and there is no file it will continue
# Need a better way to track all of this
if not historical_eventID_set:
  func_getEventIDsFromFile()

while failed_counter < 6:
  try:
    list_of_processed_events = func_getEvents()
  except:
    print(f'There was an error getting events')
    logging.info(f'There was an error getting events')
    failed_counter += 1
  print(f'Completed processing, waiting 60 seconds')
  logging.info(f'Completed process, waiting 60 seconds')
  time.sleep(60)



