from myCal_dictionary import myCal_dictionary
import json
import requests

def search_show():
    myCal_query = input("Please tell me which show you're looking for: ")
    myCal_search = requests.get(f"https://api.tvmaze.com/search/shows?q={myCal_query}") #get details about a series
    myCal_results = myCal_search.json()
    with open(f'temp.json', 'wt', encoding='utf-8') as json_dump: #create/open a file and dump the json in there
        json.dump(myCal_results, json_dump, ensure_ascii=False, indent=2)
    search_sort()

def search_sort():
    with open(f'temp.json', 'rt', encoding='utf-8') as json_load: #open file
        myCal_load = json.load(json_load) #makes it read the json as a dictionary
        for i in myCal_load:
            show_entry = i['show']
            show_name = show_entry['name']
            show_id = show_entry['id']
            show_summ = show_entry['summary']
            print("Name:", show_name,"\nID:", show_id, "\nSummary:", show_summ, "\n")
        user_input = input("Is the show you're looking for in here? (Answer with yes or no): ")
        if user_input == "yes":
            search_add()
        else:
            search_show()
            
def search_add():
    show_id = input(str("Enter the ID of the show you want to add to your calendar: "))
    get_response_series = requests.get(f"https://api.tvmaze.com/shows/{show_id}") #get details about a series
    series_info = get_response_series.json() #convert to json
    show_name = series_info['name']
    for show_name2, show_id2 in myCal_dictionary.items():
        if show_name in myCal_dictionary:
            print(type(show_id))
            print("No need to add that one. It has been added already.\nLet's search for another one.")
            search_show()
        else:
            #show_name = input(str("Now enter the name of the show: "))
            myCal_dictionary[show_name] = str(show_id) #adds show_name:show_id to dictionary
            search_write()
            print(show_name, "has been added!")
            search_add_remove()

def search_write(): #write updated json dumps to dictionary
    with open('myCal_dictionary.py', 'wt') as convert_file:
        convert_file.write("myCal_dictionary = ")
        convert_file.write(json.dumps(myCal_dictionary))
        convert_file.close()

def search_add_remove():
    add_remove = input("Do you want to add or remove a show from your calendar? ")
    if add_remove == "add":
        search_show()
    elif add_remove == "remove":
        search_remove()
    else:
        print("I don't understand. Please try again.")
        search_add_remove()

def search_remove():
    for item in myCal_dictionary:
        print(item)
    show_remove = input("What is the name of the show you want to remove? ")
    if show_remove in myCal_dictionary:
        
        del myCal_dictionary[show_remove]
        print(show_remove, "has been deleted from the list!")
        search_write()
        search_add_remove()
    else:
        print("Sorry, I don't recognize what you just typed.")
        search_remove()

search_add_remove()