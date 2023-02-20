# temp
#### parse_arguments()

reads arguments parsed from terminal. Takes in following arguements:
* -c, --cfg: the path + name of configuration file
* -s, --startday: if the user wants to extract data from a specific time interval, add startday and endday. If hour not specified, default start will be first data registered from 00:00 for that day.
* -e, --endday: If hour not specified, default end will be last data registered up until 23:59.
* -t, --type: Must specify type of station to extract data from. Can choose between "block" (stations registered with  blockNumber and stateIdentifier), "wigos" (stations registered with wigosNumbers) or "radio" (radiosondes).
* -i, --init: reads all the files from the folder containing the bufr files.
* -u, --update: reads the files from output folder to find the last date to update from. Goes to the folder containing bufr files and collects data from said date.
* -a, --all: extracts data from all available stations
* -st, --station: extracts data from specified station. Must be in the from "st1 st2 .. stn". If the stationtype, t = block, the stations have to be specified through "[blockNumber][stationNumber]". If t = wigos the stations have to be specified as "[wigosIdentifierSeries]-[wigosIssuerOfIdentifier]-[wigosIssueNumber]-[wigosLocalIdentifierCharacter]", and if t = radio the stations must be specified as "[radiosondeSerialNumber]"


#### parse_cfg(cfgfile)

Returns the arguments from the configuration file parsed by user.

#### get_files_specified_dates(desired_path)

If the user wants to extract data from specific dates, this function will run. It opens up the file folder, checks the date from the parser input and returns a list of files that contains data from within the timeinterval given. 

#### get_files_initialize(desired_path)

Opens the folder containing the bufr file and returns all files

#### bufr_2_json(file)
This function converts bufr file to json file using the eccodes bufr_dump. By running "bufr_dump -j f [file]", the bufr file is converted to a flat layed json output in terminal. Using the subprocess-module, the terminal output is saved as a variable. Once loaded as json, the file undergoes a couple of iterations to be sorted in order for it to be more easily converted to dataframe/dataarray.

#### return_list_of_stations(get_files)
This function is used if --update is parsed. It returns a list of all stations within a time interval, and allows for comparing which stations have already existing files and which do not.

#### sorting_hat(get_files)
Sorts the data by station. Returns a dictionary with the stationname as key, and each message contains data from one timestamp.

#### json_to_ds(msg)
Converts the json-data sorted by the sorting_hat function to pandas dataframe to xarray dataset. Start of by sorting which variables should have both a vertical(pressure) and a time coordinate, and which ones are only dependent on time. Adding variable attributes as well as global attributes.

#### set_encoding(ds, fill=-9999, time_name = 'time', time_units='seconds since 1970-01-01 00:00:00')
Returns a dictionary with the encoding. Have had some trouble with the time encoding, but it should be fixed by now.

#### saving_grace(file, key, destdir)
sorts ds into monthly data and saves each of the new dfs. Some global attributes have to be unique for each save, so these are added in this function.
