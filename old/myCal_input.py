import json
import requests
import time
from myCal_dictionary import myCal_dictionary
from pathlib import Path
import os

fileserver_path = '/code/src'
os.chdir(fileserver_path)

#print("myCalendar input\n")

for key, value in myCal_dictionary.items():
    try:
        series_id = value
        get_response_series = requests.get(f"https://api.tvmaze.com/shows/{series_id}") #get details about a series
        get_response_ep = requests.get(f"https://api.tvmaze.com/shows/{series_id}/episodes?specials=1") #get list of all episodes from a series
        ep_list = get_response_ep.json() #convert to json
        series_info = get_response_series.json() #convert to json
        
        Path(f"json_files/{series_id}").mkdir(parents=True, exist_ok=True)

        with open(f'json_files/{series_id}/{series_id}_episode.json', 'w', encoding='utf-8') as file_ep: #create/open a file and dump the json in there
            json.dump(ep_list, file_ep, ensure_ascii=False, indent=2)
        
        with open(f'json_files/{series_id}/{series_id}_series.json', 'w', encoding='utf-8') as file_series: #create/open a file and dump the json in there
            json.dump(series_info, file_series, ensure_ascii=False, indent=2)
        #print("Updated", key)
        time.sleep(30)
    except:
        #print("myCalendar input\n")
        print("myCalendar_input.py: An error occurred!")
        continue