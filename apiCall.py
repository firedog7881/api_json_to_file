class APICall:
    def __init__(request_type,)
        self.request_type = request_type
        self.eventId = eventId
        self.rawEventId = rawEventId

    def getFromFile():
        if self.request_type == 'event':
            try:
                with open('./demo_data.json','r') as file_data:
                requestJSON = json.load(file_data)
            except IOError:
                print(f'Cannot load data from file, exiting')
                print(f'{IOError}')
                print(f'Have a nice day! Sorry.')
                exit()
            return  requestJSON
        else:
            logging.info(f'getFromFile called with request_type other than "event"')
            print(f'function expected event request_type, something else was presented')
            return -1


    def sendRequest(API_URL,request_type):
        global latest_event_time
        URLParamsResult = func_setURLParams(request_type)
        # this is the main point of the URL request, the URL is built out based on the parameters of the call
        if URLParamsResult:
            api_request = requests.get(f'{API_URL}', auth=requests.auth.HTTPBasicAuth(un, f.decrypt(pw_encrypted)), verify=False, params=URL_params)
            logging.info(f'Request sent to {api_request.url}')
            print(f'Request sent to {api_request.url}')
            if api_request.status_code == 200:    # 200 code is success
            logging.info(f'Request successful - status code 200 received')
            requestJSON = api_request.json()    # Store JSON response into JSON object
            return  requestJSON
            else:
            # If a response other than 200 is returned then the call was unsuccessful
            error = f'Error in response while trying to retrieve. HTML Code {api_request.status_code} received'
            logging.info(error)
            print(error)
            return -1    # Return error code

    def func_setURLParams(request_type,eventId=000000,rawEventId=0000000000):
        global URL_params
        requests_dict = {'event': {'URL_Params': {'lastSeenFrom': latest_event_time, 'lastSeenTo': current_run_time},'return':True},
                         'organization': {'URL_Params':{},'return':True},
                         'raw_event': {'URL_Params':{'eventId': eventId, 'organization': enSilo_organization_name},'return':True},
                         'raw_event_file': {'URL_Params': {'rawEventIds': rawEventId, 'return': True},
        URL_params = request_dict[request_type][URL_params]
        return True
