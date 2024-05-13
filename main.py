import requests
import configparser
import time
from datetime import datetime

# Containing all secret non-publishable information
config = configparser.ConfigParser()
config.read('secrets.cfg')
api_key = config['KEYS']['api_key']
slack_post_url = config['KEYS']['slack_POST']

# time between sending API requests
sleep_time = 60*5  # [sec]

# time between considering an aircraft's state to be new
# (transponder on, takeoff)
# This prevents the slack bot from sending a message every 5 mins for no new info
ping_delta_time = 28800000

# dict of all the aircraft to track. N-number must match aircraft, value is descriptor (or bio)
tracked_regs = {
    'N809NA': "NASA ER-2",
    'N990XB': "Boom XB-1",
    'N351SL': "Stratolaunch Roc",
    'N140SC': "L1011 Stargazer",
    'N949SL': "Cosmic Girl",
}

# API things
headers = {
	"X-RapidAPI-Key": api_key,
	"X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com"
}

# Each aircraft is defined as an object in order to store status information
class aircraft:
    def __init__(self, reg: str, bio: str):
        self.reg = reg
        self.bio = bio
        self.pinged_in_last_day = False
        self.taken_off_in_last_day = False

    # return 0 = dont send slack message
    # return 1 = send slack message, transponder on
    # return 2 = send slack message, aircraft taking off
    # This function runs every 5 mins, whether or not the aircraft's transponder is on
        # The purpose is to figure out if slack should send a message or not
        # As well as store/update the aircraft's state
    def update(self, transponder_state: bool, now: int, airspeed: float) -> int:
        self.transponder_state = transponder_state
        self.now = now
        self.airspeed = airspeed
        # transponder_state == True -> transponder on
        # transponder_state == False -> transponder off

        # If transponder is on
        if transponder_state == True:
            # Check if it's flying
            if airspeed > 40:
                # Check if this is new state
                if self.taken_off_in_last_day == False:
                    # If it is, then send slack message: takeoff
                    self.taken_off_in_last_day = True
                    self.pinged_in_last_day = True
                    self.first_takeoff_time = self.now
                    self.first_ping_time = self.now
                    return 2
                # Otherwise no need to send message
                else:
                    return 0
            
            # Whether or not it's flying:
            # Check if transponder being on is a new state
            if self.pinged_in_last_day == False:
                # If it is, then send slack message: transponder on
                self.first_ping_time = self.now
                self.pinged_in_last_day = True
                return 1
            else:
                # Otherwise no need to send message
                return 0
        
        # If it doesn't have the transponder on
        else: 
            # Check if alotted time for new state has passed
            # If so, return the prevent-message flag to false
            if self.now > (self.pinged_in_last_day + ping_delta_time):
                self.pinged_in_last_day = False
            if self.now > (self.taken_off_in_last_day + ping_delta_time):
                self.taken_off_in_last_day = False
        return 0
    # this code does not work if the plane does not have transponder off for more than 8 hours
    # between flights. i don't forsee that happening (lol)



def send_slack_msg(aircraft_object: object, state: int) -> int:
    if state == 1:
        action = "turned its transponder on"
    if state == 2:
        action = "taken off!"

    msg = f"The {aircraft_object.bio} ({aircraft_object.reg}) aircraft has {action}"
    # slack_response = requests.post(slack_post_url, data={"text": msg})
    print(msg)

def loop(aircraft_arr):
    # go through each aircraft
        for count, aircraft_object in enumerate(aircraft_arr):
            # API request for information
            reg = aircraft_object.reg
            url = f"https://adsbexchange-com1.p.rapidapi.com/v2/registration/{reg}/"
            while True:
                try:
                    response = requests.get(url, headers=headers)
                except: 
                    print('Failed to get API response. Trying again in 30 seconds')
                    time.sleep(30)
                else:
                    break
            # parsing response for relevant info
                # time of request
                # whether or not its flying
            try:
                response_json = response.json()
                aircraft_ping_time = int(response_json['now'])
                aircraft_info = response_json['ac']
            except KeyError:
                print('Bad API response: ')
                print(response)
                print(response_json)
            # aircraft transponder not active if 'ac' tag empty
            if aircraft_info == []:
                # aircraft transponder not active
                state = aircraft_object.update(transponder_state=False, now=aircraft_ping_time, airspeed=0)
            else:
                # get groundspeed information
                # tas and ias not available for all flights, but gs is
                try:
                    print(aircraft_info[0]['gs'])
                except KeyError:
                    print(f'KeyError: gs not indexed on reg {reg}. Continuing.')
                    continue
                aircraft_airspeed = int(aircraft_info[0]['gs'])

                # go to update() function and see if message needs to be sent
                state = aircraft_object.update(transponder_state=True, now=aircraft_ping_time, airspeed=aircraft_airspeed)
            
            # if state is non-zero, then slack message will be sent
            if state > 0:
                send_slack_msg(aircraft_object, state)


def main() -> int:
    # initializing aircraft objects according to tracked_regs
    aircraft_arr = []
    for count, reg in enumerate(tracked_regs):
        aircraft_arr.append(aircraft(reg=reg, bio=tracked_regs[reg]))
        print(aircraft_arr[count].reg)

    # run until forever
    while True:
        # Get time
        hour = datetime.now().hour
        day = datetime.now().day
        if 8 <= hour < 16:
            if day < 5:
                loop(aircraft_arr=aircraft_arr)

        # sleep for 5 mins to prevent going over API request limitations (10,000/mo)
        time.sleep(sleep_time)
    

if __name__ == "__main__":
    main()





    
