import json
from datetime import datetime
from datetime import timedelta 
from myCal_dictionary import myCal_dictionary
import os
import requests
from pathlib import Path
import shutil
import time

fileserver_path = '/code/src'
public_path = '/code/static'

#print("myCalendar output\n")

#create calendar file and write default data to it
os.chdir(public_path)
myCal = open("calendar.ics", "wt", encoding='utf-8')
myCal.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:myProject\nCALSCALE:GREGORIAN\n")
myCal.close()

#write show info to status file. create new file
myCal_status = open("status.txt", "wt")
myCal_status.write(f"These are the shows I'm subscribed to:\nShow name - Tvmaze ID - Status\n")
myCal_status.close()

#read all tv show IDs(value) from dictionary which is in myCal_dictionary.py file
def myCal_outputter():
    for key, series_id in myCal_dictionary.items():
        try:
            os.chdir(public_path)
            with open(f'{fileserver_path}/json_files/{series_id}/{series_id}_series.json', 'rt', encoding='utf-8') as json_s_file: #open series file
                parsed_s_file = json.load(json_s_file) #makes it read the json as a dictionary
                global series_name
                series_name = parsed_s_file['name'] #take key from dictionary and set as a variable
                global series_status
                series_status = parsed_s_file['status']
                myCal_status = open("status.txt", "at")
                myCal_status.write(f"{series_name} - {series_id} - {series_status}\n") #write show info to status file. append to existing file
                myCal_status.close()
                #print("Updated", series_name)

            with open(f'{fileserver_path}/json_files/{series_id}/{series_id}_episode.json', 'rt', encoding='utf-8') as json_e_file: #open episodes file
                parsed_e_file = json.load(json_e_file) #makes it read the json as a dictionary

                for i in parsed_e_file: #loop through episodes dictionary
                    new_date = i['airdate'] #grab date as type string from dictionary
                    date_convert = datetime.strptime(new_date,'%Y-%m-%d') #convert string to datetime object
                    ep_id = i['id']
                    ep_start = date_convert + timedelta(days=1) #add one day for proper calendar event start date
                    ep_end = date_convert + timedelta(days=2) #add two days for event end
                    ep_descr = i['summary']
                    ep_season_nr = i['season'] #grab season number from episodes dictionary
                    ep_nr = i['number'] #grab episode number from episodes dictionary
                    ep_name = i['name'] 
                    try:
                        formatted_ep_nr = '{:02d}'.format(ep_nr) #format episode number to at least 2 digits
                    except(TypeError):
                        formatted_ep_nr = '00'
                    formatted_season_nr = '{:02d}'.format(ep_season_nr) #format season number to at least 2 digits
                    zero = "BEGIN:VEVENT"
                    one = "DTSTART;VALUE=DATE:" + ep_start.strftime("%Y%m%d") #print datetime object as a string with a specified format
                    two = "DTEND;VALUE=DATE:" + ep_end.strftime("%Y%m%d")
                    three = ep_name
                    four = "SUMMARY:" + series_name + f' S{formatted_season_nr}E{formatted_ep_nr}'
                    five = "DTSTAMP:" + ep_start.strftime("%Y%m%d") + 'T000000Z'
                    six = f'UID:{ep_id}'
                    seven = f"BEGIN:VALARM\nUID:{ep_id}A\nACTION:DISPLAY\nTRIGGER;VALUE=DATE-TIME:" + ep_start.strftime("%Y%m%d") + "T160000Z\nDESCRIPTION:This is an event reminder\nEND:VALARM"
                    last = "END:VEVENT"

                    myCal = open("calendar.ics", "at", encoding='utf-8') #open calendar file and append episode data
                    myCal.write(f'{zero}\n')
                    myCal.write(f'{one}\n')
                    myCal.write(f'{two}\n')
                    try:
                        myCal.write(f'DESCRIPTION:{three}\n')
                    except(TypeError, UnicodeEncodeError):
                        myCal.write("DESCRIPTION:No description\n")
                    myCal.write(f'{four}\n')
                    #myCal.write(f'{five}\n')
                    myCal.write(f'{six}\n')
                    myCal.write(f'{seven}\n')
                    myCal.write(f'{last}\n')
                    myCal.close()
        except(FileNotFoundError):
            #print("myCalendar output\n")
            print(f"myCalendar_output.py: There was an error handling {key}: File not found")

            get_response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}") #get details about a series
            get_response_ep = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes?specials=1") #get list of all episodes from a series
            ep_list = get_response_ep.json() #convert to json
            series_info = get_response_series.json() #convert to json
            os.chdir(fileserver_path)
            Path(f"json_files/{series_id}").mkdir(parents=True, exist_ok=True)

            with open(f'json_files/{series_id}/{series_id}_episode.json', 'w', encoding='utf-8') as file_ep: #create/open a file and dump the json in there
                json.dump(ep_list, file_ep, ensure_ascii=False, indent=2)
            
            with open(f'json_files/{series_id}/{series_id}_series.json', 'w', encoding='utf-8') as file_series: #create/open a file and dump the json in there
                json.dump(series_info, file_series, ensure_ascii=False, indent=2)
            print("Downloaded missing files of:", key)
            time.sleep(30)
            myCal_outputter()
        except:
            print("myCalendar output\n")
            print("A general error occurred.")
            continue

myCal_outputter()
os.chdir(public_path)
myCal = open("calendar.ics", "at", encoding='utf-8')
myCal.write("END:VCALENDAR")
myCal.close()

#start removal process
#the following code will create and compare lists of the dictionary against the stored files/folders
#if a shows folder exists but theres no dictionary entry the folder and contents will be deleted
os.chdir(fileserver_path)
dir_list = os.listdir("json_files/")
dict_list = []
for key3, value3 in myCal_dictionary.items():
    dict_list.append(value3)
for my_var in dir_list:
    if my_var not in dict_list:
        try:
            del_path = f"json_files/{my_var}" 
            shutil.rmtree(del_path)
        except:
            print("There has been an error while cleaning up myCal files (myCal_output)")