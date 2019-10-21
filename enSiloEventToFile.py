
"""Pull events from the enSilo API and store in a folder with each file as a separate file
 ******************TO DO LIST*******************
 DONE - Add organization name to save log files under organization name
 Figure out how to pull the raw events for each event
 Add conversion to XML and save to file
 Pull organization list, Iterate through organization list and pull logs for each organization
 Ask for specific configurations (un/pw, organization(s), disable api call, retrieve raw data, save to xml, save to json)
 While gettting password need to hash
 error handling throughout
 After asking for ensilo console name - pull list of organizations to choose from

 BUG FIXES NEEDED
 error if trying to run XML
  error if both dates are not available for URL on subsequent calls, tried to run new pull if error, need to verify
"""
import json
import requests
import time
import datetime
import logging
import os
from collections import defaultdict
import getpass

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


latest_event_time = datetime.datetime(year=1900,month=1,day=1)
new_events = set()
json_event = ''
new_events_remaining = False
URL_params = {}
# ***************FUNCTIONS****************
# input is to type - event or organization list or raw event
def func_buildURL(request_type):
  if request_type == 'event':  
    current_run_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    global first_run
    global latest_event_time
    # Checking if this is the first run. Make sure that the dates are populated before building the URL stream
    if first_run:  
      logging.info(f'First Run set to True - Sending request to retrieve all events')
    else:
      if not latest_event_time:
        logging.info(f'variable latest_event_time is empty, returning code -2. Will clear history and start over')
        return -2
      if not current_run_time:
        logging.info(f'variable current_run_time is empty, returning code -2. Will clear history and start over')
        return -2
      else:
        logging.info(f'This is not the first pass - Sending request to retrieve events from {latest_event_time}')
        URL_params.update({'lastSeenFrom': latest_event_time, 'lastSeenTo': current_run_time})
    request_type_url = 'events/list-events'
    URL_params.update({'organization':enSilo_organization_name})
  if request_type == 'organization':
    request_type_url = 'organizations/list-organizations'
  if enable_API_calls:
    events_request = requests.get(f'{enSilo_API_URL}{request_type_url}', auth=requests.auth.HTTPBasicAuth(un, pw), verify=False, params=URL_params)
    logging.info(f'Request sent for {request_type} to {events_request.url}')
    print(f'Request sent for {request_type} to {events_request.url}')
    if events_request.status_code == 200:
      logging.info(f'Request successful - status code 200 received')
      requestJSON = events_request.json()
      latest_event_time = datetime.datetime.now().replace(microsecond=0)
      return  requestJSON
    else:
      error = f'Error in response while trying to retrieve enSilo {request_type}. HTML Code {events_request.status_code} recieved'
      logging.info(error)
      print(error)
      return -1
  else:
    #Pull in demo data for testing purposes since API Calls are disabled
    if request_type == 'event':  
      try:
        with open('./demo_data.json','r') as file_data:
          requestJSON = json.load(file_data)
      except IOError:
        print(f'{IOError}')
      return  requestJSON

def func_listOrganizations(json_org):
  org_list = []
  for org in json_org:
    org_list.append(org['name'])
  return org_list

# This function is needed when the program restarts it will be able to continue without getting the same events
# This reads in the list of eventIDs that have been saved to file. During the file creation the eventID will be...
# saved in multiple locations including this file as well as the variable this populates to make the lookup...
# faster at runtime
def func_getEventIDsFromFile():
  global first_run
  try:
    with open(event_tracking_file_location,'r') as file_data:
      logging.info('Historical event file found - importing')
      if os.stat(event_tracking_file_location).st_size == 0:
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

# This function is to save the eventData into a file
# The eventID will be saved in the variable to keep which events have been pulled
def func_saveEventToFile(requestJSON):
  this_event_id = requestJSON['eventId']
  if this_event_id in historical_eventID_set:
    logging.info(f'Event {this_event_id} is in historical set and will be skipped, need to verify log created')
    #need to add a verification of the log file and if the log file is missing then go through and creaete it
    #new event set = check
    return
  else:
    if save_json_to_file:
      logging.info(f'Preparing JSON to save to file for event ID {this_event_id}')
      file_save = f'{event_save_file_location}json/enSilo_event_{this_event_id}.json'
      os.makedirs(os.path.dirname(file_save), exist_ok=True)
      try:
        with open(file_save, 'w+') as jsonfile:
          json.dump(requestJSON, jsonfile)
          logging.info(f'JSON for {this_event_id} saved to {file_save}')
      except IOError:
        logging.info(f'Error writing EventID {this_event_id} file to disk at location {file_save}')
    if save_xml_to_file:
      print(f'XML NOT IMPLEMENTED')
      logging.info(f'XML NOT IMPLEMENTED')
      return
    historical_eventID_set.add(this_event_id)
    try:
      with open(event_tracking_file_location, 'a+') as jsonfile:
        jsonfile.write(f'{this_event_id}\n')
    except IOError:
      logging.info(f'Error writing EventID to tracking file location {this_event_id}')


# This returns the difference between the two sets. The logic as that it outputs what is in the what is in 'current' that is not in historical.
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


def func_getEventWriteFile():
  global first_run
  while len(new_events) > 0:
    try:
      magic_eventId = new_events.pop() # This removes and returns a value from the set, we'll use this to pull from the API data
      logging.info(f'Popping event ID {magic_eventId}')
    except KeyError:
      logging.info(f'Error in new_events Set - Set is Empty')

    for event in json_event:
      # This can be greatly optimized by doing for each in set locate the dictionary key for event ID
      # Right now it is scanning through the JSON data
      if event['eventId'] == magic_eventId: # for each event in the list match with the popped ID and pull that data
        logging.info(f'Event ID {magic_eventId} was found, saving to file')
        func_saveEventToFile(event)
  logging.info(f'Completed creating files')
  first_run = False

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
def func_getBoolAnswerFromUser(console_question):
  while True:
    question = input(console_question)
    if question in ('Y','y'):
      return True
    if question in ('N','n'):
      return False
    else:
      print(f'You must choose y or n. Please respond again')

# Ask the user configuration questions - if bool use bool function otherwise add input value
def func_askUserForConfiguration():
  satisfied = False
  while not satisfied:
    for key in config_data:
      if key not in ('error','enSilo_URL_customer_name'):
        user_question = config_data[key]['question']
        if config_data[key]['type'] == 'bool':
          user_response = func_getBoolAnswerFromUser(user_question)
        if config_data[key]['type'] == 'text':
          if key == 'enSilo_organization_name':
            org_response = func_getBoolAnswerFromUser('Would like like see a list of organizations? (y/n)')
            if org_response:
              user_response = func_printOrgsGetResponse(list_organizations)
            else:
              user_response = input(user_question)
          else:
            user_response = input(user_question)
        config_temp[key]['setting'] = user_response
    config_temp['error']['result'] = False
    func_printConfig(config_temp)
    satisfied = func_getBoolAnswerFromUser(f'Are you satisfied with your configuration? (y/n)')
    

def func_printConfig(config_dict):
  if config_dict['error']['result']:
    print(f'Error in retrieving config data from file')
  else:
    print(f'Here is your existing configuration')
    for key in config_dict:
      if key not in ('save_config_to_file','error'):
        output_string = config_dict[key]['setting']
        output = f'{key}: {output_string}'
        print(output)
    
def func_populateConfigData(config_dict):
  for key in config_dict:
    if key not in ('error',):
      setting_string = config_dict[key]['setting']
      config_data[key]['setting'] = setting_string
  logging.info(f'Saved configuration imported into runtime')

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


# ********END OF FUNCTIONS********

# *********LOGGING**********
logs_location = './log/ensilo_API_event_to_file.log'
os.makedirs(os.path.dirname(logs_location), exist_ok=True)

config_file_location = './config/ensilo_event.config'
os.makedirs(os.path.dirname(config_file_location), exist_ok=True)

with open(logs_location,'a+') as outfile:
  current_run_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  outfile.write(f'{current_run_time} STARTING SCRIPT - Retrieve enSilo events and save to JSON and XML\n')
logging.basicConfig(filename=logs_location, level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y %m %d %H:%M:%S')

# ********END OF LOGGING**********


# *********CONFIGURATION**********

# Initialize the dictionary for configuration settings
config_data = {'enSilo_URL_customer_name':{'name':'enSilo Instance Name','type':'text','setting':'','question':f'enSilo console name (https://THIS.console.ensilo.com): '},
    'enSilo_organization_name':{'name':'Organization Name','type':'text','setting':'','question':f'What is the name of the organization to pull events from - name must be exact: '},
    'enable_API_calls':{'name':'Enable API Calls','type':'bool','setting':True,'question':f'Do you want to enable API calls (This can be disabled for testing)? (y/n): '},
    'Retrieve_Raw_Data':{'name':'Retrieve Raw Data files','type':'bool','setting':False,'question':f'Do you want to retrieve the raw data files for events? (y/n): '},
    'save_json_to_file':{'name':'Save file in JSON format','type':'bool','setting':True,'question':f'Do you want to save events in JSON format? (y/n): '},
    'save_xml_to_file':{'name':'Savefile in XML format (currently not supported)','type':'bool','setting':False,'question':f'Do you want to save events in XML format? (y/n): '},
    'convert_for_fortisiem':{'name':'Format XML for FortiSIEM (currently not supported)','type':'bool','setting':False,'question':f'Do you want to convert XML data for FortiSIEM? (y/n): '},
    'retrieve_from_all_organizations':{'name':'Retrive events from ALL organizations','type':'bool','setting':False,'question':f'Do you want to retrieve events from all organizations? (y/n): '},
    'separate_per_organization':{'name':'Separate events into folders','type':'bool','setting':False,'question':f'Do you want to separate events from different organizations into folders? (y/n): '},
    'save_config_to_file':{'name':'Save this config to a file','type':'bool','setting':True,'question':f'Do you want to save this configuration for next time? (y/n): '},
    'error':{'result':False,'code':''},
    }
# Create copy of config data to work with
config_temp = config_data

un = input('Username: ') # 'brandon_api'   # need to retrieve at runtime from user
pw = getpass.getpass(prompt='Password: ', stream=None)  # 'MasterPassword' # need to retrieve at runtime from user
config_data['enSilo_URL_customer_name']['setting'] = input(config_data['enSilo_URL_customer_name']['question'])

enSilo_URL_customer_name = config_data['enSilo_URL_customer_name']['setting']
enSilo_organization_name = config_data['enSilo_organization_name']['setting']
enable_API_calls = config_data['enable_API_calls']['setting']
Retrieve_Raw_Data = config_data['Retrieve_Raw_Data']['setting']
save_json_to_file = config_data['save_json_to_file']['setting']
save_xml_to_file = config_data['save_xml_to_file']['setting']
convert_for_fortisiem = config_data['convert_for_fortisiem']['setting']
retrieve_from_all_organizations = config_data['retrieve_from_all_organizations']['setting']
separate_per_organization = config_data['separate_per_organization']['setting']
save_config_to_file = config_data['save_config_to_file']['setting']  

enSilo_API_URL = f'https://{enSilo_URL_customer_name}.console.ensilo.com/management-rest/'
URL_params = {'organization': enSilo_organization_name}


# Get the configuration from the saved file
config_from_file = func_getConfigurationFromFile(config_file_location)
config_temp.update(config_from_file)
json_organizations = func_buildURL('organization')
list_organizations = func_listOrganizations(json_organizations)
if config_temp['error']['result']:
  logging.info(f'Configuration NOT FOUND, will get config from user')
  print(f'No configuration found, please configure settings')
  func_askUserForConfiguration()
  func_populateConfigData(config_temp)
  use_existing_config = False
else:  
  func_printConfig(config_temp)
  user_input_view_config = input(f'Would you like to use this existing configuration? (y/n): ')
  if user_input_view_config in ('y','Y'):
    if config_temp['error']['result']:
        question = input(f'Error retrieving config file. Would you like to continue with manual configuration? (y/n)')
        if question in ('y','Y'):
          func_askUserForConfiguration()
          func_populateConfigData(config_temp)
          use_existing_config = False
        if question in ('n','N'):
          question = input(f'Are you sure you want to exit? (y/n)')
          if question in ('y','Y'):
            logging.info(f'Exiting after confirmation from user')
            exit()
          if question in ('n','N'):
            func_askUserForConfiguration()
            func_populateConfigData(config_temp)
            use_existing_config = False
    else:
      print(f'Using existing configuration')
      logging.info(f'Using existing configuration')
      func_populateConfigData(config_temp)
      print(f'Configuration loaded, moving on')
      use_existing_config = True
          
  if user_input_view_config in ('n','N'):
    func_askUserForConfiguration()
    func_populateConfigData(config_temp)
    use_existing_config = False

if not use_existing_config:
  if config_data['save_config_to_file']['setting']:
    try:
      with open(config_file_location, 'w+') as config_outfile:
        json.dump(config_data, config_outfile)
        logging.info(f'Config file saved at {config_file_location}')
    except IOError:
      print(f'IOError saving configuration file - CONFIGURATION NOT SAVED')
      logging.info(f'Configuration File NOT SAVED') 

if separate_per_organization:
  event_save_file_location = f'./events/{enSilo_organization_name}/'
else:
  event_save_file_location = './events/'

event_tracking_file_location = './tracking/tracking.txt'

# Logging of CONFIGURATION
if enable_API_calls:
  logging.info(f'API Calls have been enabled')
else:
  logging.info(f'API Calls have been disabled')

if Retrieve_Raw_Data:
  logging.info(f'Retrieving Raw Data files from events')
else:
  logging.info(f'Not retrieving Raw Data for events')

logging.info(f'Events being saved in {event_save_file_location}')
logging.info(f'Event Tracking log file is being stored at {event_tracking_file_location}')
# ********END OF CONFIGURATION******

logging.info(f'Connecting to URL base: {enSilo_API_URL}')
logging.info(f'Organization: {enSilo_organization_name}')


os.makedirs(os.path.dirname(event_tracking_file_location), exist_ok=True)
os.makedirs(os.path.dirname(event_save_file_location), exist_ok=True)


# Pull in historical EventIds if historical set is empty
# If set is empty and there is no file it will continue
if not historical_eventID_set:
  func_getEventIDsFromFile()

while failed_counter < 6:
  json_event = func_buildURL('event')
  if json_event == -2:    # -2 indicates one of the dates for the URL was missing, we should clear and try again
    first_run = True
    json_event = func_buildURL('event')
  if json_event != -1:    # -1 means there was a URL response error code
    failed_counter = 0
    func_populateEventIdList(json_event)
    new_events = func_compareBothSets()
    if new_events == -1:
      # sleep for 1 minute if less than a minute has passed since last event
      now = datetime.datetime.now().replace(microsecond=0)
      timeDif = (latest_event_time - now)
      if timeDif < datetime.timedelta(minutes=1):
        print(f'No new events, will wait for 60 seconds')
        logging.info(f'No new events, will wait for 60 seconds')
        time.sleep(60)
        print(f'60 seconds elapsed, call API again')
    else:
      logging.info(f'Calling function to write file')
      func_getEventWriteFile()
      latest_event_time = datetime.datetime.now().replace(microsecond=0)
  if json_event == -1:
    failed_counter+=1
    logging.info(f'API call has failed {failed_counter} times')
    logging.info(f'Will wait for 5 miutes and try again {failed_counter - 5} more time(s)')
    print(f'API call has failed {failed_counter} time(s). Check log file for more info')
    print(f'Will wait for 5 miutes and will try again {failed_counter - 5} more times')
    time.sleep(300)



